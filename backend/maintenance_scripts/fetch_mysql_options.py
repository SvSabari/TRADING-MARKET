import asyncio
import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import AsyncSessionLocal
from models import BrokerConnection, OptionCandle
from services.brokers.aliceblue_client import get_user_aliceblue_client
from aliceblue_chain import build_aliceblue_chain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("options-fetcher")

async def fetch_options_history():
    logger.info("Starting Options Historical Fetcher for MySQL...")
    
    async with AsyncSessionLocal() as session:
        # 1. Get AliceBlue client
        stmt = select(BrokerConnection).where(
            BrokerConnection.broker == "aliceblue", 
            BrokerConnection.connected == True
        )
        res = await session.execute(stmt)
        conn = res.scalar_one_or_none()
        
        if not conn:
            logger.error("No connected AliceBlue user found in MySQL.")
            return
            
        alice = await get_user_aliceblue_client(session, conn.user_id)
        if not alice:
            logger.error("Failed to authenticate AliceBlue client.")
            return
            
        logger.info(f"AliceBlue Authenticated! Fetching CE/PE historical data...")
        
        symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=7) # Fetch last 7 days of 5-min candles
        
        for symbol in symbols:
            logger.info(f"Building chain for {symbol}...")
            try:
                chain_data = await build_aliceblue_chain(alice, symbol=symbol)
                if not chain_data or "rows" not in chain_data:
                    logger.warning(f"No chain data for {symbol}")
                    continue
                    
                new_candles = []
                expiry = chain_data.get("expiry", "")
                
                for row in chain_data["rows"]:
                    strike = float(row["strike"])
                    
                    # CE
                    if row.get("ce_token"):
                        token = row["ce_token"]
                        if "|" in token:
                            token = token.split("|")[1] # AliceBlue client needs just the token usually, or NFO|... wait, let's keep it as is, AliceBlue get_historical splits it.
                            
                        try:
                            hist = alice.get_historical(row["ce_token"], from_date, to_date, "5")
                            if isinstance(hist, list):
                                for c in hist:
                                    ts = datetime.datetime.fromisoformat(c["datetime"])
                                    new_candles.append(OptionCandle(
                                        symbol=symbol,
                                        strike=strike,
                                        opt_type="CE",
                                        expiry=expiry,
                                        ts=ts,
                                        ltp=float(c["close"])
                                    ))
                        except Exception as e:
                            logger.error(f"Error CE {strike}: {e}")
                            
                    # PE
                    if row.get("pe_token"):
                        token = row["pe_token"]
                        try:
                            hist = alice.get_historical(row["pe_token"], from_date, to_date, "5")
                            if isinstance(hist, list):
                                for c in hist:
                                    ts = datetime.datetime.fromisoformat(c["datetime"])
                                    new_candles.append(OptionCandle(
                                        symbol=symbol,
                                        strike=strike,
                                        opt_type="PE",
                                        expiry=expiry,
                                        ts=ts,
                                        ltp=float(c["close"])
                                    ))
                        except Exception as e:
                            logger.error(f"Error PE {strike}: {e}")
                
                if new_candles:
                    logger.info(f"Saving {len(new_candles)} historical candles for {symbol} to MySQL...")
                    session.add_all(new_candles)
                    await session.commit()
                else:
                    logger.warning(f"No historical candles found for {symbol}")
                    
            except Exception as e:
                logger.error(f"Failed processing {symbol}: {e}")
                
    logger.info("Done fetching CE/PE historical data for backtesting!")

if __name__ == "__main__":
    asyncio.run(fetch_options_history())
