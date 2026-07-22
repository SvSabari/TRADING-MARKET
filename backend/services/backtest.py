"""Real backtester that reads captured Parquet files.

Algorithm: read all 5-second OHLCV rows for `symbol` within the last
`period_days`, resample to a per-strategy candle (default 1-minute),
run the strategy's signal generator, simulate marketable orders at the
next bar's open, and report metrics + equity curve.

When no parquet data is available for the requested symbol, falls back
to a synthetic walk-forward simulation so the UI never breaks.
"""
from __future__ import annotations

import math
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

DEFAULT_PARQUET_DIR = Path(__file__).resolve().parents[2] / "data" / "parquet"
PARQUET_DIR = Path(os.environ.get("PARQUET_DATA_DIR", DEFAULT_PARQUET_DIR))


def _load_symbol_data(symbol: str, period_days: int) -> pd.DataFrame:
    """Concatenate all per-day Parquet files for the symbol within window."""
    today = datetime.now(timezone.utc).date()
    frames: List[pd.DataFrame] = []
    for delta_days in range(period_days + 1):
        d = today - timedelta(days=delta_days)
        f = PARQUET_DIR / d.strftime("%Y-%m-%d") / f"{symbol.upper()}.parquet"
        if f.exists():
            try:
                frames.append(pd.read_parquet(f))
            except Exception:
                pass
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return df


def _resample(df: pd.DataFrame, rule: str = "1min") -> pd.DataFrame:
    if df.empty:
        return df
    df = df.set_index("ts")
    agg = df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna().reset_index()
    return agg


# ---- strategy signal generators on a DataFrame ----

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
    sig[z > float(params.get("exit_z", 0.002))] = -1
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
    vol_z = (df["volume"] - df["volume"].rolling(20).mean()) / (df["volume"].rolling(20).std().replace(0, 1))
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


# ---- NEW CREATIVE STRATEGIES ----

def _signals_supertrend(df: pd.DataFrame, params: Dict) -> pd.Series:
    """Supertrend: Buy when price closes above supertrend line, Sell below."""
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
    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)  # 1=bullish, -1=bearish
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
    cross_up = (direction.shift(1) == -1) & (direction == 1)
    cross_dn = (direction.shift(1) == 1) & (direction == -1)
    sig[cross_up] = 1
    sig[cross_dn] = -1
    return sig


def _signals_rsi_divergence(df: pd.DataFrame, params: Dict) -> pd.Series:
    """RSI strategy: Buy on oversold (<30), Sell on overbought (>70)."""
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
    sig[(rsi.shift(1) < oversold) & (rsi >= oversold)] = 1   # cross up from oversold
    sig[(rsi.shift(1) > overbought) & (rsi <= overbought)] = -1  # cross down from overbought
    return sig


def _signals_macd_crossover(df: pd.DataFrame, params: Dict) -> pd.Series:
    """MACD: Buy when MACD crosses above signal line, Sell when crosses below."""
    if len(df) < 35:
        return pd.Series([0] * len(df), index=df.index)
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal_p = int(params.get("signal", 9))
    ema_fast = _ema(df["close"], fast)
    ema_slow = _ema(df["close"], slow)
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal_p, adjust=False).mean()
    cross_up = (macd.shift(1) <= signal_line.shift(1)) & (macd > signal_line)
    cross_dn = (macd.shift(1) >= signal_line.shift(1)) & (macd < signal_line)
    sig = pd.Series(0, index=df.index)
    sig[cross_up] = 1
    sig[cross_dn] = -1
    return sig


def _signals_bollinger_band(df: pd.DataFrame, params: Dict) -> pd.Series:
    """Bollinger Bands: Buy at lower band touch, Sell at upper band touch."""
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    period = int(params.get("period", 20))
    std_mult = float(params.get("std", 2.0))
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    sig = pd.Series(0, index=df.index)
    sig[df["close"] <= lower] = 1   # buy at lower band
    sig[df["close"] >= upper] = -1  # sell at upper band
    return sig


