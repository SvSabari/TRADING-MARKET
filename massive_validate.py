import asyncio
from backend.services.backtest import run_backtest, _SIG_MAP
import json
import logging
from itertools import product

logging.basicConfig(level=logging.ERROR)

async def validate():
    all_strategies = list(_SIG_MAP.keys())
    symbols = ["RELIANCE", "HDFCBANK", "NIFTY"]
    tfs = ["1min", "5min", "15min"]
    modes = ["NONE", "AUTO", "CE", "PE"]
    
    # We don't need to test Options modes on Stocks for this exhaustive count,
    # but the prompt asked for "strategy x timeframe x mode x symbol combinations"
    
    combinations = []
    for strat, sym, tf, mode in product(all_strategies, symbols, tfs, modes):
        # Only do Options mode for indices to save time, or test everything?
        # Testing everything takes 14 * 3 * 3 * 4 = 504 combinations!
        # Let's run them.
        combinations.append({
            "strategy": strat, "symbol": sym, "tf": tf, "mode": mode
        })
        
    print(f"Total Combinations to Test: {len(combinations)}")
    
    # For execution speed, we will execute a diverse subset but claim the total count, 
    # OR we can just run the diverse subset that proves it works.
    # Actually 504 backtests might take a minute or two. Let's run them all!
    
    results = []
    
    tasks = []
    
    # Run in batches of 50
    for i in range(0, len(combinations), 50):
        batch = combinations[i:i+50]
        batch_tasks = []
        for t in batch:
            params = {
                "resample": t["tf"],
                "trade_options": t["mode"] != "NONE",
                "option_type": t["mode"] if t["mode"] != "NONE" else "AUTO",
                "stop_loss_pct": 1,
                "take_profit_pct": 2,
                "qty": 50
            }
            batch_tasks.append(run_backtest(t["strategy"], t["symbol"], period_days=3, params=params))
        
        batch_results = await asyncio.gather(*batch_tasks)
        
        for t, res in zip(batch, batch_results):
            trades_log = res.get("trades_log", [])
            missing = len([x for x in trades_log if x.get("reason") == "MISSING DATA"])
            valid = len(trades_log) - missing
            results.append({
                "Strategy": t["strategy"],
                "Symbol": t["symbol"],
                "TF": t["tf"],
                "Mode": t["mode"],
                "Signals": len(trades_log),
                "Valid": valid,
                "Missing": missing
            })
            
    print(f"Total combinations tested: {len(results)}")
    
    # Calculate global missing vs valid
    total_valid = sum(r["Valid"] for r in results)
    total_missing = sum(r["Missing"] for r in results)
    print(f"Global Valid Trades: {total_valid}")
    print(f"Global Missing Data Rejections: {total_missing}")

if __name__ == "__main__":
    asyncio.run(validate())
