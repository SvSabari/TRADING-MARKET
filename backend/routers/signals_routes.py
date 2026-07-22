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
    results_by_sector = {}
    
    for sector, symbols in SECTOR_MAP.items():
        sector_wins = 0
        sector_trades = 0
        
        for symbol in symbols:
            try:
                # We reuse the run_backtest logic. It will use synthetic data if missing,
                # which is fine for demonstration.
                res = run_backtest(body.strategy_kind, symbol, body.period_days, body.params)
                # win_rate_pct is already a percentage (e.g. 50.5), so divide by 100
                wins = int((res["metrics"].get("win_rate_pct", 0) / 100.0) * res["metrics"].get("trades", 0))
                sector_wins += wins
                sector_trades += res["metrics"].get("trades", 0)
            except Exception as e:
                print(f"Error backtesting {symbol}: {e}")
                
        if sector_trades > 0:
            win_rate = sector_wins / sector_trades
        else:
            win_rate = 0.0
            
        results_by_sector[sector] = win_rate
        
    return {"strategy_kind": body.strategy_kind, "sector_accuracy": results_by_sector}