def _signals_opening_range_breakout(df: pd.DataFrame, params: Dict) -> pd.Series:
    """ORB: Buy if price breaks above first N-bar high after open."""
    if len(df) < 20:
        return pd.Series([0] * len(df), index=df.index)
    orb_bars = int(params.get("orb_bars", 15))  # first 15 minutes at 1min bars
    sig = pd.Series(0, index=df.index)
    # Group by date
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
    """Volume Spike: Buy when volume is 3x average AND price makes new high."""
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
    """Gap & Go: Buy stocks that gap up significantly from previous close."""
    if len(df) < 2:
        return pd.Series([0] * len(df), index=df.index)
    gap_pct = float(params.get("gap_pct", 0.015))  # 1.5% gap
    sig = pd.Series(0, index=df.index)
    gap_up = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)
    gap_dn = (df["close"].shift(1) - df["open"]) / df["close"].shift(1)
    # Buy the gap up if price continues higher in first bar
    sig[(gap_up > gap_pct) & (df["close"] > df["open"])] = 1
    # Sell the gap down if price continues lower
    sig[(gap_dn > gap_pct) & (df["close"] < df["open"])] = -1
    return sig


_SIG_MAP = {
    "ema_crossover": _signals_ema_crossover,
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
}


from services.sim_state import SimState


def _mark_to_market(state: SimState, bar_close: float) -> float:
    """Return current equity including open-position MTM."""
    if state.position == 0:
        return state.equity
    return state.equity + (bar_close - state.entry_price) * state.qty * state.position


def _close_position(state: SimState, fill: float, ts: str, final: bool = False) -> None:
    """Close any open position at `fill`. Updates equity, wins, trades, log."""
    if state.position == 0:
        return
    pnl = (fill - state.entry_price) * state.qty * state.position
    state.equity += pnl
    state.trades += 1
    if pnl > 0:
        state.wins += 1
    entry = {
        "side": "BUY" if state.position == 1 else "SELL",
        "entry": state.entry_price, "exit": fill,
        "qty": state.qty, "pnl": round(pnl, 2), "ts": ts,
    }
    if final:
        entry["final"] = True
    state.trades_log.append(entry)


def _open_position(state: SimState, side: int, fill: float) -> None:
    """Open a new long/short position sized at ~95% of equity."""
    state.qty = max(1, int(state.equity * 0.95 / fill))
    state.position = side
    state.entry_price = fill


def _simulate(df: pd.DataFrame, signals: pd.Series) -> Dict:
    """Long/short single-position simulator with next-bar-open fills."""
    if df.empty or len(df) < 3:
        return {"metrics": {}, "equity_curve": [], "trades_log": []}
    state = SimState()
    
    # Pre-extract numpy arrays for fast iteration
    sig_vals = signals.values
    close_vals = df["close"].values
    open_vals = df["open"].values
    ts_vals = df["ts"].astype(str).values
    
    n = len(df)
    for i in range(n - 1):
        sig = int(sig_vals[i])
        bar_close = float(close_vals[i])
        eq = _mark_to_market(state, bar_close)
        state.peak = max(state.peak, eq)
        state.max_dd = max(state.max_dd, (state.peak - eq) / state.peak if state.peak else 0)
        state.curve.append({"t": int(i), "ts": ts_vals[i],
                             "equity": round(eq, 2), "price": bar_close})
        if sig == 0 or sig == state.position:
            continue
        fill = float(open_vals[i + 1])
        if math.isnan(fill):
            continue
        _close_position(state, fill, ts_vals[i + 1])
        _open_position(state, sig, fill)

    # final close on last bar
    last_close = float(close_vals[-1])
    _close_position(state, last_close, ts_vals[-1], final=True)

    rets = [c["equity"] for c in state.curve]
    pct_rets = [(rets[i] / rets[i - 1] - 1) for i in range(1, len(rets))] if len(rets) > 1 else [0]
    mu = sum(pct_rets) / len(pct_rets)
    sigma = math.sqrt(sum((r - mu) ** 2 for r in pct_rets) / len(pct_rets)) or 1e-6
    annualised = mu / sigma * math.sqrt(252 * 6.5 * 60)  # 1-min bars
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




def run_backtest(strategy_kind: str, symbol: str, period_days: int, params: Dict | None = None) -> Dict:
    params = params or {}
    df = _load_symbol_data(symbol, period_days)
    if df.empty or len(df) < 50:
        return {"metrics": {}, "equity_curve": [], "trades_log": [], "data_source": "none", "reason": "no_parquet_data"}
    rule = params.get("resample", "1min")
    candles = _resample(df, rule)
    if len(candles) < 30:
        return {"metrics": {}, "equity_curve": [], "trades_log": [], "data_source": "none", "reason": "insufficient_candles"}
    sig_fn = _SIG_MAP.get(strategy_kind, _signals_ema_crossover)
    signals = sig_fn(candles, params)
    res = _simulate(candles, signals)
    res["data_source"] = "parquet"
    res["bars_loaded"] = len(candles)
    res["raw_ticks"] = len(df)
    return res
