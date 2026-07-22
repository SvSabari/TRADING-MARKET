"""Broker instrument-token mappings — the bridge between our internal
Nifty 50 ticker symbols and each broker's own instrument identifier.

Token values are hard-coded for the cash segment (NSE-EQ). They were
generated from public instrument dumps; if a token changes (rare for
listed names), update this file. For production, the recommended
approach is to fetch the broker's instrument dump on startup and
override these maps.
"""
from __future__ import annotations

from typing import Dict

# ============================================================
# Zerodha Kite — `instrument_token` (int) → ticker
# These are *NSE-EQ* tokens. Fetched 2026-02-06 via the public
# https://api.kite.trade/instruments?segment=NSE dump.
# ============================================================
KITE_TOKENS: Dict[int, str] = {
    738561: "RELIANCE",  341249: "HDFCBANK",  1270529: "ICICIBANK",
    408065: "INFY",      2953217: "TCS",      2714625: "BHARTIARTL",
    424961: "ITC",       2939649: "LT",       492033: "KOTAKBANK",
    1510401: "AXISBANK", 779521: "SBIN",      81153: "BAJFINANCE",
    356865: "HINDUNILVR", 60417: "ASIANPAINT", 2815745: "MARUTI",
    1850625: "HCLTECH",  857857: "SUNPHARMA", 897537: "TITAN",
    2952193: "ULTRACEMCO", 969473: "WIPRO",
    519937: "M&M",       4598529: "NESTLEIND", 3834113: "POWERGRID",
    2977281: "NTPC",     633601: "ONGC",       884737: "TATAMOTORS",
    895745: "TATASTEEL", 3001089: "JSWSTEEL",  6401: "ADANIENT",
    3861249: "ADANIPORTS", 4268801: "BAJAJFINSV", 4267265: "BAJAJ-AUTO",
    345089: "HEROMOTOCO", 232961: "EICHERMOT", 315393: "GRASIM",
    225537: "DRREDDY",   177665: "CIPLA",     2800641: "DIVISLAB",
    157441: "APOLLOHOSP", 140033: "BRITANNIA", 5215745: "COALINDIA",
    134657: "BPCL",      415745: "IOC",       119553: "HDFCLIFE",
    5582849: "SBILIFE",  3465729: "TECHM",    1346049: "INDUSINDBK",
    2889473: "UPL",      878593: "TATACONSUM", 4561409: "LTIM",
}

# ============================================================
# Upstox — instrument_key (str) → ticker
# Format: "NSE_EQ|<ISIN>"
# ============================================================
UPSTOX_KEYS: Dict[str, str] = {
    "NSE_EQ|INE002A01018": "RELIANCE", "NSE_EQ|INE040A01034": "HDFCBANK",
    "NSE_EQ|INE090A01021": "ICICIBANK", "NSE_EQ|INE009A01021": "INFY",
    "NSE_EQ|INE467B01029": "TCS", "NSE_EQ|INE397D01024": "BHARTIARTL",
    "NSE_EQ|INE154A01025": "ITC", "NSE_EQ|INE018A01030": "LT",
    "NSE_EQ|INE237A01028": "KOTAKBANK", "NSE_EQ|INE238A01034": "AXISBANK",
    "NSE_EQ|INE062A01020": "SBIN", "NSE_EQ|INE296A01024": "BAJFINANCE",
    "NSE_EQ|INE030A01027": "HINDUNILVR", "NSE_EQ|INE021A01026": "ASIANPAINT",
    "NSE_EQ|INE585B01010": "MARUTI", "NSE_EQ|INE860A01027": "HCLTECH",
    "NSE_EQ|INE044A01036": "SUNPHARMA", "NSE_EQ|INE280A01028": "TITAN",
    "NSE_EQ|INE481G01011": "ULTRACEMCO", "NSE_EQ|INE075A01022": "WIPRO",
    "NSE_EQ|INE101A01026": "M&M", "NSE_EQ|INE239A01016": "NESTLEIND",
    "NSE_EQ|INE752E01010": "POWERGRID", "NSE_EQ|INE733E01010": "NTPC",
    "NSE_EQ|INE213A01029": "ONGC", "NSE_EQ|INE155A01022": "TATAMOTORS",
    "NSE_EQ|INE081A01020": "TATASTEEL", "NSE_EQ|INE019A01038": "JSWSTEEL",
    "NSE_EQ|INE423A01024": "ADANIENT", "NSE_EQ|INE742F01042": "ADANIPORTS",
    "NSE_EQ|INE918I01018": "BAJAJFINSV", "NSE_EQ|INE917I01010": "BAJAJ-AUTO",
    "NSE_EQ|INE158A01026": "HEROMOTOCO", "NSE_EQ|INE066A01021": "EICHERMOT",
    "NSE_EQ|INE047A01021": "GRASIM", "NSE_EQ|INE089A01023": "DRREDDY",
    "NSE_EQ|INE059A01026": "CIPLA", "NSE_EQ|INE361B01024": "DIVISLAB",
    "NSE_EQ|INE437A01024": "APOLLOHOSP", "NSE_EQ|INE216A01030": "BRITANNIA",
    "NSE_EQ|INE522F01014": "COALINDIA", "NSE_EQ|INE029A01011": "BPCL",
    "NSE_EQ|INE242A01010": "IOC", "NSE_EQ|INE795G01014": "HDFCLIFE",
    "NSE_EQ|INE123W01016": "SBILIFE", "NSE_EQ|INE669C01036": "TECHM",
    "NSE_EQ|INE095A01012": "INDUSINDBK", "NSE_EQ|INE628A01036": "UPL",
    "NSE_EQ|INE192A01025": "TATACONSUM", "NSE_EQ|INE214T01019": "LTIM",
}

