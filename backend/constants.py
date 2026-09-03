"""Static constants — Nifty 50 universe, brokers list, etc."""
NIFTY_50 = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
    "BHARTIARTL", "ITC", "LT", "KOTAKBANK", "AXISBANK",
    "SBIN", "BAJFINANCE", "HINDUNILVR", "ASIANPAINT", "MARUTI",
    "HCLTECH", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO",
    "M&M", "NESTLEIND", "POWERGRID", "NTPC", "ONGC",
    "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
    "BAJAJFINSV", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "GRASIM",
    "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP", "BRITANNIA",
    "COALINDIA", "BPCL", "IOC", "HDFCLIFE", "SBILIFE",
    "TECHM", "INDUSINDBK", "UPL", "TATACONSUM", "LTIM",
]

INDICES = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"
]

ICICI_INDEX_MAP = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "CNXBAN",
    "FINNIFTY": "NIFFIN",
    "MIDCPNIFTY": "NIFMID",
    "SENSEX": "BSESEN", 
    "NIFTYNXT50": "CNXNXT"
}

ALL_SYMBOLS = NIFTY_50 + INDICES

BROKERS = ["zerodha", "breeze", "angel", "fyers", "upstox", "dhan"]

STRATEGY_KINDS = [
    "ema_crossover",
    "macd_crossover",
    "supertrend",
    "rsi_divergence",
    "bollinger_band",
    "vwap_scalping",
    "opening_range_breakout",
    "volume_spike_breakout",
    "oi_breakout",
    "gap_and_go",
    "smart_money",
    "gamma_scalping",
    "donchian_breakout",
    "zscore_reversion",
    "keltner_channel",
]
