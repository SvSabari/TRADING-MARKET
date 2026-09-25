import asyncio
import datetime
from datetime import timezone
import logging
from db import sync_db, db
from services.brokers.aliceblue_client import get_user_aliceblue_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daily-scraper")

async def scrape_options():
    logger.info("Starting Daily Options Scraper...")
    
    # Get any valid aliceblue client (e.g. from the admin user)
    # We'll just grab the first connected AliceBlue credentials we find
    client_doc = await db.broker_connections.find_one({"broker": "aliceblue", "connected": True})
    if not client_doc:
        logger.error("No AliceBlue connected user found.")
        return
        
    alice = await get_user_aliceblue_client(db, client_doc["user_id"])
    if not alice:
        logger.error("Failed to authenticate AliceBlue.")
        return
        
    logger.info(f"Authenticated AliceBlue for user {client_doc['user_id']}")
    
    # We want ALL supported indices for backtesting
    symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "MIDCPNIFTY", "BANKEX"]
    
    today = datetime.datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    from_date = datetime.datetime.now() - datetime.timedelta(days=1)
    to_date = datetime.datetime.now()
    
    from aliceblue_chain import build_aliceblue_chain
    
    for symbol in symbols:
        logger.info(f"Building option chain to discover active strikes for {symbol}...")
        try:
            chain_data = await build_aliceblue_chain(alice, symbol=symbol)
            if not chain_data or "data" not in chain_data:
                continue
                
            docs = []
            
            for row in chain_data["data"]:
                strike = float(row["strikePrice"])
                expiry = row["expiryDate"]
                
                # Fetch CE
                if "CE" in row and row["CE"].get("token"):
                    ce_token = row["CE"]["token"]
                    try:
                        hist = alice.get_historical(ce_token, from_date, to_date, "5")
                        if isinstance(hist, list):
                            for candle in hist:
                                ts = datetime.datetime.fromisoformat(candle["datetime"])
                                docs.append({
                                    "symbol": symbol,
                                    "strike": strike,
                                    "opt_type": "CE",
                                    "expiry": expiry,
                                    "ts": ts,
                                    "ltp": float(candle["close"])
                                })
                    except Exception as e:
                        logger.error(f"Error fetching CE {strike}: {e}")
                
                # Fetch PE
                if "PE" in row and row["PE"].get("token"):
                    pe_token = row["PE"]["token"]
                    try:
                        hist = alice.get_historical(pe_token, from_date, to_date, "5")
                        if isinstance(hist, list):
                            for candle in hist:
                                ts = datetime.datetime.fromisoformat(candle["datetime"])
                                docs.append({
                                    "symbol": symbol,
                                    "strike": strike,
                                    "opt_type": "PE",
                                    "expiry": expiry,
                                    "ts": ts,
                                    "ltp": float(candle["close"])
                                })
                    except Exception as e:
                        logger.error(f"Error fetching PE {strike}: {e}")
                        
            if docs:
                logger.info(f"Saving {len(docs)} candles to option_candles for {symbol}...")
                sync_db.option_candles.insert_many(docs, ordered=False)
            
        except Exception as e:
            logger.error(f"Failed to scrape {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_options())
