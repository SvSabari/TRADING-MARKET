"""Pydantic models for the Algo Trading platform."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from db import BaseDocument, utc_now

# ---------- Auth ----------
class User(BaseDocument):
    email: EmailStr
    name: str
    password_hash: str
    role: str = "trader"  # trader, admin
    tv_webhook_secret: str = ""  # per-user webhook secret
    created_at: datetime = Field(default_factory=utc_now)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    tv_webhook_secret: str = ""
    created_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------- TradingView signals ----------
class TVSignal(BaseDocument):
    user_id: str
    symbol: str
    side: str  # BUY / SELL
    price: float
    qty: int = 1
    strategy: str = "tradingview"
    payload: Dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=utc_now)
    processed: bool = False
    order_id: Optional[str] = None


class TVSignalCreate(BaseModel):
    symbol: str
    side: str
    price: float
    qty: int = 1
    strategy: str = "tradingview"
    alert_id: Optional[str] = None  # for idempotency
    secret: Optional[str] = None
    # accept arbitrary additional fields via model_config
    model_config = ConfigDict(extra="allow")


# ---------- Orders ----------
class Order(BaseDocument):
    user_id: str
    broker: str  # zerodha / breeze / angel / mock
    symbol: str
    side: str
    qty: int
    price: float
    order_type: str = "MARKET"  # MARKET / LIMIT
    product: str = "MIS"
    status: str = "OPEN"  # OPEN / FILLED / CANCELLED / REJECTED
    source: str = "manual"  # manual / tradingview / strategy
    signal_id: Optional[str] = None
    placed_at: datetime = Field(default_factory=utc_now)
    filled_at: Optional[datetime] = None
    pnl: float = 0.0


class OrderCreate(BaseModel):
    broker: str = "mock"
    symbol: str
    side: str
    qty: int
    price: float
    order_type: str = "MARKET"
    product: str = "MIS"


# ---------- Positions ----------
class Position(BaseDocument):
    user_id: str
    symbol: str
    qty: int  # signed: + long, - short
    avg_price: float
    last_price: float = 0.0
    pnl: float = 0.0
    updated_at: datetime = Field(default_factory=utc_now)


# ---------- Strategies ----------
class Strategy(BaseDocument):
    user_id: str
    name: str
    kind: str  # ema_crossover / oi_breakout / vwap_scalping / gamma_scalping / smart_money
    enabled: bool = False
    params: Dict[str, Any] = Field(default_factory=dict)
    symbols: List[str] = Field(default_factory=list)
    fire_count: int = 0
    last_fire_at: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class StrategyCreate(BaseModel):
    name: str
    kind: str
    enabled: bool = False
    params: Dict[str, Any] = Field(default_factory=dict)
    symbols: List[str] = Field(default_factory=list)
    interval_seconds: int = 15


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    params: Optional[Dict[str, Any]] = None
    symbols: Optional[List[str]] = None


# ---------- Broker connections (mock) ----------
class BrokerConnection(BaseDocument):
    user_id: str
    broker: str  # zerodha / breeze / angel / fyers / upstox / dhan
    api_key: str = ""
    api_secret: str = ""  # never returned in public DTO
    access_token: str = ""  # daily, encrypted
    session_date: str = ""  # YYYY-MM-DD IST trading day
    credentials: Dict[str, Any] = Field(default_factory=dict)  # encrypted blob of extra fields
    connected: bool = False
    mock_mode: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class BrokerConnectionPublic(BaseModel):
    id: str
    broker: str
    connected: bool
    mock_mode: bool
    has_keys: bool
    has_access_token: bool = False
    session_date: str = ""
    fields_filled: List[str] = Field(default_factory=list)


class BrokerConnectionUpsert(BaseModel):
    broker: str
    api_key: str = ""
    api_secret: str = ""
    mock_mode: bool = True
    credentials: Dict[str, Any] = Field(default_factory=dict)


# ---------- Notifications ----------
class Notification(BaseDocument):
    user_id: str
    kind: str  # signal / order / strategy / system
    title: str
    message: str
    severity: str = "info"  # info / success / warning / danger
    read: bool = False
    created_at: datetime = Field(default_factory=utc_now)


# ---------- Backtest ----------
class BacktestRun(BaseDocument):
    user_id: str
    strategy_kind: str
    symbol: str
    period_days: int
    metrics: Dict[str, Any] = Field(default_factory=dict)
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class BacktestRequest(BaseModel):
    strategy_kind: str
    symbol: str
    period_days: int = 30
    params: Dict[str, Any] = Field(default_factory=dict)


# ---------- Parquet file metadata ----------
class ParquetFileInfo(BaseModel):
    symbol: str
    filename: str
    path: str
    size_bytes: int
    row_count: int
    last_modified: datetime
