import os

file_path = 'backend/services/backtest.py'
with open(file_path, 'r') as f:
    text = f.read()

import re

# Find the second _fetch_option_premium definition and replace it
pattern = r"async def _fetch_option_premium\(symbol: str, spot_price: float, opt_type: str, ts_utc: datetime\) -> tuple:.*?return ltp, float\(closest_row\['strike'\]\), None, \"REAL_EXACT\""

replacement = '''async def _fetch_option_premium(symbol: str, spot_price: float, opt_type: str, ts_utc: datetime) -> tuple:
    date_str = ts_utc.strftime("%Y-%m-%d")
    ohlc = _load_options_ohlc_for_day(symbol, date_str)
    if ohlc.empty: return None, None, None, "NO DATA"
    
    # 1. Strict Requirement: Expiry must be present
    if 'expiry' not in ohlc.columns:
        return None, None, None, "NO DATA"
        
    minute_ts = ts_utc.replace(second=0, microsecond=0)
    minute_df = ohlc[ohlc['timestamp'] == minute_ts]
    
    if minute_df.empty: return None, None, None, "NO DATA"
    
    # 2. Strict Requirement: Exact ATM Calculation (No spot-distance proxy)
    from services.options_analytics import INDEX_CONFIG
    step = INDEX_CONFIG.get(symbol, {}).get("step", 50)
    exact_strike = round(spot_price / step) * step
    
    minute_df = minute_df[minute_df['strike'] == exact_strike]
    if minute_df.empty: return None, None, None, "NO DATA"
    
    row = minute_df.iloc[0]
    
    # 3. Strict Requirement: Exact Strike Validation
    if float(row['strike']) == 0.0 or pd.isna(row['strike']):
        return None, None, None, "NO DATA"
        
    # 4. Strict Requirement: Expiry Validation
    expiry_val = row.get('expiry')
    if pd.isna(expiry_val) or not expiry_val:
        return None, None, None, "NO DATA"
    
    prefix = opt_type.lower()
    ltp = row[f"{prefix}_close"]
    if pd.isna(ltp) or ltp <= 0:
        return None, None, None, "NO DATA"
    
    return ltp, exact_strike, str(expiry_val), "REAL_EXACT"'''

new_text = re.sub(pattern, replacement, text, flags=re.DOTALL)
if new_text != text:
    with open(file_path, 'w') as f:
        f.write(new_text)
    print("Replaced _fetch_option_premium")
else:
    print("Could not find the function definition")
