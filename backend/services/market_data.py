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

from constants import NIFTY_50, SEED_PRICES

TICK_INTERVAL = 1.0  # seconds — synthetic tick cadence
HISTORY_LEN = 600    # keep last 10min of 1s ticks per symbol
LIVE_FRESH_SECONDS = 60.0  # if a symbol has had a live tick within this window,
                          # the synthetic loop won't overwrite it.


class TickEngine:
    def __init__(self) -> None:
        self.prices: Dict[str, float] = dict(SEED_PRICES)
        self.history: Dict[str, Deque[dict]] = {
            s: deque(maxlen=HISTORY_LEN) for s in NIFTY_50
        }
        self.volume_cum: Dict[str, int] = {s: 0 for s in NIFTY_50}
        self.last_volume_delta: Dict[str, int] = {s: 0 for s in NIFTY_50}
        # tracks the most-recent live-feed timestamp per symbol
        self._last_live_ts: Dict[str, float] = {}
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

    def push_live_tick(self, symbol: str, ltp: float, volume_delta: int) -> None:
        """Inject a tick from a broker WebSocket adapter."""
        if symbol not in self.history:
            return
        ts_iso = datetime.now(timezone.utc).isoformat()
        self.prices[symbol] = float(ltp)
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
        for s in NIFTY_50:
            last = self.prices[s]
            seed = SEED_PRICES[s]
            change_pct = (last - seed) / seed * 100
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
        while self.running:
            ts = datetime.now(timezone.utc)
            ts_iso = ts.isoformat()
            live = self.live_symbols
            tick_batch = []
            for s in NIFTY_50:
                if s in live:
                    # live feed owns this symbol — don't synthesize over it
                    continue
                prev = self.prices[s]
                drift = random.uniform(-0.0008, 0.0008)
                new_price = max(0.5, prev * (1 + drift))
                self.prices[s] = new_price
                vol_delta = random.randint(50, 5000)
                self.volume_cum[s] += vol_delta
                self.last_volume_delta[s] = vol_delta
                rec = {
                    "ts": ts_iso, "symbol": s,
                    "ltp": round(new_price, 2),
                    "volume": vol_delta,
                    "cum_volume": self.volume_cum[s],
                    "source": "synthetic",
                }
                self.history[s].append(rec)
                tick_batch.append(rec)
            for q in list(self._listeners):
                try:
                    q.put_nowait(tick_batch)
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
