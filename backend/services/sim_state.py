"""Small dataclass-like state container for the backtest simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class SimState:
    equity: float = 100000.0
    position: int = 0  # +1 long, -1 short, 0 flat
    entry_price: float = 0.0
    qty: int = 0
    peak: float = 100000.0
    max_dd: float = 0.0
    wins: int = 0
    trades: int = 0
    curve: List[Dict] = field(default_factory=list)
    trades_log: List[Dict] = field(default_factory=list)
