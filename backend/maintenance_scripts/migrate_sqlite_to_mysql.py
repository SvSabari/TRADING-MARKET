import asyncio
import sqlite3
import pandas as pd
import datetime
import pytz
import logging
import sys
import os

# Ensure backend directory is in path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import AsyncSessionLocal
from models import OptionCandle
from sqlalchemy.dialects.mysql import insert
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger("sqlite-to-mysql")

async def migrate_options():
    sqlite_db = r"D:\stock market\data\tracker.db"
    
    if not os.path.exists(sqlite_db):
        logger.error(f"Could not find {sqlite_db}")
        return
        
    logger.info(f"Connecting to SQLite database: {sqlite_db}")
    conn = sqlite3.connect(sqlite_db)
    
    ist = pytz.timezone('Asia/Kolkata')
    
    query = """
        SELECT date, time, symbol, expiry_date, strike_price, ce_ltp, pe_ltp
        FROM nse_1min_history
        WHERE ce_ltp IS NOT NULL OR pe_ltp IS NOT NULL
    """
    
    chunk_size = 50000
    total_inserted = 0
    
    async with AsyncSessionLocal() as session:
        # First, count existing rows to avoid dropping if user wants to append
        # But we use ON DUPLICATE KEY UPDATE so it's safe to just run
        
        logger.info("Reading from SQLite in chunks and migrating to MySQL...")
        
        for chunk in pd.read_sql_query(query, conn, chunksize=chunk_size):
            records = []
            for _, row in chunk.iterrows():
                dt_str = f"{row['date']} {row['time']}"
                try:
                    local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    local_dt = ist.localize(local_dt)
                    utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)  # naive UTC
                except Exception:
                    continue

                ce_ltp = row['ce_ltp']
                pe_ltp = row['pe_ltp']
                symbol = row['symbol']
                try:
                    strike = float(row['strike_price'])
                except:
                    continue
                expiry = row['expiry_date']

                if ce_ltp is not None and float(ce_ltp) > 0:
                    records.append({
                        "symbol": symbol, "strike": strike, "opt_type": "CE",
                        "expiry": expiry, "ts": utc_dt, "ltp": float(ce_ltp)
                    })
                if pe_ltp is not None and float(pe_ltp) > 0:
                    records.append({
                        "symbol": symbol, "strike": strike, "opt_type": "PE",
                        "expiry": expiry, "ts": utc_dt, "ltp": float(pe_ltp)
                    })

            if records:
                try:
                    # Break into smaller batches for MySQL insertion
                    batch_size = 5000
                    for i in range(0, len(records), batch_size):
                        batch = records[i:i+batch_size]
                        
                        stmt = insert(OptionCandle).values(batch)
                        # Avoid duplicates
                        stmt = stmt.on_duplicate_key_update(
                            ltp=stmt.inserted.ltp
                        )
                        
                        await session.execute(stmt)
                    
                    await session.commit()
                    total_inserted += len(records)
                    logger.info(f"Progress: {total_inserted:,} options candles inserted into MySQL...")
                except Exception as e:
                    logger.error(f"Insert error: {e}")
                    await session.rollback()

    logger.info(f"MIGRATION COMPLETE! Successfully inserted {total_inserted:,} CE/PE candles into MySQL.")
    conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_options())
