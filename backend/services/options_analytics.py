"""Option-chain analytics — live Kite quote() for ATM±15 strikes, with
synthetic fallback when the user has no connected Kite session.

Also computes Black-Scholes implied volatility (Newton-Raphson) and
analytical Greeks (delta, gamma, theta, vega, rho) per strike."""
from __future__ import annotations

import math
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from services.greeks import greeks as bs_greeks, implied_vol
from services.kite_client import KiteService
from services.market_data import tick_engine

NIFTY_SPOT_PROXY = "RELIANCE"
STRIKE_RANGE = 15
RISK_FREE_RATE = float(os.environ.get("RISK_FREE_RATE", "0.07"))

INDEX_CONFIG = {
    "NIFTY": {"spot": "NSE:NIFTY 50", "prefix": "NFO:NIFTY", "step": 50},
    "BANKNIFTY": {"spot": "NSE:NIFTY BANK", "prefix": "NFO:BANKNIFTY", "step": 100},
    "FINNIFTY": {"spot": "NSE:NIFTY FIN SERVICE", "prefix": "NFO:FINNIFTY", "step": 50},
    "MIDCPNIFTY": {"spot": "NSE:NIFTY MID SELECT", "prefix": "NFO:MIDCPNIFTY", "step": 25},
    "SENSEX": {"spot": "BSE:SENSEX", "prefix": "BFO:SENSEX", "step": 100},
    "BANKEX": {"spot": "BSE:BANKEX", "prefix": "BFO:BANKEX", "step": 100},
}


def _synth_spot(symbol: str) -> float:
    if symbol == "BANKNIFTY":
        big = ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"]
        avg = sum(tick_engine.prices.get(s, 1000) for s in big) / len(big)
        return round(avg * 38.8, 2)
    elif symbol == "FINNIFTY":
        big = ["HDFCBANK", "ICICIBANK", "BAJFINANCE", "BAJAJFINSV", "SBIN"]
        avg = sum(tick_engine.prices.get(s, 1000) for s in big) / len(big)
        return round(avg * 9.4, 2)
    elif symbol == "MIDCPNIFTY":
        return 12000.0
    # default NIFTY
    big = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS"]
    avg = sum(tick_engine.prices.get(s, 1000) for s in big) / len(big)
    return round(avg * 10.5, 2)


def build_synthetic_chain(spot: float | None = None, symbol: str = "NIFTY", expiry: str = None) -> Dict:
    if spot is None:
        spot = _synth_spot(symbol)
    step = INDEX_CONFIG.get(symbol, INDEX_CONFIG["NIFTY"])["step"]
    atm = round(spot / step) * step
    strikes = [atm + (i - STRIKE_RANGE) * step for i in range(STRIKE_RANGE * 2 + 1)]
    rng = random.Random(int(spot) % 9999)
    rows = []
    
    def get_trend(coi, cltp):
        if coi > 0 and cltp > 0: return "Long Buildup"
        if coi > 0 and cltp < 0: return "Short Buildup"
        if coi < 0 and cltp < 0: return "Long Unwinding"
        if coi < 0 and cltp > 0: return "Short Covering"
        return "Neutral"
        
    for k in strikes:
        diff = (k - spot) / spot
        ce_iv = 12 + abs(diff) * 60 + rng.uniform(-1.5, 1.5)
        pe_iv = 12 + abs(diff) * 60 + rng.uniform(-1.5, 1.5)
        ce_oi = max(1000, int(900000 * math.exp(-((k - atm) ** 2) / (2 * (step * 5) ** 2)) + rng.randint(-50000, 50000)))
        pe_oi = max(1000, int(900000 * math.exp(-((k - atm) ** 2) / (2 * (step * 5) ** 2)) + rng.randint(-50000, 50000)))
        ce_ltp = max(0.5, spot - k + rng.uniform(20, 80)) if k < spot else max(0.5, rng.uniform(5, 60))
        pe_ltp = max(0.5, k - spot + rng.uniform(20, 80)) if k > spot else max(0.5, rng.uniform(5, 60))
        
        ce_change_oi = rng.randint(-50000, 50000)
        pe_change_oi = rng.randint(-50000, 50000)
        ce_change_ltp = rng.uniform(-5.0, 5.0)
        pe_change_ltp = rng.uniform(-5.0, 5.0)
        
        rows.append({
            "strike": k,
            "ce_oi": ce_oi, "ce_iv": round(ce_iv, 2), "ce_ltp": round(ce_ltp, 2),
            "ce_change_oi": ce_change_oi, "ce_change_ltp": round(ce_change_ltp, 2),
            "ce_trend": get_trend(ce_change_oi, ce_change_ltp),
            "pe_oi": pe_oi, "pe_iv": round(pe_iv, 2), "pe_ltp": round(pe_ltp, 2),
            "pe_change_oi": pe_change_oi, "pe_change_ltp": round(pe_change_ltp, 2),
            "pe_trend": get_trend(pe_change_oi, pe_change_ltp),
        })
    return {
        "spot": spot,
        "atm": atm,
        "rows": rows,
        "source": "synthetic",
        "expiry": expiry or datetime.now(timezone.utc).strftime("%d %b").upper(),
        "available_expiries": [expiry] if expiry else [datetime.now(timezone.utc).strftime("%d %b").upper()]
    }


