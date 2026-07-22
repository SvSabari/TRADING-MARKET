"""Broker-agnostic order routing.

Hybrid: when the user has a connected broker session (real keys
+ access/auth tokens + mock_mode=false) we route to the real client.
Otherwise we route to the MockBroker (paper trading).

Supported live brokers: Zerodha Kite, Angel One SmartAPI, Upstox v2,
Dhan HQ, ICICI Breeze. All others fall back to mock.
"""
from __future__ import annotations

import logging
import os
import random
import string
from datetime import datetime, timezone
from typing import Dict, Optional

from services.crypto import decrypt_str
from services.instrument_map import (
    ANGEL_TOKENS, UPSTOX_KEYS,
)
from services.kite_client import get_user_kite_service

logger = logging.getLogger(__name__)
LOCAL_ONLY = os.environ.get("LOCAL_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}


def _gen_broker_order_id(broker: str) -> str:
    rnd = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f"{broker.upper()[:3]}-{rnd}"


class MockBroker:
    name = "mock"

    async def place_order(self, *, symbol: str, side: str, qty: int, price: float,
                          order_type: str = "MARKET", product: str = "MIS") -> Dict:
        slip = price * random.uniform(-0.0005, 0.0005)
        fill_price = round(price + slip, 2)
        return {
            "broker_order_id": _gen_broker_order_id(self.name),
            "status": "FILLED",
            "fill_price": fill_price,
            "filled_at": datetime.now(timezone.utc).isoformat(),
            "mode": "mock",
        }

    async def cancel_order(self, broker_order_id: str) -> Dict:
        return {"status": "CANCELLED"}


_mock = MockBroker()
_brokers: Dict[str, MockBroker] = {
    "mock": _mock, "zerodha": _mock, "breeze": _mock, "angel": _mock,
    "upstox": _mock, "dhan": _mock, "fyers": _mock,
}


def get_broker(broker_name: str) -> MockBroker:
    """Legacy accessor — returns the mock broker (callers that need real
    routing must use `route_order` with user context)."""
    return _brokers.get(broker_name.lower(), _brokers["mock"])


# --------------------------------------------------------- per-broker dispatch
async def _route_kite(db, user_id: str, *, symbol: str, side: str, qty: int,
                     price: float, order_type: str, product: str) -> Optional[Dict]:
    kite = await get_user_kite_service(db, user_id)
    if kite is None:
        return None
    try:
        broker_order_id = kite.place_order(
            tradingsymbol=symbol, exchange="NSE",
            transaction_type=side.upper(), quantity=int(qty),
            order_type=order_type, product=product, variety="regular",
            price=price if order_type == "LIMIT" else None,
        )
        return _live_response(broker_order_id, price, "live-zerodha")
    except Exception as e:
        logger.warning("Kite order failed, falling back: %s", e)
        return None


async def _route_angel(db, user_id: str, *, symbol: str, side: str, qty: int,
                       price: float, order_type: str, product: str) -> Optional[Dict]:
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "angel"})
    if not doc or doc.get("mock_mode"):
        return None
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    client_code = decrypt_str(creds.get("client_code", ""))
    pin = decrypt_str(creds.get("pin", ""))
    totp_secret = decrypt_str(creds.get("totp_secret", ""))
    auth_token = decrypt_str(creds.get("auth_token", ""))
    if not (api_key and client_code and pin and totp_secret):
        return None
    token = next((tok for tok, sym in ANGEL_TOKENS.items() if sym == symbol), None)
    if not token:
        logger.warning("Angel: no token mapping for %s", symbol)
        return None
    try:
        from services.brokers.angel_client import AngelClient
        client = AngelClient(
            api_key=api_key, client_code=client_code, pin=pin,
            totp_secret=totp_secret, auth_token=auth_token,
        )
        order_id = client.place_order(
            tradingsymbol=f"{symbol}-EQ", exchange="NSE",
            transaction_type=side.upper(), quantity=int(qty),
            symbol_token=token, order_type=order_type,
            product="INTRADAY" if product == "MIS" else "DELIVERY",
            price=price if order_type == "LIMIT" else None,
        )
        if order_id:
            return _live_response(order_id, price, "live-angel")
    except Exception as e:
        logger.warning("Angel order failed, falling back: %s", e)
    return None


async def _route_upstox(db, user_id: str, *, symbol: str, side: str, qty: int,
                        price: float, order_type: str, product: str) -> Optional[Dict]:
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "upstox"})
    if not doc or doc.get("mock_mode") or not doc.get("access_token"):
        return None
    access_token = decrypt_str(doc["access_token"])
    if not access_token:
        return None
    instrument_key = next((k for k, sym in UPSTOX_KEYS.items() if sym == symbol), None)
    if not instrument_key:
        logger.warning("Upstox: no instrument_key mapping for %s", symbol)
        return None
    try:
        from services.brokers.upstox_client import UpstoxClient
        client = UpstoxClient(access_token=access_token)
        order_id = client.place_order(
            instrument_token=instrument_key,
            transaction_type=side.upper(), quantity=int(qty),
            order_type=order_type,
            product="I" if product == "MIS" else "D",
            price=price if order_type == "LIMIT" else None,
        )
        if order_id:
            return _live_response(order_id, price, "live-upstox")
    except Exception as e:
        logger.warning("Upstox order failed, falling back: %s", e)
    return None


