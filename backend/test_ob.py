import asyncio
from db import AsyncSessionLocal
from services.brokers.aliceblue_client import get_user_aliceblue_client
from models import BrokerConnection
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BrokerConnection).where(BrokerConnection.broker == 'aliceblue')
        )
        conn = result.scalar_one_or_none()
        if not conn:
            print("No alice blue connection found")
            return
            
        client = await get_user_aliceblue_client(session, conn.user_id)
        if not client:
            print("Failed to get client")
            return
            
        try:
            print("Fetching order book via pya3...")
            orders = client.get_order_book()
            print(orders)
        except Exception as e:
            print("Error fetching order book:", e)

if __name__ == "__main__":
    asyncio.run(main())
