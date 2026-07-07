"""Signals + Backtest endpoints."""
from fastapi import APIRouter, Depends

from auth import get_current_user
from db import db
from models import BacktestRequest, BacktestRun, User
from services.backtest import run_backtest
from services.signals import detect_signals

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/live")
async def live_signals(user: User = Depends(get_current_user)):
    return {"signals": detect_signals()}


backtest_router = APIRouter(prefix="/backtest", tags=["backtest"])


@backtest_router.post("/run")
async def run(body: BacktestRequest, user: User = Depends(get_current_user)):
    result = run_backtest(body.strategy_kind, body.symbol, body.period_days, body.params)
    run_doc = BacktestRun(
        user_id=user.id,
        strategy_kind=body.strategy_kind,
        symbol=body.symbol,
        period_days=body.period_days,
        metrics=result["metrics"],
        equity_curve=result["equity_curve"],
    )
    await db.backtests.insert_one(run_doc.to_mongo())
    return {"id": run_doc.id, **result}


@backtest_router.get("/history")
async def history(limit: int = 20, user: User = Depends(get_current_user)):
    cur = db.backtests.find({"user_id": user.id}, {"equity_curve": 0}).sort("created_at", -1).limit(limit)
    out = []
    async for d in cur:
        out.append(BacktestRun.from_mongo(d).model_dump())
    return {"runs": out}
