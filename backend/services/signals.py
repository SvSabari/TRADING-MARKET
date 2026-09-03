"""Heuristic signal engine: build-ups, traps, breakouts, reversals.

Operates on the in-memory tick history maintained by `tick_engine`.
Returns recent signals for the dashboard. This is deliberately simple —
the goal is realistic-looking signals for the UI, not a profitable model.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Dict, List

from constants import ALL_SYMBOLS
from services.market_data import tick_engine


def _recent(symbol: str, n: int = 60) -> List[dict]:
    hist = tick_engine.get_history(symbol)
    return hist[-n:] if hist else []


def detect_signals() -> List[Dict]:
    out: List[Dict] = []
    for s in ALL_SYMBOLS:
        h = _recent(s, 60)
        if len(h) < 20:
            continue
        prices = [r["ltp"] for r in h]
        vols = [r["volume"] for r in h]
        last = prices[-1]
        first = prices[0]
        change = (last - first) / first * 100
        avg_vol = statistics.mean(vols)
        last_vol = vols[-1]
        std_p = statistics.pstdev(prices) or 0.0001
        z = (last - statistics.mean(prices)) / std_p
        kind = None
        confidence = 0.5
        
        # Calculate a deterministic data-driven confidence boost based on volume and volatility
        vol_boost = min(0.15, (last_vol / avg_vol) * 0.05) if avg_vol > 0 else 0
        z_boost = min(0.15, abs(z) * 0.05)
        
        if change > 0.05 and last_vol > avg_vol * 1.2:
            kind = "long_buildup"
            confidence = min(0.98, 0.6 + abs(change) + vol_boost + z_boost)
        elif change < -0.05 and last_vol > avg_vol * 1.2:
            kind = "short_buildup"
            confidence = min(0.98, 0.6 + abs(change) + vol_boost + z_boost)
        elif abs(z) > 1.8 and abs(change) > 0.02:
            kind = "breakout" if z > 0 else "breakdown"
            confidence = min(0.98, 0.55 + abs(z) / 10 + vol_boost)
        elif change > 0.04 and avg_vol > 2 and last_vol <= avg_vol * 0.4:
            kind = "bull_trap"
            confidence = min(0.95, 0.60 + z_boost)
        elif change < -0.04 and avg_vol > 2 and last_vol <= avg_vol * 0.4:
            kind = "bear_trap"
            confidence = min(0.95, 0.60 + z_boost)
            
        if kind:
            safe_avg_vol = avg_vol if avg_vol > 0 else 1
            out.append({
                "symbol": s,
                "kind": kind,
                "price": last,
                "change_pct": round(change, 3),
                "volume_ratio": round(last_vol / safe_avg_vol, 2),
                "confidence": round(confidence, 2),
                "ts": h[-1]["ts"], # Use the actual timestamp of the last tick
            })
    # sort by confidence desc
    out.sort(key=lambda x: x["confidence"], reverse=True)
    return out[:25]
