"""Strategy CRUD + toggle + scheduler status endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_current_user
from constants import STRATEGY_KINDS
from db import db
from models import Strategy, StrategyCreate, StrategyUpdate, User
from services.strategy_scheduler import scheduler

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/kinds")
async def kinds(user: User = Depends(get_current_user)):
    return {
        "kinds": [
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
async def scheduler_status(user: User = Depends(get_current_user)):
    return scheduler.stats()


@router.get("")
async def list_strategies(user: User = Depends(get_current_user)):
    cur = db.strategies.find({"user_id": user.id}).sort("created_at", -1)
    out = []
    async for d in cur:
        out.append(Strategy.from_mongo(d).model_dump())
    return {"strategies": out}


@router.post("", response_model=Strategy, response_model_by_alias=False)
async def create_strategy(body: StrategyCreate, user: User = Depends(get_current_user)):
    if body.kind not in STRATEGY_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid strategy kind")
    params = dict(body.params or {})
    params.setdefault("interval_seconds", max(5, int(body.interval_seconds)))
    params.setdefault("qty", int(params.get("qty", 1)))
    strat = Strategy(
        user_id=user.id, name=body.name, kind=body.kind, enabled=body.enabled,
        params=params, symbols=body.symbols,
    )
    await db.strategies.insert_one(strat.to_mongo())
    return strat


@router.patch("/{strategy_id}", response_model=Strategy, response_model_by_alias=False)
async def update_strategy(strategy_id: str, body: StrategyUpdate,
                          user: User = Depends(get_current_user)):
    doc = await db.strategies.find_one({"_id": strategy_id, "user_id": user.id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if update:
        await db.strategies.update_one({"_id": strategy_id}, {"$set": update})
    new_doc = await db.strategies.find_one({"_id": strategy_id})
    return Strategy.from_mongo(new_doc)


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, user: User = Depends(get_current_user)):
    res = await db.strategies.delete_one({"_id": strategy_id, "user_id": user.id})
    return {"deleted": res.deleted_count}
