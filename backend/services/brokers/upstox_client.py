"""Upstox API v2 client wrapper.

`upstox-python-sdk` provides typed API classes; we use them per-call so
no long-lived session is held. The access token is OAuth-issued; the
OAuth flow itself is handled in `routers.broker_routes` (similar to
Kite — redirect to Upstox login, capture the auth code, exchange for
an access token).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("upstox-client")


class UpstoxClient:
    def __init__(self, *, access_token: str) -> None:
        import upstox_client  # type: ignore
        cfg = upstox_client.Configuration()
        cfg.access_token = access_token
        self._cfg = cfg
        self._api_client = upstox_client.ApiClient(cfg)
        self._upstox = upstox_client

    # ---------------------------------------------------------- orders
    def place_order(self, *, instrument_token: str, transaction_type: str,
                    quantity: int, order_type: str = "MARKET",
                    product: str = "I", price: Optional[float] = None) -> str:
        """instrument_token = NSE_EQ|<ISIN> (Upstox key format)."""
        u = self._upstox
        body = u.PlaceOrderV3Request(
            quantity=int(quantity),
            product=product,                # I=Intraday, D=Delivery
            validity="DAY",
            price=float(price) if (price and order_type.upper() == "LIMIT") else 0.0,
            tag="algonid",
            instrument_token=instrument_token,
            order_type=order_type.upper(),
            transaction_type=transaction_type.upper(),
            disclosed_quantity=0,
            trigger_price=0.0,
            is_amo=False,
            slice=False,
        )
        api = u.OrderApiV3(self._api_client)
        resp = api.place_order(body)
        if hasattr(resp, "data") and getattr(resp.data, "order_ids", None):
            return resp.data.order_ids[0]
        if hasattr(resp, "data") and getattr(resp.data, "order_id", None):
            return resp.data.order_id
        return str(resp)

    def ltp(self, instrument_key: str) -> float:
        u = self._upstox
        try:
            api = u.MarketQuoteApi(self._api_client)
            resp = api.ltp(instrument_key, api_version="v2")
            data = resp.data or {}
            for _, payload in data.items():
                return float(payload.last_price or 0)
        except Exception as e:
            logger.warning("upstox ltp failed: %s", e)
        return 0.0
