"""Angel One SmartAPI client wrapper.

The SmartAPI SDK handles HTTPS REST + TOTP auth. We expose two methods:
  * `login()` — does TOTP-based session generation, returns
    `{auth_token, refresh_token, feed_token}` for storage.
  * `place_order(...)` — places a CNC / MIS order on NSE EQ.

Use `pyotp` to derive the live 6-digit TOTP from the user's stored
base32 secret (Angel mandates TOTP on every session login).
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger("angel-client")


def _import_smart():
    from SmartApi import SmartConnect  # type: ignore
    return SmartConnect


class AngelClient:
    """Thin wrapper — instantiate per-request from decrypted creds."""

    def __init__(self, *, api_key: str, client_code: str, pin: str,
                 totp_secret: str, auth_token: str = "",
                 refresh_token: str = "", feed_token: str = "") -> None:
        SmartConnect = _import_smart()
        self._smart = SmartConnect(api_key=api_key)
        self.api_key = api_key
        self.client_code = client_code
        self._pin = pin
        self._totp_secret = totp_secret
        self.auth_token = auth_token
        self.refresh_token = refresh_token
        self.feed_token = feed_token
        if auth_token:
            # SDK stores the token internally on `setAccessToken` calls during login
            self._smart.access_token = auth_token

    # ---------------------------------------------------------- session
    def login(self) -> Dict[str, str]:
        """Run TOTP-based session generation. Returns the 3 tokens."""
        import pyotp
        totp = pyotp.TOTP(self._totp_secret).now()
        data = self._smart.generateSession(self.client_code, self._pin, totp)
        if not data or not data.get("status"):
            raise RuntimeError(f"Angel login failed: {data}")
        d = data["data"]
        self.auth_token = d.get("jwtToken", "")
        self.refresh_token = d.get("refreshToken", "")
        # feed_token is fetched separately
        try:
            self.feed_token = self._smart.getfeedToken()
        except Exception as e:
            logger.warning("feed_token fetch failed: %s", e)
            self.feed_token = ""
        return {
            "auth_token": self.auth_token,
            "refresh_token": self.refresh_token,
            "feed_token": self.feed_token,
        }

    # ---------------------------------------------------------- orders
    def place_order(self, *, tradingsymbol: str, exchange: str, transaction_type: str,
                    quantity: int, symbol_token: str,
                    order_type: str = "MARKET", product: str = "INTRADAY",
                    price: Optional[float] = None) -> str:
        params = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": symbol_token,
            "transactiontype": transaction_type.upper(),
            "exchange": exchange or "NSE",
            "ordertype": order_type.upper(),
            "producttype": product.upper(),
            "duration": "DAY",
            "price": str(price) if (price and order_type.upper() == "LIMIT") else "0",
            "squareoff": "0", "stoploss": "0",
            "quantity": str(int(quantity)),
        }
        resp = self._smart.placeOrder(params)
        if isinstance(resp, dict):
            return str(resp.get("data", {}).get("orderid") or resp.get("orderid") or "")
        return str(resp)

    def ltp(self, exchange: str, tradingsymbol: str, symbol_token: str) -> float:
        try:
            r = self._smart.ltpData(exchange, tradingsymbol, symbol_token)
            return float(r.get("data", {}).get("ltp") or 0)
        except Exception as e:
            logger.warning("ltp fetch failed: %s", e)
            return 0.0