async def _route_dhan(db, user_id: str, *, symbol: str, side: str, qty: int,
                      price: float, order_type: str, product: str) -> Optional[Dict]:
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "dhan"})
    if not doc or doc.get("mock_mode"):
        return None
    creds = doc.get("credentials") or {}
    client_id = decrypt_str(creds.get("client_id", ""))
    access_token = decrypt_str(creds.get("access_token", ""))
    security_id = decrypt_str(creds.get(f"sec_{symbol}", ""))  # optional per-symbol map
    if not (client_id and access_token and security_id):
        return None
    try:
        from services.brokers.dhan_client import DhanClient
        client = DhanClient(client_id=client_id, access_token=access_token)
        order_id = client.place_order(
            security_id=security_id, exchange_segment="NSE_EQ",
            transaction_type=side.upper(), quantity=int(qty),
            order_type=order_type,
            product="INTRADAY" if product == "MIS" else "CNC",
            price=price if order_type == "LIMIT" else None,
        )
        if order_id:
            return _live_response(order_id, price, "live-dhan")
    except Exception as e:
        logger.warning("Dhan order failed, falling back: %s", e)
    return None


async def _route_breeze(db, user_id: str, *, symbol: str, side: str, qty: int,
                        price: float, order_type: str, product: str) -> Optional[Dict]:
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "breeze"})
    if not doc or doc.get("mock_mode"):
        return None
    from services.brokers.breeze_client import get_user_breeze_client
    client = await get_user_breeze_client(db, user_id)
    if not client:
        return None
    try:
        order_id = client.place_order(
            stock_code=symbol, exchange_code="NSE",
            transaction_type=side.upper(), quantity=int(qty),
            order_type=order_type,
            product="margin" if product == "MIS" else "cash",
            price=price if order_type == "LIMIT" else None,
        )
        if order_id:
            return _live_response(order_id, price, "live-breeze")
    except Exception as e:
        logger.warning("Breeze order failed, falling back: %s", e)
    return None


async def _route_aliceblue(db, user_id: str, *, symbol: str, side: str, qty: int,
                           price: float, order_type: str, product: str) -> Optional[Dict]:
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "aliceblue"})
    if not doc or doc.get("mock_mode") or not doc.get("access_token"):
        return None
    from services.brokers.aliceblue_client import get_user_aliceblue_client
    client = await get_user_aliceblue_client(db, user_id)
    if not client:
        return None
    
    # Needs instrument token mapping in the future, for now fallback to just standard symbol
    # This requires ALICEBLUE_TOKENS map in instrument_map.py
    from services.instrument_map import ALICEBLUE_TOKENS
    instrument_token = next((k for k, sym in ALICEBLUE_TOKENS.items() if sym == symbol), None)
    if not instrument_token:
        # Fallback format: NSE|26000
        instrument_token = f"NSE|{symbol}"
        
    try:
        order_id = client.place_order(
            instrument_token=instrument_token,
            transaction_type=side.upper(), quantity=int(qty),
            order_type=order_type,
            product="I" if product == "MIS" else "D",
            price=price if order_type == "LIMIT" else None,
        )
        if order_id:
            return _live_response(order_id, price, "live-aliceblue")
    except Exception as e:
        logger.warning("AliceBlue order failed, falling back: %s", e)
    return None


def _live_response(order_id: str, price: float, mode: str) -> Dict:
    return {
        "broker_order_id": order_id, "status": "PLACED",
        "fill_price": price, "filled_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    }


_LIVE_DISPATCH = {
    "zerodha": _route_kite,
    "angel": _route_angel,
    "upstox": _route_upstox,
    "dhan": _route_dhan,
    "breeze": _route_breeze,
    "aliceblue": _route_aliceblue,
}


async def route_order(db, user_id: str, broker_name: str, *,
                      symbol: str, side: str, qty: int, price: float,
                      order_type: str = "MARKET", product: str = "MIS") -> Dict:
    """High-level routing: routes to the real broker if requested, otherwise mock."""
    if LOCAL_ONLY or broker_name.lower() == "mock":
        return await _mock.place_order(symbol=symbol, side=side, qty=qty, price=price,
                                       order_type=order_type, product=product)
                                       
    handler = _LIVE_DISPATCH.get(broker_name.lower())
    if handler is not None:
        result = await handler(
            db, user_id, symbol=symbol, side=side, qty=qty, price=price,
            order_type=order_type, product=product,
        )
        if result is not None:
            return result
            
    # If a real broker was requested but failed (e.g. API error, IP rejection)
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail=f"Broker {broker_name} rejected the order or is disconnected.")
