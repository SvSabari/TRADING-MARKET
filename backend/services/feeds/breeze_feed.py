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

        import json, os
        dump_file = "d:/TRADING-TERMINAL-main/backend/breeze_tick_dump.txt"
        if not hasattr(self, "_dumped_ticks"):
            self._dumped_ticks = 0
        if self._dumped_ticks < 5:
            try:
                with open(dump_file, "a") as f:
                    f.write(json.dumps(ticks) + "\n")
                self._dumped_ticks += 1
            except Exception:
                pass

        to_emit = []
        if isinstance(ticks, list):
            for t in ticks:
                parsed = self._parse_tick(t)
                if parsed: to_emit.append(parsed)
        elif isinstance(ticks, dict):
            parsed = self._parse_tick(ticks)
            if parsed: to_emit.append(parsed)
            
        if to_emit and self._loop:
            self._loop.call_soon_threadsafe(self._emit_many, to_emit)

    def _parse_tick(self, t: dict) -> tuple | None:
        stock_code = t.get("stock_code") or t.get("symbol")
        if not stock_code:
            return None
            
        sym = getattr(self, "_reverse_map", {}).get(stock_code) or self.symbol_map.get(stock_code)
        if not sym:
            return None
            
        ltp = float(t.get("last") or t.get("ltp") or t.get("close") or 0)
        
        cum_vol = int(t.get("totalQtyTraded") or t.get("volume") or 0)
        prev = self._last_cum_volume.get(sym, cum_vol)
        delta = max(0, cum_vol - prev)
        self._last_cum_volume[sym] = cum_vol
        
        return (sym, ltp, delta, t)

    def _emit_many(self, batch: list):
        for args in batch:
            self._emit(*args)

    def _do_subscribe_all(self):
        # WORKAROUND for ICICI SDK bug: get_stock_token_value expects self.interval to exist
        self._breeze.interval = ""
        for breeze_sym, std_sym in list(self.symbol_map.items()):
            if "|" in breeze_sym:
                continue

            is_option = "!" in breeze_sym
            exchange = "BSE" if breeze_sym == "BSESEN" else "NSE"
            if is_option:
                exchange = "NFO"
                
            product = "options" if is_option else "cash"

            if not is_option:
                try:
                    exch_token, _ = self._breeze.get_stock_token_value(
                        exchange_code=exchange, stock_code=breeze_sym, product_type=product,
                        get_exchange_quotes=True, get_market_depth=False
                    )
                    if exch_token:
                        self._reverse_map[exch_token] = std_sym
                except Exception:
                    pass
            else:
                self._reverse_map[breeze_sym] = std_sym

            kwargs = {
                "exchange_code": exchange,
                "product_type": product,
                "get_exchange_quotes": True,
                "get_market_depth": False
            }
            if is_option:
                kwargs["stock_token"] = breeze_sym
                # For options, ICICI SDK subscribe_feeds requires stock_code to be something, even 'NIFTY', or it can just use stock_token
                # But to be safe we pass stock_token
            else:
                kwargs["stock_code"] = breeze_sym

            try:
                self._breeze.subscribe_feeds(**kwargs)
            except Exception as e:
                logger.debug("breeze sub error: %s", e)

    async def connect(self) -> None:
        try:
            from breeze_connect import BreezeConnect
            import logging
            logging.getLogger("APILogger").propagate = False
            logging.getLogger("WebsocketLogger").propagate = False
        except ImportError as e:
            self.last_error = f"breeze_connect is not installed: {e}"
            logger.warning(self.last_error)
            return

        self._loop = asyncio.get_running_loop()
        self._breeze = BreezeConnect(api_key=self._api_key)
        self._reverse_map = {}
        
        try:
            await asyncio.to_thread(
                self._breeze.generate_session,
                api_secret=self._secret_key,
                session_token=self._session_token
            )
        except Exception as e:
            self.last_error = f"Failed to generate breeze session: {e}"
            logger.warning(self.last_error)
            return
            
        # Register the callback
        self._breeze.on_ticks = self._on_ticks
        
        try:
            # Connect the websocket (starts its own thread usually)
            await asyncio.to_thread(self._breeze.ws_connect)
            self.connected = True
            logger.info("Breeze websocket connected, beginning subscriptions...")
            
            # Subscribe to all tokens in a single background thread to avoid spamming threadpool
            await asyncio.to_thread(self._do_subscribe_all)
            
            logger.info("Breeze subscriptions complete. Waiting for stop event.")
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
