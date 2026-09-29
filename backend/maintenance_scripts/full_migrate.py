"""
Full migration from tracker.db to Atlas.
Strategy: Drop existing option_candles, then migrate ALL data from June 9
up to the safe capacity limit (stop before Sept 10 which pushes over limit).
"""
import sqlite3
from pymongo import MongoClient
import datetime
import pytz
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger("full-migrate")

sqlite_db = r"D:\stock market\tracker.db"
mongo_url = "mongodb+srv://sabaris192004_db_user:Sabari0109@cluster0.1j0p7kt.mongodb.net/?appName=Cluster0"

conn = sqlite3.connect(sqlite_db)
mongo_client = MongoClient(mongo_url)
db = mongo_client["algo_trading_db"]

ist = pytz.timezone('Asia/Kolkata')

# From audit: June 9 to Sept 9 = 2,077,720 docs = 435.9 MB — fits safely.
# Sept 10 pushes to 451.8 MB, which slightly exceeds safe limit.
# So we migrate June 9 to Sept 9 inclusive for all 5 symbols.
FROM_DATE = "2026-06-09"
TO_DATE   = "2026-09-09"  # inclusive

logger.info(f"Migration window: {FROM_DATE} to {TO_DATE}")
logger.info("Dropping existing option_candles collection...")
db.option_candles.drop()
logger.info("Collection dropped.")

symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']

query = f"""
    SELECT date, time, symbol, expiry_date, strike_price, ce_ltp, pe_ltp
    FROM nse_1min_history
    WHERE symbol IN ('NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX')
    AND date >= '{FROM_DATE}' AND date <= '{TO_DATE}'
"""

logger.info("Reading from SQLite in chunks...")
chunk_size = 50000
total_inserted = 0

for chunk in pd.read_sql_query(query, conn, chunksize=chunk_size):
    docs = []
    for _, row in chunk.iterrows():
        dt_str = f"{row['date']} {row['time']}"
        try:
            local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            local_dt = ist.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)  # naive UTC for consistency
        except Exception:
            continue

        ce_ltp = row['ce_ltp']
        pe_ltp = row['pe_ltp']
        symbol = row['symbol']
        strike = float(row['strike_price'])
        expiry = row['expiry_date']

        if ce_ltp is not None and ce_ltp > 0:
            docs.append({
                "symbol": symbol, "strike": strike, "opt_type": "CE",
                "expiry": expiry, "ts": utc_dt, "ltp": float(ce_ltp)
            })
        if pe_ltp is not None and pe_ltp > 0:
            docs.append({
                "symbol": symbol, "strike": strike, "opt_type": "PE",
                "expiry": expiry, "ts": utc_dt, "ltp": float(pe_ltp)
            })

    if docs:
        try:
            db.option_candles.insert_many(docs, ordered=False)
            total_inserted += len(docs)
        except Exception as e:
            logger.error(f"Insert error: {e}")

    logger.info(f"Progress: {total_inserted:,} docs inserted...")

logger.info("Creating compound indexes...")
db.option_candles.create_index([("symbol", 1), ("strike", 1), ("opt_type", 1), ("ts", 1)])
db.option_candles.create_index([("symbol", 1), ("opt_type", 1), ("ts", 1)])
db.option_candles.create_index([("ts", 1)])
logger.info(f"MIGRATION COMPLETE. Total docs inserted: {total_inserted:,}")

# Quick per-symbol count
logger.info("Per-symbol counts in Atlas after migration:")
for sym in symbols:
    count = db.option_candles.count_documents({"symbol": sym})
    first = db.option_candles.find_one({"symbol": sym}, sort=[("ts", 1)])
    last  = db.option_candles.find_one({"symbol": sym}, sort=[("ts", -1)])
    d_from = first["ts"].strftime("%Y-%m-%d") if first else "N/A"
    d_to   = last["ts"].strftime("%Y-%m-%d") if last else "N/A"
    logger.info(f"  {sym:<14} {count:>8} docs   {d_from} → {d_to}")

conn.close()
mongo_client.close()
