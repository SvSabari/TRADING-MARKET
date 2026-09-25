import asyncio
import datetime
from datetime import timezone
import logging
import pandas as pd
from db import sync_db, db
from services.brokers.aliceblue_client import get_user_aliceblue_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("historical-options-scraper")

async def scrape_historical_options():
    logger.info("Starting Historical Options Scraper...")
    
    client_doc = await db.broker_connections.find_one({"broker": "aliceblue", "connected": True})
    if not client_doc:
        logger.error("No AliceBlue connected user found.")
        return
        
    alice = await get_user_aliceblue_client(db, client_doc["user_id"])
    if not alice:
        logger.error("Failed to authenticate AliceBlue.")
        return
        
    logger.info(f"Authenticated AliceBlue for user {client_doc['user_id']}")
    
    # Read NFO.csv
    try:
        df = pd.read_csv("NFO.csv")
    except Exception as e:
        logger.error(f"Could not read NFO.csv: {e}")
        return

    # Filter for NIFTY and BANKNIFTY options in Sept 2026
    # Trading Symbol format: BANKNIFTY29SEP26C45000
    options = df[
        (df["Symbol"].isin(["NIFTY", "BANKNIFTY"])) & 
        (df["Instrument Type"] == "OPTIDX") & 
        (df["Trading Symbol"].str.contains("SEP26", na=False))
    ]
    
    from_date = datetime.datetime(2026, 9, 9)
    to_date = datetime.datetime(2026, 9, 12) # focus on sept 10!
    
    docs = []
    
    # For testing, just get strikes close to ATM (e.g. 56000-57000 for BANKNIFTY)
    # The backtest is around 56400 to 56500. So let's grab 56200 to 56600
    options = options[
        ((options["Symbol"] == "BANKNIFTY") & (options["Strike Price"].astype(float) >= 56000) & (options["Strike Price"].astype(float) <= 56700))
    ]
    
    logger.info(f"Fetching historical data for {len(options)} tokens...")
    
    for idx, row in options.iterrows():
        token = str(row["Token"])
        symbol = row["Symbol"]
        strike = float(row["Strike Price"])
        opt_type = row["Option Type"]
        expiry = row["Expiry Date"]
        
        try:
            hist = alice.get_historical(token, from_date, to_date, "1")
            if isinstance(hist, list) and len(hist) > 0:
                for candle in hist:
                    try:
                        ts = datetime.datetime.fromisoformat(candle["datetime"])
                        docs.append({
                            "symbol": symbol,
                            "strike": strike,
                            "opt_type": opt_type,
                            "expiry": expiry,
                            "ts": ts,
                            "ltp": float(candle["close"])
                        })
                    except Exception as e:
                        pass
                logger.info(f"Fetched {len(hist)} candles for {symbol} {strike} {opt_type}")
            else:
                pass
        except Exception as e:
            logger.error(f"Error fetching {symbol} {strike} {opt_type}: {e}")
            
    if docs:
        logger.info(f"Saving {len(docs)} candles to option_candles...")
        sync_db.option_candles.insert_many(docs, ordered=False)
        logger.info("Done!")
    else:
        logger.warning("No data found!")

if __name__ == "__main__":
    asyncio.run(scrape_historical_options())
