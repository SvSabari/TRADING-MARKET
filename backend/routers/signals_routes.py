"""Signals + Backtest endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
import uuid

from auth import get_current_user
from db import get_db
from models import BacktestRun, User
from schemas import BacktestRequest
from services.backtest import run_backtest
from services.signals import detect_signals

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/live")
async def live_signals(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return {"signals": detect_signals()}


backtest_router = APIRouter(prefix="/backtest", tags=["backtest"])


@backtest_router.post("/run")
async def run(body: BacktestRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    result = await run_backtest(body.strategy_kind, body.symbol, body.period_days, body.params)
    run_doc = BacktestRun(
        id=str(uuid.uuid4()),
        user_id=user.id,
        strategy_kind=body.strategy_kind,
        symbol=body.symbol,
        period_days=body.period_days,
        metrics=result["metrics"],
        equity_curve=result["equity_curve"],
        trades_log=result["trades_log"],
        created_at=datetime.now(timezone.utc)
    )
    try:
        session.add(run_doc)
        await session.commit()
    except Exception as e:
        import logging
        logging.getLogger("backtest").warning(f"Could not save backtest history (DB full?): {e}")
    return {"id": run_doc.id, **result}


@backtest_router.get("/history")
async def history(limit: int = 20, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(BacktestRun).where(BacktestRun.user_id == user.id).order_by(BacktestRun.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    runs = result.scalars().all()
    out = []
    for d in runs:
        out.append({
            "id": d.id,
            "user_id": d.user_id,
            "strategy_kind": d.strategy_kind,
            "symbol": d.symbol,
            "period_days": d.period_days,
            "metrics": d.metrics,
            "trades_log": d.trades_log,
            "created_at": d.created_at
            # Exclude equity_curve just like the old implementation
        })
    return {"runs": out}

@backtest_router.get("/run/{run_id}")
async def get_run(run_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        stmt = select(BacktestRun).where(BacktestRun.id == run_id, BacktestRun.user_id == user.id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "id": doc.id,
            "user_id": doc.user_id,
            "strategy_kind": doc.strategy_kind,
            "symbol": doc.symbol,
            "period_days": doc.period_days,
            "metrics": doc.metrics,
            "equity_curve": doc.equity_curve,
            "trades_log": doc.trades_log,
            "created_at": doc.created_at
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@backtest_router.delete("/run/{run_id}")
async def delete_run(run_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        stmt = select(BacktestRun).where(BacktestRun.id == run_id, BacktestRun.user_id == user.id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found or unauthorized")
        await session.delete(doc)
        await session.commit()
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
async def sector_accuracy(body: BacktestRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Runs a backtest across all sectors and symbols for a strategy to compute win rate by sector."""
    import asyncio
    
    results_by_sector = {}
    
    # Pre-build all tasks
    tasks = []
    for sector, symbols in SECTOR_MAP.items():
        for symbol in symbols:
            tasks.append((sector, symbol, run_backtest(
                body.strategy_kind, symbol, body.period_days, body.params
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
