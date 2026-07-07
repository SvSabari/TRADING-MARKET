"""Common interface for live-market-data WebSocket adapters.

Each broker has its own SDK + protocol — Kite uses `KiteTicker`, Upstox
uses MarketDataStreamerV3 (protobuf), Angel One uses `SmartWebSocketV2`
(JSON over websockets). The `LiveFeed` interface hides those details so
the `LiveFeedManager` and `TickEngine` only talk to a uniform API.

Adapters MUST:
  * Be cheap to construct (no network I/O in __init__).
  * Run their network loop inside `connect()` (async — uses asyncio).
  * Call `self._emit(symbol, ltp, volume_delta)` for every tick.
  * Set `self.connected = True/False` and `self.last_error` for status.
  * Disconnect cleanly on `stop()`.

Symbol normalisation — adapters MUST map broker-native instrument
tokens / IDs back to the cash-segment ticker used internally
(e.g. RELIANCE, HDFCBANK). The `symbol_map` passed into the constructor
is the broker-instrument-token → ticker mapping.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional

logger = logging.getLogger("live-feed")

# Callback signature: (symbol, ltp, volume_delta, raw_payload)
TickCallback = Callable[[str, float, int, dict], None]


class LiveFeed(ABC):
    """Abstract base for broker WebSocket feed adapters."""

    name: str = "abstract"

    def __init__(self, *, symbol_map: Dict[int | str, str], on_tick: TickCallback) -> None:
        self.symbol_map = symbol_map
        self.on_tick = on_tick
        self.connected: bool = False
        self.last_error: Optional[str] = None
        self.tick_count: int = 0
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def _emit(self, symbol: str, ltp: float, volume_delta: int, raw: dict | None = None) -> None:
        try:
            self.on_tick(symbol, float(ltp), int(volume_delta or 0), raw or {})
            self.tick_count += 1
        except Exception as e:
            logger.exception("on_tick handler failed: %s", e)

    @abstractmethod
    async def connect(self) -> None:
        """Open the WebSocket and run until `stop()` is called."""

    async def start(self) -> None:
        """Spawn the connect loop as a background task."""
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._safe_loop())

    async def _safe_loop(self) -> None:
        try:
            await self.connect()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.last_error = str(e)
            logger.exception("%s feed crashed: %s", self.name, e)
        finally:
            self.connected = False

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.connected = False

    def status(self) -> dict:
        return {
            "name": self.name,
            "connected": self.connected,
            "tick_count": self.tick_count,
            "last_error": self.last_error,
            "subscribed_symbols": len(self.symbol_map),
        }
