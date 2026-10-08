import os
import json
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv('backend/.env')

Base = declarative_base()

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
    access_token = Column(String(1000))
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
    brokers = Column(JSON)
    symbol_multipliers = Column(JSON)
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

class Backtest(Base):
    __tablename__ = "backtests"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    strategy = Column(String(100))
    symbol = Column(String(100))
    timeframe = Column(String(20))
    start_date = Column(String(50))
    end_date = Column(String(50))
    initial_capital = Column(Float)
    final_capital = Column(Float)
    total_return = Column(Float)
    max_drawdown = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)
    status = Column(String(50))
    error = Column(String(1000))
    created_at = Column(DateTime)
    trades = Column(JSON)

def run_migration():
    print("Connecting to MongoDB Atlas...")
    mongo_client = MongoClient(os.getenv("MONGO_URL"))
    mongo_db = mongo_client[os.getenv("DB_NAME")]

    print("Connecting to Local MySQL...")
    engine = create_engine("mysql+pymysql://root:@localhost/algo_trading_db")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Migrating users...")
    for doc in mongo_db.users.find():
        u = User(id=str(doc.get("_id")), email=doc.get("email"), password_hash=doc.get("password_hash"), role=doc.get("role"))
        session.add(u)
    session.commit()

    print("Migrating broker_connections...")
    for doc in mongo_db.broker_connections.find():
        b = BrokerConnection(
            id=str(doc.get("_id")), user_id=doc.get("user_id"), broker=doc.get("broker"),
            is_data_feed=doc.get("is_data_feed"), is_order_exec=doc.get("is_order_exec"),
            mock_mode=doc.get("mock_mode"), connected=doc.get("connected"),
            credentials=doc.get("credentials"), access_token=doc.get("access_token"),
            session_date=doc.get("session_date")
        )
        session.add(b)
    session.commit()

    print("Migrating market_candles (this will take a moment)...")
    batch = []
    count = 0
    for doc in mongo_db.market_candles.find():
        c = MarketCandle(
            symbol=doc.get("symbol"), timeframe=doc.get("timeframe"), ts=doc.get("ts"),
            open=doc.get("open"), high=doc.get("high"), low=doc.get("low"),
            close=doc.get("close"), volume=doc.get("volume")
        )
        batch.append(c)
        if len(batch) >= 10000:
            session.bulk_save_objects(batch)
            session.commit()
            count += len(batch)
            print(f"  Inserted {count} candles...")
            batch = []
    if batch:
        session.bulk_save_objects(batch)
        session.commit()
        
    print("Migration Complete!")

if __name__ == "__main__":
    run_migration()
