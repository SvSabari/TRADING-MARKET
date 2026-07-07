import asyncio
from db import db
from services.crypto import decrypt_str
from breeze_connect import BreezeConnect
from services.instrument_map import breeze_token_map

async def main():
    doc = await db.broker_connections.find_one({"broker": "breeze"})
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    secret_key = decrypt_str(creds.get("api_secret", ""))
    session_token = decrypt_str(creds.get("session_token", ""))
    
    b = BreezeConnect(api_key=api_key)
    b.generate_session(api_secret=secret_key, session_token=session_token)
    
    b.interval = ""
    
    for breeze_sym, std_sym in breeze_token_map().items():
        try:
            res = b.get_stock_token_value(
                exchange_code="NSE", stock_code=breeze_sym, product_type="cash",
                get_exchange_quotes=True, get_market_depth=False
            )
            if isinstance(res, Exception):
                print(f"FAILED for {std_sym} -> ICICI {breeze_sym} -> returned Exception: {res}")
            else:
                exch_token, market_depth_token = res
                print(f"SUCCESS for {std_sym} -> ICICI {breeze_sym} -> token {exch_token}")
        except Exception as e:
            print(f"FAILED for {std_sym} -> {breeze_sym} -> {e}")

asyncio.run(main())
