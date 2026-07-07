"""LiveFeedManager — picks the best available broker WebSocket feed and
routes its ticks into the shared `tick_engine`.

Selection priority on startup / when re-checking:
  1. **Zerodha Kite**  — when any user has a connected Kite session
     (live access_token, mock_mode=false). Most accurate Indian retail
     feed; covers all Nifty 50.
  2. **Upstox**        — when any user has a non-mock Upstox connection
     with an access_token.
  3. **Angel One**     — when any user has a non-mock Angel SmartAPI
     connection.
  4. **None**          — the synthetic tick generator owns every symbol.

The manager is single-feed at any moment (no concurrent live streams)
to keep the architecture simple. A future iteration could shard symbols
across brokers, but at Nifty 50 size one broker is plenty.

The manager rechecks every `RECHECK_SECONDS` so toggling a broker
connection on / off in the UI takes effect within a minute.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Optional

from db import db
from services.crypto import decrypt_str
from services.feeds.base import LiveFeed
from services.instrument_map import (
    angel_token_map, kite_token_map, upstox_instrument_map,
)
from services.market_data import tick_engine

logger = logging.getLogger("live-feed-manager")

RECHECK_SECONDS = 30
LOCAL_ONLY = os.environ.get("LOCAL_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}


class LiveFeedManager:
    def __init__(self) -> None:
        self._active: Optional[LiveFeed] = None
        self._active_broker: Optional[str] = None
        self._active_user_id: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.last_recheck_at: Optional[str] = None

    def status(self) -> dict:
        return {
            "running": self.running,
            "source": tick_engine.live_source or "synthetic",
            "active_broker": self._active_broker,
            "active_user_id": self._active_user_id,
            "live_symbol_count": len(tick_engine.live_symbols),
            "feed": self._active.status() if self._active else None,
        }

    # ---------------------------------------------------------- selection
    async def _pick_connection(self) -> Optional[dict]:
        """Find the best live broker connection in the DB."""
        if LOCAL_ONLY:
            return None
        # Priority order (breeze added)
        for broker in ("zerodha", "upstox", "angel", "breeze"):
            # We want to pull live data even if mock_mode is True!
            doc = await db.broker_connections.find_one({
                "broker": broker,
                "connected": True,
            })
            if doc and (doc.get("access_token") or doc.get("credentials")):
                return {"broker": broker, **doc}
        return None

    async def _build_feed(self, conn: dict) -> Optional[LiveFeed]:
        broker = conn["broker"]
        creds = conn.get("credentials") or {}

        def _on_tick(symbol: str, ltp: float, volume_delta: int, _raw: dict) -> None:
            tick_engine.push_live_tick(symbol, ltp, volume_delta)

        try:
            if broker == "zerodha":
                from services.feeds.kite_feed import KiteFeed
                api_key = decrypt_str(creds.get("api_key") or conn.get("api_key", ""))
                access_token = decrypt_str(conn["access_token"])
                if not (api_key and access_token):
                    return None
                return KiteFeed(
                    api_key=api_key, access_token=access_token,
                    symbol_map=kite_token_map(), on_tick=_on_tick,
                )
            if broker == "upstox":
                from services.feeds.upstox_feed import UpstoxFeed
                access_token = decrypt_str(conn["access_token"])
                if not access_token:
                    return None
                return UpstoxFeed(
                    access_token=access_token,
                    symbol_map=upstox_instrument_map(), on_tick=_on_tick,
                )
            if broker == "angel":
                from services.feeds.angel_feed import AngelFeed
                # Angel needs auth_token + feed_token (set after login() flow)
                auth_token = decrypt_str(creds.get("auth_token", ""))
                feed_token = decrypt_str(creds.get("feed_token", ""))
                api_key = decrypt_str(creds.get("api_key", ""))
                client_code = decrypt_str(creds.get("client_code", ""))
                if not (auth_token and feed_token and api_key and client_code):
                    return None
                return AngelFeed(
                    auth_token=auth_token, api_key=api_key,
                    client_code=client_code, feed_token=feed_token,
                    symbol_map=angel_token_map(), on_tick=_on_tick,
                )
            if broker == "breeze":
                from services.feeds.breeze_feed import BreezeFeed
                from services.instrument_map import breeze_token_map
                api_key = decrypt_str(creds.get("api_key", ""))
                secret_key = decrypt_str(creds.get("api_secret", ""))
                session_token = decrypt_str(creds.get("session_token", ""))
                if not (api_key and secret_key and session_token):
                    return None
                return BreezeFeed(
                    api_key=api_key, secret_key=secret_key, session_token=session_token,
                    symbol_map=breeze_token_map(), on_tick=_on_tick,
                )
        except Exception as e:
            logger.exception("Failed to build %s feed: %s", broker, e)
        return None

    # ---------------------------------------------------------- lifecycle
    async def _stop_active(self) -> None:
        if self._active:
            try:
                await self._active.stop()
            except Exception as e:
                logger.debug("feed stop error: %s", e)
        self._active = None
        self._active_broker = None
        self._active_user_id = None
        tick_engine.live_source = None

    async def _recheck(self) -> None:
        conn = await self._pick_connection()
        if not conn:
            if self._active:
                logger.info("No live broker connections left — reverting to synthetic")
                await self._stop_active()
            return
        # already running the right feed for the right user?
        if (self._active and self._active_broker == conn["broker"]
                and self._active_user_id == conn.get("user_id")):
            return
        # switch
        await self._stop_active()
        feed = await self._build_feed(conn)
        if not feed:
            return
        await feed.start()
        self._active = feed
        self._active_broker = conn["broker"]
        self._active_user_id = conn.get("user_id")
        tick_engine.live_source = conn["broker"]
        logger.info("LiveFeedManager: started %s feed for user=%s",
                    conn["broker"], conn.get("user_id"))

    async def _loop(self) -> None:
        self.running = True
        while self.running:
            try:
                await self._recheck()
            except Exception as e:
                logger.exception("recheck failed: %s", e)
            self.last_recheck_at = asyncio.get_event_loop().time().__repr__()
            await asyncio.sleep(RECHECK_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
        # best-effort stop of active feed
        if self._active:
            try:
                asyncio.create_task(self._active.stop())
            except Exception as e:
                logger.debug("feed stop on shutdown: %s", e)


live_feed_manager = LiveFeedManager()
