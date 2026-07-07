"""Angel One SmartAPI WebSocket v2 live feed adapter.

`SmartWebSocketV2` is a synchronous websocket client; we bridge it to
asyncio via call_soon_threadsafe. The adapter expects an authenticated
session (auth_token + feed_token + api_key + client_code) — see
`services.brokers.angel_client.AngelClient.login()`.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Dict

from services.feeds.base import LiveFeed

logger = logging.getLogger("angel-feed")

# Angel exchange-type codes for the WS subscribe payload
ANGEL_EXCHANGE_NSE_CM = 1
ANGEL_MODE_QUOTE = 2  # quote = ltp + volume; full mode is heavier


class AngelFeed(LiveFeed):
    name = "angel"

    def __init__(self, *, auth_token: str, api_key: str, client_code: str,
                 feed_token: str, symbol_map: Dict[str, str], on_tick) -> None:
        # symbol_map: token-string (e.g. "1333") -> ticker (e.g. "HDFCBANK")
        super().__init__(symbol_map=symbol_map, on_tick=on_tick)
        self._auth_token = auth_token
        self._api_key = api_key
        self._client_code = client_code
        self._feed_token = feed_token
        self._sws = None
        self._last_cum_volume: Dict[str, int] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _decode(self, msg: dict) -> None:
        # SmartWebSocketV2 emits a dict with `token` + `last_traded_price` (paise)
        tok = str(msg.get("token") or "")
        sym = self.symbol_map.get(tok)
        if not sym:
            return
        # Angel LTP arrives in *paise* — divide by 100 for INR
        ltp_paise = msg.get("last_traded_price")
        if ltp_paise is None:
            ltp_paise = msg.get("ltp") or 0
        ltp = float(ltp_paise) / 100.0
        cum = int(msg.get("volume_trade_for_the_day") or msg.get("vol") or 0)
        prev = self._last_cum_volume.get(tok, cum)
        delta = max(0, cum - prev)
        self._last_cum_volume[tok] = cum
        self._emit(sym, ltp, delta, msg)

    def _ws_thread(self) -> None:
        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2  # type: ignore
        except ImportError as e:  # pragma: no cover
            self.last_error = f"smartapi-python missing: {e}"
            return
        sws = SmartWebSocketV2(
            self._auth_token, self._api_key, self._client_code, self._feed_token
        )
        self._sws = sws

        def _on_data(_wsapp, message):
            if self._loop:
                self._loop.call_soon_threadsafe(self._decode, message)

        def _on_open(_wsapp):
            self.connected = True
            tokens = list(self.symbol_map.keys())
            sub_list = [{
                "exchangeType": ANGEL_EXCHANGE_NSE_CM,
                "tokens": tokens,
            }]
            sws.subscribe("algonid-feed", ANGEL_MODE_QUOTE, sub_list)
            logger.info("Angel SmartWS connected — subscribed %d tokens", len(tokens))

        def _on_error(_wsapp, error):
            self.last_error = str(error)
            logger.warning("Angel WS error: %s", error)

        def _on_close(_wsapp):
            self.connected = False

        sws.on_open = _on_open
        sws.on_data = _on_data
        sws.on_error = _on_error
        sws.on_close = _on_close
        try:
            sws.connect()
        except Exception as e:
            self.last_error = str(e)
            logger.exception("Angel WS connect failed: %s", e)

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        thread = threading.Thread(target=self._ws_thread, name="angel-ws", daemon=True)
        thread.start()
        try:
            await self._stop_event.wait()
        finally:
            if self._sws:
                try:
                    self._sws.close_connection()
                except Exception as e:
                    logger.debug("angel close error: %s", e)
            self.connected = False
