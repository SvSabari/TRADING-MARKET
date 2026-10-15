import asyncio
from services.backtest import run_backtest

async def run_audit():
    print("======================================================================")
    print("TRADER PRO BACKTEST ENGINE: REPRODUCIBLE AUDIT & VALIDATION EVIDENCE")
    print("======================================================================\n")

    # 1. STOCK / INDEX MODE: LONG & SHORT TEST
    print(">>> 1. STOCK / INDEX MODE (NIFTY 5-day test)")
    res_stock = await run_backtest('EMA Crossover', 'NIFTY', 5, {'trade_options': False, 'target_pct': 0.5, 'stop_loss_pct': 0.2})
    trades = res_stock['trades_log']
    print(f"Total trades generated: {len(trades)}")
    
    # Check long trade
    long_trades = [t for t in trades if t['side'] == 'BUY']
    if long_trades:
        t = long_trades[0]
        recalc_pnl = round((t['exit'] - t['entry']) * t['qty'], 2)
        print(f"  [STOCK LONG TRADE]")
        print(f"    Symbol: {t['symbol']} | Side: {t['side']} | Signal: {t['signal']}")
        print(f"    Entry TS: {t['entry_ts']} @ {t['entry']} | Exit TS: {t['exit_ts']} @ {t['exit']}")
        print(f"    Qty: {t['qty']} | Exit Reason: {t['reason']}")
        print(f"    Reported P&L: {t['pnl']} | Recalculated P&L: {recalc_pnl} | Match: {t['pnl'] == recalc_pnl}")

    # Check short trade
    short_trades = [t for t in trades if t['side'] == 'SELL']
    if short_trades:
        t = short_trades[0]
        recalc_pnl = round((t['entry'] - t['exit']) * t['qty'], 2)
        print(f"  [STOCK SHORT TRADE]")
        print(f"    Symbol: {t['symbol']} | Side: {t['side']} | Signal: {t['signal']}")
        print(f"    Entry TS: {t['entry_ts']} @ {t['entry']} | Exit TS: {t['exit_ts']} @ {t['exit']}")
        print(f"    Qty: {t['qty']} | Exit Reason: {t['reason']}")
        print(f"    Reported P&L: {t['pnl']} | Recalculated P&L: {recalc_pnl} | Match: {t['pnl'] == recalc_pnl}")

    # 2. OPTIONS MODES: AUTO, FORCE CE, FORCE PE
    for mode in ['AUTO', 'CE', 'PE']:
        print(f"\n>>> 2. OPTIONS MODE: {mode} (NIFTY)")
        res_opt = await run_backtest('EMA Crossover', 'NIFTY', 2, {'trade_options': True, 'option_type': mode, 'target_pct': 5, 'stop_loss_pct': 3})
        executed = [t for t in res_opt['trades_log'] if t['reason'] != 'MISSING DATA']
        missing = [t for t in res_opt['trades_log'] if t['reason'] == 'MISSING DATA']
        print(f"  Executed Trades: {len(executed)} | Missing Data Trades: {len(missing)}")
        if executed:
            t = executed[0]
            recalc_pnl = round((t['exit_premium'] - t['entry_premium']) * t['qty'], 2)
            print(f"  [EXECUTED OPTION TRADE ({mode})]")
            print(f"    Symbol: {t['symbol']} | Side: {t['side']} | Signal: {t['signal']}")
            print(f"    Contract: {t['strike']} {t['type']} (Expiry: {t['expiry']})")
            print(f"    Entry TS: {t['entry_ts']} @ {t['entry_premium']} | Exit TS: {t['exit_ts']} @ {t['exit_premium']}")
            print(f"    Qty: {t['qty']} | Exit Reason: {t['reason']}")
            print(f"    Reported P&L: {t['pnl']} | Recalculated P&L: {recalc_pnl} | Match: {t['pnl'] == recalc_pnl}")

    # 3. MISSING DATA VERIFICATION
    if missing:
        t_m = missing[0]
        print(f"\n>>> 3. MISSING DATA AUDIT")
        print(f"  Trade record: Reason={t_m['reason']} | EntryPrem={t_m['entry_premium']} | ExitPrem={t_m['exit_premium']} | Qty={t_m['qty']} | PnL={t_m['pnl']}")
        print(f"  Zero P&L confirmed: {t_m['pnl'] == 0 and t_m['qty'] == 0}")

    # 4. MULTI-STRATEGY AUDIT (VWAP Scalping, Supertrend, MACD)
    print("\n>>> 4. MULTI-STRATEGY AUDIT ACROSS SYMBOLS")
    for sym, strat in [('RELIANCE', 'supertrend'), ('TCS', 'vwap_scalping'), ('NIFTY', 'macd_crossover')]:
        res_s = await run_backtest(strat, sym, 5, {'trade_options': False})
        log = res_s['trades_log']
        print(f"  Strategy: {strat.upper()} on {sym} -> Total Trades: {len(log)}")
        if log:
            t = log[0]
            mult = 1 if t['side'] == 'BUY' else -1
            recalc = round((t['exit'] - t['entry']) * t['qty'] * mult, 2)
            print(f"    Sample: {t['side']} Entry={t['entry']} Exit={t['exit']} Qty={t['qty']} PnL={t['pnl']} Recalc={recalc} Match={t['pnl'] == recalc} Reason={t['reason']}")

if __name__ == '__main__':
    asyncio.run(run_audit())
