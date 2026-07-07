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
        self._b = BreezeConnect(api_key=api_key)
        try:
            self._b.generate_session(api_secret=secret_key, session_token=session_token)
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
