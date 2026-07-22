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
        self._alice = Aliceblue(user_id=client_code, api_key=api_key)
        # Instead of calling get_session_id() which triggers an old login flow,
        # we manually inject the valid userSession obtained via OAuth
        self._alice.session_id = session_id

    # ---------------------------------------------------------- orders
    def place_order(self, *, instrument_token: str, transaction_type: str,
                    quantity: int, order_type: str = "MARKET",
                    product: str = "I", price: Optional[float] = None) -> str:
        """
        instrument_token = Token provided by Alice Blue (e.g. 26000)
        """
        # Map our internal transaction type string to pya3 enums
        t_type = TransactionType.Buy if transaction_type.upper() == "BUY" else TransactionType.Sell
        
        # Map order type
        o_type = OrderType.Market
        if order_type.upper() == "LIMIT":
            o_type = OrderType.Limit
        elif order_type.upper() == "SL-M":
            o_type = OrderType.StopLossMarket
        elif order_type.upper() == "SL":
            o_type = OrderType.StopLossLimit
            
        # Map product type (I = MIS, D = CNC)
        p_type = ProductType.Intraday if product.upper() == "I" else ProductType.Delivery

        # For Aliceblue, we need to pass a dict representing the instrument, 
        # but the SDK also has `get_instrument_by_token`.
        # We will assume instrument_token is in the format "EXCHANGE|TOKEN" (e.g., "NSE|26000")
        try:
            exchange, token = instrument_token.split("|")
        except ValueError:
            exchange, token = "NSE", instrument_token
            
        instrument = self._alice.get_instrument_by_token(exchange, int(token))

        resp = self._alice.place_order(
            transaction_type=t_type,
            instrument=instrument,
            quantity=int(quantity),
            order_type=o_type,
            product_type=p_type,
            price=float(price) if price else 0.0,
            trigger_price=0.0,
            stop_loss=None,
            square_off=None,
            trailing_sl=None,
            is_amo=False,
            order_tag="algonid"
        )
        
        if isinstance(resp, dict) and resp.get("stat") == "Ok":
            return resp.get("NOrdNo", "unknown")
        
        logger.error(f"Alice Blue order failed: {resp}")
        raise Exception(f"Alice Blue order rejected: {resp}")

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

async def get_user_aliceblue_client(db, user_id: str) -> Optional[AliceBlueClient]:
    doc = await db.broker_connections.find_one({
        "user_id": user_id,
        "broker": "aliceblue"
    })
    if not doc or "access_token" not in doc:
        return None
    from services.crypto import decrypt_str
    try:
        session_id = decrypt_str(doc["access_token"])
        return AliceBlueClient(
            client_code=doc["credentials"]["user_id"],
            api_key=doc["credentials"]["api_key"],
            session_id=session_id
        )
    except Exception:
        return None
