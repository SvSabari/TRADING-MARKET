"""5-second volume capture per Nifty 50 symbol → Parquet files.

Aggregates 1-second ticks emitted by the tick engine into 5-second buckets
and appends rows to a per-symbol Parquet file. Files are stored under
PARQUET_DATA_DIR/<DATE>/<SYMBOL>.parquet.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from constants import ALL_SYMBOLS
from services.market_data import tick_engine

DEFAULT_PARQUET_DIR = Path(__file__).resolve().parents[2] / "data" / "parquet"
PARQUET_DIR = Path(os.environ.get("PARQUET_DATA_DIR", DEFAULT_PARQUET_DIR))
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

BUCKET_SECONDS = 5


def _today_dir() -> Path:
    d = PARQUET_DIR / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


class ParquetCapture:
    def __init__(self) -> None:
        # buffers: symbol -> list of partial 5s bucket rows
        self._buffer: Dict[str, List[dict]] = {s: [] for s in ALL_SYMBOLS}
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.last_flush: Optional[str] = None
        self.flush_count: int = 0
        self.rows_written: int = 0

    def stats(self) -> dict:
        return {
            "running": self.running,
            "interval_seconds": BUCKET_SECONDS,
            "last_flush": self.last_flush,
            "flush_count": self.flush_count,
            "rows_written": self.rows_written,
            "parquet_dir": str(PARQUET_DIR),
        }

    async def _loop(self) -> None:
        self.running = True
        while self.running:
            # build one 5s bucket per symbol from current state
            ts = datetime.now(timezone.utc)
            bucket_ts = ts.replace(microsecond=0).isoformat()
            rows: Dict[str, dict] = {}
            for s in ALL_SYMBOLS:
                # last BUCKET_SECONDS ticks of 1s tick history
                hist = list(tick_engine.history.get(s, []))[-BUCKET_SECONDS:]
                if not hist:
                    continue
                volume_sum = sum(h["volume"] for h in hist)
                prices = [h["ltp"] for h in hist]
                rows[s] = {
                    "ts": bucket_ts,
                    "symbol": s,
                    "open": prices[0],
                    "high": max(prices),
                    "low": min(prices),
                    "close": prices[-1],
                    "volume": volume_sum,
                    "cum_volume": hist[-1]["cum_volume"],
                }
            # flush each symbol to its parquet file
            today = _today_dir()
            for s, row in rows.items():
                f = today / f"{s}.parquet"
                df = pd.DataFrame([row])
                if f.exists():
                    try:
                        existing = pd.read_parquet(f)
                        df = pd.concat([existing, df], ignore_index=True)
                    except Exception:
                        pass
                df.to_parquet(f, engine="pyarrow", index=False)
                self.rows_written += 1
            self.flush_count += 1
            self.last_flush = bucket_ts
            await asyncio.sleep(BUCKET_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()


parquet_capture = ParquetCapture()


def list_parquet_files() -> List[dict]:
    """Walk PARQUET_DIR and list every .parquet file with metadata."""
    out: List[dict] = []
    if not PARQUET_DIR.exists():
        return out
    for date_dir in sorted(PARQUET_DIR.iterdir()):
        if not date_dir.is_dir():
            continue
        for f in sorted(date_dir.glob("*.parquet")):
            try:
                size = f.stat().st_size
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                try:
                    rows = len(pd.read_parquet(f, columns=["ts"]))
                except Exception:
                    rows = 0
                out.append({
                    "date": date_dir.name,
                    "symbol": f.stem,
                    "filename": f.name,
                    "path": str(f.relative_to(PARQUET_DIR)),
                    "size_bytes": size,
                    "row_count": rows,
                    "last_modified": mtime.isoformat(),
                })
            except Exception:
                continue
    return out


def read_parquet_preview(rel_path: str, limit: int = 200) -> List[dict]:
    p = (PARQUET_DIR / rel_path).resolve()
    base = PARQUET_DIR.resolve()
    if not str(p).startswith(str(base)):
        return []
    if not p.exists():
        return []
    df = pd.read_parquet(p)
    if len(df) > limit:
        df = df.tail(limit)
    return df.to_dict(orient="records")


def parquet_file_path(rel_path: str) -> Optional[Path]:
    p = (PARQUET_DIR / rel_path).resolve()
    base = PARQUET_DIR.resolve()
    if not str(p).startswith(str(base)):
        return None
    return p if p.exists() else None
