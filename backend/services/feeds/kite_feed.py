"""Zerodha Kite WebSocket (KiteTicker) live feed adapter.

KiteTicker runs its own thread / Twisted reactor. We bridge it into the
asyncio world by using `asyncio.get_running_loop().call_soon_threadsafe`
to ship ticks back to the LiveFeedManager.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from services.feeds.base import LiveFeed

logger = logging.getLogger("kite-feed")


class KiteFeed(LiveFeed):
    name = "zerodha"

    def __init__(self, *, api_key: str, access_token: str,
                 symbol_map: Dict[int, str], on_tick) -> None:
        super().__init__(symbol_map=symbol_map, on_tick=on_tick)
        self._api_key = api_key
        self._access_token = access_token
        self._ticker: Any | None = None
        self._last_cum_volume: Dict[int, int] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _on_ticks(self, _ws, ticks):
        for t in ticks:
            tok = t.get("instrument_token")
            sym = self.symbol_map.get(tok)
            if not sym:
                continue
            ltp = t.get("last_price") or t.get("ohlc", {}).get("close") or 0
            vol_val = t.get("volume_traded") or t.get("volume") or 0
            try:
                cum = int(vol_val)
            except (ValueError, TypeError):
                cum = 0
            prev = self._last_cum_volume.get(tok, cum)
            delta = max(0, cum - prev)
            self._last_cum_volume[tok] = cum
            # call_soon_threadsafe — bridge from KiteTicker thread into asyncio
            if self._loop:
                self._loop.call_soon_threadsafe(self._emit, sym, ltp, delta, t)

    def _on_connect(self, ws, _response):
        self.connected = True
        tokens = list(self.symbol_map.keys())
        if tokens:
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
        logger.info("Kite ticker connected — subscribed to %d tokens", len(tokens))

    def _on_close(self, _ws, _code, _reason):
        self.connected = False

    def _on_error(self, _ws, _code, reason):
        self.last_error = str(reason)
        logger.warning("Kite ticker error: %s", reason)

    async def connect(self) -> None:
        try:
            from kiteconnect import KiteTicker
        except ImportError as e:
            self.last_error = f"kiteconnect is not installed: {e}"
            logger.warning(self.last_error)
            return
        self._loop = asyncio.get_running_loop()
        self._ticker = KiteTicker(self._api_key, self._access_token)
        self._ticker.on_ticks = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close = self._on_close
        self._ticker.on_error = self._on_error
        # KiteTicker.connect() starts a Twisted reactor in a thread.
        # threaded=True returns immediately, so we use it.
        self._ticker.connect(threaded=True, disable_ssl_verification=False)
        # park the coroutine until stop()
        try:
            await self._stop_event.wait()
        finally:
            if self._ticker:
                try:
                    self._ticker.close()
                except Exception as e:
                    logger.debug("ticker close error: %s", e)
