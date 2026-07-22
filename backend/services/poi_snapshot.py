"""Background task to snapshot Open Interest daily to act as Previous OI.

Strategy:
- Save snapshot every 5 min with current oi_cache + prices into poi_snapshots.
- On startup, load the most recent PAST snapshot (before today) as poi_cache.
- Special handling: if no BFO tokens exist in the past snapshot, also look at
  any past snapshot that has BFO tokens (for SENSEX/BANKEX support).
- Additionally, save the first tick-of-day OI as POI using a "day_start" snapshot
  so intraday CHNG OI is calculated correctly even if yesterday had no BFO data.
"""
import asyncio
import logging
from datetime import datetime, timezone

from db import db, utc_now_iso
from services.market_data import tick_engine

logger = logging.getLogger(__name__)

# Track whether we have already initialized the POI from first ticks today
_poi_initialized_today = False


async def save_snapshot():
    """Takes the current oi_cache and saves it to db.poi_snapshots for today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not tick_engine.oi_cache:
        return

    doc = {
        "date": today,
        "oi_data": dict(tick_engine.oi_cache),
        "close_data": dict(tick_engine.prices),
        "updated_at": utc_now_iso()
    }

    try:
        await db.poi_snapshots.update_one(
            {"date": today},
            {"$set": doc},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Failed to save POI snapshot: {e}")


async def initialize_poi_from_first_ticks():
    """
    Called once per day after the first live ticks arrive.
    Seeds poi_cache from the day-start OI so CHNG OI shows delta from market open.
    Only runs once per process lifetime (resets on restart).
    """
    global _poi_initialized_today
    if _poi_initialized_today:
        return
    if not tick_engine.oi_cache:
        return

    # Only seed tokens that aren't already in poi_cache (from yesterday's snapshot)
    new_tokens = {k: v for k, v in tick_engine.oi_cache.items()
                  if k not in tick_engine.poi_cache}
    if new_tokens:
        tick_engine.poi_cache.update(new_tokens)
        logger.info(f"POI initialized from first ticks: {len(new_tokens)} new tokens seeded.")
    _poi_initialized_today = True


async def load_snapshot():
    """Loads the most recent snapshot prior to today into tick_engine.poi_cache."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # Fetch the 10 most recent snapshots so we can find data for all segments
        cursor = db.poi_snapshots.find({}).sort("date", -1).limit(10)
        docs = []
        async for doc in cursor:
            docs.append(doc)

        # Separate past vs today docs
        past_docs = [d for d in docs if d.get("date", "") < today]
        today_doc = next((d for d in docs if d.get("date", "") == today), None)

        nfo_loaded = False
        bfo_loaded = False

        # Load from past snapshots — try to get NFO and BFO separately
        for doc in past_docs:
            oi_data = doc.get("oi_data", {})
            close_data = doc.get("close_data", {})

            nfo_tokens = {k: v for k, v in oi_data.items() if k.startswith("NFO")}
            bfo_tokens = {k: v for k, v in oi_data.items() if k.startswith("BFO")}

            if nfo_tokens and not nfo_loaded:
                tick_engine.poi_cache.update(nfo_tokens)
                logger.info(f"Loaded NFO POI from {doc['date']}: {len(nfo_tokens)} tokens.")
                nfo_loaded = True

            if bfo_tokens and not bfo_loaded:
                tick_engine.poi_cache.update(bfo_tokens)
                logger.info(f"Loaded BFO POI from {doc['date']}: {len(bfo_tokens)} tokens.")
                bfo_loaded = True

            if close_data:
                tick_engine.prev_close_cache.update(close_data)

            if nfo_loaded and bfo_loaded:
                break

        # If BFO still not found in any past snapshot, fall back to today's snapshot
        # (happens the first time SENSEX/BANKEX data is collected — use it as baseline)
        if not bfo_loaded and today_doc:
            oi_data = today_doc.get("oi_data", {})
            bfo_tokens = {k: v for k, v in oi_data.items() if k.startswith("BFO")}
            if bfo_tokens:
                tick_engine.poi_cache.update(bfo_tokens)
                logger.info(
                    f"No past BFO snapshot found — seeding POI from today's snapshot: "
                    f"{len(bfo_tokens)} BFO tokens."
                )

        logger.info(
            f"POI load complete. poi_cache has {len(tick_engine.poi_cache)} total tokens. "
            f"NFO loaded: {nfo_loaded}, BFO loaded: {bfo_loaded}."
        )

    except Exception as e:
        logger.error(f"Failed to load POI snapshot: {e}")


async def snapshot_loop():
    """Background loop to periodically save the snapshot and initialize POI."""
    global _poi_initialized_today
    logger.info("Starting POI snapshot loop...")
    ticks_waited = 0

    while True:
        try:
            await save_snapshot()

            # After 2 minutes of running, seed any missing poi_cache entries
            # from first ticks (handles symbols not in any past snapshot)
            if ticks_waited >= 2 and not _poi_initialized_today:
                await initialize_poi_from_first_ticks()

        except Exception as e:
            logger.error(f"Error in snapshot_loop: {e}")

        await asyncio.sleep(60)  # tick every 1 min
        ticks_waited += 1
