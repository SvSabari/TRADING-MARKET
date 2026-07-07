"""Lightweight technical indicators used by the chart endpoint."""
from __future__ import annotations

from typing import List


def ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values: List[float], period: int = 14) -> List[float]:
    if len(values) < period + 1:
        return [50.0] * len(values)
    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(values) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    # simplified: fill RSI for last value only, repeat for length
    rs = avg_gain / avg_loss if avg_loss else 100
    rsi_val = 100 - 100 / (1 + rs)
    return [50.0] * (len(values) - 1) + [rsi_val]


def vwap(prices: List[float], volumes: List[int]) -> List[float]:
    cum_pv = 0.0
    cum_v = 0
    out = []
    for p, v in zip(prices, volumes):
        cum_pv += p * v
        cum_v += v
        out.append(cum_pv / cum_v if cum_v else p)
    return out


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    e_fast = ema(values, fast)
    e_slow = ema(values, slow)
    macd_line = [a - b for a, b in zip(e_fast, e_slow)]
    sig = ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, sig)]
    return macd_line, sig, hist
