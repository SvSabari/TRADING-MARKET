"""ICICI Breeze WebSocket live feed adapter.

Uses the breeze_connect SDK to stream live ticks and route them into the asyncio world.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict

from services.feeds.base import LiveFeed

logger = logging.getLogger("breeze-feed")


class BreezeFeed(LiveFeed):
    name = "breeze"

    def __init__(self, *, api_key: str, secret_key: str, session_token: str,
                 symbol_map: Dict[str, str], on_tick) -> None:
        super().__init__(symbol_map=symbol_map, on_tick=on_tick)
        self._api_key = api_key
        self._secret_key = secret_key
        self._session_token = session_token
        self._breeze = None
        self._loop = None
        
        # We need cumulative volume tracking to emit delta
        self._last_cum_volume: Dict[str, int] = {}

    def _on_ticks(self, ticks: dict | list):
        if not ticks:
            return
            
        # The breeze on_ticks can sometimes return a list of ticks or a single dict
        if isinstance(ticks, list):
            for t in ticks:
                self._process_single_tick(t)
        elif isinstance(ticks, dict):
            self._process_single_tick(ticks)

    def _process_single_tick(self, t: dict):
        stock_code = t.get("stock_code") or t.get("symbol")
        if not stock_code:
            return
            
        # First check reverse map (for '4.1!2885' style tokens), fallback to direct map (for 'RELIANCE')
        sym = getattr(self, "_reverse_map", {}).get(stock_code) or self.symbol_map.get(stock_code)
        if not sym:
            return
            
        ltp = float(t.get("last") or t.get("ltp") or t.get("close") or 0)
        if not ltp:
            return
            
        cum_vol = int(t.get("totalQtyTraded") or t.get("volume") or 0)
        prev = self._last_cum_volume.get(sym, cum_vol)
        delta = max(0, cum_vol - prev)
        self._last_cum_volume[sym] = cum_vol
        
        # bridge into asyncio
        if self._loop:
            self._loop.call_soon_threadsafe(self._emit, sym, ltp, delta, t)

    async def connect(self) -> None:
        try:
            from breeze_connect import BreezeConnect
        except ImportError as e:
            self.last_error = f"breeze_connect is not installed: {e}"
            logger.warning(self.last_error)
            return

        self._loop = asyncio.get_running_loop()
        self._breeze = BreezeConnect(api_key=self._api_key)
        self._reverse_map = {}
        
        try:
            self._breeze.generate_session(api_secret=self._secret_key, session_token=self._session_token)
        except Exception as e:
            self.last_error = f"Failed to generate breeze session: {e}"
            logger.warning(self.last_error)
            return
            
        # Register the callback
        self._breeze.on_ticks = self._on_ticks
        
        try:
            # Connect the websocket (starts its own thread usually)
            self._breeze.ws_connect()
            self.connected = True
            logger.info("Breeze websocket connected")
            
            # Subscribe to all tokens
            # self.symbol_map keys are ICICI proprietary symbols e.g. "RELIND"
            # values are standard tickers e.g. "RELIANCE"
            
            # WORKAROUND for ICICI SDK bug: get_stock_token_value expects self.interval to exist
            self._breeze.interval = ""
            
            for breeze_sym, std_sym in self.symbol_map.items():
                try:
                    # Get the exact token string ICICI will return for this stock
                    exch_token, _ = self._breeze.get_stock_token_value(
                        exchange_code="NSE", stock_code=breeze_sym, product_type="cash",
                        get_exchange_quotes=True, get_market_depth=False
                    )
                    if exch_token:
                        self._reverse_map[exch_token] = std_sym
                except Exception:
                    pass

                self._breeze.subscribe_feeds(
                    exchange_code="NSE",
                    stock_code=breeze_sym,
                    product_type="cash",
                    get_exchange_quotes=True,
                    get_market_depth=False
                )
            logger.info(f"Breeze ticker subscribed to {len(self.symbol_map)} tokens")
            
            # Park the coroutine until stop is requested
            await self._stop_event.wait()
            
        except Exception as e:
            self.last_error = f"Breeze WS error: {e}"
            logger.warning(self.last_error)
        finally:
            self.connected = False
            if self._breeze:
                try:
                    self._breeze.ws_disconnect()
                except Exception as e:
                    logger.debug("breeze disconnect error: %s", e)
