"""Heuristic signal engine: build-ups, traps, breakouts, reversals.

Operates on the in-memory tick history maintained by `tick_engine`.
Returns recent signals for the dashboard. This is deliberately simple —
the goal is realistic-looking signals for the UI, not a profitable model.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Dict, List

from constants import NIFTY_50
from services.market_data import tick_engine


def _recent(symbol: str, n: int = 60) -> List[dict]:
    hist = tick_engine.get_history(symbol)
    return hist[-n:] if hist else []


def detect_signals() -> List[Dict]:
    out: List[Dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for s in NIFTY_50:
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
        if change > 0.4 and last_vol > avg_vol * 1.6:
            kind = "long_buildup"
            confidence = min(0.95, 0.6 + change / 5)
        elif change < -0.4 and last_vol > avg_vol * 1.6:
            kind = "short_buildup"
            confidence = min(0.95, 0.6 + abs(change) / 5)
        elif abs(z) > 1.8:
            kind = "breakout" if z > 0 else "reversal"
            confidence = min(0.95, 0.55 + abs(z) / 10)
        elif change > 0.3 and last_vol < avg_vol * 0.6:
            kind = "bull_trap"
            confidence = 0.65
        elif change < -0.3 and last_vol < avg_vol * 0.6:
            kind = "bear_trap"
            confidence = 0.65
        if kind:
            out.append({
                "symbol": s,
                "kind": kind,
                "price": last,
                "change_pct": round(change, 3),
                "volume_ratio": round(last_vol / avg_vol, 2),
                "confidence": round(confidence, 2),
                "ts": now_iso,
            })
    # sort by confidence desc
    out.sort(key=lambda x: x["confidence"], reverse=True)
    return out[:25]
