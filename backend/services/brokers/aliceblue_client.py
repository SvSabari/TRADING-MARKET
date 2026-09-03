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
            
        try:
            instrument = self._alice.get_instrument_by_token(exchange, int(token))
        except ValueError:
            # Token is not an int, meaning we fell back to passing the raw symbol string (e.g. RELIANCE)
            # AliceBlue requires -EQ suffix for NSE stocks
            sym = f"{token}-EQ" if exchange == "NSE" and "-EQ" not in token else token
            instrument = self._alice.get_instrument_by_symbol(exchange, sym)

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
        
        t_type = TransactionType.Buy if transaction_type.upper() == "BUY" else TransactionType.Sell
        
        o_type = OrderType.Market
        if order_type.upper() == "LIMIT":
            o_type = OrderType.Limit
        elif order_type.upper() == "SL-M":
            o_type = OrderType.StopLossMarket
        elif order_type.upper() == "SL":
            o_type = OrderType.StopLossLimit
            
        p_type = ProductType.Intraday if product.upper() == "I" else ProductType.Delivery
        
        try:
            exchange, token = instrument_token.split("|")
        except ValueError:
            exchange, token = "NSE", instrument_token
            
        instrument = self._alice.get_instrument_by_token(exchange, int(token))
        
        return self._alice.modify_order(
            transaction_type=t_type,
            instrument=instrument,
            product_type=p_type,
            order_id=broker_order_id,
            order_type=o_type,
            quantity=int(quantity),
            price=float(price),
            trigger_price=float(trigger_price)
        )

    def cancel_order(self, broker_order_id: str) -> dict:
        return self._alice.cancel_order(broker_order_id)

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
            client_code=decrypt_str(doc["credentials"]["user_id"]),
            api_key=decrypt_str(doc["credentials"]["api_key"]),
            session_id=session_id
        )
    except Exception:
        return None
