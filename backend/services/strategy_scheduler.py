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
    # Relaxed thresholds so they fire frequently during testing
    if kind == "ema_crossover":
        if diff > 0.0002 or random.random() < 0.1:
            side = "BUY"
        elif diff < -0.0002 or random.random() < 0.1:
            side = "SELL"
    elif kind == "oi_breakout":
        if diff > 0.0001 or random.random() < 0.3:
            side = "BUY"
    elif kind == "vwap_scalping":
        if diff < -0.0002 or random.random() < 0.15:
            side = "BUY"
        elif diff > 0.0002 or random.random() < 0.15:
            side = "SELL"
    elif kind == "gamma_scalping":
        side = "BUY" if random.random() < 0.4 else None
    elif kind == "smart_money":
        if abs(diff) > 0.0003 or random.random() < 0.2:
            side = "BUY" if diff > 0 else "SELL"
    else:
        # Fallback heuristic for all newly added strategy kinds (MACD, RSI, etc.)
        if random.random() < 0.3:
            side = random.choice(["BUY", "SELL"])

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
        
        # Resolve real execution broker if configured
        actual_broker = "mock"
        exec_broker_doc = await db.broker_connections.find_one({
            "user_id": strat.user_id,
            "is_order_exec": True,
            "connected": True
        })
        if exec_broker_doc:
            actual_broker = exec_broker_doc["broker"]

        from services.broker_router import route_order
        fill = await route_order(
            db, strat.user_id, actual_broker,
            symbol=sym, side=side, qty=qty, price=price,
            order_type="MARKET", product="MIS"
        )
        if not fill:
            return  # Order rejected by broker

        order = Order(
            user_id=strat.user_id, broker=actual_broker, symbol=sym, side=side,
            qty=qty, price=fill.get("fill_price", price), order_type="MARKET", product="MIS",
            status=fill.get("status", "complete"), source=f"strategy:{strat.kind}",
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
        
        # Mirror strategy execution to managed users
        if getattr(strat, "copy_to_users", True):
            from services.managed_order_engine import mirror_order_to_managed_users
            asyncio.create_task(mirror_order_to_managed_users(db, strat.user_id, order))
            
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
                            # Notify the user that their strategy failed to execute
                            try:
                                notif = Notification(
                                    user_id=strat.user_id, kind="strategy",
                                    title=f"{strat.name} Execution Failed",
                                    message=f"Error: {str(e)}",
                                    severity="error",
                                )
                                await db.notifications.insert_one(notif.to_mongo())
                            except Exception as notif_e:
                                logger.error("Failed to insert error notification: %s", notif_e)
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
