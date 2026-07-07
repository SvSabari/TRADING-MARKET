import asyncio
from db import db
from services.crypto import decrypt_str
from breeze_connect import BreezeConnect
from datetime import datetime

async def main():
    doc = await db.broker_connections.find_one({"broker": "breeze"})
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    secret_key = decrypt_str(creds.get("api_secret", ""))
    session_token = decrypt_str(creds.get("session_token", ""))
    
    b = BreezeConnect(api_key=api_key)
    b.generate_session(api_secret=secret_key, session_token=session_token)
    
    # Get current expiry for breeze. format is usually ISO
    expiry = datetime.now().strftime("%Y-%m-%dT06:00:00.000Z") # Wait, how does Breeze expect dates?
    
    res = b.get_option_chain_quotes(
        stock_code="NIFTY", 
        exchange_code="NFO", 
        expiry_date="", # Let's see if empty expiry gets all, or we need to find nearest
        product_type="options"
    )
    
    print(res)

asyncio.run(main())
