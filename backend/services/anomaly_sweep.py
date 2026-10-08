"""Anomaly-detection background sweep — runs Claude over recent tick
windows for every Nifty 50 symbol, posting Notification rows whenever a
high-severity anomaly is detected. Throttled so we don't burn the LLM
budget: scans 5 symbols/cycle, every `SWEEP_INTERVAL` seconds.

The sweeper only writes notifications for the most-recently-active user
(any user with broker connections); on a fresh install with only the
demo trader, notifications go to that user.
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, insert, delete
from db import AsyncSessionLocal
from constants import ALL_SYMBOLS
from models import Notification, BrokerConnection, User
from services.ai_engine import analyse_window
from services.market_data import tick_engine

logger = logging.getLogger("anomaly-sweep")
SWEEP_INTERVAL = 60        # seconds between sweep cycles
SYMBOLS_PER_CYCLE = 3      # how many symbols to scan per cycle (budget control)
MIN_BARS_REQUIRED = 30     # min ticks before we bother asking the LLM
COOLDOWN_PER_SYMBOL = 600  # don't re-alert the same symbol within 10min


class AnomalySweeper:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.last_run_at: Optional[str] = None
        self.detections: int = 0
        self._symbol_cooldown: dict[str, float] = {}

    def stats(self) -> dict:
        return {
            "running": self.running,
            "last_run_at": self.last_run_at,
            "detections_total": self.detections,
            "interval_seconds": SWEEP_INTERVAL,
            "symbols_per_cycle": SYMBOLS_PER_CYCLE,
        }

    async def _target_user_id(self, session) -> Optional[str]:
        """Notify any user that has at least one broker connection; falls back
        to the first registered user."""
        doc = (await session.execute(select(BrokerConnection).limit(1))).scalar_one_or_none()
        if doc and doc.user_id:
            return doc.user_id
        u = (await session.execute(select(User).limit(1))).scalar_one_or_none()
        if u:
            return str(u.id)
        return None

    async def _sweep_cycle(self) -> None:
        async with AsyncSessionLocal() as session:
            user_id = await self._target_user_id(session)
            if not user_id:
                return
            loop_now = asyncio.get_event_loop().time()
            candidates = [s for s in ALL_SYMBOLS
                          if loop_now - self._symbol_cooldown.get(s, 0) > COOLDOWN_PER_SYMBOL]
            if not candidates:
                return
            random.shuffle(candidates)
            for sym in candidates[:SYMBOLS_PER_CYCLE]:
                window = tick_engine.get_history(sym)
                if len(window) < MIN_BARS_REQUIRED:
                    continue
                # Synthesize 5s OHLCV-ish bars from the 1s ticks (cheap)
                bars = []
                chunk_size = 5
                for i in range(0, len(window), chunk_size):
                    seg = window[i:i+chunk_size]
                    if not seg:
                        continue
                    closes = [b["ltp"] for b in seg]
                    bars.append({
                        "close": closes[-1],
                        "volume": sum(b["volume"] for b in seg),
                    })
                try:
                    result = await analyse_window(f"anomaly:{sym}", sym, bars)
                except Exception as e:
                    logger.exception("analyse_window failed for %s: %s", sym, e)
                    continue
                self._symbol_cooldown[sym] = loop_now
                if not result.get("anomaly"):
                    continue
                severity = result.get("severity", "low")
                if severity == "low":
                    continue
                self.detections += 1
                notif = Notification(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    kind="system",
                    title=f"⚡ Anomaly · {sym}",
                    message=f"{result.get('reason', 'unusual move')} (severity: {severity})",
                    severity="warning" if severity == "medium" else "danger",
                    created_at=datetime.utcnow()
                )
                session.add(notif)
                await session.commit()

    async def _loop(self) -> None:
        self.running = True
        while self.running:
            try:
                await self._sweep_cycle()
            except Exception as e:
                logger.exception("anomaly sweep error: %s", e)
            self.last_run_at = datetime.now(timezone.utc).isoformat()
            await asyncio.sleep(SWEEP_INTERVAL)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()


anomaly_sweeper = AnomalySweeper()
