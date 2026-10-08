"""Market data capture endpoints."""
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from db import get_db
from models import MarketCandle, User
from auth import get_current_user
from services.market_data_capture import market_data_capture

router = APIRouter(prefix="/parquet", tags=["parquet"])


@router.get("/status")
async def get_capture_status(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    from services.live_feed_manager import live_feed_manager
    st = live_feed_manager.status()
    is_owner = (st.get("active_user_id") == user.id)

    stats = market_data_capture.stats()
    
    if not is_owner:
        stats["running"] = False
        stats["rows_written"] = 0
        stats["last_flush"] = None
        stats["flush_count"] = 0

    stmt = select(func.count(MarketCandle.id))
    result = await session.execute(stmt)
    total = result.scalar_one()
    
    stats["total_db_candles"] = total
    return stats


@router.post("/start")
async def start_capture(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    market_data_capture.start()
    return await get_capture_status(user, session)


@router.post("/stop")
async def stop_capture(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    market_data_capture.stop()
    return await get_capture_status(user, session)


@router.get("/files")
async def list_files():
    import glob, os, time
    from datetime import datetime, timezone
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_pattern = os.path.join(base_dir, "data", "options_history", "*.parquet")
    files = glob.glob(search_pattern)
    
    out = []
    for f in files:
        filename = os.path.basename(f)
        parts = filename.replace('.parquet', '').split('_options_')
        symbol = parts[0] if len(parts) == 2 else "UNKNOWN"
        date_str = parts[1] if len(parts) == 2 else ""
        
        size = os.path.getsize(f)
        mod_time = os.path.getmtime(f)
        last_mod = datetime.fromtimestamp(mod_time, tz=timezone.utc).isoformat()
        
        out.append({
            "date": date_str,
            "symbol": symbol,
            "filename": filename.replace('.parquet', '.csv'),
            "path": f,
            "size_bytes": size,
            "row_count": max(1, size // 100),
            "last_modified": last_mod
        })
        
    out.sort(key=lambda x: (x['symbol'], x['date']), reverse=True)
    return {"files": out}


@router.get("/info")
async def get_data_info(symbol: str, session: AsyncSession = Depends(get_db)):
    import glob, os
    symbol = symbol.upper()
    
    # 1. Equity Days
    stmt_count = select(func.count(MarketCandle.id)).where(MarketCandle.symbol == symbol)
    result_count = await session.execute(stmt_count)
    count = result_count.scalar_one()
    
    equity_days = 0
    start_iso = None
    if count > 0:
        stmt_first = select(MarketCandle.ts).where(MarketCandle.symbol == symbol).order_by(MarketCandle.ts.asc()).limit(1)
        start = (await session.execute(stmt_first)).scalar_one_or_none()
        stmt_last = select(MarketCandle.ts).where(MarketCandle.symbol == symbol).order_by(MarketCandle.ts.desc()).limit(1)
        end = (await session.execute(stmt_last)).scalar_one_or_none()
        
        if start and end:
            if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            diff = end - start
            equity_days = max(1, round(diff.total_seconds() / 86400, 1))
            start_iso = start.isoformat()

    # 2. Options Days
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_pattern = os.path.join(base_dir, "data", "options_history", f"{symbol}_options_*.parquet")
    files = glob.glob(search_pattern)
    options_days = len(files)

    return {
        "days": equity_days,
        "candles": count,
        "start": start_iso,
        "equity_days": equity_days,
        "options_days": options_days
    }


@router.get("/preview")
async def get_data_preview(path: str, limit: int = 100):
    import os, pandas as pd
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "data", "options_history", os.path.basename(path))
    
    if not os.path.exists(file_path):
        return {"rows": []}
        
    df = pd.read_parquet(file_path)
    if df.empty:
        return {"rows": []}
        
    df = df.head(limit)
    
    docs = []
    for _, row in df.iterrows():
        docs.append({
            "ts": str(row['timestamp']),
            "open": float(row['strike']),
            "high": float(row.get('ce_ltp', 0)),
            "low": float(row.get('pe_ltp', 0)),
            "close": 0,
            "volume": 0
        })
        
    return {"rows": docs}


@router.get("/download")
async def download_parquet(path: str):
    import os, io, pandas as pd
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "data", "options_history", os.path.basename(path))
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    df = pd.read_parquet(file_path)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    csv_filename = os.path.basename(file_path).replace('.parquet', '.csv')
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"}
    )
