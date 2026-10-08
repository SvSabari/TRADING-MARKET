"""Alice Blue API v3 client wrapper.

We use the official `pya3` SDK to handle authentication and order placement.
"""
from __future__ import annotations

import logging
from typing import Optional
from pya3 import Aliceblue, TransactionType, OrderType, ProductType

logger = logging.getLogger("aliceblue-client")

class AliceBlueClient:
    def __init__(self, *, client_code: str, api_key: str, session_id: str) -> None:
        self.client_code = client_code
        self.api_key = api_key
        
        # New A3 API: Generate SHA-256 Checksum and grab JWT Token
        import hashlib
        import requests
        checksum_raw = f"{client_code}{api_key}".encode('utf-8')
        checksum = hashlib.sha256(checksum_raw).hexdigest()
        
        payload = {
            "userId": client_code,
            "userData": checksum
        }
        resp = requests.post("https://a3.aliceblueonline.com/open-api/od/v1/users/getUserDetails", json=payload, headers={"Content-Type": "application/json"})
        
        try:
            data = resp.json(); print(f"AliceBlue API Response: {data}")
            # The A3 API returns the JWT Bearer token in the sessionID field
            self._a3_token = data.get("sessionID", session_id); logger.error(f"AliceBlue Auth A3 Response: {data}")
        except Exception:
            self._a3_token = session_id

        self._alice = Aliceblue(user_id=client_code, api_key=api_key)
        self._alice.session_id = self._a3_token

    # ---------------------------------------------------------- orders
    def place_order(self, *, instrument_token: str, transaction_type: str,
                    quantity: int, order_type: str = "MARKET",
                    product: str = "I", price: Optional[float] = None) -> str:
        import requests
        try:
            exchange, token = instrument_token.split("|")
        except ValueError:
            exchange, token = "NSE", instrument_token
            
        t_type = "BUY" if transaction_type.upper() == "BUY" else "SELL"
        o_type = "MARKET"
        if order_type.upper() == "LIMIT":
            o_type = "LIMIT"
        elif order_type.upper() == "SL-M":
            o_type = "SL-M"
        elif order_type.upper() == "SL":
            o_type = "SL"
            
        p_type = "INTRADAY" if product.upper() == "I" else "LONGTERM"
        
        payload = [{
            "exchange": exchange,
            "instrumentId": str(token),
            "transactionType": t_type,
            "quantity": int(quantity),
            "product": p_type,
            "orderComplexity": "REGULAR",
            "orderType": o_type,
            "validity": "DAY",
            "price": str(price) if price else "0",
            "slLegPrice": "",
            "targetLegPrice": "",
            "slTriggerPrice": "",
            "disclosedQuantity": "",
            "marketProtectionPercent": "",
            "deviceId": "traderspro123",
            "trailingSlAmount": "",
            "apiOrderSource": "",
            "algoId": "",
            "orderTag": "algonid"
        }]
        
        headers = {
            "Authorization": f"Bearer {self._a3_token}",
            "Content-Type": "application/json"
        }
        
        resp = requests.post(
            "https://a3.aliceblueonline.com/open-api/od/v1/orders/placeorder",
            json=payload,
            headers=headers
        )
        
        data = resp.json()
        
        # Check for list response
        if isinstance(data, list) and len(data) > 0:
            res = data[0]
            if res.get("status") == "Ok" and res.get("brokerOrderId"):
                return res.get("brokerOrderId")
            raise Exception(res.get("message", "Unknown error in list response"))
            
        # Check for dict response
        if isinstance(data, dict):
            if data.get("status") == "Ok" and "result" in data and len(data["result"]) > 0:
                res = data["result"][0]
                if res.get("brokerOrderId"):
                    return res.get("brokerOrderId")
                raise Exception(res.get("message", str(data)))
                
        logger.error(f"Alice Blue A3 order failed: {data}")
        raise Exception(f"Alice Blue A3 order rejected: {data}")
        
    def __del__(self) -> None:
        pass
        
    def get_profile(self) -> dict:
        return self._alice.get_profile()
        
    def get_funds(self) -> dict:
        return self._alice.get_balance()
        
    def get_order_book(self) -> dict:
        return self._alice.order_data()

    def ltp(self, instrument_token: str) -> float:
        """Fallback LTP fetcher if not using websocket."""
        try:
            exchange, token = instrument_token.split("|")
        except ValueError:
            exchange, token = "NSE", instrument_token
            
        instrument = self._alice.get_instrument_by_token(exchange, int(token))
        resp = self._alice.get_scrip_info(instrument)
        if isinstance(resp, dict) and "LTP" in resp:
            return float(resp["LTP"])
        return 0.0

    def get_order_history(self, broker_order_id: str) -> dict:
        return self._alice.get_order_history(broker_order_id)

    def modify_order(self, *, transaction_type: str, instrument_token: str, product: str,
                     broker_order_id: str, order_type: str, quantity: int,
                     price: float = 0.0, trigger_price: float = 0.0) -> dict:
        import requests
        o_type = "MARKET"
        if order_type.upper() == "LIMIT":
            o_type = "LIMIT"
        elif order_type.upper() == "SL-M":
            o_type = "SL-M"
        elif order_type.upper() == "SL":
            o_type = "SL"

        payload = {
            "brokerOrderId": broker_order_id,
            "quantity": int(quantity),
            "orderType": o_type,
            "slTriggerPrice": str(trigger_price) if trigger_price else "0",
            "price": str(price) if price else "0",
            "slLegPrice": "0",
            "trailingSLAmount": "",
            "targetLegPrice": "0",
            "validity": "DAY",
            "disclosedQuantity": "0",
            "marketProtection": "",
            "deviceId": "traderspro123"
        }
        headers = {
            "Authorization": f"Bearer {self._a3_token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            "https://a3.aliceblueonline.com/open-api/od/v1/orders/modify",
            json=payload, headers=headers
        )
        return resp.json()

    def cancel_order(self, broker_order_id: str) -> dict:
        import requests
        headers = {
            "Authorization": f"Bearer {self._a3_token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            "https://a3.aliceblueonline.com/open-api/od/v1/orders/cancel",
            json={"brokerOrderId": str(broker_order_id)}, headers=headers
        )
        return resp.json()

    def get_trade_book(self) -> dict:
        return self._alice.get_trade_book()

    def get_basket_margin(self, orders: list) -> dict:
        """
        orders should be a list of dicts matching Aliceblue's required structure:
        [{ "exchange": "NSE", "tradingSymbol": "TCS-EQ", "price": "3056.8", "qty": "1", 
           "product": "CNC", "priceType": "L", "triggerPrice": "", "transType": "B" }]
        """
        return self._alice.basket_margin(orders)

    def exit_bracket_order(self, broker_order_id: str, symbol_order_id: str = "NA", status: str = "open") -> dict:
        """
        Usually symbolOrderId is NA and status is open, depending on the response from order book.
        """
        return self._alice.exitboorder(broker_order_id, symbol_order_id, status)

    def get_historical(self, instrument_token: str, from_datetime, to_datetime, interval: str = "1", indices: bool = False) -> dict:
        try:
            exchange, token = instrument_token.split("|")
        except ValueError:
            exchange, token = "NSE", instrument_token
            
        try:
            instrument = self._alice.get_instrument_by_token(exchange, int(token))
        except ValueError:
            sym = f"{token}-EQ" if exchange == "NSE" and "-EQ" not in token else token
            instrument = self._alice.get_instrument_by_symbol(exchange, sym)
            
        return self._alice.get_historical(instrument, from_datetime, to_datetime, interval, indices)

