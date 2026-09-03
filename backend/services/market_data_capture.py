"""5-second volume capture per Nifty 50 symbol -> MongoDB.

Aggregates 1-second ticks emitted by the tick engine into 5-second buckets
and inserts them into the `market_candles` MongoDB collection.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from constants import ALL_SYMBOLS
from db import db
from services.market_data import tick_engine

BUCKET_SECONDS = 5

class MarketDataCapture:
    def __init__(self) -> None:
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
        }

    async def _loop(self) -> None:
        self.running = True
        
        # Create index for fast querying by backtester
        try:
            await db.market_candles.create_index([("symbol", 1), ("ts", 1)])
        except Exception:
            pass

        while self.running:
            ts = datetime.now(timezone.utc)
            # IST is UTC + 5:30
            ist_time = ts + timedelta(hours=5, minutes=30)
            
            # Check if NSE is open (Mon-Fri, 09:15 - 15:30)
            is_market_open = True
            if ist_time.weekday() >= 5:
                is_market_open = False
            else:
                market_start = ist_time.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = ist_time.replace(hour=15, minute=30, second=0, microsecond=0)
                if not (market_start <= ist_time <= market_end):
                    is_market_open = False
                    
            if not is_market_open:
                await asyncio.sleep(BUCKET_SECONDS)
                continue

            # build one 5s bucket per symbol from current state
            bucket_ts = ts.replace(microsecond=0)
            rows = []
            for s in ALL_SYMBOLS:
                if self.last_flush:
                    # Parse last_flush back to datetime if it's string, though we store it as ISO
                    hist = [h for h in tick_engine.history.get(s, []) if h["ts"] > self.last_flush]
                else:
                    last_tick = tick_engine.history.get(s, [])
                    hist = [last_tick[-1]] if last_tick else []

                if not hist:
                    # No new ticks. Insert a 0-volume candle at the last known price to keep time series contiguous
                    last_price = tick_engine.prices.get(s, 0.0)
                    if last_price == 0.0:
                        continue
                    rows.append({
                        "ts": bucket_ts,
                        "symbol": s,
                        "open": last_price,
                        "high": last_price,
                        "low": last_price,
                        "close": last_price,
                        "volume": 0,
                        "cum_volume": tick_engine.volume_cum.get(s, 0),
                    })
                else:
                    volume_sum = sum(h["volume"] for h in hist)
                    prices = [h["ltp"] for h in hist]
                    rows.append({
                        "ts": bucket_ts,
                        "symbol": s,
                        "open": prices[0],
                        "high": max(prices),
                        "low": min(prices),
                        "close": prices[-1],
                        "volume": volume_sum,
                        "cum_volume": hist[-1]["cum_volume"],
                    })
            
            if rows:
                try:
                    await db.market_candles.insert_many(rows)
                    self.rows_written += len(rows)
                except Exception as e:
                    print(f"Error inserting market candles: {e}")
                    
            self.flush_count += 1
            self.last_flush = bucket_ts.isoformat()
            await asyncio.sleep(BUCKET_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()

market_data_capture = MarketDataCapture()
