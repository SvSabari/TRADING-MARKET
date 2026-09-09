"""Market data capture endpoints."""
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter

from db import db
from services.market_data_capture import market_data_capture

router = APIRouter(prefix="/parquet", tags=["parquet"])


@router.get("/status")
async def get_capture_status():
    stats = market_data_capture.stats()
    stats["total_db_candles"] = await db.market_candles.count_documents({})
    return stats


@router.post("/start")
async def start_capture():
    market_data_capture.start()
    return await get_capture_status()


@router.post("/stop")
async def stop_capture():
    market_data_capture.stop()
    return await get_capture_status()



@router.get('/files')
async def list_files():
    out = []
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    try:
        pipeline = [
            {'$group': {
                '_id': '$symbol',
                'count': {'$sum': 1},
                'latest': {'$max': '$ts'}
            }}
        ]
        async for doc in db.market_candles.aggregate(pipeline):
            s = doc['_id']
            count = doc['count']
            ts_obj = doc['latest']
            if ts_obj:
                if ts_obj.tzinfo is None:
                    ts_obj = ts_obj.replace(tzinfo=timezone.utc)
                last_mod = ts_obj.isoformat()
            else:
                last_mod = datetime.now(timezone.utc).isoformat()
            out.append({
                'date': today_str,
                'symbol': s,
                'filename': f'{s}.csv',
                'path': s,
                'size_bytes': count * 128,
                'row_count': count,
                'last_modified': last_mod
            })
    except Exception as e:
        print('Error in list_files:', e)
    return {'files': out}

@router.get("/preview")
async def get_data_preview(path: str, interval: str = "1", limit: int = 1000):
    # 'path' from frontend is now just the symbol
    symbol = path.upper()
    # Fetch more ticks so we can form enough grouped candles
    cursor = db.market_candles.find({"symbol": symbol}).sort("ts", -1).limit(limit * 60)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        # Ensure timestamp is timezone-aware so the UI displays local time
        if "ts" in doc and doc["ts"].tzinfo is None:
            doc["ts"] = doc["ts"].replace(tzinfo=timezone.utc)
        docs.append(doc)
    docs.reverse()
    
    if not docs:
        return {"rows": []}
        
    import pandas as pd
    
    df = pd.DataFrame(docs)
    df.set_index("ts", inplace=True)
    
    # Resample based on the interval (e.g., '1min', 'D')
    if interval == "D":
        rule = "D"
    else:
        rule = f"{interval}min"
    
    # The tick data in market_candles has 'open', 'high', 'low' as the DAY's values,
    # and 'close' as the Last Traded Price (LTP) at that instant.
    # To form proper interval candles, we must calculate the interval's OHLC using ONLY the LTP ('close').
    resampled = df.resample(rule).agg({
        "close": ["first", "max", "min", "last"],
        "volume": "sum"
    }).dropna()
    
    # Flatten multi-level columns from aggregation
    resampled.columns = ["open", "high", "low", "close", "volume"]
    
    resampled.reset_index(inplace=True)
    
    # Convert back to dict list
    final_docs = []
    for _, row in resampled.tail(limit).iterrows():
        final_docs.append({
            "ts": row["ts"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"]
        })
        
    return {"rows": final_docs}


@router.get("/download")
async def download_parquet(path: str):
    symbol = path.upper()
    cursor = db.market_candles.find({"symbol": symbol}).sort("ts", 1)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        if "ts" in doc and doc["ts"].tzinfo is None:
            doc["ts"] = doc["ts"].replace(tzinfo=timezone.utc)
        docs.append(doc)
        
    if not docs:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No data found")
        
    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse
    
    df = pd.DataFrame(docs)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={symbol}.csv"}
    )


@router.get('/debug-mongo')
async def debug_mongo():
    import os
    url = os.environ.get('MONGO_URL', '')
    uri = os.environ.get('MONGO_URI', '')
    return {'MONGO_URL': url[:15] + '...', 'MONGO_URI': uri[:15] + '...', 'USE_IN_MEMORY': os.environ.get('USE_IN_MEMORY_DB', '')}



