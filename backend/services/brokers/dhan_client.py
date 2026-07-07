"""Dhan HQ client wrapper.

`dhanhq` is the official SDK. Auth is a static client_id + access_token
(no daily refresh needed). Orders go through `place_order(...)`.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("dhan-client")


class DhanClient:
    def __init__(self, *, client_id: str, access_token: str) -> None:
        from dhanhq import dhanhq  # type: ignore
        self._dhan = dhanhq(client_id, access_token)

    def place_order(self, *, security_id: str, exchange_segment: str,
                    transaction_type: str, quantity: int,
                    order_type: str = "MARKET", product: str = "INTRADAY",
                    price: Optional[float] = None) -> str:
        d = self._dhan
        resp = d.place_order(
            security_id=str(security_id),
            exchange_segment=getattr(d, exchange_segment, exchange_segment),
            transaction_type=getattr(d, transaction_type.upper(), transaction_type),
            quantity=int(quantity),
            order_type=getattr(d, order_type.upper(), order_type),
            product_type=getattr(d, product.upper(), product),
            price=float(price) if (price and order_type.upper() == "LIMIT") else 0,
        )
        if isinstance(resp, dict):
            return str(resp.get("data", {}).get("orderId") or resp.get("orderId") or "")
        return str(resp)

    def ltp(self, security_id: str, exchange_segment: str = "NSE_EQ") -> float:
        try:
            d = self._dhan
            r = d.ohlc_data(securities={exchange_segment: [int(security_id)]})
            if isinstance(r, dict) and r.get("data"):
                seg = r["data"].get(exchange_segment, {})
                payload = seg.get(str(security_id), {})
                return float(payload.get("last_price") or 0)
        except Exception as e:
            logger.warning("dhan ltp failed: %s", e)
        return 0.0
