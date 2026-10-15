import asyncio
import logging
import os
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from constants import ALL_SYMBOLS
from db import AsyncSessionLocal
from models import BrokerConnection

logger = logging.getLogger("options-sweeper")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "options_history")
os.makedirs(DATA_DIR, exist_ok=True)

class OptionSweeper:
    def __init__(self):
        self.running = False
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.last_update: Dict[str, float] = {}

    def start(self):
        if self.running: return
        self.running = True
        asyncio.create_task(self._sweep_loop())

    def stop(self):
        self.running = False

    async def get_any_active_user(self):
        async with AsyncSessionLocal() as session:
            doc = (await session.execute(
                select(BrokerConnection).where(BrokerConnection.is_data_feed == True, BrokerConnection.connected == True).limit(1)
            )).scalar_one_or_none()
            if doc and doc.user_id:
                return doc.user_id, doc.broker
            return None, None
            
    def _save_to_parquet(self, symbol: str, chain: dict):
        if not chain or not chain.get("rows"): return
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            file_path = os.path.join(DATA_DIR, f"{symbol}_options_{today_str}.parquet")
            
            df = pd.DataFrame(chain["rows"])
            df["symbol"] = symbol
            df["spot"] = chain.get("spot", 0.0)

            df["atm"] = chain.get("atm", 0.0)
            df['expiry'] = chain.get('expiry', '26OCT')
            df["timestamp"] = pd.Timestamp.utcnow()
            
            if os.path.exists(file_path):
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df.to_parquet(file_path, engine="pyarrow", index=False)
            else:
                df.to_parquet(file_path, engine="pyarrow", index=False)
                
        except Exception as e:
            logger.error(f"Failed to save parquet for {symbol}: {e}")

    async def _sweep_loop(self):
        logger.info("OptionSweeper started. Parquet data capture enabled.")
        while self.running:
            try:
                from datetime import datetime, timezone, timedelta
                ts = datetime.now(timezone.utc)
                ist_time = ts + timedelta(hours=5, minutes=30)
                
                is_market_open = True
                is_after_hours = False
                if ist_time.weekday() >= 5:
                    is_market_open = False
                else:
                    market_start = ist_time.replace(hour=9, minute=15, second=0, microsecond=0)
                    market_end = ist_time.replace(hour=15, minute=30, second=0, microsecond=0)
                    if ist_time > market_end:
                        is_market_open = False
                        is_after_hours = True
                    elif ist_time < market_start:
                        is_market_open = False
                        
                if is_after_hours:
                    logger.info("Market closed for the day. Auto-stopping OptionsSweeper.")
                    self.running = False
                    break
                    
                if not is_market_open:
                    await asyncio.sleep(10)
                    continue

                user_id, broker = await self.get_any_active_user()
                if not user_id:
                    await asyncio.sleep(10)
                    continue
                  
                from services.options_analytics import build_option_chain
                for symbol in ALL_SYMBOLS:
                    if not self.running: break
                    try:
                        # Add a tiny sleep to avoid CPU lockup and API rate limits
                        await asyncio.sleep(1.0)
                        
                        async with AsyncSessionLocal() as session:
                            chain = await build_option_chain(db=session, user_id=user_id, symbol=symbol)
                            
                        if chain and chain.get("rows"):
                            self.cache[symbol] = chain
                            self.last_update[symbol] = datetime.now(timezone.utc).timestamp()
                            
                            # Dump the full chain into highly-compressed Parquet!
                            # To prevent massive CPU blocking in the asyncio loop, we offload it
                            await asyncio.to_thread(self._save_to_parquet, symbol, chain)
                            
                    except Exception as e:
                        logger.debug(f"OptionSweeper error for {symbol}: {e}")
                        
            except Exception as e:
                logger.error(f"OptionSweeper critical error: {e}")
                await asyncio.sleep(5)
                
options_sweeper = OptionSweeper()
