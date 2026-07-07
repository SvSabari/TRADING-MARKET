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
            {"id": "ema_crossover", "name": "EMA Crossover", "description": "Classic 9/21 EMA crossover."},
            {"id": "oi_breakout", "name": "OI Breakout", "description": "Open Interest unwind/breakout detector."},
            {"id": "vwap_scalping", "name": "VWAP Scalping", "description": "Mean-reversion around session VWAP."},
            {"id": "gamma_scalping", "name": "Gamma Scalping", "description": "Delta-hedge around ATM options."},
            {"id": "smart_money", "name": "Smart Money", "description": "Volume + OI confluence with delta footprint."},
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
