from fastapi import APIRouter, Depends, Query
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from auth import get_current_user
from constants import NIFTY_50, ALL_SYMBOLS
from models import User, SymbolMaster
from services.market_data import tick_engine
from db import get_db

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/symbols")
async def list_symbols(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
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
        "TECHM": 600, "INDUSINDBK": 500, "UPL": 1300, "TATACONSUM": 900, "LTIM": 150,
        "SUNTV": 500, "TVSMOTOR": 700, "VEDL": 2000, "HAL": 300, "BHEL": 5250
    }

    stmt_count = select(func.count(SymbolMaster.symbol))
    result_count = await session.execute(stmt_count)
    count = result_count.scalar_one()
    
    if count < len(default_lots):
        stmt_del = select(SymbolMaster)
        res_del = await session.execute(stmt_del)
        all_sm = res_del.scalars().all()
        for sm in all_sm:
            await session.delete(sm)
            
        for sym, size in default_lots.items():
            session.add(SymbolMaster(symbol=sym, lot_size=size, exchange="NSE"))
        await session.commit()

    stmt = select(SymbolMaster)
    result = await session.execute(stmt)
    masters = result.scalars().all()
    
    lot_sizes = {}
    for doc in masters:
        lot_sizes[doc.symbol] = doc.lot_size

    # Return all symbols from the database as the valid symbols list
    all_symbols_from_db = sorted(list(lot_sizes.keys()))
    return {"nifty50": NIFTY_50, "symbols": all_symbols_from_db, "lot_sizes": lot_sizes}


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
async def feed_status(user: User = Depends(get_current_user)):
    """Return status of live feed."""
    from services.live_feed_manager import live_feed_manager
    st = live_feed_manager.status()
    if st.get("active_user_id") != user.id:
        st["source"] = "none"
        st["active_broker"] = None
        st["active_user_id"] = None
    return st

@router.get("/debug-prices")
async def debug_prices():
    from services.market_data import tick_engine
    nfo_keys = [k for k in tick_engine.prices.keys() if "NFO" in k]
    return {
        "size": len(tick_engine.prices),
        "nfo_count": len(nfo_keys),
        "nfo_keys": nfo_keys[:30],
        "sample": {k: float(v) for k, v in list(tick_engine.prices.items())[:20] if not str(v).startswith("<")}
    }
