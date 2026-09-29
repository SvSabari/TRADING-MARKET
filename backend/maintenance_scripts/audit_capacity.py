"""
Step 1: Audit tracker.db date ranges and counts per symbol.
Step 2: Calculate current Atlas usage.
Step 3: Determine how much we can safely add.
"""
import sqlite3
from pymongo import MongoClient
import pytz

sqlite_db = r"D:\stock market\tracker.db"
mongo_url = "mongodb+srv://sabaris192004_db_user:Sabari0109@cluster0.1j0p7kt.mongodb.net/?appName=Cluster0"

conn = sqlite3.connect(sqlite_db)
cursor = conn.cursor()
mongo_client = MongoClient(mongo_url)
db = mongo_client["algo_trading_db"]

symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX']

print("=" * 80)
print("STEP 1: tracker.db FULL AUDIT")
print("=" * 80)
print(f"{'SYMBOL':<14} {'SQLITE_ROWS':<14} {'CE_DOCS':<12} {'PE_DOCS':<12} {'DATE_FROM':<14} {'DATE_TO':<14}")
print("-" * 80)

sqlite_summary = {}
total_expected_docs = 0

for sym in symbols:
    cursor.execute(f"""
        SELECT COUNT(*), 
               SUM(CASE WHEN ce_ltp IS NOT NULL AND ce_ltp > 0 THEN 1 ELSE 0 END),
               SUM(CASE WHEN pe_ltp IS NOT NULL AND pe_ltp > 0 THEN 1 ELSE 0 END),
               MIN(date), MAX(date)
        FROM nse_1min_history WHERE symbol = ?
    """, (sym,))
    row = cursor.fetchone()
    rows, ce, pe, d_from, d_to = row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 'N/A', row[4] or 'N/A'
    expected_docs = ce + pe
    total_expected_docs += expected_docs
    sqlite_summary[sym] = {'rows': rows, 'ce': ce, 'pe': pe, 'from': d_from, 'to': d_to, 'docs': expected_docs}
    print(f"{sym:<14} {rows:<14} {ce:<12} {pe:<12} {d_from:<14} {d_to:<14}")

print(f"\n{'TOTAL expected MongoDB docs from tracker.db':>50}: {total_expected_docs:,}")

print("\n" + "=" * 80)
print("STEP 2: CURRENT ATLAS STORAGE ESTIMATE")
print("=" * 80)

# Count current docs in Atlas
current_docs = db.option_candles.count_documents({})
print(f"Current option_candles docs in Atlas : {current_docs:,}")

# Rough BSON doc size estimate: ~220 bytes per option_candles document
bytes_per_doc = 220
current_used_mb = (current_docs * bytes_per_doc) / (1024 * 1024)
atlas_limit_mb = 450  # Conservative limit (M0 is 512MB total, ~450MB for data)
available_mb = atlas_limit_mb - current_used_mb
available_docs = int((available_mb * 1024 * 1024) / bytes_per_doc)

print(f"Estimated current usage            : {current_used_mb:.1f} MB")
print(f"Atlas M0 safe limit                : {atlas_limit_mb} MB")
print(f"Available remaining space          : {available_mb:.1f} MB")
print(f"Estimated docs we can still add    : {available_docs:,}")

print("\n" + "=" * 80)
print("STEP 3: WHAT IS MISSING FROM ATLAS (per symbol, outside Aug 15+ window)")
print("=" * 80)
print(f"{'SYMBOL':<14} {'SQLITE_DOCS':<14} {'ALREADY_IN_MONGO':<18} {'MISSING':<14}")
print("-" * 80)

for sym in symbols:
    mongo_count = db.option_candles.count_documents({"symbol": sym})
    missing = max(0, sqlite_summary[sym]['docs'] - mongo_count)
    print(f"{sym:<14} {sqlite_summary[sym]['docs']:<14} {mongo_count:<18} {missing:<14}")

print(f"\nIf we migrate everything from tracker.db:")
print(f"  Total docs needed     : {total_expected_docs:,}")
print(f"  Available in Atlas    : {available_docs:,}")
if total_expected_docs <= available_docs + current_docs:
    print(f"  STATUS: FULL MIGRATION FITS in Atlas (after replacing existing docs)")
else:
    print(f"  STATUS: TOO LARGE — need to filter by date or symbol priority")

conn.close()
mongo_client.close()
