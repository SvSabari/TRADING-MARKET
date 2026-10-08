import os

with open('backend/services/backtest.py', 'r') as f:
    text = f.read()

target = '        pnl = (exit_premium - state.opt_entry_premium) * state.qty * state.position if reason != "MISSING DATA" else 0'
replace = '        pnl = (exit_premium - state.opt_entry_premium) * state.qty if reason != "MISSING DATA" else 0'

if target in text:
    text = text.replace(target, replace)
    with open('backend/services/backtest.py', 'w') as f:
        f.write(text)
    print('Fixed options PnL multiplier.')
else:
    print('Could not find PnL logic!')
