"""Local, dependency-free trade explanation helpers.

This module intentionally does not call external AI services. It keeps the
existing API shape so the UI can run locally while returning deterministic,
rule-based explanations.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict


def _side_from_signal(kind: str, change_pct: float, volume_ratio: float) -> str:
    kind_l = kind.lower()
    if "sell" in kind_l or "short" in kind_l or "bear" in kind_l:
        return "SELL"
    if "buy" in kind_l or "long" in kind_l or "bull" in kind_l:
        return "BUY"
    if change_pct > 0.15 and volume_ratio >= 1.1:
        return "BUY"
    if change_pct < -0.15 and volume_ratio >= 1.1:
        return "SELL"
    return "NEUTRAL"


def _signal_reason(kind: str, side: str, change_pct: float, volume_ratio: float, confidence: float) -> str:
    bits = []
    if abs(change_pct) >= 0.15:
        direction = "up" if change_pct > 0 else "down"
        bits.append(f"price is moving {direction} by {abs(change_pct):.2f}%")
    if volume_ratio >= 1.2:
        bits.append(f"volume is {volume_ratio:.1f}x normal")
    if confidence >= 0.7:
        bits.append("the signal engine confidence is high")
    context = ", and ".join(bits) if bits else "inputs are mixed and do not show a strong edge"
    if side == "NEUTRAL":
        return f"{kind.replace('_', ' ').title()} is neutral because {context}."
    return f"{kind.replace('_', ' ').title()} leans {side} because {context}."


async def stream_explanation(session_id: str, prompt: str) -> AsyncGenerator[str, None]:
    """Return a small local explanation stream for the AI chat endpoint."""
    text = (
        "Local assistant mode is enabled. I can summarize trading inputs using "
        "built-in rules, but no external AI provider is being called.\n\n"
        f"Your prompt: {prompt.strip()[:500] or '(empty)'}"
    )
    yield text


async def explain_signal(session_id: str, signal: Dict[str, Any]) -> Dict[str, Any]:
    """Return rule-based reasoning plus suggested SL/target for a signal."""
    price = float(signal.get("price") or 0)
    kind = str(signal.get("kind") or "signal")
    change_pct = float(signal.get("change_pct") or 0)
    volume_ratio = float(signal.get("volume_ratio") or 1)
    confidence = float(signal.get("confidence") or 0.5)
    side = _side_from_signal(kind, change_pct, volume_ratio)

    if side == "SELL":
        suggested_sl = round(price * 1.003, 2)
        suggested_target = round(price * 0.995, 2)
    elif side == "BUY":
        suggested_sl = round(price * 0.997, 2)
        suggested_target = round(price * 1.005, 2)
    else:
        suggested_sl = round(price * 0.997, 2)
        suggested_target = round(price * 1.003, 2)

    return {
        "reasoning": _signal_reason(kind, side, change_pct, volume_ratio, confidence),
        "suggested_sl": suggested_sl,
        "suggested_target": suggested_target,
        "risk_reward": 1.5,
        "confidence_score": round(max(0.0, min(confidence, 1.0)), 2),
        "side_bias": side,
        "model": "local-rules",
    }


async def analyse_window(session_id: str, symbol: str, window: list[dict]) -> Dict[str, Any]:
    """Detect simple local price/volume anomalies from a recent OHLCV window."""
    if not window or len(window) < 10:
        return {"anomaly": False, "severity": "low", "reason": "insufficient data"}

    closes = [float(b.get("close") or 0) for b in window[-30:]]
    vols = [float(b.get("volume") or 0) for b in window[-30:]]
    first = max(closes[0], 0.01)
    pct_move = (closes[-1] - first) / first * 100
    avg_vol = sum(vols[:-1]) / max(len(vols) - 1, 1)
    vol_ratio = vols[-1] / max(avg_vol, 1)

    anomaly = abs(pct_move) >= 0.8 or vol_ratio >= 2.5
    if abs(pct_move) >= 1.5 or vol_ratio >= 4:
        severity = "high"
    elif anomaly:
        severity = "medium"
    else:
        severity = "low"

    if anomaly:
        reason = f"{symbol} moved {pct_move:.2f}% with {vol_ratio:.1f}x volume"
    else:
        reason = "within local thresholds"
    return {"anomaly": anomaly, "severity": severity, "reason": reason[:120]}
