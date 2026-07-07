import asyncio
from db import db

async def main():
    sigs = await db.tv_signals.find().to_list(length=10)
    print("Signals:", [s.get("symbol") for s in sigs])
    
    ords = await db.orders.find().sort("filled_at", -1).to_list(length=10)
    for o in ords:
        print(f"Order: {o.get('symbol')} {o.get('side')} {o.get('status')} via {o.get('broker')}")

asyncio.run(main())