def _nearest_weekly_expiry_date() -> datetime:
    today = datetime.now(timezone.utc).date()
    days_to_thursday = (3 - today.weekday()) % 7 or 7
    thu = today + timedelta(days=days_to_thursday)
    # market close ~3:30 PM IST
    return datetime(thu.year, thu.month, thu.day, 10, 0, tzinfo=timezone.utc)


def _nearest_weekly_expiry() -> str:
    thu = _nearest_weekly_expiry_date()
    yy = thu.strftime("%y")
    mon = thu.strftime("%b").upper()
    return f"{yy}{mon}"


def _time_to_expiry_years() -> float:
    now = datetime.now(timezone.utc)
    expiry = _nearest_weekly_expiry_date()
    seconds = max(60.0, (expiry - now).total_seconds())
    return seconds / (365.0 * 24 * 3600)


def _compute_iv_and_greeks(rows: List[Dict], spot: float) -> None:
    """In-place: backfill iv/greeks for each row using the row's LTP.

    Guarantees ce_greeks/pe_greeks are always populated (uses the seeded
    synthetic IV as a fallback when the BS solver fails to converge —
    happens for deep ITM/OTM strikes where premium ≈ intrinsic).
    """
    T = _time_to_expiry_years()
    r = RISK_FREE_RATE
    for row in rows:
        K = float(row["strike"])
        # CE
        ce_ltp = float(row.get("ce_ltp", 0) or 0)
        iv = implied_vol(market_price=ce_ltp, S=spot, K=K, T=T, r=r, opt="C") if ce_ltp > 0.05 else None
        if iv is None or iv <= 0:
            iv = max(0.01, float(row.get("ce_iv", 15.0)) / 100.0)
        else:
            row["ce_iv"] = round(iv * 100, 2)
        row["ce_greeks"] = bs_greeks(S=spot, K=K, T=T, r=r, sigma=iv, opt="C")
        # PE
        pe_ltp = float(row.get("pe_ltp", 0) or 0)
        iv = implied_vol(market_price=pe_ltp, S=spot, K=K, T=T, r=r, opt="P") if pe_ltp > 0.05 else None
        if iv is None or iv <= 0:
            iv = max(0.01, float(row.get("pe_iv", 15.0)) / 100.0)
        else:
            row["pe_iv"] = round(iv * 100, 2)
        row["pe_greeks"] = bs_greeks(S=spot, K=K, T=T, r=r, sigma=iv, opt="P")


def build_kite_chain(kite: KiteService, symbol: str) -> Optional[Dict]:
    """Try to build a real option chain from kite.quote(); return None on any error."""
    conf = INDEX_CONFIG.get(symbol, INDEX_CONFIG["NIFTY"])
    step = conf["step"]
    try:
        spot_q = kite.ltp([conf["spot"]])
        spot = float(list(spot_q.values())[0]["last_price"])
    except Exception:
        return None
    atm = round(spot / step) * step
    strikes = [atm + (i - STRIKE_RANGE) * step for i in range(STRIKE_RANGE * 2 + 1)]
    expiry_code = _nearest_weekly_expiry()
    instruments: List[str] = []
    prefix = conf["prefix"]
    for k in strikes:
        instruments.append(f"{prefix}{expiry_code}{int(k)}CE")
        instruments.append(f"{prefix}{expiry_code}{int(k)}PE")
    try:
        q = kite.quotes(instruments)
    except Exception:
        return None
    rows = []
    for k in strikes:
        ce = q.get(f"{prefix}{expiry_code}{int(k)}CE", {})
        pe = q.get(f"{prefix}{expiry_code}{int(k)}PE", {})
        rows.append({
            "strike": k,
            "ce_oi": int(ce.get("oi", 0)),
            "ce_iv": 0.0,  # Kite does not provide IV; compute later if needed
            "ce_ltp": float(ce.get("last_price", 0) or 0),
            "ce_change_oi": int(ce.get("oi_day_high", 0) - ce.get("oi_day_low", 0)) if ce else 0,
            "pe_oi": int(pe.get("oi", 0)),
            "pe_iv": 0.0,
            "pe_ltp": float(pe.get("last_price", 0) or 0),
            "pe_change_oi": int(pe.get("oi_day_high", 0) - pe.get("oi_day_low", 0)) if pe else 0,
        })
    return {"spot": spot, "atm": atm, "rows": rows, "source": "kite-live", "expiry": expiry_code}