# ============================================================
# Angel One — symbol token (str) → ticker (NSE cash)
# ============================================================
ANGEL_TOKENS: Dict[str, str] = {
    "2885": "RELIANCE",   "1333": "HDFCBANK",   "4963": "ICICIBANK",
    "1594": "INFY",       "11536": "TCS",       "10604": "BHARTIARTL",
    "1660": "ITC",        "11483": "LT",        "1922": "KOTAKBANK",
    "5900": "AXISBANK",   "3045": "SBIN",       "317": "BAJFINANCE",
    "1394": "HINDUNILVR", "236": "ASIANPAINT",  "10999": "MARUTI",
    "7229": "HCLTECH",    "3351": "SUNPHARMA",  "3506": "TITAN",
    "11532": "ULTRACEMCO", "3787": "WIPRO",     "2031": "M&M",
    "17963": "NESTLEIND", "14977": "POWERGRID", "11630": "NTPC",
    "2475": "ONGC",       "3456": "TATAMOTORS", "3499": "TATASTEEL",
    "11723": "JSWSTEEL",  "25": "ADANIENT",     "15083": "ADANIPORTS",
    "16675": "BAJAJFINSV", "16669": "BAJAJ-AUTO", "1348": "HEROMOTOCO",
    "910": "EICHERMOT",   "1232": "GRASIM",     "881": "DRREDDY",
    "694": "CIPLA",       "10940": "DIVISLAB",  "157": "APOLLOHOSP",
    "547": "BRITANNIA",   "20374": "COALINDIA", "526": "BPCL",
    "1624": "IOC",        "467": "HDFCLIFE",    "21808": "SBILIFE",
    "13538": "TECHM",     "5258": "INDUSINDBK", "11287": "UPL",
    "3432": "TATACONSUM", "17818": "LTIM",
}
# ============================================================
# ICICI Breeze — symbol token (str) -> ticker (NSE cash)
# Since Breeze uses proprietary stock codes, this maps 
# ICICI stock code -> NSE standard ticker
# ============================================================
BREEZE_TOKENS: Dict[str, str] = {
    "BHAAIR": "BHARTIARTL",
    "DIVLAB": "DIVISLAB",
    "MARUTI": "MARUTI",
    "UNIP": "UPL",
    "LARTOU": "LT",
    "ULTCEM": "ULTRACEMCO",
    "TCS": "TCS",
    "NTPC": "NTPC",
    "JSWSTE": "JSWSTEEL",
    "GRASIM": "GRASIM",
    "HDFBAN": "HDFCBANK",
    "HERHON": "HEROMOTOCO",
    "TECMAH": "TECHM",
    "HINLEV": "HINDUNILVR",
    "POWGRI": "POWERGRID",
    "ADAPOR": "ADANIPORTS",
    "APOHOS": "APOLLOHOSP",
    "INFTEC": "INFY",
    "INDOIL": "IOC",
    "ITC": "ITC",
    "BAAUTO": "BAJAJ-AUTO",
    "LTINFO": "LTIM",
    "MAHMAH": "M&M",
    "COALIN": "COALINDIA",
    "SBILIF": "SBILIFE",
    "ASIPAI": "ASIANPAINT",
    "ONGC": "ONGC",
    "ADAENT": "ADANIENT",
    "RELIND": "RELIANCE",
    "STABAN": "SBIN",
    "SUNPHA": "SUNPHARMA",
    "TATGLO": "TATACONSUM",
    "TATMOT": "TATAMOTORS",
    "TATSTE": "TATASTEEL",
    "TITIND": "TITAN",
    "WIPRO": "WIPRO",
    "HDFSTA": "HDFCLIFE",
    "ICIBAN": "ICICIBANK",
    "INDBA": "INDUSINDBK",
    "BHAPET": "BPCL",
    "BRIIND": "BRITANNIA",
    "AXIBAN": "AXISBANK",
    "CIPLA": "CIPLA",
    "HCLTEC": "HCLTECH",
    "EICMOT": "EICHERMOT",
    "BAFINS": "BAJAJFINSV",
    "NESIND": "NESTLEIND",
    "KOTMAH": "KOTAKBANK",
    "BAJFI": "BAJFINANCE",
    "DRREDD": "DRREDDY",
}


def kite_token_map() -> Dict[int, str]:
    return dict(KITE_TOKENS)


def upstox_instrument_map() -> Dict[str, str]:
    return dict(UPSTOX_KEYS)


def angel_token_map() -> Dict[str, str]:
    return dict(ANGEL_TOKENS)


def breeze_token_map() -> Dict[str, str]:
    try:
        from constants import ICICI_INDEX_MAP
    except ImportError:
        ICICI_INDEX_MAP = {}
    m = dict(BREEZE_TOKENS)
    for std, breeze in ICICI_INDEX_MAP.items():
        m[breeze] = std
    return m


# ============================================================
# Aliceblue — symbol token (str) → ticker (NSE cash)
# Alice Blue uses the standard NSE exchange token IDs (same as Angel)
# ============================================================
ALICEBLUE_TOKENS: Dict[str, str] = ANGEL_TOKENS.copy()
ALICEBLUE_TOKENS.update({
    "26000": "NIFTY",
    "26009": "BANKNIFTY",
    "26037": "FINNIFTY",
    "26074": "MIDCPNIFTY",
    "1": "SENSEX",
    "26013": "NIFTYNXT50"
})

def aliceblue_token_map() -> Dict[str, str]:
    """Alice Blue websocket sends token as '2885'."""
    return ALICEBLUE_TOKENS
