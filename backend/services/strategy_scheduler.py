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

from db import AsyncSessionLocal
from sqlalchemy import select
from models import Notification, Order, Strategy
from services.broker_router import get_broker
from services.market_data import tick_engine
from services.telegram import send_for_user

logger = logging.getLogger("strategy-scheduler")


def _build_ohlc(hist, timeframe=60):
    candles = []
    if not hist: return []
    current_bucket = int(hist[0]['ts']) // timeframe
    curr_c = {'open': hist[0]['ltp'], 'high': hist[0]['ltp'], 'low': hist[0]['ltp'], 'close': hist[0]['ltp']}
    for r in hist:
        b = int(r['ts']) // timeframe
        if b == current_bucket:
            curr_c['high'] = max(curr_c['high'], r['ltp'])
            curr_c['low'] = min(curr_c['low'], r['ltp'])
            curr_c['close'] = r['ltp']
        else:
            candles.append(curr_c)
            current_bucket = b
            curr_c = {'open': r['ltp'], 'high': r['ltp'], 'low': r['ltp'], 'close': r['ltp']}
    candles.append(curr_c)
    return candles

def _signal_for_strategy(strat: Strategy) -> tuple[str | None, str | None, float]:
    from services.indicators import stoch, supertrend, ema, macd, rsi, vwap
    symbols = strat.symbols or list(tick_engine.prices.keys())[:5]
    if not symbols:
        return None, None, 0.0
        
    for sym in symbols:
        hist = tick_engine.get_history(sym)
        if len(hist) < 60:
            continue
            
        prices = [r['ltp'] for r in hist]
        last = prices[-1]
        
        kind = strat.kind
        side = None
        
        if kind == 'pyro_algo':
            candles = _build_ohlc(hist, 60)
            if len(candles) >= 10:
                highs = [c['high'] for c in candles]
                lows = [c['low'] for c in candles]
                closes = [c['close'] for c in candles]
                k_line, d_line = stoch(highs, lows, closes)
                st, trend = supertrend(highs, lows, closes)
                if len(k_line) > 2:
                    if k_line[-1] > d_line[-1] and k_line[-2] <= d_line[-2] and trend[-1] == 1:
                        side = 'BUY'
                    elif k_line[-1] < d_line[-1] and k_line[-2] >= d_line[-2] and trend[-1] == -1:
                        side = 'SELL'
                        
        elif kind == "ema_crossover":
            fast_ema = ema(prices, 9)
            slow_ema = ema(prices, 21)
            if len(fast_ema) >= 2 and len(slow_ema) >= 2:
                if fast_ema[-1] > slow_ema[-1] and fast_ema[-2] <= slow_ema[-2]:
                    side = "BUY"
                elif fast_ema[-1] < slow_ema[-1] and fast_ema[-2] >= slow_ema[-2]:
                    side = "SELL"
                    
        elif kind == "macd_crossover":
            macd_line, sig_line, _ = macd(prices)
            if len(macd_line) >= 2:
                if macd_line[-1] > sig_line[-1] and macd_line[-2] <= sig_line[-2]:
                    side = "BUY"
                elif macd_line[-1] < sig_line[-1] and macd_line[-2] >= sig_line[-2]:
                    side = "SELL"
                    
        elif kind == "rsi_reversal":
            rsi_vals = rsi(prices, 14)
            if len(rsi_vals) >= 2:
                if rsi_vals[-1] > 30 and rsi_vals[-2] <= 30:
                    side = "BUY"
                elif rsi_vals[-1] < 70 and rsi_vals[-2] >= 70:
                    side = "SELL"
                    
        elif kind == "vwap_scalping":
            volumes = [r.get('v', 1) for r in hist]
            vwap_vals = vwap(prices, volumes)
            if len(vwap_vals) >= 2:
                if prices[-1] > vwap_vals[-1] and prices[-2] <= vwap_vals[-2]:
                    side = "BUY"
                elif prices[-1] < vwap_vals[-1] and prices[-2] >= vwap_vals[-2]:
                    side = "SELL"
        else:
            if random.random() < 0.005:
                side = random.choice(["BUY", "SELL"])
                
        if side:
            return sym, side, round(last, 2)
            
    return None, None, 0.0


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
        from models import BrokerConnection
        async with AsyncSessionLocal() as session:
            from sqlalchemy import and_
            result = await session.execute(
                select(BrokerConnection).where(
                    and_(BrokerConnection.user_id == strat.user_id,
                         BrokerConnection.is_order_exec == True,
                         BrokerConnection.connected == True)
                )
            )
            exec_broker_doc = result.scalar_one_or_none()
            if exec_broker_doc:
                actual_broker = exec_broker_doc.broker

            from services.broker_router import route_order
            fill = None
            reject_reason = None
            from fastapi import HTTPException
            try:
                fill = await route_order(
                    session, strat.user_id, actual_broker,
                    symbol=sym, side=side, qty=qty, price=price,
                    order_type="LIMIT", product="MIS"
                )
            except HTTPException as he:
                reject_reason = he.detail
            except Exception as e:
                reject_reason = str(e)
                
            import uuid
            order_status = fill.get("status", "complete") if fill else "REJECTED"
            order_price = fill.get("fill_price", price) if fill else price
            order = Order(
                id=str(uuid.uuid4()),
                user_id=strat.user_id, broker=actual_broker, symbol=sym, side=side,
                qty=qty, price=order_price, order_type="LIMIT", product="MIS",
                status=order_status, source=f"strategy:{strat.kind}",
                placed_at=datetime.now(timezone.utc), 
                filled_at=datetime.now(timezone.utc) if order_status == "FILLED" else None, 
                broker_order_id=fill.get("broker_order_id") if fill else None,
                reject_reason=reject_reason
            )
            session.add(order)

            strat.last_fire_at = datetime.now(timezone.utc).isoformat()
            strat.fire_count = (strat.fire_count or 0) + 1

            notif = Notification(
                id=str(uuid.uuid4()),
                user_id=strat.user_id, kind="strategy",
                title=f"{strat.name}: {side} {sym}",
                message=f"Strategy auto-executed {qty} @ ₹{order.price}",
                severity="error" if reject_reason else ("success" if side == "BUY" else "warning"),
                created_at=datetime.now(timezone.utc),
            )
            session.add(notif)
            await session.commit()

        # Mirror strategy execution to managed users
        if getattr(strat, "copy_to_users", True):
            from services.managed_order_engine import mirror_order_to_managed_users
            asyncio.create_task(mirror_order_to_managed_users(None, strat.user_id, order))

        await send_for_user(
            None, strat.user_id,
            f"*🤖 Strategy fire — {strat.name}*\n`{side}` {sym} × {qty} @ ₹{order.price}",
        )
        from services.push_fcm import send_for_user as push_for_user
        await push_for_user(
            None, strat.user_id,
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
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(Strategy).where(Strategy.enabled == True)
                    )
                    strats = result.scalars().all()
                for strat in strats:
                    interval = max(5, int((strat.params or {}).get("interval_seconds", 15)))
                    last = self._last_run.get(strat.id, 0)
                    if now - last >= interval:
                        self._last_run[strat.id] = now
                        try:
                            await self._evaluate(strat)
                        except Exception as e:
                            logger.exception("strategy %s eval failed: %s", strat.id, e)
                            try:
                                import uuid
                                async with AsyncSessionLocal() as session:
                                    notif = Notification(
                                        id=str(uuid.uuid4()),
                                        user_id=strat.user_id, kind="strategy",
                                        title=f"{strat.name} Execution Failed",
                                        message=f"Error: {str(e)}",
                                        severity="error",
                                        created_at=datetime.now(timezone.utc),
                                    )
                                    session.add(notif)
                                    await session.commit()
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
