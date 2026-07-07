"""Per-user strategy execution scheduler.

Periodically evaluates enabled strategies and emits paper-trade orders
whose entry conditions are met. Each strategy carries its own
`interval_seconds` parameter; the scheduler ticks every second and runs
any strategy whose interval has elapsed.

Strategy evaluations are intentionally simple — the goal is to make the
"RUNNING" toggle do something visible (orders + notifications) rather
than be a perfect alpha engine.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Dict

from db import db
from models import Notification, Order, Strategy
from services.broker_router import get_broker
from services.market_data import tick_engine
from services.telegram import send_for_user

logger = logging.getLogger("strategy-scheduler")


def _signal_for_strategy(strat: Strategy) -> tuple[str | None, str | None, float]:
    """Return (symbol, side, price) if the strategy fires now, else (None, None, 0)."""
    symbols = strat.symbols or list(tick_engine.prices.keys())[:5]
    sym = random.choice(symbols)
    hist = tick_engine.get_history(sym)
    if len(hist) < 10:
        return None, None, 0.0
    prices = [r["ltp"] for r in hist[-20:]]
    last = prices[-1]
    avg = sum(prices) / len(prices)
    diff = (last - avg) / avg

    kind = strat.kind
    side = None
    # Each kind has a different trigger heuristic
    if kind == "ema_crossover":
        if diff > 0.002:
            side = "BUY"
        elif diff < -0.002:
            side = "SELL"
    elif kind == "oi_breakout":
        if diff > 0.0035:
            side = "BUY"
    elif kind == "vwap_scalping":
        if diff < -0.0025:
            side = "BUY"
        elif diff > 0.0025:
            side = "SELL"
    elif kind == "gamma_scalping":
        side = "BUY" if random.random() < 0.4 else None
    elif kind == "smart_money":
        if abs(diff) > 0.003 and random.random() < 0.6:
            side = "BUY" if diff > 0 else "SELL"

    if not side:
        return None, None, 0.0
    return sym, side, round(last, 2)


class StrategyScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._last_run: Dict[str, float] = {}
        self.running = False
        self.fires = 0

    def stats(self) -> dict:
        return {"running": self.running, "fires": self.fires, "tracked": len(self._last_run)}

    async def _evaluate(self, strat: Strategy) -> None:
        sym, side, price = _signal_for_strategy(strat)
        if not sym:
            return
        qty = int(strat.params.get("qty", 1))
        broker = get_broker("mock")
        fill = await broker.place_order(symbol=sym, side=side, qty=qty, price=price)
        order = Order(
            user_id=strat.user_id, broker="mock", symbol=sym, side=side,
            qty=qty, price=fill["fill_price"], order_type="MARKET", product="MIS",
            status=fill["status"], source=f"strategy:{strat.kind}",
            filled_at=datetime.now(timezone.utc),
        )
        await db.orders.insert_one(order.to_mongo())
        await db.strategies.update_one(
            {"_id": strat.id},
            {"$set": {"last_fire_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"fire_count": 1}},
        )
        notif = Notification(
            user_id=strat.user_id, kind="strategy",
            title=f"{strat.name}: {side} {sym}",
            message=f"Strategy auto-executed {qty} @ ₹{order.price}",
            severity="success" if side == "BUY" else "warning",
        )
        await db.notifications.insert_one(notif.to_mongo())
        await send_for_user(
            db, strat.user_id,
            f"*🤖 Strategy fire — {strat.name}*\n`{side}` {sym} × {qty} @ ₹{order.price}",
        )
        from services.push_fcm import send_for_user as push_for_user
        await push_for_user(
            db, strat.user_id,
            f"Strategy · {strat.name}",
            f"{side} {sym} × {qty} @ ₹{order.price}",
            data={"kind": "strategy", "strategy_id": strat.id, "order_id": order.id},
        )
        self.fires += 1

    async def _loop(self) -> None:
        self.running = True
        while self.running:
            try:
                now = asyncio.get_event_loop().time()
                cursor = db.strategies.find({"enabled": True})
                async for doc in cursor:
                    strat = Strategy.from_mongo(doc)
                    interval = max(5, int(strat.params.get("interval_seconds", 15)))
                    last = self._last_run.get(strat.id, 0)
                    if now - last >= interval:
                        self._last_run[strat.id] = now
                        try:
                            await self._evaluate(strat)
                        except Exception as e:
                            logger.exception("strategy %s eval failed: %s", strat.id, e)
            except Exception as e:
                logger.exception("scheduler loop error: %s", e)
            await asyncio.sleep(1.0)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()


scheduler = StrategyScheduler()
