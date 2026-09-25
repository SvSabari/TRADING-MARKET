import sqlite3
import pandas as pd
from pymongo import MongoClient
import datetime
import pytz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate-atlas")

def migrate():
    sqlite_db = r"D:\stock market\tracker.db"
    
    # User provided MongoDB Atlas connection string
    mongo_url = "mongodb+srv://sabaris192004_db_user:Sabari0109@cluster0.1j0p7kt.mongodb.net/?appName=Cluster0"
    db_name = "algo_trading_db" # Standard DB name used in this project
    
    logger.info(f"Connecting to MongoDB Atlas...")
    try:
        mongo_client = MongoClient(mongo_url)
        # Test connection
        mongo_client.admin.command('ping')
        logger.info("Pinged your deployment. You successfully connected to MongoDB Atlas!")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {e}")
        return

    db = mongo_client[db_name]
    
    logger.info(f"Connecting to SQLite at {sqlite_db}")
    conn = sqlite3.connect(sqlite_db)
    
    query = """
    SELECT date, time, symbol, expiry_date, strike_price, ce_ltp, pe_ltp
    FROM nse_1min_history
    WHERE symbol IN ('NIFTY', 'BANKNIFTY')
    """
    
    logger.info("Reading from SQLite and pushing to Atlas (this may take a few minutes)...")
    chunk_size = 50000
    total_inserted = 0
    ist = pytz.timezone('Asia/Kolkata')
    
    # To prevent duplicating data if run multiple times, we'll just insert everything for now,
    # MongoDB might complain about duplicate _id if we defined them, but we aren't.
    # It's better to clear existing option_candles in Atlas for a fresh sync, 
    # but we will just append to be safe.
    
    for chunk in pd.read_sql_query(query, conn, chunksize=chunk_size):
        docs = []
        for _, row in chunk.iterrows():
            dt_str = f"{row['date']} {row['time']}"
            try:
                local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                local_dt = ist.localize(local_dt)
                utc_dt = local_dt.astimezone(pytz.utc)
            except Exception:
                continue
                
            symbol = row['symbol']
            strike = float(row['strike_price'])
            expiry = row['expiry_date']
            
            if row['ce_ltp'] > 0:
                docs.append({
                    "symbol": symbol,
                    "strike": strike,
                    "opt_type": "CE",
                    "expiry": expiry,
                    "ts": utc_dt,
                    "ltp": float(row['ce_ltp'])
                })
                
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
            try:
                db.option_candles.insert_many(docs, ordered=False)
                total_inserted += len(docs)
                logger.info(f"Inserted {total_inserted} documents so far into Atlas...")
            except Exception as e:
                logger.error(f"Error inserting chunk: {e}")
                
    logger.info(f"Migration complete! Total options documents inserted to Atlas: {total_inserted}")
    
    logger.info("Ensuring indexes on option_candles in Atlas...")
    db.option_candles.create_index([("symbol", 1), ("strike", 1), ("opt_type", 1), ("ts", 1)])
    db.option_candles.create_index([("ts", 1)])
    logger.info("Done!")

if __name__ == "__main__":
    migrate()
