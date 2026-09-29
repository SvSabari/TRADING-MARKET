"""
Migrate specifically September data so it perfectly overlaps with the Atlas market_candles.
"""
import sqlite3
from pymongo import MongoClient
import datetime
import pytz
import pandas as pd

sqlite_db = r"D:\stock market\tracker.db"
mongo_url = "mongodb+srv://sabaris192004_db_user:Sabari0109@cluster0.1j0p7kt.mongodb.net/?appName=Cluster0"

conn = sqlite3.connect(sqlite_db)
mongo_client = MongoClient(mongo_url)
db = mongo_client["algo_trading_db"]

# Drop ALL option_candles to clear space (since they don't overlap anyway)
db.option_candles.drop()
print("Dropped old non-overlapping option_candles.")

symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']

# Market data is Sept 8 to Sept 25. We migrate Sept 1 onwards.
query = f"""
    SELECT date, time, symbol, expiry_date, strike_price, ce_ltp, pe_ltp
    FROM nse_1min_history
    WHERE date >= '2026-09-01'
"""
ist = pytz.timezone('Asia/Kolkata')
chunk_size = 50000
total_inserted = 0

for chunk in pd.read_sql_query(query, conn, chunksize=chunk_size):
    docs = []
    for _, row in chunk.iterrows():
        dt_str = f"{row['date']} {row['time']}"
        try:
            local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            local_dt = ist.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
        except:
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
        db.option_candles.insert_many(docs, ordered=False)
        total_inserted += len(docs)

print(f"Inserted {total_inserted} docs from Sept 1 onwards.")

db.option_candles.create_index([("symbol", 1), ("strike", 1), ("opt_type", 1), ("ts", 1)])
db.option_candles.create_index([("symbol", 1), ("opt_type", 1), ("ts", 1)])

conn.close()
mongo_client.close()
