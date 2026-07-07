"""Zerodha Kite Connect client wrapper.

A thin abstraction over the official `kiteconnect` SDK. Each call site
instantiates a fresh `KiteService` from decrypted DB credentials so we
never hold long-lived API keys in memory beyond the request scope.
"""
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class KiteService:
    def __init__(self, api_key: str, access_token: Optional[str] = None):
        try:
            from kiteconnect import KiteConnect
        except ImportError as e:
            raise RuntimeError("kiteconnect is not installed; live Zerodha mode is unavailable") from e
        self.api_key = api_key
        self._kite = KiteConnect(api_key=api_key)
        if access_token:
            self._kite.set_access_token(access_token)

    # --- session ---
    def login_url(self, redirect_params: Optional[str] = None) -> str:
        url = self._kite.login_url()
        if redirect_params:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}redirect_params={redirect_params}"
        return url

    def generate_session(self, request_token: str, api_secret: str) -> dict:
        return self._kite.generate_session(request_token, api_secret=api_secret)

    # --- orders ---
    def place_order(self, *, tradingsymbol: str, exchange: str, transaction_type: str,
                    quantity: int, order_type: str = "MARKET", product: str = "MIS",
                    variety: str = "regular", price: Optional[float] = None) -> str:
        kwargs = dict(
            variety=variety, exchange=exchange, tradingsymbol=tradingsymbol,
            transaction_type=transaction_type, quantity=int(quantity),
            order_type=order_type, product=product,
        )
        if price is not None and order_type == "LIMIT":
            kwargs["price"] = price
        return self._kite.place_order(**kwargs)

    # --- quotes ---
    def quotes(self, symbols: List[str]) -> dict:
        return self._kite.quote(symbols)

    def ltp(self, symbols: List[str]) -> dict:
        return self._kite.ltp(symbols)

    def instruments(self, exchange: Optional[str] = None) -> list:
        return self._kite.instruments(exchange) if exchange else self._kite.instruments()


async def get_user_kite_service(db, user_id: str) -> Optional[KiteService]:
    """Return a KiteService for the user if they have a connected Kite app.

    Returns None when keys missing or mock_mode is enabled — callers should
    fall back to the mock broker / synthetic data.
    """
    from services.crypto import decrypt_str
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "zerodha"})
    if not doc or doc.get("mock_mode") or not doc.get("api_key") or not doc.get("access_token"):
        return None
    api_key = decrypt_str(doc["api_key"])
    access_token = decrypt_str(doc.get("access_token", ""))
    if not api_key or not access_token:
        return None
    return KiteService(api_key=api_key, access_token=access_token)
