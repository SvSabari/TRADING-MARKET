import asyncio
from services.backtest import run_backtest

async def run_final_audit():
    print("=" * 80)
    print("TRADER PRO BACKTEST ENGINE: COMPREHENSIVE CLOSURE AUDIT & PASS/FAIL VERIFICATION")
    print("=" * 80)
    all_passed = True

    def check(name, condition, details=""):
        nonlocal all_passed
        status = "PASS" if condition else "FAIL"
        if not condition:
            all_passed = False
        print(f"[{status}] {name}")
        if details:
            print(f"       -> {details}")

    # 1. STOCK / INDEX MODE: LONG & SHORT
    print("\n--- TEST 1: Stock/Index Mode (NIFTY 5-day) ---")
    r_stock = await run_backtest('EMA Crossover', 'NIFTY', 5, {'trade_options': False, 'target_pct': 0.5, 'stop_loss_pct': 0.2})
    trades_stock = r_stock['trades_log']
    check("Stock mode trades generated", len(trades_stock) > 0, f"Count: {len(trades_stock)}")
    
    long_t = next((t for t in trades_stock if t['side'] == 'BUY'), None)
    if long_t:
        recalc_long = round((long_t['exit'] - long_t['entry']) * long_t['qty'], 2)
        check("Stock Long P&L calculation", long_t['pnl'] == recalc_long,
              f"Entry: {long_t['entry']} | Exit: {long_t['exit']} | Qty: {long_t['qty']} | Reported: {long_t['pnl']} | Recalc: {recalc_long}")
    
    short_t = next((t for t in trades_stock if t['side'] == 'SELL'), None)
    if short_t:
        recalc_short = round((short_t['entry'] - short_t['exit']) * short_t['qty'], 2)
        check("Stock Short P&L calculation", short_t['pnl'] == recalc_short,
              f"Entry: {short_t['entry']} | Exit: {short_t['exit']} | Qty: {short_t['qty']} | Reported: {short_t['pnl']} | Recalc: {recalc_short}")

    # 2. OPTIONS - AUTO MODE
    print("\n--- TEST 2: Options - Auto Mode (NIFTY) ---")
    r_auto = await run_backtest('EMA Crossover', 'NIFTY', 2, {'trade_options': True, 'option_type': 'AUTO', 'target_pct': 5, 'stop_loss_pct': 3})
    exec_auto = [t for t in r_auto['trades_log'] if t['reason'] not in ('MISSING DATA', 'ENTRY DATA MISSING', 'EXIT DATA MISSING')]
    check("Options Auto trades executed", len(exec_auto) > 0, f"Count: {len(exec_auto)}")
    if exec_auto:
        t = exec_auto[0]
        recalc = round((t['exit_premium'] - t['entry_premium']) * t['qty'], 2)
        check("Options Auto P&L calculation", t['pnl'] == recalc,
              f"Contract: {t['strike']} {t['type']} | Entry: {t['entry_premium']} | Exit: {t['exit_premium']} | Qty: {t['qty']} | P&L: {t['pnl']}")
        check("Options Auto side is strictly BUY", t['side'] == 'BUY', f"Side: {t['side']} (Signal: {t['signal']})")

    # 3. OPTIONS - FORCE CE MODE
    print("\n--- TEST 3: Options - Force CE Mode (NIFTY) ---")
    r_ce = await run_backtest('EMA Crossover', 'NIFTY', 2, {'trade_options': True, 'option_type': 'CE', 'target_pct': 5, 'stop_loss_pct': 3})
    exec_ce = [t for t in r_ce['trades_log'] if t['reason'] not in ('MISSING DATA', 'ENTRY DATA MISSING', 'EXIT DATA MISSING')]
    check("Force CE trades executed", len(exec_ce) > 0, f"Count: {len(exec_ce)}")
    all_ce = all(t['type'] == 'CE' and t['side'] == 'BUY' for t in exec_ce)
    check("Force CE strictly trades long CE on all signals", all_ce, f"All {len(exec_ce)} trades are long CE")

    # 4. OPTIONS - FORCE PE MODE
    print("\n--- TEST 4: Options - Force PE Mode (NIFTY) ---")
    r_pe = await run_backtest('EMA Crossover', 'NIFTY', 2, {'trade_options': True, 'option_type': 'PE', 'target_pct': 5, 'stop_loss_pct': 3})
    exec_pe = [t for t in r_pe['trades_log'] if t['reason'] not in ('MISSING DATA', 'ENTRY DATA MISSING', 'EXIT DATA MISSING')]
    check("Force PE trades executed", len(exec_pe) > 0, f"Count: {len(exec_pe)}")
    all_pe = all(t['type'] == 'PE' and t['side'] == 'BUY' for t in exec_pe)
    check("Force PE strictly trades long PE on all signals", all_pe, f"All {len(exec_pe)} trades are long PE")

    # Validate both Force PE trades from discussion
    print("\n--- Force PE Trades Audit Verification ---")
    if len(exec_pe) >= 2:
        t1, t2 = exec_pe[0], exec_pe[1]
        recalc1 = round((t1['exit_premium'] - t1['entry_premium']) * t1['qty'], 2)
        recalc2 = round((t2['exit_premium'] - t2['entry_premium']) * t2['qty'], 2)
        check("Force PE Trade #1 (22700 PE on SELL signal)", t1['pnl'] == recalc1 and t1['strike'] == 22700,
              f"TS: {t1['entry_ts']} | Strike: {t1['strike']} | Entry: {t1['entry_premium']} | Exit: {t1['exit_premium']} | Qty: {t1['qty']} | P&L: {t1['pnl']}")
        check("Force PE Trade #2 (22750 PE on BUY signal)", t2['pnl'] == recalc2 and t2['strike'] == 22750,
              f"TS: {t2['entry_ts']} | Strike: {t2['strike']} | Entry: {t2['entry_premium']} | Exit: {t2['exit_premium']} | Qty: {t2['qty']} | P&L: {t2['pnl']}")

    # 5. MISSING DATA EXCLUSION
    print("\n--- TEST 5: Missing Data Exclusion Verification ---")
    miss_entry = [t for t in r_pe['trades_log'] if t['reason'] in ('MISSING DATA', 'ENTRY DATA MISSING')]
    check("Missing data attempts logged", len(miss_entry) > 0, f"Count: {len(miss_entry)}")
    miss_pnl_zero = all(t['pnl'] == 0 and t['qty'] == 0 for t in miss_entry)
    check("Missing data trades have strictly 0 P&L and 0 Qty", miss_pnl_zero)
    metrics_match = r_pe['metrics']['trades'] == len(exec_pe)
    check("Executed trades count excludes missing data in metrics", metrics_match,
          f"Reported trades in metrics: {r_pe['metrics']['trades']} | Actual executed: {len(exec_pe)}")

    # 6. MULTI-STRATEGY AUDIT
    print("\n--- TEST 6: Multi-Strategy Verification ---")
    for sym, strat in [('RELIANCE', 'supertrend'), ('TCS', 'vwap_scalping'), ('NIFTY', 'macd_crossover')]:
        r = await run_backtest(strat, sym, 5, {'trade_options': False})
        log = r['trades_log']
        check(f"{strat.upper()} on {sym}", len(log) > 0, f"Generated {len(log)} trades")
        if log:
            sample = log[0]
            mult = 1 if sample['side'] == 'BUY' else -1
            calc = round((sample['exit'] - sample['entry']) * sample['qty'] * mult, 2)
            check(f"  -> {strat.upper()} P&L match", sample['pnl'] == calc,
                  f"Side: {sample['side']} | Entry: {sample['entry']} | Exit: {sample['exit']} | Qty: {sample['qty']} | P&L: {sample['pnl']} | Recalc: {calc}")

    print("\n" + "=" * 80)
    print(f"FINAL AUDIT RESULT: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(run_final_audit())
