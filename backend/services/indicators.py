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

def stoch(high: List[float], low: List[float], close: List[float], k_period=14, d_period=3):
    if len(close) < k_period:
        return [50.0] * len(close), [50.0] * len(close)
    k_line = []
    for i in range(len(close)):
        if i < k_period - 1:
            k_line.append(50.0)
            continue
        h_max = max(high[i - k_period + 1: i + 1])
        l_min = min(low[i - k_period + 1: i + 1])
        if h_max == l_min:
            k_line.append(50.0)
        else:
            k_line.append(100 * (close[i] - l_min) / (h_max - l_min))
    # d_line is SMA of k_line
    d_line = []
    for i in range(len(k_line)):
        if i < d_period - 1:
            d_line.append(50.0)
            continue
        d_line.append(sum(k_line[i - d_period + 1: i + 1]) / d_period)
    return k_line, d_line

def supertrend(high: List[float], low: List[float], close: List[float], period=10, multiplier=3.0):
    if len(close) < period + 1:
        return [0.0] * len(close), [1] * len(close)
    atr = []
    for i in range(len(close)):
        if i == 0:
            atr.append(high[i] - low[i])
            continue
        tr = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        if i < period:
            atr.append((sum(atr) + tr) / (i + 1))
        else:
            atr.append((atr[-1] * (period - 1) + tr) / period)
            
    st = []
    trend = [] # 1 up, -1 down
    final_upper = [0.0] * len(close)
    final_lower = [0.0] * len(close)
    
    for i in range(len(close)):
        hl2 = (high[i] + low[i]) / 2
        basic_upper = hl2 + multiplier * atr[i]
        basic_lower = hl2 - multiplier * atr[i]
        if i == 0:
            final_upper[i] = basic_upper
            final_lower[i] = basic_lower
            st.append(0.0)
            trend.append(1)
            continue
            
        if basic_upper < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper
        else:
            final_upper[i] = final_upper[i-1]
            
        if basic_lower > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower
        else:
            final_lower[i] = final_lower[i-1]
            
        prev_trend = trend[-1]
        curr_trend = prev_trend
        if prev_trend == 1 and close[i] < final_lower[i]:
            curr_trend = -1
        elif prev_trend == -1 and close[i] > final_upper[i]:
            curr_trend = 1
            
        trend.append(curr_trend)
        st.append(final_lower[i] if curr_trend == 1 else final_upper[i])
        
    return st, trend

