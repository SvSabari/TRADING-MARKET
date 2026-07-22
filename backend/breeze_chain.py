"""
ICICI Breeze Option Chain builder using REST API (get_option_chain_quotes).
Uses NFO.csv to find valid expiry dates, avoiding costly API probing.
Respects Breeze rate limits with 60s caching at the route level.
"""
import asyncio
import os
import pandas as pd
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Module-level cache for the NFO dataframe
_NFO_DF = None
_BFO_DF = None


def _load_nfo_df():
    """Load and cache the NFO instrument master."""
    global _NFO_DF
    if _NFO_DF is None:
        csv_path = os.path.join(os.path.dirname(__file__), "NFO.csv")
        df = pd.read_csv(csv_path, low_memory=False)
        df["Strike"] = pd.to_numeric(df["Strike Price"], errors="coerce")
        df["ExpiryDate"] = pd.to_datetime(df["Expiry Date"]).dt.date
        _NFO_DF = df
    return _NFO_DF


def _load_bfo_df():
    """Load and cache the BFO instrument master."""
    global _BFO_DF
    if _BFO_DF is None:
        csv_path = os.path.join(os.path.dirname(__file__), "BFO.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, low_memory=False)
            df["Strike"] = pd.to_numeric(df["Strike Price"], errors="coerce")
            df["ExpiryDate"] = pd.to_datetime(df["Expiry Date"]).dt.date
            _BFO_DF = df
        else:
            _BFO_DF = pd.DataFrame(columns=["Symbol", "ExpiryDate"])
    return _BFO_DF


def _get_available_expiries(symbol: str) -> list[str]:
    """
    Get available option expiry dates for a symbol from the NFO/BFO CSV.
    Returns list of "YYYY-MM-DD" strings for future expiries.
    """
    try:
        if symbol in ("SENSEX", "BANKEX"):
            df = _load_bfo_df()
        else:
            df = _load_nfo_df()

        today = datetime.now(timezone.utc).date()
        sym_df = df[df["Symbol"] == symbol].copy()
        sym_df = sym_df[sym_df["Instrument Type"].isin(["OPTIDX", "OPTSTK", "IO", "SO"])]
        sym_df = sym_df[sym_df["ExpiryDate"] >= today]

        if sym_df.empty:
            return []

        return [d.strftime("%Y-%m-%d") for d in sorted(sym_df["ExpiryDate"].unique())]
    except Exception as e:
        logger.warning("Failed to get expiries from CSV: %s", e)
        return []


def _get_trend(coi, cltp):
    if coi > 0 and cltp > 0: return "Long Buildup"
    if coi > 0 and cltp < 0: return "Short Buildup"
    if coi < 0 and cltp < 0: return "Long Unwinding"
    if coi < 0 and cltp > 0: return "Short Covering"
    if cltp > 0: return "Bullish"
    if cltp < 0: return "Bearish"
    return "Neutral"


async def build_breeze_chain(breeze, symbol: str = "NIFTY", expiry: str = None) -> dict | None:
    """
    Build option chain using ICICI Breeze REST API.
    breeze: BreezeClient instance (has get_quotes and get_option_chain_quotes methods)

    Only makes 3 API calls total:
      1. get_quotes (spot price)
      2. get_option_chain_quotes (calls)
      3. get_option_chain_quotes (puts)
    """
    try:
        # --- 1. Map symbol to Breeze codes ---
        stock_map = {
            "NIFTY":      ("NIFTY",  "NFO", "NSE"),
            "BANKNIFTY":  ("CNXBAN", "NFO", "NSE"),
            "FINNIFTY":   ("NIFFIN", "NFO", "NSE"),
            "MIDCPNIFTY": ("NIFMID", "NFO", "NSE"),
            "NIFTYNXT50": ("CNXNXT", "NFO", "NSE"),
            "SENSEX":     ("BSESEN", "BFO", "BSE"),
            "BANKEX":     ("BSEBAN", "BFO", "BSE"),
        }
        breeze_stock, breeze_exch, breeze_spot_exch = stock_map.get(
            symbol, ("NIFTY", "NFO", "NSE")
        )

        # --- 2. Get expiry dates from NFO.csv (no API calls!) ---
        available_expiries = _get_available_expiries(symbol)
        if not available_expiries:
            logger.error("No expiry dates found in NFO.csv for %s", symbol)
            return None

        # Choose requested expiry, or default to nearest
        if expiry and expiry in available_expiries:
            chosen = expiry
        else:
            chosen = available_expiries[0]

        chosen_dt = datetime.strptime(chosen, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        chosen_breeze = chosen_dt.strftime("%Y-%m-%dT06:00:00.000Z")

        # --- 3. Fetch spot price (1 API call) ---
        spot_price = 0.0
        try:
            spot_resp = await asyncio.to_thread(
                breeze.get_quotes,
                stock_code=breeze_stock,
                exchange_code=breeze_spot_exch,
                product_type="cash"
            )
            if (spot_resp and isinstance(spot_resp, dict)
                    and spot_resp.get("Success")):
                rows = spot_resp["Success"]
                for row in rows:
                    ltp = float(row.get("ltp") or 0)
                    if ltp > 0:
                        spot_price = ltp
                        break
        except Exception as e:
            logger.warning("Breeze get_quotes spot failed: %s", e)

        # Fallback to tick engine
        if spot_price == 0.0:
            from services.market_data import tick_engine
            spot_price = tick_engine.prices.get(symbol, 0.0)

        if spot_price == 0.0:
            logger.error("Breeze option chain: could not get spot for %s", symbol)
            return None

        # --- 4. Fetch calls and puts (2 API calls) ---
        all_items = []
        for right in ("call", "put"):
            try:
                r = await asyncio.to_thread(
                    breeze.get_option_chain_quotes,
                    stock_code=breeze_stock,
                    exchange_code=breeze_exch,
                    product_type="options",
                    expiry_date=chosen_breeze,
                    right=right,
                    strike_price=""
                )
                if r and isinstance(r, dict):
                    if r.get("Success"):
                        all_items.extend(r["Success"])
                    elif r.get("Status") == 5:
                        # Rate limit hit — abort fetch so we fallback to cached chain
                        logger.warning("Breeze rate limit hit for %s %s. Aborting.", right, symbol)
                        return None
            except Exception as e:
                logger.warning("Breeze get_option_chain_quotes %s failed: %s", right, e)

        if not all_items:
            logger.error("Breeze option chain: no option data for %s %s", symbol, chosen)
            return None

        # --- 5. Build strike map ---
        strike_map: dict[float, dict] = {}
        for item in all_items:
            try:
                strike = float(item.get("strike_price", 0))
                right_key = item.get("right", "").lower()
                if strike == 0:
                    continue
                if strike not in strike_map:
                    strike_map[strike] = {"CE": None, "PE": None}

                ltp = float(item.get("ltp", 0) or 0)
                prev = float(item.get("previous_close", ltp) or ltp)
                change_ltp = ltp - prev
                oi = float(item.get("open_interest", 0) or 0)
                change_oi = float(item.get("chnge_oi", 0) or 0)

                data = {
                    "oi": oi, "change_oi": change_oi,
                    "ltp": ltp, "change_ltp": change_ltp,
                    "trend": _get_trend(change_oi, change_ltp),
                }
                if right_key == "call":
                    strike_map[strike]["CE"] = data
                elif right_key == "put":
                    strike_map[strike]["PE"] = data
            except Exception:
                continue

        # --- 6. Compute ATM and select ±15 strikes ---
        unique_strikes = sorted(strike_map.keys())
        if len(unique_strikes) < 2:
            return None

        step = unique_strikes[1] - unique_strikes[0]
        if step <= 0:
            step = 50.0

        atm = round(spot_price / step) * step

        if atm in unique_strikes:
            atm_idx = unique_strikes.index(atm)
        else:
            atm_idx = min(range(len(unique_strikes)),
                          key=lambda i: abs(unique_strikes[i] - atm))

        start_idx = max(0, atm_idx - 15)
        end_idx = min(len(unique_strikes), start_idx + 31)

        # --- 7. Build rows ---
        empty = {"oi": 0, "change_oi": 0, "ltp": 0.0, "change_ltp": 0.0, "trend": "Neutral"}
        rows = []
        for k in unique_strikes[start_idx:end_idx]:
            ce = strike_map[k]["CE"] or empty
            pe = strike_map[k]["PE"] or empty
            rows.append({
                "strike":        k,
                "ce_oi":         ce["oi"],        "ce_iv":  0.0,
                "ce_ltp":        ce["ltp"],       "ce_change_ltp": ce["change_ltp"],
                "ce_change_oi":  ce["change_oi"], "ce_trend": ce["trend"],
                "pe_oi":         pe["oi"],        "pe_iv":  0.0,
                "pe_ltp":        pe["ltp"],       "pe_change_ltp": pe["change_ltp"],
                "pe_change_oi":  pe["change_oi"], "pe_trend": pe["trend"],
            })

        return {
            "spot":               spot_price,
            "atm":                atm,
            "rows":               rows,
            "source":             "breeze-rest",
            "expiry":             chosen,
            "available_expiries": available_expiries,
        }

    except Exception as e:
        logger.error("Breeze option chain fatal error: %s", e, exc_info=True)
        return None
