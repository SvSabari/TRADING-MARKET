import asyncio
import datetime
import logging
import pandas as pd
from db import sync_db, db
from services.brokers.aliceblue_client import get_user_aliceblue_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fill_options")

async def fill_historical_options():
    logger.info("Starting Historical Options Fetcher...")
    
    client_doc = await db.broker_connections.find_one({"broker": "aliceblue", "connected": True})
    alice = await get_user_aliceblue_client(db, client_doc["user_id"])
    
    try:
        df = pd.read_csv("NFO.csv")
    except Exception as e:
        logger.error(f"Could not read NFO.csv: {e}")
        return

    options = df[
        (df["Symbol"] == "NIFTY") & 
        (df["Instrument Type"] == "OPTIDX")
    ]
    
    from_date = datetime.datetime.now() - datetime.timedelta(days=20)
    to_date = datetime.datetime.now()
    
    docs = []
    
    logger.info(f"Fetching historical data for {len(options)} active NIFTY tokens...")
    
    count = 0
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
                    # AliceBlue historical times might be '2026-09-25 09:15:59'
                    ts = pd.to_datetime(ts_str).to_pydatetime()
                    docs.append({
                        "symbol": sym,
                        "strike": strike,
                        "opt_type": opt_type,
                        "expiry": expiry,
                        "ts": ts,
                        "ltp": float(tick["close"])
                    })
                count += 1
                if count % 10 == 0:
                    logger.info(f"Fetched {count} tokens... Collected {len(docs)} candles.")
        except Exception as e:
            pass
            
    if docs:
        logger.info(f"Saving {len(docs)} candles to option_candles...")
        sync_db.option_candles.insert_many(docs, ordered=False)
        logger.info("Done!")
    else:
        logger.info("No data fetched.")

if __name__ == "__main__":
    asyncio.run(fill_historical_options())
