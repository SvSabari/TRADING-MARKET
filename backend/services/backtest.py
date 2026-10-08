"""Real backtester that reads captured MySQL tick data.

Trade Modes (passed via params["trade_mode"]):
  - "NONE"  -> Stock / Index: trade the underlying price directly, no options.
  - "AUTO"  -> Options Automatic: CE on bullish signal (+1), PE on bearish signal (-1).
  - "CE"    -> Force Call (CE): every option leg is CE regardless of signal direction.
  - "PE"    -> Force Put  (PE): every option leg is PE regardless of signal direction.

Option prices come ONLY from the option_candles MySQL table.
If data is missing, the trade is logged with entry_source="NO DATA" and pnl=0.
No simulation, no estimated price, no fallback arithmetic.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from db import AsyncSessionLocal
from sqlalchemy import select, func, desc, and_
from models import MarketCandle, OptionCandle
from services.sim_state import SimState

logger = logging.getLogger("backtest")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

async def _load_symbol_data(symbol: str, period_days: int) -> pd.DataFrame:
    """Fetch historical MarketCandle rows from MySQL for the given symbol."""
    try:
        async with AsyncSessionLocal() as session:
            stmt_dates = (
                select(func.date(MarketCandle.ts).label("day"))
                .where(MarketCandle.symbol == symbol.upper())
                .distinct()
                .order_by(desc("day"))
                .limit(period_days)
            )
            result = await session.execute(stmt_dates)
            dates = sorted([str(row[0]) for row in result.fetchall()])
            if not dates:
                return pd.DataFrame()

            available_days = len(dates)
            missing_days = max(0, period_days - available_days)
            if missing_days > 0:
                logger.info(
                    "Requested %d days for %s, only %d days available in DB.",
                    period_days, symbol, available_days
                )

            start_time = datetime.strptime(dates[0], "%Y-%m-%d")
            end_time = datetime.strptime(dates[-1], "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )

            stmt_candles = (
                select(MarketCandle)
                .where(
                    MarketCandle.symbol == symbol.upper(),
                    MarketCandle.ts >= start_time,
                    MarketCandle.ts <= end_time,
                )
                .order_by(MarketCandle.ts)
            )
            result2 = await session.execute(stmt_candles)
            rows = result2.scalars().all()
            if not rows:
                return pd.DataFrame()

            docs = [
                {"ts": r.ts, "open": r.open, "high": r.high,
                 "low": r.low, "close": r.close, "volume": r.volume}
                for r in rows
            ]
            df = pd.DataFrame(docs)
            df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
            df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
            return df

    except Exception as e:
        logger.error("_load_symbol_data error: %s", e)
        return pd.DataFrame()


import os
import pandas as pd

def _read_parquet_premium(symbol: str, strike: float, opt_type: str, ts_utc: datetime, window_seconds: int = 1800):
    try:
        date_str = ts_utc.strftime("%Y-%m-%d")
        file_path = os.path.join(os.path.dirname(__file__), "..", "data", "options_history", f"{symbol}_options_{date_str}.parquet")
        if not os.path.exists(file_path):
            return None, None
            
        df = pd.read_parquet(file_path)
        if 'timestamp' not in df.columns: return None, None
        
        # Ensure UTC
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
        else:
            df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')
            
        if ts_utc.tzinfo is None:
            ts_utc = ts_utc.replace(tzinfo=timezone.utc)
            
        # Filter for future timestamps
        future_df = df[df['timestamp'] >= ts_utc]
        if future_df.empty: return None, None
        
        # Exact strike
        exact_df = future_df[future_df['strike'] == float(strike)]
        if not exact_df.empty:
            row = exact_df.iloc[0]
            if (row['timestamp'] - ts_utc).total_seconds() <= window_seconds:
                ltp = float(row['ce_ltp']) if opt_type.upper() == "CE" else float(row['pe_ltp'])
                if ltp > 0: return ltp, "REAL_EXACT"
                    
        # Fallback
        row = future_df.iloc[0]
        if (row['timestamp'] - ts_utc).total_seconds() <= window_seconds:
            ltp = float(row['ce_ltp']) if opt_type.upper() == "CE" else float(row['pe_ltp'])
            if ltp > 0: return ltp, "REAL_FALLBACK"
                
    except Exception as e:
        logger.error(f"Parquet read error: {e}")
    return None, None

async def _fetch_option_premium(
    symbol: str,
    strike: float,
    opt_type: str,
    ts_utc: datetime,
    window_seconds: int = 1800,
) -> tuple:
    ltp, source = _read_parquet_premium(symbol, strike, opt_type, ts_utc, window_seconds)
    if ltp is not None:
        return ltp, strike, "N/A", source
    return None, None, None, "NO DATA"

async def _fetch_exit_premium(
    symbol: str,
    strike: float,
    opt_type: str,
    ts_utc: datetime,
    window_seconds: int = 1800,
) -> tuple:
    ltp, source = _read_parquet_premium(symbol, strike, opt_type, ts_utc, window_seconds)
    if ltp is not None:
        return ltp, source
    return None, "NO DATA"



# ---------------------------------------------------------------------------
# Resample
# ---------------------------------------------------------------------------

def _resample(df: pd.DataFrame, rule: str = "1min") -> pd.DataFrame:
    if df.empty:
        return df
    df = df.set_index("ts")
    agg = df.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna().reset_index()
    return agg


# ---------------------------------------------------------------------------
# Strategy signal generators
# ---------------------------------------------------------------------------

def _ema(values: pd.Series, period: int) -> pd.Series:
    return values.ewm(span=period, adjust=False).mean()


def _signals_ema_crossover(df: pd.DataFrame, params: Dict) -> pd.Series:
    fast = int(params.get("fast", 9))
    slow = int(params.get("slow", 21))
    if len(df) < slow + 2:
        return pd.Series([0] * len(df), index=df.index)
    ef = _ema(df["close"], fast)
    es = _ema(df["close"], slow)
    cross_up = (ef.shift(1) <= es.shift(1)) & (ef > es)
    cross_dn = (ef.shift(1) >= es.shift(1)) & (ef < es)
    sig = pd.Series(0, index=df.index)
    sig[cross_up] = 1
    sig[cross_dn] = -1
    return sig


def _signals_vwap_scalping(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 10:
        return pd.Series([0] * len(df), index=df.index)
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vwap = (tp * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, 1)
    z = (df["close"] - vwap) / vwap
    sig = pd.Series(0, index=df.index)
    sig[z < -float(params.get("entry_z", 0.002))] = 1
    sig[z > float(params.get("entry_z", 0.002))] = -1
    sig[z.abs() < float(params.get("exit_z", 0.0005))] = 2
    return sig


def _signals_oi_breakout(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    win = int(params.get("window", 20))
    high_n = df["high"].rolling(win).max()
    low_n = df["low"].rolling(win).min()
    sig = pd.Series(0, index=df.index)
    sig[df["close"] > high_n.shift(1)] = 1
    sig[df["close"] < low_n.shift(1)] = -1
    return sig


def _signals_smart_money(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    ret = df["close"].pct_change()
    vol_z = (df["volume"] - df["volume"].rolling(20).mean()) / (
        df["volume"].rolling(20).std().replace(0, 1)
    )
    sig = pd.Series(0, index=df.index)
    sig[(ret > 0.001) & (vol_z > 1.5)] = 1
    sig[(ret < -0.001) & (vol_z > 1.5)] = -1
    return sig


def _signals_gamma_scalping(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 14:
        return pd.Series([0] * len(df), index=df.index)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    sma = df["close"].rolling(14).mean()
    sig = pd.Series(0, index=df.index)
    sig[(df["close"] - sma) > 1.2 * atr] = -1
    sig[(sma - df["close"]) > 1.2 * atr] = 1
    return sig


def _signals_supertrend(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 14:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 10))
    multiplier = float(params.get("multiplier", 3.0))
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    direction = pd.Series(1, index=df.index)
    for i in range(period, len(df)):
        prev_upper = upper.iloc[i - 1]
        prev_lower = lower.iloc[i - 1]
        upper.iloc[i] = upper.iloc[i] if upper.iloc[i] < prev_upper or df["close"].iloc[i - 1] > prev_upper else prev_upper
        lower.iloc[i] = lower.iloc[i] if lower.iloc[i] > prev_lower or df["close"].iloc[i - 1] < prev_lower else prev_lower
        if direction.iloc[i - 1] == -1 and df["close"].iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif direction.iloc[i - 1] == 1 and df["close"].iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    sig = pd.Series(0, index=df.index)
    sig[(direction.shift(1) == -1) & (direction == 1)] = 1
    sig[(direction.shift(1) == 1) & (direction == -1)] = -1
    return sig


def _signals_rsi_divergence(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 15:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 14))
    oversold = float(params.get("oversold", 30))
    overbought = float(params.get("overbought", 70))
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-6)
    rsi = 100 - (100 / (1 + rs))
    sig = pd.Series(0, index=df.index)
    sig[(rsi.shift(1) < oversold) & (rsi >= oversold)] = 1
    sig[(rsi.shift(1) > overbought) & (rsi <= overbought)] = -1
    sig[(rsi.shift(1) < 50) & (rsi >= 50)] = 2
    sig[(rsi.shift(1) > 50) & (rsi <= 50)] = 2
    return sig


def _signals_macd_crossover(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 35:
        return pd.Series([0] * len(df), index=df.index)
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal_p = int(params.get("signal", 9))
    ema_fast = _ema(df["close"], fast)
    ema_slow = _ema(df["close"], slow)
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal_p, adjust=False).mean()
    sig = pd.Series(0, index=df.index)
    sig[(macd.shift(1) <= signal_line.shift(1)) & (macd > signal_line)] = 1
    sig[(macd.shift(1) >= signal_line.shift(1)) & (macd < signal_line)] = -1
    return sig


def _signals_bollinger_band(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 20))
    std_mult = float(params.get("std", 2.0))
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    sig = pd.Series(0, index=df.index)
    sig[df["close"] <= lower] = 1
    sig[df["close"] >= upper] = -1
    sig[(df["close"].shift(1) < sma) & (df["close"] >= sma)] = 2
    sig[(df["close"].shift(1) > sma) & (df["close"] <= sma)] = 2
    return sig


def _signals_opening_range_breakout(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    orb_bars = int(params.get("orb_bars", 15))
    sig = pd.Series(0, index=df.index)
    if "ts" in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["ts"]).dt.date
        for date, grp in df.groupby("date"):
            if len(grp) < orb_bars + 1:
                continue
            orb_high = grp["high"].iloc[:orb_bars].max()
            orb_low = grp["low"].iloc[:orb_bars].min()
            for idx in grp.index[orb_bars:]:
                if df.loc[idx, "close"] > orb_high:
                    sig.loc[idx] = 1
                elif df.loc[idx, "close"] < orb_low:
                    sig.loc[idx] = -1
    return sig


def _signals_volume_spike_breakout(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    vol_mult = float(params.get("vol_multiplier", 3.0))
    lookback = int(params.get("lookback", 20))
    avg_vol = df["volume"].rolling(lookback).mean()
    high_n = df["high"].rolling(lookback).max()
    low_n = df["low"].rolling(lookback).min()
    vol_spike = df["volume"] >= vol_mult * avg_vol
    sig = pd.Series(0, index=df.index)
    sig[vol_spike & (df["close"] > high_n.shift(1))] = 1
    sig[vol_spike & (df["close"] < low_n.shift(1))] = -1
    return sig


def _signals_gap_and_go(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 2:
        return pd.Series([0] * len(df), index=df.index)
    gap_pct = float(params.get("gap_pct", 0.015))
    sig = pd.Series(0, index=df.index)
    gap_up = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)
    gap_dn = (df["close"].shift(1) - df["open"]) / df["close"].shift(1)
    sig[(gap_up > gap_pct) & (df["close"] > df["open"])] = 1
    sig[(gap_dn > gap_pct) & (df["close"] < df["open"])] = -1
    return sig


def _signals_donchian_breakout(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 20))
    upper = df["high"].rolling(period).max()
    lower = df["low"].rolling(period).min()
    sma_fast = df["close"].rolling(10).mean()
    sig = pd.Series(0, index=df.index)
    sig[df["close"] > upper.shift(1)] = 1
    sig[df["close"] < lower.shift(1)] = -1
    sig[(df["close"].shift(1) < sma_fast) & (df["close"] >= sma_fast)] = 2
    sig[(df["close"].shift(1) > sma_fast) & (df["close"] <= sma_fast)] = 2
    return sig


def _signals_zscore_reversion(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 20))
    entry_z = float(params.get("entry_z", 2.0))
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    z_score = (df["close"] - sma) / std.replace(0, 1e-6)
    sig = pd.Series(0, index=df.index)
    sig[z_score < -entry_z] = 1
    sig[z_score > entry_z] = -1
    sig[z_score.abs() < 0.2] = 2
    return sig


def _signals_keltner_channel(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 20))
    mult = float(params.get("multiplier", 2.0))
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    ema = _ema(df["close"], period)
    upper = ema + mult * atr
    lower = ema - mult * atr
    sig = pd.Series(0, index=df.index)
    sig[df["close"] > upper] = 1
    sig[df["close"] < lower] = -1
    sig[(df["close"].shift(1) < ema) & (df["close"] >= ema)] = 2
    sig[(df["close"].shift(1) > ema) & (df["close"] <= ema)] = 2
    return sig


def _signals_pyro_algo(df: pd.DataFrame, params: Dict) -> pd.Series:
    if len(df) < 50:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("st_period", 10))
    multiplier = float(params.get("st_mult", 2.0))
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    direction = pd.Series(1, index=df.index)
    for i in range(period, len(df)):
        prev_upper = upper.iloc[i - 1]
        prev_lower = lower.iloc[i - 1]
        upper.iloc[i] = upper.iloc[i] if upper.iloc[i] < prev_upper or df["close"].iloc[i - 1] > prev_upper else prev_upper
        lower.iloc[i] = lower.iloc[i] if lower.iloc[i] > prev_lower or df["close"].iloc[i - 1] < prev_lower else prev_lower
        if direction.iloc[i - 1] == -1 and df["close"].iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif direction.iloc[i - 1] == 1 and df["close"].iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    k_period = int(params.get("k", 14))
    d_period = int(params.get("d", 3))
    smooth_k = int(params.get("smooth", 3))
    lowest_low = df["low"].rolling(k_period).min()
    highest_high = df["high"].rolling(k_period).max()
    limit_highest = df["high"].rolling(20).max()
    limit_lowest = df["low"].rolling(20).min()
    stoch_range = (highest_high - lowest_low).replace(0, 1e-6)
    stoch = limit_lowest + (limit_highest - limit_lowest) * (df["close"] - lowest_low) / stoch_range
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(d_period).mean()
    cross_up = (k.shift(1) <= d.shift(1)) & (k > d)
    cross_dn = (k.shift(1) >= d.shift(1)) & (k < d)
    sig = pd.Series(0, index=df.index)
    sig[cross_up & (direction == 1)] = 1
    sig[cross_dn & (direction == -1)] = -1
    return sig


_SIG_MAP = {
    "pyro_algo": _signals_pyro_algo,
    "ema_crossover": _signals_ema_crossover,
    "EMA Crossover": _signals_ema_crossover,
    "vwap_scalping": _signals_vwap_scalping,
    "oi_breakout": _signals_oi_breakout,
    "smart_money": _signals_smart_money,
    "gamma_scalping": _signals_gamma_scalping,
    "supertrend": _signals_supertrend,
    "rsi_divergence": _signals_rsi_divergence,
    "macd_crossover": _signals_macd_crossover,
    "bollinger_band": _signals_bollinger_band,
    "opening_range_breakout": _signals_opening_range_breakout,
    "volume_spike_breakout": _signals_volume_spike_breakout,
    "gap_and_go": _signals_gap_and_go,
    "donchian_breakout": _signals_donchian_breakout,
    "zscore_reversion": _signals_zscore_reversion,
    "keltner_channel": _signals_keltner_channel,
}

import os
from datetime import timezone

# ---------------------------------------------------------------------------
# Trade mode helpers
# ---------------------------------------------------------------------------

def _resolve_opt_type(trade_mode: str, signal: int) -> str:
    if trade_mode == "AUTO":
        return "CE" if signal == 1 else "PE"
    return trade_mode  # "CE" or "PE"

def _ts_to_utc(ts_str: str) -> datetime:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        dt = datetime.fromisoformat(str(ts_str))
    return dt

# ---------------------------------------------------------------------------
# Parquet OHLC Caching
# ---------------------------------------------------------------------------

_PARQUET_CACHE = {}

def _load_options_ohlc_for_day(symbol: str, date_str: str) -> pd.DataFrame:
    cache_key = f"{symbol}_{date_str}"
    if cache_key in _PARQUET_CACHE:
        return _PARQUET_CACHE[cache_key]
        
    file_path = os.path.join(os.path.dirname(__file__), "..", "data", "options_history", f"{symbol}_options_{date_str}.parquet")
    if not os.path.exists(file_path):
        _PARQUET_CACHE[cache_key] = pd.DataFrame()
        return _PARQUET_CACHE[cache_key]
        
    try:
        df = pd.read_parquet(file_path)
        if df.empty or 'timestamp' not in df.columns:
            _PARQUET_CACHE[cache_key] = pd.DataFrame()
            return _PARQUET_CACHE[cache_key]
            
        # Ensure naive UTC
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)
            
        df['strike'] = pd.to_numeric(df['strike'], errors='coerce')
        df = df.dropna(subset=['strike'])
        
        df.set_index('timestamp', inplace=True)
        
        ohlc = df.groupby('strike').resample('1min').agg({
            'ce_ltp': ['first', 'max', 'min', 'last'],
            'pe_ltp': ['first', 'max', 'min', 'last']
        }).reset_index()
        
        ohlc.columns = ['strike', 'timestamp', 
                        'ce_open', 'ce_high', 'ce_low', 'ce_close',
                        'pe_open', 'pe_high', 'pe_low', 'pe_close']
                        
        _PARQUET_CACHE[cache_key] = ohlc
        return ohlc
    except Exception as e:
        logger.error(f"OHLC Parquet load error: {e}")
        _PARQUET_CACHE[cache_key] = pd.DataFrame()
        return _PARQUET_CACHE[cache_key]

async def _fetch_option_premium(symbol: str, spot_price: float, opt_type: str, ts_utc: datetime) -> tuple:
    date_str = ts_utc.strftime("%Y-%m-%d")
    ohlc = _load_options_ohlc_for_day(symbol, date_str)
    if ohlc.empty: return None, None, None, "NO DATA"
    
    minute_ts = ts_utc.replace(second=0, microsecond=0)
    minute_df = ohlc[ohlc['timestamp'] == minute_ts]
    
    if minute_df.empty: return None, None, None, "NO DATA"
    
    minute_df = minute_df.copy()
    minute_df['diff'] = (minute_df['strike'] - spot_price).abs()
    closest_row = minute_df.loc[minute_df['diff'].idxmin()]
    
    prefix = opt_type.lower()
    ltp = closest_row[f"{prefix}_close"]
    if pd.isna(ltp) or ltp <= 0:
        print(f"[MISSING DATA] Could not fetch entry for {symbol} {opt_type} at {minute_ts} UTC. Available minutes in parquet start at: {ohlc['timestamp'].min()} and end at {ohlc['timestamp'].max()}")
        return None, None, None, "NO DATA"
    
    return ltp, float(closest_row['strike']), None, "REAL_EXACT"

# ---------------------------------------------------------------------------
# Position open / close
# ---------------------------------------------------------------------------

def _mark_to_market(state: SimState, bar_close: float) -> float:
    if state.position == 0:
        return state.equity
    if getattr(state, "is_options_trade", False):
        return state.equity # Accurate MTM requires querying Parquet every minute, skipping to speed up.
    return state.equity + (bar_close - state.entry_price) * state.qty * state.position

async def _open_position(
    state: SimState,
    symbol: str,
    side: int,
    fill: float,
    ts_str: str,
    params: Dict,
    trade_mode: str,
) -> None:
    if state.equity <= 0:
        return

    fixed_qty = params.get("qty")
    is_options_trade = trade_mode != "NONE"
    
    state.is_options_trade = is_options_trade

    if is_options_trade:
        opt_type = _resolve_opt_type(trade_mode, side)
        ts_utc = _ts_to_utc(ts_str)
        
        ltp, actual_strike, actual_expiry, source = await _fetch_option_premium(
            symbol.upper(), fill, opt_type, ts_utc
        )

        if ltp is None or ltp <= 0:
            state.trades_log.append({
                "mode": trade_mode,
                "signal": "BUY" if side == 1 else "SELL",
                "side": "BUY" if side == 1 else "SELL",
                "index_entry": round(fill, 2),
                "index_exit": round(fill, 2),
                "strike": 0,
                "type": opt_type,
                "expiry": None,
                "entry_premium": 0,
                "exit_premium": 0,
                "entry_source": "NO DATA",
                "exit_source": "NO DATA",
                "qty": 0,
                "pnl": 0,
                "ts": ts_str,
                "reason": "MISSING DATA",
            })
            return

        if fixed_qty and int(fixed_qty) > 0:
            qty = int(fixed_qty)
        else:
            qty = max(1, int(state.equity * 0.95 / ltp))

        state.is_index = True # Keep for backwards compatibility with UI
        state.index_entry = fill
        state.opt_strike = actual_strike
        state.opt_type = opt_type
        state.opt_expiry = actual_expiry
        state.opt_entry_premium = ltp
        state.opt_entry_source = source
        state.position = side
        state.qty = qty
        state.entry_price = fill

    else:
        if fixed_qty and int(fixed_qty) > 0:
            qty = int(fixed_qty)
        else:
            qty = max(1, int(state.equity * 0.95 / fill))

        state.position = side
        state.entry_price = fill
        state.qty = qty

async def _close_position(
    state: SimState, fill: float, ts_str: str, reason: str = None, exact_premium: float = None, final: bool = False
) -> None:
    if state.position == 0:
        return

    is_options_trade = getattr(state, "is_options_trade", False)

    if is_options_trade:
        if exact_premium is not None:
            exit_premium = exact_premium
            exit_source = "REAL_EXACT"
        else:
            ts_utc = _ts_to_utc(ts_str)
            ltp, _, _, source = await _fetch_option_premium(
                state._symbol, state.opt_strike, state.opt_type, ts_utc
            )
            if ltp is None or ltp <= 0:
                exit_premium = 0
                exit_source = "NO DATA"
                reason = "MISSING DATA"
            else:
                exit_premium = ltp
                exit_source = source

        pnl = (exit_premium - state.opt_entry_premium) * state.qty * state.position if reason != "MISSING DATA" else 0

        trade = {
            "mode": getattr(state, "_trade_mode", "AUTO"),
            "side": "BUY" if state.position == 1 else "SELL",
            "signal_ts": getattr(state, "_signal_ts", ts_str),
            "index_entry": round(state.index_entry, 2),
            "index_exit": round(fill, 2),
            "strike": state.opt_strike,
            "type": state.opt_type,
            "expiry": getattr(state, "opt_expiry", None),
            "entry_premium": round(state.opt_entry_premium, 2),
            "exit_premium": round(exit_premium, 2),
            "entry_source": getattr(state, "opt_entry_source", "?"),
            "exit_source": exit_source,
            "qty": state.qty if exit_source != "NO DATA" else 0,
            "pnl": round(pnl, 2),
            "ts": ts_str,
            "reason": reason or ("EOD" if final else "Strategy"),
        }
    else:
        pnl = (fill - state.entry_price) * state.qty * state.position
        trade = {
            "mode": getattr(state, "_trade_mode", "NONE"),
            "side": "BUY" if state.position == 1 else "SELL",
            "signal_ts": getattr(state, "_signal_ts", ts_str),
            "entry": round(state.entry_price, 2),
            "exit": round(fill, 2),
            "qty": state.qty,
            "pnl": round(pnl, 2),
            "ts": ts_str,
            "reason": reason or ("EOD" if final else "Strategy"),
        }

    state.equity += pnl
    if reason != "MISSING DATA":
        state.trades += 1
        if pnl > 0:
            state.wins += 1

    if final:
        trade["final"] = True
    state.trades_log.append(trade)
    state.position = 0
    state.is_options_trade = False

# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

async def _simulate(
    symbol: str,
    df: pd.DataFrame,
    signals: pd.Series,
    params: Dict,
    trade_mode: str,
) -> Dict:
    sl_pct = float(params.get("stop_loss_pct", 0.01))
    tp_pct = float(params.get("take_profit_pct", 0.02))
    
    if df.empty or len(df) < 3:
        return {"metrics": {}, "equity_curve": [], "trades_log": []}

    state = SimState()
    state._symbol = symbol.upper()
    state._trade_mode = trade_mode

    square_off_times = ["09:45:00", "09:50:00", "09:55:00"]

    sig_vals = signals.values
    close_vals = df["close"].values
    open_vals = df["open"].values
    high_vals = df["high"].values
    low_vals = df["low"].values
    ts_vals = df["ts"].astype(str).values

    n = len(df)
    for i in range(n - 1):
        sig = int(sig_vals[i])
        bar_close = float(close_vals[i])
        eq = _mark_to_market(state, bar_close)
        state.peak = max(state.peak, eq)
        state.max_dd = max(state.max_dd, (state.peak - eq) / state.peak if state.peak else 0)
        state.curve.append({"t": int(i), "ts": ts_vals[i], "equity": round(eq, 2), "price": bar_close})

        if state.position != 0:
            is_eod = any(t in ts_vals[i] for t in square_off_times)
            bar_high = float(high_vals[i])
            bar_low = float(low_vals[i])
            reason = None
            exact_exit = None

            is_options_trade = getattr(state, "is_options_trade", False)

            if is_options_trade:
                target_price = state.opt_entry_premium * (1 + tp_pct) if state.position == 1 else state.opt_entry_premium * (1 - tp_pct)
                sl_price = state.opt_entry_premium * (1 - sl_pct) if state.position == 1 else state.opt_entry_premium * (1 + sl_pct)
                
                # Fetch exact OHLC from parquet for this minute
                ts_utc = _ts_to_utc(ts_vals[i]).replace(second=0, microsecond=0)
                date_str = ts_utc.strftime("%Y-%m-%d")
                ohlc = _load_options_ohlc_for_day(symbol, date_str)
                
                opt_high = None
                opt_low = None
                
                if not ohlc.empty:
                    minute_df = ohlc[(ohlc['timestamp'] == ts_utc) & (ohlc['strike'] == state.opt_strike)]
                    if not minute_df.empty:
                        prefix = state.opt_type.lower()
                        opt_high = minute_df.iloc[0][f"{prefix}_high"]
                        opt_low = minute_df.iloc[0][f"{prefix}_low"]
                
                if opt_high is not None and not pd.isna(opt_high):
                    hit_target = False
                    hit_sl = False
                    if state.position == 1:
                        if opt_high >= target_price: hit_target = True
                        if opt_low <= sl_price: hit_sl = True
                    else:
                        if opt_low <= target_price: hit_target = True
                        if opt_high >= sl_price: hit_sl = True
                        
                    if hit_sl:
                        reason = "SL"
                        exact_exit = round(sl_price, 2)
                    elif hit_target:
                        reason = "Target"
                        exact_exit = round(target_price, 2)
                    elif is_eod:
                        reason = "EOD"
                elif is_eod:
                    reason = "EOD"
            else:
                target_price = state.entry_price * (1 + tp_pct) if state.position == 1 else state.entry_price * (1 - tp_pct)
                sl_price = state.entry_price * (1 - sl_pct) if state.position == 1 else state.entry_price * (1 + sl_pct)
                hit_target = bar_high >= target_price if state.position == 1 else bar_low <= target_price
                hit_sl = bar_low <= sl_price if state.position == 1 else bar_high >= sl_price
                if hit_sl:
                    reason = "SL"
                    exact_exit = round(sl_price, 2)
                elif hit_target:
                    reason = "Target"
                    exact_exit = round(target_price, 2)
                elif is_eod:
                    reason = "EOD"

            if reason:
                fill = float(open_vals[i + 1])
                if not math.isnan(fill):
                    await _close_position(state, fill, ts_vals[i + 1], reason=reason, exact_premium=exact_exit)
                continue

        if sig == 0 or sig == state.position:
            continue
        fill = float(open_vals[i + 1])
        if math.isnan(fill):
            continue
        if state.position != 0:
            await _close_position(state, fill, ts_vals[i + 1], reason="Strategy")
        if sig in (1, -1):
            state._signal_ts = ts_vals[i]
            await _open_position(state, symbol, sig, fill, ts_vals[i + 1], params, trade_mode)

    last_close = float(close_vals[-1])
    if state.position != 0:
        await _close_position(state, last_close, ts_vals[-1], reason="EOD", final=True)

    rets = [c["equity"] for c in state.curve]
    pct_rets = [(rets[i] / rets[i - 1] - 1) for i in range(1, len(rets))] if len(rets) > 1 else [0]
    mu = sum(pct_rets) / len(pct_rets)
    sigma = math.sqrt(sum((r - mu) ** 2 for r in pct_rets) / len(pct_rets)) or 1e-6
    annualised = mu / sigma * math.sqrt(252 * 6.5 * 60)

    return {
        "metrics": {
            "total_return_pct": round((state.equity / 100000.0 - 1) * 100, 2),
            "final_equity": round(state.equity, 2),
            "trades": state.trades,
            "win_rate_pct": round(state.wins / state.trades * 100, 2) if state.trades else 0.0,
            "max_drawdown_pct": round(state.max_dd * 100, 2),
            "sharpe": round(annualised, 2),
            "bars": len(df),
        },
        "equity_curve": state.curve[::max(1, len(state.curve) // 200)],
        "trades_log": state.trades_log,
    }

async def run_backtest(strategy_kind: str, symbol: str, period_days: int, params: Dict | None = None) -> Dict:
    params = params or {}

    raw_trade_options = params.get("trade_options", False)
    if isinstance(raw_trade_options, str):
        trade_options = raw_trade_options.lower() not in ("false", "0", "no", "none", "")
    else:
        trade_options = bool(raw_trade_options)

    if not trade_options:
        trade_mode = "NONE"
    else:
        opt_type_raw = str(params.get("option_type", "AUTO")).upper()
        if opt_type_raw in ("CE", "PE", "AUTO"):
            trade_mode = opt_type_raw
        else:
            trade_mode = "AUTO"

    df = await _load_symbol_data(symbol, period_days)
    if df.empty or len(df) < 50:
        return {
            "metrics": {}, "equity_curve": [], "trades_log": [],
            "data_source": "none", "reason": "no_data_in_db",
            "trade_mode": trade_mode,
        }

    rule = params.get("resample", "1min")
    candles = _resample(df, rule)
    if len(candles) < 30:
        return {
            "metrics": {}, "equity_curve": [], "trades_log": [],
            "data_source": "none", "reason": "insufficient_candles",
            "trade_mode": trade_mode,
        }

    days_available = candles["ts"].dt.date.nunique() if not candles.empty else 0
    days_missing = max(0, period_days - days_available)

    sig_fn = _SIG_MAP.get(strategy_kind, _signals_ema_crossover)
    signals = sig_fn(candles, params)
    
    # Global Parquet OHLC memory cache - reset on every backtest run to prevent huge memory leaks
    global _PARQUET_CACHE
    _PARQUET_CACHE = {}
    
    res = await _simulate(symbol, candles, signals, params, trade_mode)
    res["data_source"] = "mysql"
    res["bars_loaded"] = len(candles)
    res["days_available"] = days_available
    res["days_missing"] = days_missing
    res["days_requested"] = period_days
    res["raw_ticks"] = len(df)
    res["trade_mode"] = trade_mode
    return res
