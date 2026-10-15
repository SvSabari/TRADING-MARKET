from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, Text
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="trader")

class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    broker = Column(String(50))
    is_data_feed = Column(Boolean, default=False)
    is_order_exec = Column(Boolean, default=False)
    mock_mode = Column(Boolean, default=True)
    connected = Column(Boolean, default=False)
    credentials = Column(JSON)
    access_token = Column(Text)
    session_date = Column(String(50))

class ManagedUser(Base):
    __tablename__ = "managed_users"
    id = Column(String(36), primary_key=True)
    trader_id = Column(String(36), index=True)
    name = Column(String(255))
    email = Column(String(255))
    max_allocation = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    auto_copy = Column(Boolean, default=False)
    place_order = Column(Boolean, default=True)
    account_status = Column(String(50), default="active")
    phone = Column(String(20))
    password_hash = Column(String(255))
    profit_pct = Column(Float, default=0.0)
    bank_account = Column(String(100))
    brokers = Column(JSON)
    symbol_multipliers = Column(JSON)
    capital_allocation_pct = Column(Float, default=100.0)
    created_at = Column(DateTime)

class MarketCandle(Base):
    __tablename__ = "market_candles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(100), index=True)
    timeframe = Column(String(20), index=True)
    ts = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)


class SymbolMaster(Base):
    __tablename__ = 'symbol_master'
    symbol = Column(String(100), primary_key=True)
    lot_size = Column(Integer)
    exchange = Column(String(50))

class OptionCandle(Base):
    __tablename__ = "option_candles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(100), index=True)
    strike = Column(Float, index=True)
    opt_type = Column(String(10), index=True)
    expiry = Column(String(50))
    ts = Column(DateTime, index=True)
    ltp = Column(Float)

class Order(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    broker = Column(String(50))
    broker_order_id = Column(String(100))
    symbol = Column(String(100))
    side = Column(String(20))
    qty = Column(Integer)
    price = Column(Float)
    order_type = Column(String(50))
    product = Column(String(50))
    status = Column(String(50))
    source = Column(String(50))
    signal_id = Column(String(36))
    placed_at = Column(DateTime)
    filled_at = Column(DateTime)
    pnl = Column(Float, default=0.0)
    target = Column(Float)
    stop_loss = Column(Float)
    is_bracket = Column(Boolean, default=False)
    reject_reason = Column(String(255))
    is_mock = Column(Boolean, default=False)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    kind = Column(String(50))
    title = Column(String(255))
    message = Column(String(1000))
    severity = Column(String(20))
    read = Column(Boolean, default=False)
    created_at = Column(DateTime)

class Strategy(Base):
    __tablename__ = "strategies"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    name = Column(String(100))
    kind = Column(String(50))
    enabled = Column(Boolean, default=False)
    copy_to_users = Column(Boolean, default=True)
    params = Column(JSON)
    symbols = Column(JSON)
    fire_count = Column(Integer, default=0)
    last_fire_at = Column(String(50))
    created_at = Column(DateTime)

class TVSignal(Base):
    __tablename__ = "tv_signals"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    symbol = Column(String(100))
    side = Column(String(10))
    price = Column(Float)
    qty = Column(Integer)
    strategy = Column(String(100))
    payload = Column(JSON)
    received_at = Column(DateTime)
    processed = Column(Boolean, default=False)
    order_id = Column(String(36))

class POISnapshot(Base):
    __tablename__ = "poi_snapshots"
    date = Column(String(20), primary_key=True)
    oi_data = Column(JSON)
    close_data = Column(JSON)
    updated_at = Column(String(50))

class Idempotency(Base):
    __tablename__ = "idempotency"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), index=True)
    key = Column(String(255), index=True, unique=True)
    signal_id = Column(String(36))
    created_at = Column(DateTime)

class Position(Base):
    __tablename__ = "positions"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    symbol = Column(String(100))
    qty = Column(Integer)
    avg_price = Column(Float)
    last_price = Column(Float)
    updated_at = Column(DateTime)
    is_mock = Column(Boolean, default=False)
    
class TelegramSettings(Base):
    __tablename__ = "telegram_settings"
    user_id = Column(String(36), primary_key=True)
    bot_token = Column(String(1000))
    chat_id = Column(String(100))
    enabled = Column(Boolean, default=True)

class PushSettings(Base):
    __tablename__ = "push_settings"
    user_id = Column(String(36), primary_key=True)
    enabled = Column(Boolean, default=True)

class PushToken(Base):
    __tablename__ = "push_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), index=True)
    token = Column(String(1000))
    platform = Column(String(50))
    
class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    strategy_kind = Column(String(100))
    symbol = Column(String(100))
    period_days = Column(Integer)
    metrics = Column(JSON)
    equity_curve = Column(JSON)
    trades_log = Column(JSON)
    created_at = Column(DateTime)
