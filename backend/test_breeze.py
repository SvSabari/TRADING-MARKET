import asyncio
from db import db
from services.crypto import decrypt_str
from breeze_connect import BreezeConnect

async def main():
    doc = await db.broker_connections.find_one({"broker": "breeze"})
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    secret_key = decrypt_str(creds.get("api_secret", ""))
    session_token = decrypt_str(creds.get("session_token", ""))
    
    b = BreezeConnect(api_key=api_key)
    b.generate_session(api_secret=secret_key, session_token=session_token)
    
    def on_ticks(ticks):
        print("TICK RECEIVED:", ticks)
        import os
        os._exit(0)
        
    b.on_ticks = on_ticks
    b.ws_connect()
    b.subscribe_feeds(exchange_code="NSE", stock_code="RELIANCE", product_type="cash", get_exchange_quotes=True, get_market_depth=False)
    
    await asyncio.sleep(10)
    print("TIMEOUT")
    import os
    os._exit(0)

asyncio.run(main())
