import pymongo
from db import AsyncSessionLocal
from models import OptionCandle
import asyncio
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import datetime

engine = create_engine("mysql+pymysql://root:@localhost/algo_trading_db")
SessionLocal = sessionmaker(bind=engine)

def migrate_mongo_to_mysql():
    client = pymongo.MongoClient('mongodb://localhost:27017/')
    db = client['algo_trading_db']
    col = db['option_candles']
    
    total = col.count_documents({})
    print(f"Total documents to migrate: {total}")
    
    session = SessionLocal()
    batch_size = 5000
    batch = []
    
    cursor = col.find({}, no_cursor_timeout=True)
    count = 0
    for doc in cursor:
        candle = OptionCandle(
            symbol=doc.get('symbol'),
            strike=doc.get('strike'),
            opt_type=doc.get('opt_type'),
            expiry=doc.get('expiry'),
            ts=doc.get('ts'),
            ltp=doc.get('ltp')
        )
        batch.append(candle)
        count += 1
        
        if len(batch) >= batch_size:
            session.add_all(batch)
            session.commit()
            print(f"Migrated {count}/{total}...")
            batch = []
            
    if batch:
        session.add_all(batch)
        session.commit()
        
    print(f"Successfully migrated {count} option candles to MySQL!")
    cursor.close()

if __name__ == "__main__":
    migrate_mongo_to_mysql()
