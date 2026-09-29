"""
Atlas is at 546MB with 2,077,720 docs — over the 512MB M0 limit.
Strategy: Delete SENSEX (stops July 2026, 59K docs) and ALL BANKNIFTY
(803K docs) to free ~240MB. This gets us to ~305MB data, leaving 
~200MB room for the essential compound index.
Then verify per-symbol counts.
"""
from pymongo import MongoClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger("trim-atlas")

mongo_url = "mongodb+srv://sabaris192004_db_user:Sabari0109@cluster0.1j0p7kt.mongodb.net/?appName=Cluster0"
mongo_client = MongoClient(mongo_url)
db = mongo_client["algo_trading_db"]

# Step 1: Check current state
total_before = db.option_candles.count_documents({})
logger.info(f"Total docs before trim: {total_before:,}")
for sym in ['NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX']:
    c = db.option_candles.count_documents({"symbol": sym})
    logger.info(f"  {sym}: {c:,}")

# Step 2: Delete SENSEX (stops July 2026, not needed for main strategies)
logger.info("Deleting SENSEX option_candles...")
res = db.option_candles.delete_many({"symbol": "SENSEX"})
logger.info(f"  Deleted {res.deleted_count:,} SENSEX docs")

# Step 3: Delete BANKNIFTY (803K docs = ~220MB; biggest consumer)
# We sacrifice BANKNIFTY for now to fit the index for NIFTY/FINNIFTY/MIDCPNIFTY
logger.info("Deleting BANKNIFTY option_candles...")
res = db.option_candles.delete_many({"symbol": "BANKNIFTY"})
logger.info(f"  Deleted {res.deleted_count:,} BANKNIFTY docs")

total_after = db.option_candles.count_documents({})
est_mb = (total_after * 273) / (1024 * 1024)
logger.info(f"Docs remaining: {total_after:,} (est. ~{est_mb:.0f} MB data)")
logger.info(f"Est. space for index: ~{512 - est_mb:.0f} MB available")

# Step 4: Create the ONE essential compound index
logger.info("Creating compound index (symbol, strike, opt_type, ts)...")
try:
    db.option_candles.create_index(
        [("symbol", 1), ("strike", 1), ("opt_type", 1), ("ts", 1)],
        name="symbol_strike_type_ts"
    )
    logger.info("  Primary index created OK")
except Exception as e:
    logger.error(f"  Primary index failed: {e}")

# Step 5: Create secondary index for fallback queries (any strike, same type)
logger.info("Creating secondary index (symbol, opt_type, ts)...")
try:
    db.option_candles.create_index(
        [("symbol", 1), ("opt_type", 1), ("ts", 1)],
        name="symbol_type_ts"
    )
    logger.info("  Secondary index created OK")
except Exception as e:
    logger.error(f"  Secondary index failed: {e}")

# Final counts
logger.info("\nFINAL STATE:")
for sym in ['NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX']:
    c = db.option_candles.count_documents({"symbol": sym})
    if c > 0:
        first = db.option_candles.find_one({"symbol": sym}, sort=[("ts", 1)])
        last  = db.option_candles.find_one({"symbol": sym}, sort=[("ts", -1)])
        logger.info(f"  {sym:<14} {c:>9} docs  {first['ts'].strftime('%Y-%m-%d')} → {last['ts'].strftime('%Y-%m-%d')}")
    else:
        logger.info(f"  {sym:<14}         0 docs  (no data)")

mongo_client.close()
logger.info("Done.")
