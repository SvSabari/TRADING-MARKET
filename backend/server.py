"""Algo Trading Platform — FastAPI production entry point (v2.1.0)."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env", override=True)
load_dotenv(ROOT_DIR.parent / ".env", override=True)

DEMO_USER_ENABLED = os.environ.get("DEMO_USER_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

from routers import (  # noqa: E402
    ai_routes, analytics_routes, auth_routes, broker_routes,
    data_routes, managed_users_routes,
    market_routes, notification_routes, order_routes,
    signals_routes, strategy_routes, tradingview_routes,
)
from auth import ensure_demo_user
from services.market_data import tick_engine  # noqa: E402
from services.market_data_capture import market_data_capture  # noqa: E402
from services.strategy_scheduler import scheduler as strategy_scheduler  # noqa: E402
from services.live_feed_manager import live_feed_manager  # noqa: E402
from services.anomaly_sweep import anomaly_sweeper  # noqa: E402
from services.options_sweeper import options_sweeper  # noqa: E402
from services.auto_session_manager import auto_session_scheduler  # noqa: E402
import asyncio
from services.poi_snapshot import load_snapshot, snapshot_loop
from services.idempotency import ensure_indexes as ensure_idem_indexes  # noqa: E402
from db import AsyncSessionLocal  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("algo-trading")

# Suppress verbose breeze-connect logging
logging.getLogger("APILogger").setLevel(logging.WARNING)
logging.getLogger("breeze_connect").setLevel(logging.WARNING)
logging.getLogger("WebsocketLogger").setLevel(logging.WARNING)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not record.args: return True
        msg = str(record.args[0])
        # Filter out noisy polling endpoints
        return not any(x in msg for x in [
            "/api/market/snapshot", 
            "/api/market/feed-status",
            "/api/parquet/status",
            "/api/health",
            "/api/analytics/premium-matcher"
        ])

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all MySQL tables exist on startup
    from db import init_db
    try:
        await init_db()
        logger.info("MySQL database tables verified and initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")

    # Download fresh master contracts from AliceBlue on startup
    import httpx
    import os
    try:
        logger.info("Downloading latest NFO and BFO master contracts...")
        async with httpx.AsyncClient() as client:
            res_nfo = await client.get('https://v2api.aliceblueonline.com/restpy/static/contract_master/NFO.csv', timeout=10.0)
            if res_nfo.status_code == 200:
                with open(str(ROOT_DIR / "NFO.csv"), 'wb') as f:
                    f.write(res_nfo.content)
            res_bfo = await client.get('https://v2api.aliceblueonline.com/restpy/static/contract_master/BFO.csv', timeout=10.0)
            if res_bfo.status_code == 200:
                with open(str(ROOT_DIR / "BFO.csv"), 'wb') as f:
                    f.write(res_bfo.content)
        logger.info("Master contracts downloaded successfully.")
        # Reload in-memory DataFrames immediately so the running server uses fresh data
        try:
            from aliceblue_chain import reload_master_dfs
            reload_master_dfs()
            logger.info("In-memory NFO/BFO DataFrames reloaded from fresh CSVs.")
        except Exception as e:
            logger.warning(f"reload_master_dfs failed: {e}")
        # Clear the stale options chain cache so it rebuilds from fresh data
        options_sweeper.cache.clear()
        options_sweeper.last_update.clear()
        logger.info("Options chain cache cleared — will rebuild from fresh master data.")
    except Exception as e:
        logger.warning(f"Failed to download master contracts: {e}")

    logger.info("Starting tick engine + market data capture + strategy scheduler")
    tick_engine.start()
    market_data_capture.start()
    strategy_scheduler.start()
    live_feed_manager.start()
    anomaly_sweeper.start()
    options_sweeper.start()
    auto_session_scheduler.start()
    
    # Snapshot system for POI
    asyncio.create_task(load_snapshot())
    poi_task = asyncio.create_task(snapshot_loop())
    
    from services.order_sync import sync_all_orders
    asyncio.create_task(sync_all_orders())
    
    try:
        await ensure_idem_indexes()
    except Exception as e:
        logger.warning("idempotency index creation failed: %s", e)
    try:
        pass  # ("expires_at", expireAfterSeconds=0)
    except Exception as e:
        logger.warning("token blacklist index creation failed: %s", e)
    if DEMO_USER_ENABLED:
        try:
            async with AsyncSessionLocal() as session:
                await ensure_demo_user(session)
        except Exception as e:
            logger.warning("ensure demo user failed: %s", e)
    else:
        logger.info("Demo user creation is disabled (DEMO_USER_ENABLED=false)")

    yield

    logger.info("Shutting down background services...")
    tick_engine.stop()
    market_data_capture.stop()
    strategy_scheduler.stop()
    anomaly_sweeper.stop()
    options_sweeper.stop()
    auto_session_scheduler.stop()
    live_feed_manager.stop()
    
    if 'poi_task' in locals() and not poi_task.done():
        poi_task.cancel()
        
    await asyncio.sleep(0.5)
    
    # Properly close all MySQL connections before the event loop closes.
    # Without this, aiomysql throws "RuntimeError: Event loop is closed" on exit.
    try:
        from db import engine as db_engine
        await db_engine.dispose()
        logger.info("MySQL connection pool disposed cleanly.")
    except Exception as e:
        logger.warning("Error disposing DB engine: %s", e)


app = FastAPI(title="Algo Trading Platform", lifespan=lifespan)

@app.get("/api/debug/prices")
def debug_prices():
    from services.market_data import tick_engine
    return {"prices": tick_engine.prices}

cors_origins = os.environ.get("CORS_ORIGINS", "*")
allow_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
allow_credentials = cors_origins != "*"

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "algo-trading", "ticks_running": tick_engine.running}


# Register routers — all under /api
for r in (
    auth_routes.router,
    managed_users_routes.router,
    market_routes.router,
    tradingview_routes.router,
    order_routes.router,
    strategy_routes.router,
    analytics_routes.router,
    signals_routes.router,
    signals_routes.backtest_router,
    broker_routes.router,
    data_routes.router,
    notification_routes.router,
    ai_routes.router,
):
    app.include_router(r, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8001))
    try:
        uvicorn.run("server:app", host=host, port=port, reload=True)
    except OSError as e:
        if "10013" in str(e) or "access permissions" in str(e).lower():
            logger.warning("Port %d or host %s forbidden, attempting 127.0.0.1:8002...", port, host)
            uvicorn.run("server:app", host="127.0.0.1", port=8002, reload=True)
        else:
            raise

