"""
Calculate the exact cut-off date to fit within Atlas M0 limit,
then perform the safe full migration from tracker.db → Atlas.
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

symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']

# Atlas M0 limit: conservatively 450 MB total data
# Each doc ~220 bytes (BSON + index overhead x2 for 3 indexes)
BYTES_PER_DOC = 220
ATLAS_SAFE_LIMIT_MB = 450
MAX_DOCS = int((ATLAS_SAFE_LIMIT_MB * 1024 * 1024) / BYTES_PER_DOC)

print(f"Atlas safe capacity : {MAX_DOCS:,} docs ({ATLAS_SAFE_LIMIT_MB} MB)")

# Full dataset from June 9: 2,195,561 docs
# That needs ~461 MB — over limit
# Full dataset from June 16: let's calculate week by week to find the safe start

print("\nCalculating cumulative doc count by week to find safe start date...")
cursor = conn.cursor()

# Build weekly cumulative from June 9
cursor.execute("""
    SELECT date,
           SUM(CASE WHEN ce_ltp IS NOT NULL AND ce_ltp > 0 THEN 1 ELSE 0 END) +
           SUM(CASE WHEN pe_ltp IS NOT NULL AND pe_ltp > 0 THEN 1 ELSE 0 END) as docs
    FROM nse_1min_history
    WHERE symbol IN ('NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX')
    GROUP BY date
    ORDER BY date ASC
""")
daily = cursor.fetchall()

cumulative = 0
safe_start = None
print(f"{'DATE':<14} {'DAILY DOCS':<14} {'CUMULATIVE':<14} {'EST MB':<10} {'FIT?'}")
print("-" * 65)
prev_date = None
for date_str, daily_docs in daily:
    cumulative += daily_docs
    est_mb = (cumulative * BYTES_PER_DOC) / (1024*1024)
    fits = est_mb <= ATLAS_SAFE_LIMIT_MB
    # Print every ~10 days for readability
    if prev_date is None or (datetime.datetime.strptime(date_str, "%Y-%m-%d") - datetime.datetime.strptime(prev_date, "%Y-%m-%d")).days >= 7:
        print(f"{date_str:<14} {daily_docs:<14} {cumulative:<14} {est_mb:<10.1f} {'YES' if fits else 'NO -- STOP HERE'}")
        prev_date = date_str
    if not fits and safe_start is None:
        # Go back one step
        safe_start = date_str
        break

if safe_start is None:
    print(f"\nAll data from June 9 fits! Starting from 2026-06-09")
    safe_start = "2026-06-09"
else:
    # Find the last date that still fit
    cumulative2 = 0
    for date_str, daily_docs in daily:
        if (cumulative2 + daily_docs) * BYTES_PER_DOC / (1024*1024) > ATLAS_SAFE_LIMIT_MB:
            print(f"\nSafe migration from: {safe_start} onward will exceed limit")
            break
        cumulative2 += daily_docs
        safe_start = date_str

print(f"\n==> SAFE MIGRATION START DATE: {safe_start}")
cursor.execute("""
    SELECT SUM(CASE WHEN ce_ltp > 0 THEN 1 ELSE 0 END) + SUM(CASE WHEN pe_ltp > 0 THEN 1 ELSE 0 END)
    FROM nse_1min_history
    WHERE symbol IN ('NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX')
    AND date >= ?
""", (safe_start,))
total_safe = cursor.fetchone()[0]
print(f"==> Total docs in safe window: {total_safe:,} ({(total_safe * BYTES_PER_DOC)/(1024*1024):.1f} MB)")

conn.close()
mongo_client.close()
