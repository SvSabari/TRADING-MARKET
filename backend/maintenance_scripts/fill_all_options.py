import asyncio
import datetime
import logging
import pandas as pd
from db import sync_db, db
from services.brokers.aliceblue_client import get_user_aliceblue_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fill_all_options")

async def fill_historical_options():
    logger.info("Starting Historical Options Fetcher for ALL Indices & Stocks...")
    
    client_doc = await db.broker_connections.find_one({"broker": "aliceblue", "connected": True})
    alice = await get_user_aliceblue_client(db, client_doc["user_id"])
    
    try:
        df = pd.read_csv("NFO.csv")
    except Exception as e:
        logger.error(f"Could not read NFO.csv: {e}")
        return

    # Grab ALL options
    options = df[df["Instrument Type"].isin(["OPTIDX", "OPTSTK"])]
    
    # Sort so OPTIDX (Indices) are fetched first, then OPTSTK (Stocks)
    options = options.sort_values(by="Instrument Type", ascending=True)
    
    from_date = datetime.datetime.now() - datetime.timedelta(days=20)
    to_date = datetime.datetime.now()
    
    docs = []
    
    logger.info(f"Fetching historical data for {len(options)} total option tokens (Indices first, then Stocks)...")
    
    count = 0
    total = len(options)
    for idx, row in options.iterrows():
        token = str(row["Token"])
        sym = row["Symbol"]
        strike = float(row["Strike Price"])
        opt_type = row["Option Type"]
        expiry = row["Expiry Date"]
        
        try:
            res_df = alice.get_historical(f"NFO|{token}", from_date, to_date, "1", False)
            if isinstance(res_df, pd.DataFrame) and not res_df.empty:
                for _, tick in res_df.iterrows():
                    ts_str = str(tick["datetime"])
                    ts = pd.to_datetime(ts_str).to_pydatetime()
                    docs.append({
                        "symbol": sym,
                        "strike": strike,
                        "opt_type": opt_type,
                        "expiry": expiry,
                        "ts": ts,
                        "ltp": float(tick["close"])
                    })
        except Exception as e:
            pass
            
        count += 1
        if count % 20 == 0:
            logger.info(f"Progress: {count}/{total} tokens fetched... Collected {len(docs)} candles so far.")
            if len(docs) > 10000:
                logger.info("Flushing to MongoDB...")
                sync_db.option_candles.insert_many(docs, ordered=False)
                docs = []
                
        # Tiny sleep to avoid AliceBlue rate limit bans
        await asyncio.sleep(0.05)
            
    if docs:
        logger.info(f"Saving final {len(docs)} candles to option_candles...")
        sync_db.option_candles.insert_many(docs, ordered=False)
        
    logger.info("Done fetching all historical options!")

if __name__ == "__main__":
    asyncio.run(fill_historical_options())
