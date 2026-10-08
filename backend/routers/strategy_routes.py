"""Strategy CRUD + toggle + scheduler status endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
import uuid

from auth import get_current_user
from constants import STRATEGY_KINDS
from db import get_db
from models import Strategy, User
from schemas import StrategyCreate, StrategyUpdate
from services.strategy_scheduler import scheduler

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/kinds")
async def kinds(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return {
        "kinds": [
            {"id": "pyro_algo",              "name": "PYRO ALGO",                "description": "Combines Stochastic crossover with SuperTrend direction for high-probability trend entries.", "params_hint": "st_period=10, k=14, d=3", "category": "trend"},
            {"id": "ema_crossover",          "name": "EMA Crossover",            "description": "Catches new trends early. Buys when the fast moving average crosses above the slow one.", "params_hint": "fast=9, slow=21", "category": "trend"},
            {"id": "macd_crossover",         "name": "MACD Crossover",           "description": "Momentum strategy. Buys when MACD line crosses above the signal line — a classic confirmation of upward momentum.", "params_hint": "fast=12, slow=26, signal=9", "category": "trend"},
            {"id": "supertrend",             "name": "Supertrend",               "description": "Uses ATR-based dynamic support/resistance. Buys when price closes above the Supertrend line, sells when it crosses below.", "params_hint": "period=10, multiplier=3.0", "category": "trend"},
            {"id": "rsi_divergence",         "name": "RSI Reversal",             "description": "Mean-reversion strategy. Buys when RSI exits oversold territory (<30), sells when it exits overbought (>70).", "params_hint": "period=14, oversold=30, overbought=70", "category": "reversal"},
            {"id": "bollinger_band",         "name": "Bollinger Band Bounce",    "description": "Buys at the lower Bollinger Band (statistical support) and sells at the upper band (statistical resistance).", "params_hint": "period=20, std=2.0", "category": "reversal"},
            {"id": "vwap_scalping",          "name": "VWAP Scalping",            "description": "Buys dips below the daily average price (VWAP) and sells the bounce. Ideal for intraday trading.", "params_hint": "entry_z=0.002, exit_z=0.002", "category": "scalping"},
            {"id": "opening_range_breakout", "name": "Opening Range Breakout",   "description": "Buys if price breaks above the first 15-minute high. One of the most popular intraday strategies in Indian markets.", "params_hint": "orb_bars=15", "category": "breakout"},
            {"id": "volume_spike_breakout",  "name": "Volume Spike Breakout",    "description": "Buys when volume is 3x the average AND price makes a new high. Confirms strong institutional buying interest.", "params_hint": "vol_multiplier=3.0, lookback=20", "category": "breakout"},
            {"id": "oi_breakout",            "name": "OI Breakout",              "description": "Spots massive price spikes when option sellers get trapped and forced to cover positions.", "params_hint": "window=20", "category": "breakout"},
            {"id": "gap_and_go",             "name": "Gap & Go",                 "description": "Buys stocks that gap up 1.5%+ at market open and continue higher. Capitalises on news-driven momentum.", "params_hint": "gap_pct=0.015", "category": "momentum"},
            {"id": "smart_money",            "name": "Smart Money Flow",         "description": "Follows huge volume spikes with directional price moves — a proxy for institutional whale activity.", "params_hint": "None", "category": "momentum"},
            {"id": "gamma_scalping",         "name": "Gamma Scalping",           "description": "Profits from wild price swings by fading extreme moves beyond ATR bands without guessing direction.", "params_hint": "None", "category": "scalping"},
            {"id": "donchian_breakout",      "name": "Donchian Breakout",        "description": "Buys when price breaks the N-period high, sells on the N-period low. Classic Turtle Trading trend strategy.", "params_hint": "period=20", "category": "trend"},
            {"id": "zscore_reversion",       "name": "Statistical Z-Score",      "description": "Mean reversion based on Z-Score. Buys when price is statistically oversold and sells when overbought.", "params_hint": "period=20, entry_z=2.0", "category": "reversal"},
            {"id": "keltner_channel",        "name": "Keltner Channel Momentum", "description": "Breakout strategy using ATR channels. Buys when price breaks above the upper channel.", "params_hint": "period=20, multiplier=2.0", "category": "momentum"},
        ]
    }



@router.get("/scheduler-status")
async def scheduler_status(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return scheduler.stats()


@router.get("")
async def list_strategies(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Strategy).where(Strategy.user_id == user.id).order_by(Strategy.created_at.desc())
    result = await session.execute(stmt)
    strategies = result.scalars().all()
    
    out = []
    for d in strategies:
        out.append({
            "id": d.id, "user_id": d.user_id, "name": d.name, "kind": d.kind,
            "enabled": d.enabled, "copy_to_users": d.copy_to_users,
            "params": d.params, "symbols": d.symbols,
            "fire_count": d.fire_count, "last_fire_at": d.last_fire_at,
            "created_at": d.created_at
        })
    return {"strategies": out}


@router.post("")
async def create_strategy(body: StrategyCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    if body.kind not in STRATEGY_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid strategy kind")
    params = dict(body.params or {})
    params.setdefault("interval_seconds", max(5, int(body.interval_seconds)))
    params.setdefault("qty", int(params.get("qty", 1)))
    strat = Strategy(
        id=str(uuid.uuid4()),
        user_id=user.id, name=body.name, kind=body.kind, enabled=body.enabled,
        params=params, symbols=body.symbols, created_at=datetime.now(timezone.utc)
    )
    session.add(strat)
    await session.commit()
    return {
        "id": strat.id, "user_id": strat.user_id, "name": strat.name, "kind": strat.kind,
        "enabled": strat.enabled, "copy_to_users": strat.copy_to_users,
        "params": strat.params, "symbols": strat.symbols,
        "fire_count": strat.fire_count, "last_fire_at": strat.last_fire_at,
        "created_at": strat.created_at
    }


@router.patch("/{strategy_id}")
async def update_strategy(strategy_id: str, body: StrategyUpdate,
                          user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
        
    update_data = body.model_dump(exclude_none=True)
    if update_data:
        for k, v in update_data.items():
            setattr(doc, k, v)
        await session.commit()
        
    return {
        "id": doc.id, "user_id": doc.user_id, "name": doc.name, "kind": doc.kind,
        "enabled": doc.enabled, "copy_to_users": doc.copy_to_users,
        "params": doc.params, "symbols": doc.symbols,
        "fire_count": doc.fire_count, "last_fire_at": doc.last_fire_at,
        "created_at": doc.created_at
    }


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if doc:
        await session.delete(doc)
        await session.commit()
        return {"deleted": 1}
    return {"deleted": 0}
