"""In-memory market data engine — synthetic + live broker tick fusion.

The TickEngine maintains the canonical "current price + recent history"
state for every Nifty 50 symbol. Two sources can feed it:

  * **Synthetic** — random-walk tick generator that fires every
    `TICK_INTERVAL` seconds for every symbol. Used in dev mode and as a
    fallback when no live broker WebSocket is connected.
  * **Live** — broker WebSocket adapters (see `services.feeds.*`) push
    real ticks in via `push_live_tick(symbol, ltp, volume_delta)`. The
    synthetic loop will *skip* any symbol that's been freshly updated
    by the live feed within `LIVE_FRESH_SECONDS` so the two sources
    never collide.
"""
from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Set

from constants import NIFTY_50, INDICES, SEED_PRICES, ALL_SYMBOLS

TICK_INTERVAL = 1.0  # seconds — synthetic tick cadence
HISTORY_LEN = 600    # keep last 10min of 1s ticks per symbol
LIVE_FRESH_SECONDS = 60.0  # if a symbol has had a live tick within this window,
                          # the synthetic loop won't overwrite it.


class TickEngine:
    def __init__(self) -> None:
        self.prices: Dict[str, float] = dict(SEED_PRICES)
        self.history: Dict[str, Deque[dict]] = {
            s: deque(maxlen=HISTORY_LEN) for s in ALL_SYMBOLS
        }
        self.volume_cum: Dict[str, int] = {s: 0 for s in ALL_SYMBOLS}
        self.last_volume_delta: Dict[str, int] = {s: 0 for s in ALL_SYMBOLS}
        self.change_pcts: Dict[str, float] = {s: 0.0 for s in ALL_SYMBOLS}
        self.oi_cache: Dict[str, int] = {}
        self.poi_cache: Dict[str, int] = {}
        self.prev_close_cache: Dict[str, float] = {}
        # tracks the most-recent live-feed timestamp per symbol
        self._last_live_ts: Dict[str, float] = {}
        self._last_nse_ts: Dict[str, float] = {}
        # currently-active live feed source name (zerodha/upstox/angel/None)
        self.live_source: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._listeners: List[asyncio.Queue] = []
        self.running = False

    # ------------------------------------------------------------------ live
    @property
    def live_symbols(self) -> Set[str]:
        now = time.monotonic()
        return {s for s, t in self._last_live_ts.items()
                if now - t < LIVE_FRESH_SECONDS}

    @property
    def nse_symbols(self) -> Set[str]:
        now = time.monotonic()
        return {s for s, t in self._last_nse_ts.items()
                if now - t < 10.0}

    def push_live_tick(self, symbol: str, ltp: float, volume_delta: int, raw: dict = None) -> None:
        """Inject a tick from a broker WebSocket adapter."""
        if symbol not in self.history:
            self.history[symbol] = deque(maxlen=HISTORY_LEN)
            self.prices[symbol] = float(ltp)
            self.volume_cum[symbol] = 0
            self.last_volume_delta[symbol] = 0
            self.change_pcts[symbol] = 0.0
        ts_iso = datetime.now(timezone.utc).isoformat()
        self.prices[symbol] = float(ltp)
        
        if raw:
            if "change" in raw and isinstance(raw["change"], (int, float)):
                # If the broker provides raw percentage change directly
                self.change_pcts[symbol] = float(raw["change"])
            else:
                # Try to extract previous close from raw payload to compute real percentage change
                # (DO NOT fallback to 'pc' here blindly, as 'pc' means % Change in some brokers)
                prev_close = raw.get("close_price") or raw.get("close") or raw.get("ohlc", {}).get("close")
                if not prev_close and symbol in self.prev_close_cache:
                    prev_close = self.prev_close_cache[symbol]
                
                if prev_close and float(prev_close) > 0:
                    self.change_pcts[symbol] = (float(ltp) - float(prev_close)) / float(prev_close) * 100.0
                    
            if "oi" in raw:
                try:
                    self.oi_cache[symbol] = int(raw["oi"])
                except (ValueError, TypeError):
                    pass
            if "poi" in raw:
                try:
                    self.poi_cache[symbol] = int(raw["poi"])
                except (ValueError, TypeError):
                    pass
                    
        if volume_delta > 0:
            self.volume_cum[symbol] += int(volume_delta)
            self.last_volume_delta[symbol] = int(volume_delta)
        rec = {
            "ts": ts_iso, "symbol": symbol,
            "ltp": round(float(ltp), 2),
            "volume": int(volume_delta or 0),
            "cum_volume": self.volume_cum[symbol],
            "source": "live",
        }
        self.history[symbol].append(rec)
        self._last_live_ts[symbol] = time.monotonic()
        # fan out to subscribers as a single-symbol batch
        for q in list(self._listeners):
            try:
                q.put_nowait([rec])
            except asyncio.QueueFull:
                pass

    # ------------------------------------------------------------------ read
    def snapshot(self) -> List[dict]:
        ts = datetime.now(timezone.utc).isoformat()
        live = self.live_symbols
        out = []
        for s in ALL_SYMBOLS:
            last = self.prices[s]
            change_pct = self.change_pcts.get(s, 0.0)
            out.append({
                "symbol": s,
                "ltp": round(last, 2),
                "change_pct": round(change_pct, 3),
                "volume": self.volume_cum[s],
                "ts": ts,
                "live": s in live,
            })
        return out

    def get_history(self, symbol: str) -> List[dict]:
        return list(self.history.get(symbol, []))

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    # ------------------------------------------------------------------ synth
    async def _tick_loop(self) -> None:
        self.running = True
        import aiohttp
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': '*/*',
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # Get initial cookies
            try:
                await session.get('https://www.nseindia.com', timeout=5)
            except Exception:
                pass
                
            last_fetch_time = 0
            nse_data_cache = {}

            while self.running:
                now = time.monotonic()
                ts_iso = datetime.now(timezone.utc).isoformat()
                
                live = {s for s, t in self._last_live_ts.items() if now - t < LIVE_FRESH_SECONDS}
                missing_symbols = [s for s in ALL_SYMBOLS if s not in live]
                
                batch = []
                
                # If we have missing symbols, fetch real data from NSE every 5 seconds
                if missing_symbols and now - last_fetch_time > 5.0:
                    last_fetch_time = now
                    try:
                        async with session.get('https://www.nseindia.com/api/allIndices', timeout=5) as r:
                            if r.status == 200:
                                data = await r.json()
                                for d in data.get('data', []):
                                    idx_name = d.get('index', '').upper()
                                    if 'NEXT 50' in idx_name:
                                        nse_data_cache['NIFTYNXT50'] = d['last']
                                    elif idx_name == 'NIFTY 50':
                                        nse_data_cache['NIFTY'] = d['last']
                                    elif idx_name == 'NIFTY BANK':
                                        nse_data_cache['BANKNIFTY'] = d['last']
                    except Exception as e:
                        pass
                
                for s in missing_symbols:
                    # Try to use real NSE data if we have it
                    if s in nse_data_cache and nse_data_cache[s] > 0:
                        self.prices[s] = float(nse_data_cache[s])
                        self._last_nse_ts[s] = now
                    
                    rec = {
                        "ts": ts_iso,
                        "symbol": s,
                        "ltp": round(self.prices[s], 2),
                        "volume": 0,
                        "cum_volume": self.volume_cum[s],
                        "source": "nse-fallback",
                    }
                    self.history[s].append(rec)
                    batch.append(rec)
                    
                if batch:
                    for q in list(self._listeners):
                        try:
                            q.put_nowait(batch)
                        except asyncio.QueueFull:
                            pass
                            
                await asyncio.sleep(TICK_INTERVAL)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._tick_loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()


tick_engine = TickEngine()
