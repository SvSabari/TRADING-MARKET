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
        trades_log=result["trades_log"],
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

@backtest_router.get("/run/{run_id}")
async def get_run(run_id: str, user: User = Depends(get_current_user)):
    try:
        doc = await db.backtests.find_one({"_id": run_id, "user_id": user.id})
        if not doc:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found")
        return BacktestRun.from_mongo(doc).model_dump()
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@backtest_router.delete("/run/{run_id}")
async def delete_run(run_id: str, user: User = Depends(get_current_user)):
    try:
        result = await db.backtests.delete_one({"_id": run_id, "user_id": user.id})
        if result.deleted_count == 0:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found or unauthorized")
        return {"success": True, "message": "Run deleted successfully"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))



SECTOR_MAP = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK"],
    "IT": ["INFY", "TCS", "WIPRO", "HCLTECH"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID"],
    "Pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB"],
    "Auto": ["TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO"],
}

@backtest_router.post("/sector-accuracy")
async def sector_accuracy(body: BacktestRequest, user: User = Depends(get_current_user)):
    """Runs a backtest across all sectors and symbols for a strategy to compute win rate by sector."""
    import asyncio
    
    results_by_sector = {}
    
    # Pre-build all tasks
    tasks = []
    for sector, symbols in SECTOR_MAP.items():
        for symbol in symbols:
            tasks.append((sector, symbol, asyncio.to_thread(
                run_backtest, body.strategy_kind, symbol, body.period_days, body.params
            )))
            
    # Run all backtests concurrently
    coros = [t[2] for t in tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)
    
    # Process results
    sector_wins = {s: 0 for s in SECTOR_MAP}
    sector_trades = {s: 0 for s in SECTOR_MAP}
    
    for (sector, symbol, _), res in zip(tasks, results):
        if isinstance(res, Exception):
            print(f"Error backtesting {symbol}: {res}")
            continue
            
        wins = int((res["metrics"].get("win_rate_pct", 0) / 100.0) * res["metrics"].get("trades", 0))
        sector_wins[sector] += wins
        sector_trades[sector] += res["metrics"].get("trades", 0)
        
    for sector, symbols in SECTOR_MAP.items():
        trades = sector_trades[sector]
        win_rate = (sector_wins[sector] / trades) if trades > 0 else 0.0
            
        results_by_sector[sector] = {
            "win_rate": win_rate,
            "symbols": symbols
        }
        
    return {"strategy_kind": body.strategy_kind, "sector_accuracy": results_by_sector}