async def build_option_chain(db=None, user_id: str | None = None, symbol: str = "NIFTY", expiry: str = None) -> Dict:
    
    from services.market_data import tick_engine
    
    if db is not None and user_id:
        from services.live_feed_manager import live_feed_manager
        
        active_broker = None
        if live_feed_manager._active:
            active_broker = getattr(live_feed_manager._active, "name", None) or live_feed_manager._active_broker
            
        if not active_broker:
            # Fallback to database
            conn = await db.broker_connections.find_one({"user_id": user_id, "is_data_feed": True, "connected": True})
            if conn:
                active_broker = conn.get("broker")
        
        if active_broker == "zerodha":
            from zerodha_chain import build_zerodha_chain
            from services.brokers.zerodha_client import get_user_zerodha_client
            kite = await get_user_zerodha_client(db, user_id)
            if kite is not None:
                live = await build_zerodha_chain(kite, symbol, expiry)
                if live is not None:
                    _compute_iv_and_greeks(live["rows"], live["spot"])
                    return live
                    
        elif active_broker == "aliceblue":
            from services.brokers.aliceblue_client import get_user_aliceblue_client
            from aliceblue_chain import build_aliceblue_chain
            alice = await get_user_aliceblue_client(db, user_id)
            if alice is not None:
                live = await build_aliceblue_chain(alice, symbol, expiry)
                if live is not None:
                    _compute_iv_and_greeks(live["rows"], live["spot"])
                    return live
                    
        elif active_broker == "breeze":
            from breeze_chain import build_breeze_chain
            from services.brokers.breeze_client import get_user_breeze_client
            breeze = await get_user_breeze_client(db, user_id)
            if breeze is not None:
                live = await build_breeze_chain(breeze, symbol, expiry)
                if live is not None:
                    _compute_iv_and_greeks(live["rows"], live["spot"])
                    return live
            else:
                return {
                    "spot": 0.0,
                    "atm": 0,
                    "rows": [],
                    "source": "BREEZE_SESSION_EXPIRED",
                    "expiry": expiry or datetime.now(timezone.utc).strftime("%d %b").upper(),
                    "available_expiries": []
                }
                
    # STRICT REQUIREMENT: No fake data. If all broker connections fail, return an empty real-time structure.
    return {
        "spot": 0.0,
        "atm": 0,
        "rows": [],
        "source": "NO_BROKER_DATA",
        "expiry": expiry or datetime.now(timezone.utc).strftime("%d %b").upper(),
        "available_expiries": []
    }


def pcr(chain: Dict) -> float:
    pe = sum(r["pe_oi"] for r in chain["rows"])
    ce = sum(r["ce_oi"] for r in chain["rows"]) or 1
    return round(pe / ce, 3)


def max_pain(chain: Dict) -> int:
    strikes = [r["strike"] for r in chain.get("rows", [])]
    if not strikes: return 0
    best_strike = strikes[0]
    best_pain = float("inf")
    for k in strikes:
        pain = 0.0
        for r in chain["rows"]:
            if r["strike"] < k:
                pain += (k - r["strike"]) * r["ce_oi"]
            else:
                pain += (r["strike"] - k) * r["pe_oi"]
        if pain < best_pain:
            best_pain = pain
            best_strike = k
    return best_strike


def oi_heatmap(chain: Dict) -> List[Dict]:
    return [{"strike": r["strike"], "ce_oi": r["ce_oi"], "pe_oi": r["pe_oi"]} for r in chain["rows"]]


def iv_smile(chain: Dict) -> List[Dict]:
    return [{"strike": r["strike"], "ce_iv": r["ce_iv"], "pe_iv": r["pe_iv"]} for r in chain["rows"]]
