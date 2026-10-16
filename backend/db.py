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


async def init_db():
    """Create all MySQL tables if they do not exist."""
    import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

