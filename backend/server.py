"""Algo Trading Platform — FastAPI entry point."""
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
    market_routes, notification_routes, order_routes, parquet_routes,
    signals_routes, strategy_routes, tradingview_routes,
)
from auth import ensure_demo_user
from services.market_data import tick_engine  # noqa: E402
from services.parquet_capture import parquet_capture  # noqa: E402
from services.strategy_scheduler import scheduler as strategy_scheduler  # noqa: E402
from services.live_feed_manager import live_feed_manager  # noqa: E402
from services.anomaly_sweep import anomaly_sweeper  # noqa: E402
from services.options_sweeper import options_sweeper  # noqa: E402
import asyncio
from services.poi_snapshot import load_snapshot, snapshot_loop
from services.idempotency import ensure_indexes as ensure_idem_indexes  # noqa: E402
from db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("algo-trading")

# Suppress verbose breeze-connect logging
logging.getLogger("APILogger").setLevel(logging.WARNING)
logging.getLogger("breeze_connect").setLevel(logging.WARNING)
logging.getLogger("WebsocketLogger").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting tick engine + parquet capture + strategy scheduler")
    tick_engine.start()
    parquet_capture.start()
    strategy_scheduler.start()
    live_feed_manager.start()
    anomaly_sweeper.start()
    options_sweeper.start()
    
    # Snapshot system for POI
    await load_snapshot()
    asyncio.create_task(snapshot_loop())
    try:
        await ensure_idem_indexes()
    except Exception as e:
        logger.warning("idempotency index creation failed: %s", e)
    try:
        await db.token_blacklist.create_index("expires_at", expireAfterSeconds=0)
    except Exception as e:
        logger.warning("token blacklist index creation failed: %s", e)
    if DEMO_USER_ENABLED:
        try:
            await ensure_demo_user()
        except Exception as e:
            logger.warning("ensure demo user failed: %s", e)
    else:
        logger.info("Demo user creation is disabled (DEMO_USER_ENABLED=false)")

    yield

    logger.info("Shutting down background services...")
    tick_engine.stop()
    parquet_capture.stop()
    strategy_scheduler.stop()
    anomaly_sweeper.stop()
    options_sweeper.stop()


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
    market_routes.router,
    tradingview_routes.router,
    order_routes.router,
    strategy_routes.router,
    analytics_routes.router,
    signals_routes.router,
    signals_routes.backtest_router,
    broker_routes.router,
    parquet_routes.router,
    notification_routes.router,
    ai_routes.router,
):
    app.include_router(r, prefix="/api")
