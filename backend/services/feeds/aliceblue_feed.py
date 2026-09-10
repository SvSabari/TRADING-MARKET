import asyncio
import logging
from typing import Dict, Callable
from pya3 import Aliceblue
from services.instrument_map import ALICEBLUE_TOKENS
from services.feeds.base import LiveFeed

logger = logging.getLogger(__name__)

class AliceblueFeed(LiveFeed):
    name = "aliceblue"

    def __init__(self, client_code: str, api_key: str, session_id: str, symbol_map: Dict[str, str], on_tick: Callable) -> None:
        super().__init__(symbol_map=symbol_map, on_tick=on_tick)
        self.client_code = client_code
        self.api_key = api_key
        self.session_id = session_id
        self._alice = None
        self._loop = None
        self.connected = False
        self._last_cum_volume: Dict[str, int] = {}
        
    def _on_message(self, message):
        try:
            self._process_message(message)
        except Exception as e:
            logger.error(f"AliceBlue _on_message crashed: {e}. Payload: {message}")

    def _process_message(self, message):
        if isinstance(message, str):
            import json
            try:
                message = json.loads(message)
            except Exception:
                return
                
        if isinstance(message, list):
            for item in message:
                self._process_message(item)
            try:
                # Alice Blue format: {'tk': '22', 'ts': '...', 'lp': 100.5, ...}
                tk = message[0].get("tk") or message[0].get("Token")
                if not tk: return
                tk_str = str(tk)
                
                # NFO tokens are typically 5-digit numbers like 67994
                if len(tk_str) > 4 and tk_str.isdigit():
                    logger.info("NFO tick received: %s, data: %s", tk_str, message[0])
            except:
                pass
            return
            
        if not isinstance(message, dict):
            return
            
        tok = str(message.get("tk") or message.get("Token") or "")
        if not tok:
            return
            
        sym = self.symbol_map.get(tok)
        if not sym:
            sym = self.symbol_map.get(f"NFO|{tok}") or self.symbol_map.get(f"BFO|{tok}") or self.symbol_map.get(f"NSE|{tok}") or self.symbol_map.get(f"BSE|{tok}")
        if not sym:
            # with open("unmapped_tokens.txt", "a") as f:
            #     f.write(f"Unmapped token: {tok} from message: {message}\n")
            return
            
        lp_val = message.get("lp") or message.get("LTP") or 0.0
        try:
            ltp = float(lp_val)
        except (ValueError, TypeError):
            ltp = 0.0
            
        # with open("all_ticks.txt", "a") as f:
        #     f.write(f"Tick received: sym={sym}, ltp={ltp}\n")
            
        if ltp <= 0:
            return
            
        # VERY IMPORTANT: Map 'c' (previous close) to close_price for Alice Blue Touchline feed
        if "c" in message:
            message["close_price"] = message["c"]
        
        if "pc" in message:
            try:
                message["change"] = float(message["pc"])
            except (ValueError, TypeError):
                pass
            
        if "v" in message or "Vol" in message:
            try:
                cum = int(message.get("v") or message.get("Vol") or 0)
                if cum > 0:
                    prev = self._last_cum_volume.get(tok, cum)
                    delta = max(0, cum - prev)
                    self._last_cum_volume[tok] = cum
                else:
                    delta = 0
            except (ValueError, TypeError):
                delta = 0
        else:
            delta = 0
        
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._emit, sym, ltp, delta, message)
            except RuntimeError:
                pass

    def _socket_open(self):
        self.connected = True
        self.last_error = None
        logger.info("Alice Blue WebSocket Connected.")
        # On reconnect, we must resubscribe to all tokens because Alice Blue drops them!
        if getattr(self, "symbol_map", None) and getattr(self, "_loop", None):
            import asyncio
            asyncio.run_coroutine_threadsafe(self.add_symbols([], force=True), self._loop)

    def _socket_close(self):
        self.connected = False
        logger.info("Alice Blue WebSocket Closed.")

    def _socket_error(self, error):
        self.last_error = str(error)
        logger.warning("Alice Blue WebSocket Error: %s", error)

    async def add_symbols(self, tokens: list[str], force: bool = False) -> None:
        if not self._alice or getattr(self._alice, "ws", None) is None:
            return
            
        new_tokens_added = False
        
        # User requested: Do not silently delete tokens. Remove 2500 cap.
        # Keep everything requested so we can test the true Alice Blue limit vs payload limit.
        for tok in tokens:
            if tok not in self.symbol_map:
                self.symbol_map[tok] = tok
                new_tokens_added = True
                
        if not self.symbol_map:
            return
            
        if not new_tokens_added and not force:
            return
            
        # Generate complete token list, remove duplicates
        unique_tokens = list(set(self.symbol_map.keys()))
        logger.info(f"Alice Blue total requested unique tokens to subscribe: {len(unique_tokens)}")
        
        all_scripts = []
        for tok in unique_tokens:
            if "|" in tok:
                exch, tkn = tok.split("|", 1)
                all_scripts.append(f"{exch}|{tkn}")
            else:
                from services.instrument_map import ALICEBLUE_TOKENS
                exch = "NSE"
                if tok == "1":
                    exch = "BSE"
                elif tok not in ALICEBLUE_TOKENS:
                    exch = "NFO"
                all_scripts.append(f"{exch}|{tok}")
                
        if all_scripts:
            import json
            # Split into chunks of 25 to bypass potential payload size limits (community suggestion)
            chunk_size = 25
            total_chunks = (len(all_scripts) + chunk_size - 1) // chunk_size
            logger.info(f"Alice Blue subscribing to {len(all_scripts)} instruments across {total_chunks} chunks of {chunk_size}.")
            
            self._alice.market_depth = False
            for i in range(0, len(all_scripts), chunk_size):
                chunk = all_scripts[i:i+chunk_size]
                payload = "#".join(chunk)
                data = {
                    "k": payload,
                    "t": "t"
                }
                try:
                    self._alice.ws.send(json.dumps(data))
                    logger.info(f"Alice Blue subscribe chunk {i//chunk_size + 1}/{total_chunks} sent: {len(chunk)} tokens")
                except Exception as e:
                    self.last_error = str(e)
                    logger.error("Alice Blue subscribe chunk error: %s", e)

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        
        import datetime
        import logging
        import pya3.alicebluepy
        pya3.alicebluepy.time = datetime.time
        import time as py_time
        pya3.alicebluepy.sleep = py_time.sleep
        pya3.alicebluepy.logger = logging.getLogger("pya3_websocket")

        self._alice = pya3.alicebluepy.Aliceblue(
            user_id=self.client_code,
            api_key=self.api_key,
            session_id=self.session_id,
            disable_ssl=True
        )
        
        try:
            self._alice.start_websocket(
                socket_open_callback=self._socket_open,
                socket_close_callback=self._socket_close,
                socket_error_callback=self._socket_error,
                subscription_callback=self._on_message,
                run_in_background=True
            )
            # We assume it will connect shortly
            self.connected = True
        except Exception as e:
            self.last_error = str(e)
            logger.error("AliceBlue start_websocket failed: %s", e)
            return
            
        async def delayed_subscribe():
            # Wait 2 seconds to ensure Alice Blue sends the 'ck' connection ack
            # before we start blasting subscription chunks
            await asyncio.sleep(2.0)
            tokens = list(self.symbol_map.keys())
            if tokens:
                logger.info(f"Alice Blue feed auto-subscribing to {len(tokens)} initial tokens...")
                await self.add_symbols(tokens, force=True)
                
        if self._loop:
            self._loop.create_task(delayed_subscribe())
            
        # Block until stop is called
        await self._stop_event.wait()

    def disconnect(self) -> None:
        self.connected = False
        if getattr(self, "_alice", None) and hasattr(self._alice, "ws") and self._alice.ws:
            try:
                self._alice.ws.close()
            except Exception:
                pass
        logger.info("Alice Blue feed disconnected.")
