import asyncio
from backend.services.backtest import run_backtest, _SIG_MAP
import json
import logging

logging.basicConfig(level=logging.ERROR)

async def validate():
    tests = [
        # 1. Stock Mode
        {"symbol": "RELIANCE", "mode": "NONE", "strategy": "ema_crossover", "tf": "5min"},
        {"symbol": "HDFCBANK", "mode": "NONE", "strategy": "macd", "tf": "15min"},
        
        # 2. Options AUTO
        {"symbol": "NIFTY", "mode": "AUTO", "strategy": "supertrend", "tf": "1min"},
        
        # 3. Force CE
        {"symbol": "NIFTY", "mode": "CE", "strategy": "pyro_algo", "tf": "5min"},
        
        # 4. Force PE
        {"symbol": "NIFTY", "mode": "PE", "strategy": "ema_crossover", "tf": "5min"},
    ]

    all_strategies = list(_SIG_MAP.keys())
    
    results = []
    sample_traces = {}

    # Check that we run every strategy at least once
    for strategy in all_strategies:
        if not any(t["strategy"] == strategy for t in tests):
            tests.append({"symbol": "RELIANCE", "mode": "NONE", "strategy": strategy, "tf": "5min"})

    for t in tests:
        params = {
            "resample": t["tf"],
            "trade_options": t["mode"] != "NONE",
            "option_type": t["mode"] if t["mode"] != "NONE" else "AUTO",
            "stop_loss_pct": 1,
            "take_profit_pct": 2,
            "qty": 50
        }
        res = await run_backtest(t["strategy"], t["symbol"], period_days=10, params=params)
        
        trades_log = res.get("trades_log", [])
        total_signals = len(trades_log)
        missing = len([x for x in trades_log if x.get("reason") == "MISSING DATA"])
        valid = total_signals - missing
        
        results.append({
            "Strategy": t["strategy"],
            "Symbol": t["symbol"],
            "TF": t["tf"],
            "Mode": t["mode"],
            "Signals": total_signals,
            "Valid": valid,
            "Missing": missing
        })
        
        # Save a sample trace if valid
        if valid > 0 and t["mode"] not in sample_traces:
            for tr in trades_log:
                if tr.get("reason") != "MISSING DATA":
                    sample_traces[t["mode"]] = tr
                    break

    print("=== VALIDATION TABLE ===")
    print(f"{'Strategy':<15} | {'Symbol':<10} | {'TF':<5} | {'Mode':<5} | {'Signals':<7} | {'Valid':<5} | {'Missing':<7}")
    print("-" * 75)
    for r in results:
        print(f"{r['Strategy']:<15} | {r['Symbol']:<10} | {r['TF']:<5} | {r['Mode']:<5} | {r['Signals']:<7} | {r['Valid']:<5} | {r['Missing']:<7}")

    print("\n=== SAMPLE TRACES ===")
    for mode, tr in sample_traces.items():
        print(f"\n--- {mode} MODE ---")
        for k, v in tr.items():
            print(f"{k}: {v}")

if __name__ == "__main__":
    asyncio.run(validate())
