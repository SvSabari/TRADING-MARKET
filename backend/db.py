import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

MONGO_URL = os.getenv("MONGO_URL")  # We'll leave this for fallback/reference
MYSQL_URL = os.getenv("MYSQL_URL", "mysql+aiomysql://root:@localhost/algo_trading_db")

engine = create_async_engine(MYSQL_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Note: The rest of the app will need heavy modifications to use `session` instead of `db.collection`
