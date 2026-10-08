import os
import codecs

with open('frontend/src/pages/Backtest.jsx', 'rb') as f:
    b = f.read()

try:
    text = b.decode('utf-8')
except:
    text = b.decode('windows-1252')

target = '''          {dataInfo && (
            <div style={{ padding: "0 16px 8px", fontSize: 11, color: "var(--text-secondary)", fontFamily: "JetBrains Mono" }}>
              <span style={{ color: "var(--primary)" }}>
                {form.trade_options ? (dataInfo.options_days || 0) : (dataInfo.equity_days || dataInfo.days || 0)} days
              </span> of {form.trade_options ? "options data" : "tick data"} available in DB for {form.symbol}
            </div>
          )}'''

replace = '''          {dataInfo && (
            <div style={{ padding: "0 16px 8px", fontSize: 11, color: "var(--text-secondary)", fontFamily: "JetBrains Mono" }}>
              <div>
                <span style={{ color: "var(--primary)" }}>
                  {form.trade_options ? (dataInfo.options_days || 0) : (dataInfo.equity_days || dataInfo.days || 0)} days
                </span> of {form.trade_options ? "options data" : "tick data"} available in DB for {form.symbol}
              </div>
              {form.trade_options && form.option_type === "AUTO" && (
                <div style={{ marginTop: 4, color: "var(--text-primary)" }}>
                  Rule: Buy Signal &rarr; Buy ATM CE, Sell Signal &rarr; Buy ATM PE. Missing data will not fall back to EQ.
                </div>
              )}
            </div>
          )}'''

if target in text:
    text = text.replace(target, replace)
    print('Replaced target')

with open('frontend/src/pages/Backtest.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print('Saved as UTF-8')