async def get_user_aliceblue_client(db, user_id: str) -> Optional[AliceBlueClient]:
    from services.crypto import decrypt_str
    # Support both MongoDB (legacy) and SQLAlchemy AsyncSession
    if hasattr(db, "broker_connections"):
        # MongoDB path (legacy)
        doc = await db.broker_connections.find_one({
            "user_id": user_id,
            "broker": "aliceblue"
        })
        if not doc or "access_token" not in doc:
            return None
        try:
            session_id = decrypt_str(doc["access_token"])
            return AliceBlueClient(
                client_code=decrypt_str(doc["credentials"]["user_id"]),
                api_key=decrypt_str(doc["credentials"]["api_key"]),
                session_id=session_id
            )
        except Exception:
            return None
    else:
        # SQLAlchemy AsyncSession path
        from sqlalchemy import select
        from models import BrokerConnection
        res = await db.execute(
            select(BrokerConnection).where(
                BrokerConnection.user_id == user_id,
                BrokerConnection.broker == "aliceblue"
            )
        )
        conn = res.scalar_one_or_none()
        if not conn or not conn.access_token:
            return None
        try:
            session_id = decrypt_str(conn.access_token)
            creds = conn.credentials or {}
            return AliceBlueClient(
                client_code=decrypt_str(creds.get("user_id", "")),
                api_key=decrypt_str(creds.get("api_key", "")),
                session_id=session_id
            )
        except Exception:
            return None

