"""Upstox Market Data WebSocket v3 feed adapter.

Uses `upstox-python-sdk`'s `MarketDataStreamerV3` which handles protobuf
decoding internally. Each tick payload arrives as a dict with shape
`{feeds: {<instrument_key>: {ff: {marketFF: {ltpc: {ltp, ltt, ltq, cp}, vtt}}}}}`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict

from services.feeds.base import LiveFeed

logger = logging.getLogger("upstox-feed")


class UpstoxFeed(LiveFeed):
    name = "upstox"

    def __init__(self, *, access_token: str, symbol_map: Dict[str, str], on_tick) -> None:
        # symbol_map: NSE_EQ|INE040A01034 → "HDFCBANK"
        super().__init__(symbol_map=symbol_map, on_tick=on_tick)
        self._access_token = access_token
        self._streamer = None
        self._last_cum_volume: Dict[str, int] = {}

    def _on_message(self, message: dict) -> None:
        feeds = message.get("feeds") or {}
        for instr_key, payload in feeds.items():
            sym = self.symbol_map.get(instr_key)
            if not sym:
                continue
            ff = payload.get("ff") or {}
            mff = ff.get("marketFF") or ff.get("indexFF") or {}
            ltpc = mff.get("ltpc") or {}
            ltp = float(ltpc.get("ltp") or 0)
            vol_val = mff.get("vtt") or 0
            try:
                cum_vol = int(vol_val)
            except (ValueError, TypeError):
                cum_vol = 0
            prev = self._last_cum_volume.get(instr_key, cum_vol)
            delta = max(0, cum_vol - prev)
            self._last_cum_volume[instr_key] = cum_vol
            self._emit(sym, ltp, delta, payload)

    async def connect(self) -> None:
        try:
            import upstox_client  # type: ignore
            from upstox_client.feeder import MarketDataStreamerV3  # type: ignore
        except ImportError as e:  # pragma: no cover - SDK should be installed
            self.last_error = f"upstox-python-sdk missing: {e}"
            return
        cfg = upstox_client.Configuration()
        cfg.access_token = self._access_token
        instrument_keys = list(self.symbol_map.keys())
        # MarketDataStreamerV3 subscribes via instrument keys + mode
        self._streamer = MarketDataStreamerV3(
            api_client=upstox_client.ApiClient(cfg),
            instrumentKeys=instrument_keys,
            mode="ltpc",
        )
        # bridge SDK's threaded callback → asyncio
        loop = asyncio.get_running_loop()

        def _cb(msg):
            loop.call_soon_threadsafe(self._on_message, msg)

        def _open(_msg):
            self.connected = True
            logger.info("Upstox v3 streamer connected (%d keys)", len(instrument_keys))

        def _err(err):
            self.last_error = str(err)
            logger.warning("Upstox stream error: %s", err)

        self._streamer.on("message", _cb)
        self._streamer.on("open", _open)
        self._streamer.on("error", _err)
        self._streamer.connect()
        try:
            await self._stop_event.wait()
        finally:
            try:
                self._streamer.disconnect()
            except Exception as e:
                logger.debug("upstox disconnect error: %s", e)
            self.connected = False
