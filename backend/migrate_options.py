import sqlite3
import pandas as pd
from pymongo import MongoClient
import datetime
import pytz
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate-options")

def migrate():
    sqlite_db = r"D:\stock market\tracker.db"
    
    # Read from dotenv to get mongo connection string
    import os
    from dotenv import load_dotenv
    load_dotenv(os.path.join(r"d:\TRADING-TERMINAL-main", ".env"))
    
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "algo_trading_db")
    
    logger.info(f"Connecting to MongoDB at {mongo_url}")
    mongo_client = MongoClient(mongo_url)
    db = mongo_client[db_name]
    
    logger.info(f"Connecting to SQLite at {sqlite_db}")
    conn = sqlite3.connect(sqlite_db)
    
    # We will migrate BANKNIFTY and NIFTY option data
    query = """
    SELECT date, time, symbol, expiry_date, strike_price, ce_ltp, pe_ltp
    FROM nse_1min_history
    WHERE symbol IN ('NIFTY', 'BANKNIFTY')
    """
    
    logger.info("Reading from SQLite (this may take a minute)...")
    # Using chunksize to avoid blowing up memory with 4M rows
    chunk_size = 50000
    total_inserted = 0
    
    ist = pytz.timezone('Asia/Kolkata')
    
    for chunk in pd.read_sql_query(query, conn, chunksize=chunk_size):
        docs = []
        for _, row in chunk.iterrows():
            # Combine date and time
            # Note: tracker.db date format is YYYY-MM-DD and time is HH:MM:SS
            dt_str = f"{row['date']} {row['time']}"
            try:
                local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                local_dt = ist.localize(local_dt)
                utc_dt = local_dt.astimezone(pytz.utc)
            except Exception as e:
                continue
                
            symbol = row['symbol']
            strike = float(row['strike_price'])
            expiry = row['expiry_date'] # DD-MMM-YYYY format usually in tracker
            
            # CE doc
            if row['ce_ltp'] > 0:
                docs.append({
                    "symbol": symbol,
                    "strike": strike,
                    "opt_type": "CE",
                    "expiry": expiry,
                    "ts": utc_dt,
                    "ltp": float(row['ce_ltp'])
                })
                
            # PE doc
            if row['pe_ltp'] > 0:
                docs.append({
                    "symbol": symbol,
                    "strike": strike,
                    "opt_type": "PE",
                    "expiry": expiry,
                    "ts": utc_dt,
                    "ltp": float(row['pe_ltp'])
                })
                
        if docs:
            # We don't want duplicates, but for a clean migration it's fine to just insert many
            # since option_candles might be empty.
            try:
                db.option_candles.insert_many(docs, ordered=False)
                total_inserted += len(docs)
                logger.info(f"Inserted {total_inserted} documents so far...")
            except Exception as e:
                logger.error(f"Error inserting chunk: {e}")
                
    logger.info(f"Migration complete! Total options documents inserted: {total_inserted}")
    
    # Create indexes for fast querying in backtest
    logger.info("Ensuring indexes on option_candles...")
    db.option_candles.create_index([("symbol", 1), ("strike", 1), ("opt_type", 1), ("ts", 1)])
    db.option_candles.create_index([("ts", 1)])
    logger.info("Done!")

if __name__ == "__main__":
    migrate()
