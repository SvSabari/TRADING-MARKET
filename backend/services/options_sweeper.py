import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from constants import ALL_SYMBOLS
from db import db

logger = logging.getLogger("options-sweeper")

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
        # Find the user designated for the active data feed
        doc = await db.broker_connections.find_one({"is_data_feed": True, "connected": True})
        if doc and doc.get("user_id"):
            return doc["user_id"], doc.get("broker")
        return None, None

    async def _sweep_loop(self):
        logger.info("OptionSweeper started.")
        while self.running:
            try:
                user_id, broker = await self.get_any_active_user()
                if not user_id:
                    await asyncio.sleep(10)
                    continue
                    
                if broker == "aliceblue":
                    # AliceBlue overwrites subscriptions and has a ~250 symbol limit.
                    # Sweeping 56 chains (2100+ symbols) will break it.
                    # Disable background sweeping for AliceBlue so the UI gets full control.
                    await asyncio.sleep(5)
                    continue
                    
                if broker == "breeze":
                    # Breeze has a strict 1 call/minute rate limit per endpoint for options.
                    # Background sweeping across 50+ symbols will instantly burn the quota 
                    # and break the UI. Disable sweeping for Breeze.
                    await asyncio.sleep(5)
                    continue
                
                from services.options_analytics import build_option_chain
                for symbol in ALL_SYMBOLS:
                    if not self.running: break
                    try:
                        # 0.2 sec pause between requests to populate cache incredibly fast
                        await asyncio.sleep(0.2)
                        chain = await build_option_chain(db=db, user_id=user_id, symbol=symbol)
                        if chain and chain.get("rows"):
                            self.cache[symbol] = chain
                            self.last_update[symbol] = datetime.now(timezone.utc).timestamp()
                    except Exception as e:
                        logger.debug(f"OptionSweeper error for {symbol}: {e}")
            except Exception as e:
                logger.error(f"OptionSweeper critical error: {e}")
                await asyncio.sleep(5)

options_sweeper = OptionSweeper()
