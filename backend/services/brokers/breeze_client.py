"""ICICI Breeze (Direct) client wrapper.

`breeze-connect` is the official SDK. Auth needs api_key + secret_key +
session_token (the session_token is generated daily via the Breeze
customer portal login URL).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("breeze-client")


class BreezeClient:
    def __init__(self, *, api_key: str, secret_key: str, session_token: str) -> None:
        from breeze_connect import BreezeConnect  # type: ignore
        
        # Suppress extremely verbose SDK loggers from polluting the terminal
        import logging
        logging.getLogger("APILogger").propagate = False
        logging.getLogger("WebsocketLogger").propagate = False
        
        self._b = BreezeConnect(api_key=api_key)
        self._session_ok = False
        try:
            self._b.generate_session(api_secret=secret_key, session_token=session_token)
            self._session_ok = True
        except Exception as e:
            logger.warning("breeze generate_session failed: %s", e)

    def place_order(self, *, stock_code: str, exchange_code: str,
                    transaction_type: str, quantity: int,
                    order_type: str = "MARKET", product: str = "MIS",
                    price: Optional[float] = None) -> str:
        action = "buy" if transaction_type.upper() == "BUY" else "sell"
        resp = self._b.place_order(
            stock_code=stock_code, exchange_code=exchange_code or "NSE",
            product=product.lower(), action=action,
            order_type=order_type.lower(),
            stoploss="", quantity=str(int(quantity)),
            price=str(price) if (price and order_type.upper() == "LIMIT") else "0",
            validity="day", validity_date="", disclosed_quantity="0",
            expiry_date="", right="others", strike_price="0",
            user_remark="algonid",
        )
        if isinstance(resp, dict):
            return str(resp.get("Success", {}).get("order_id") or resp.get("order_id") or "")
        return str(resp)

    def ltp(self, stock_code: str, exchange_code: str = "NSE") -> float:
        try:
            r = self._b.get_quotes(
                stock_code=stock_code, exchange_code=exchange_code,
                product_type="cash",
            )
            if isinstance(r, dict) and r.get("Success"):
                rows = r["Success"]
                if rows:
                    return float(rows[0].get("ltp") or 0)
        except Exception as e:
            logger.warning("breeze ltp failed: %s", e)
        return 0.0

    def get_quotes(self, **kwargs):
        return self._b.get_quotes(**kwargs)
        
    def get_option_chain_quotes(self, **kwargs):
        return self._b.get_option_chain_quotes(**kwargs)


_client_cache: dict = {}


async def get_user_breeze_client(db, user_id: str) -> Optional[BreezeClient]:
    """
    Return a BreezeClient for the user's is_data_feed=True breeze connection.
    Falls back to any connected breeze connection if none is marked as data feed.
    Returns None if session is invalid/expired.
    """
    # Prefer the connection marked as data feed
    doc = await db.broker_connections.find_one(
        {"user_id": user_id, "broker": "breeze", "is_data_feed": True}
    )
    if not doc:
        # Fall back to any breeze connection for this user
        doc = await db.broker_connections.find_one(
            {"user_id": user_id, "broker": "breeze", "connected": True}
        )
    if not doc:
        # Final fallback: any breeze connection across all users (shared key)
        doc = await db.broker_connections.find_one(
            {"broker": "breeze", "is_data_feed": True}
        )
    if not doc:
        return None

    from services.crypto import decrypt_str
    
    creds = doc.get("credentials") or {}
    
    api_key = decrypt_str(doc.get("api_key", ""))
    if not api_key: api_key = creds.get("api_key", "")
    
    secret_key = decrypt_str(doc.get("api_secret", ""))
    if not secret_key: secret_key = creds.get("api_secret", "")
    
    session_token = decrypt_str(doc.get("access_token", ""))
    if not session_token: session_token = creds.get("session_token", "")
    
    if not (api_key and secret_key and session_token):
        return None
        
    # Use cache to avoid recreating session every request
    cache_key = (api_key, session_token)
    if cache_key in _client_cache:
        cached = _client_cache[cache_key]
        if cached._session_ok:
            return cached
        # Session was bad last time — retry
        _client_cache.pop(cache_key, None)
        
    try:
        client = BreezeClient(api_key=api_key, secret_key=secret_key, session_token=session_token)
        if client._session_ok:
            _client_cache[cache_key] = client
            return client
        logger.warning("Breeze session not OK for user %s", user_id[:8])
        return None
    except Exception as e:
        logger.exception("Failed to create BreezeClient: %s", e)
        return None
