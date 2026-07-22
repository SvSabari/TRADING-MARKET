from fastapi import APIRouter, Depends, Query
from typing import List, Optional, Dict, Any

from auth import get_current_user
from constants import NIFTY_50, ALL_SYMBOLS
from models import User
from services.market_data import tick_engine

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/symbols")
async def list_symbols() -> Dict[str, Any]:
    return {"nifty50": NIFTY_50, "symbols": ALL_SYMBOLS}


@router.get("/snapshot")
async def snapshot(user: User = Depends(get_current_user)):
    return {"ticks": tick_engine.snapshot()}


@router.get("/history/{symbol}")
async def history(symbol: str, limit: int = Query(120, ge=10, le=600),
                  user: User = Depends(get_current_user)):
    hist = tick_engine.get_history(symbol.upper())[-limit:]
    return {"symbol": symbol.upper(), "candles": hist}


@router.get("/top-movers")
async def top_movers(n: int = 10, user: User = Depends(get_current_user)):
    snap = tick_engine.snapshot()
    gainers = sorted(snap, key=lambda x: x["change_pct"], reverse=True)[:n]
    losers = sorted(snap, key=lambda x: x["change_pct"])[:n]
    return {"gainers": gainers, "losers": losers}


@router.get("/feed-status")
async def feed_status():
    """Return status of live feed."""
    from services.live_feed_manager import live_feed_manager
    return live_feed_manager.status()

@router.get("/debug-prices")
async def debug_prices():
    from services.market_data import tick_engine
    return {
        "size": len(tick_engine.prices),
        "nfo_count": sum(1 for k in tick_engine.prices.keys() if "NFO" in k),
        "sample": {k: float(v) for k, v in list(tick_engine.prices.items())[:20] if not str(v).startswith("<")}
    }
