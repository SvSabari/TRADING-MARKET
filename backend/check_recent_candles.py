import asyncio
from db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        for sym in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'RELIANCE']:
            res = await session.execute(text(f"SELECT DATE(ts) as d, MIN(ts), MAX(ts), COUNT(*) FROM market_candles WHERE symbol='{sym}' GROUP BY d ORDER BY d DESC LIMIT 3"))
            print(f"=== {sym} ===")
            for r in res.fetchall():
                print(" ", r)

if __name__ == '__main__':
    asyncio.run(check())
