from fastapi import APIRouter, Depends, Query
from typing import List, Optional, Dict, Any

from auth import get_current_user
from constants import NIFTY_50, ALL_SYMBOLS
from models import User
from services.market_data import tick_engine
from db import db

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/symbols")
async def list_symbols() -> Dict[str, Any]:
    count = await db.symbol_master.count_documents({})
    if count == 0:
        default_lots = {
            "NIFTY": 25, "BANKNIFTY": 15, "FINNIFTY": 40, "MIDCPNIFTY": 75, "SENSEX": 10, "NIFTYNXT50": 25,
            "RELIANCE": 250, "HDFCBANK": 550, "ICICIBANK": 700, "INFY": 400, "TCS": 175,
            "BHARTIARTL": 950, "ITC": 1600, "LT": 300, "KOTAKBANK": 400, "AXISBANK": 625,
            "SBIN": 1500, "BAJFINANCE": 125, "HINDUNILVR": 300, "ASIANPAINT": 200, "MARUTI": 50,
            "HCLTECH": 700, "SUNPHARMA": 700, "TITAN": 175, "ULTRACEMCO": 100, "WIPRO": 1500,
            "M&M": 700, "NESTLEIND": 40, "POWERGRID": 3600, "NTPC": 3000, "ONGC": 3850,
            "TATAMOTORS": 1425, "TATASTEEL": 5500, "JSWSTEEL": 675, "ADANIENT": 300, "ADANIPORTS": 800,
            "BAJAJFINSV": 500, "BAJAJ-AUTO": 125, "HEROMOTOCO": 300, "EICHERMOT": 175, "GRASIM": 475,
            "DRREDDY": 125, "CIPLA": 650, "DIVISLAB": 200, "APOLLOHOSP": 125, "BRITANNIA": 200,
            "COALINDIA": 4200, "BPCL": 1800, "IOC": 9750, "HDFCLIFE": 1100, "SBILIFE": 750,
            "TECHM": 600, "INDUSINDBK": 500, "UPL": 1300, "TATACONSUM": 900, "LTIM": 150
        }
        docs = [{"symbol": sym, "lot_size": default_lots.get(sym, 1), "exchange": "NSE"} for sym in ALL_SYMBOLS]
        await db.symbol_master.insert_many(docs)

    cursor = db.symbol_master.find({}, {"_id": 0, "symbol": 1, "lot_size": 1})
    lot_sizes = {}
    async for doc in cursor:
        lot_sizes[doc["symbol"]] = doc["lot_size"]

    return {"nifty50": NIFTY_50, "symbols": ALL_SYMBOLS, "lot_sizes": lot_sizes}


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
