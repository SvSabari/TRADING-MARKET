import asyncio
from sqlalchemy import text
from db import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text('ALTER TABLE managed_users ADD COLUMN place_order BOOLEAN DEFAULT TRUE'))
            await session.commit()
            print('Column added successfully')
        except Exception as e:
            print('Error:', e)

if __name__ == "__main__":
    asyncio.run(main())
