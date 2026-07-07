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
    # Toy proxy: mean-revert ATR-band breaks
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
    sig[(df["close"] - sma) > 1.2 * atr] = -1   # fade up move
    sig[(sma - df["close"]) > 1.2 * atr] = 1    # fade down move
    return sig


_SIG_MAP = {
    "ema_crossover": _signals_ema_crossover,
    "vwap_scalping": _signals_vwap_scalping,
    "oi_breakout": _signals_oi_breakout,
    "smart_money": _signals_smart_money,
    "gamma_scalping": _signals_gamma_scalping,
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
    next_open = df["open"].shift(-1)
    for i in range(len(df) - 1):
        sig = int(signals.iloc[i])
        bar_close = float(df["close"].iloc[i])
        eq = _mark_to_market(state, bar_close)
        state.peak = max(state.peak, eq)
        state.max_dd = max(state.max_dd, (state.peak - eq) / state.peak if state.peak else 0)
        state.curve.append({"t": int(i), "ts": str(df["ts"].iloc[i]),
                             "equity": round(eq, 2), "price": bar_close})
        if sig == 0 or sig == state.position:
            continue
        fill = float(next_open.iloc[i])
        if pd.isna(fill):
            continue
        _close_position(state, fill, str(df["ts"].iloc[i + 1]))
        _open_position(state, sig, fill)

    # final close on last bar
    last_close = float(df["close"].iloc[-1])
    _close_position(state, last_close, str(df["ts"].iloc[-1]), final=True)

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
        "trades_log": state.trades_log[-50:],
    }


def _synthetic(strategy_kind: str, symbol: str, period_days: int, params: Dict) -> Dict:
    rng = random.Random(hash((strategy_kind, symbol, period_days)) % (2 ** 32))
    n = max(40, period_days * 50)
    equity = 100000.0
    curve = []
    trades = 0
    wins = 0
    peak = equity
    max_dd = 0.0
    bias = {"ema_crossover": 0.0009, "oi_breakout": 0.0011, "vwap_scalping": 0.0006,
            "gamma_scalping": 0.0007, "smart_money": 0.0013}.get(strategy_kind, 0.0005)
    for i in range(n):
        ret = rng.gauss(bias, 0.012)
        equity *= 1 + ret
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        if ret > 0:
            wins += 1
        trades += 1
        curve.append({"t": i, "ts": "", "equity": round(equity, 2), "price": 0.0})
    pct_rets = [(curve[i]["equity"] / curve[i - 1]["equity"] - 1) for i in range(1, len(curve))]
    mu = sum(pct_rets) / len(pct_rets)
    sigma = math.sqrt(sum((r - mu) ** 2 for r in pct_rets) / len(pct_rets)) or 1e-6
    return {
        "metrics": {
            "total_return_pct": round((equity / 100000.0 - 1) * 100, 2),
            "final_equity": round(equity, 2),
            "trades": trades,
            "win_rate_pct": round(wins / trades * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sharpe": round(mu / sigma * math.sqrt(252), 2),
            "bars": n,
        },
        "equity_curve": curve,
        "trades_log": [],
        "data_source": "synthetic",
    }


def run_backtest(strategy_kind: str, symbol: str, period_days: int, params: Dict | None = None) -> Dict:
    params = params or {}
    df = _load_symbol_data(symbol, period_days)
    if df.empty or len(df) < 50:
        out = _synthetic(strategy_kind, symbol, period_days, params)
        out["data_source"] = "synthetic"
        out["reason"] = "no_parquet_data"
        return out
    rule = params.get("resample", "1min")
    candles = _resample(df, rule)
    if len(candles) < 30:
        out = _synthetic(strategy_kind, symbol, period_days, params)
        out["data_source"] = "synthetic"
        out["reason"] = "insufficient_candles"
        return out
    sig_fn = _SIG_MAP.get(strategy_kind, _signals_ema_crossover)
    signals = sig_fn(candles, params)
    res = _simulate(candles, signals)
    res["data_source"] = "parquet"
    res["bars_loaded"] = len(candles)
    res["raw_ticks"] = len(df)
    return res
