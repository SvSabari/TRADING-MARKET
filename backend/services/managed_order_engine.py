"""Managed Order Engine — mirrors a trader's order to all eligible managed users.

Eligibility gates (ALL must pass):
  1. place_order == True
  2. account_status == "active"
  3. At least one configured broker where:
       a. session_generated == True
       b. session_token is non-empty
       c. All required credentials for that broker are present

Routing:
  Each eligible user's order is executed using THAT USER'S own broker
  credentials and session token — never the trader's broker account.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from models import ManagedUser, ManagedUserBroker, Order
from services.crypto import decrypt_str

logger = logging.getLogger("managed-order-engine")


# ---------------------------------------------------------------------------
# Credential validation — per broker
# ---------------------------------------------------------------------------

def validate_broker_credentials(b: ManagedUserBroker) -> Tuple[bool, str]:
    """Return (is_valid, reason).  Checks session + required credential fields."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if not getattr(b, "session_generated", False):
        return False, "session not generated"
    if getattr(b, "session_date", "") != today_str:
        return False, "session expired (generated on a previous day)"
    if not (getattr(b, "session_token", "") or "").strip():
        return False, "session token is empty"

    creds = b.credentials or {}
    api_key = (creds.get("api_key") or b.api_key or "").strip()
    if not api_key:
        return False, "api_key missing"

    broker = b.broker.lower().replace(" ", "_")

    if "alice" in broker:
        user_id = (creds.get("user_id") or b.account_number or "").strip()
        if not user_id:
            return False, "user_id / client code missing (AliceBlue)"

    elif "angel" in broker:
        client_code = (creds.get("client_code") or b.account_number or "").strip()
        pin = (creds.get("pin") or b.account_password or "").strip()
        totp = (creds.get("totp_secret") or b.api_secret or "").strip()
        if not client_code:
            return False, "client_code missing (Angel)"
        if not pin:
            return False, "pin missing (Angel)"
        if not totp:
            return False, "totp_secret missing (Angel)"

    elif "zerodha" in broker or "kite" in broker:
        api_secret = (creds.get("api_secret") or b.api_secret or "").strip()
        if not api_secret:
            return False, "api_secret missing (Zerodha)"

    elif "icici" in broker or "breeze" in broker:
        api_secret = (creds.get("api_secret") or b.api_secret or "").strip()
        if not api_secret:
            return False, "api_secret missing (ICICI Breeze)"

    elif "upstox" in broker:
        api_secret = (creds.get("api_secret") or b.api_secret or "").strip()
        if not api_secret:
            return False, "api_secret missing (Upstox)"

    return True, "ok"


# ---------------------------------------------------------------------------
# Per-managed-user broker order routing (uses the user's OWN credentials)
# ---------------------------------------------------------------------------

async def _route_for_managed_user_broker(
    db, mu: ManagedUser, b: ManagedUserBroker,
    *, symbol: str, side: str, qty: int, price: float,
    order_type: str, product: str, force_mock: bool = False,
) -> dict:
    """Route an order through a managed user's own broker credentials.

    Tries the live broker first; falls back to mock only if LOCAL_ONLY is set.
    """
    import os
    LOCAL_ONLY = os.environ.get("LOCAL_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}

    creds = b.credentials or {}
    broker_name = b.broker.lower().replace(" ", "_")
    api_key = creds.get("api_key") or b.api_key
    api_secret = creds.get("api_secret") or b.api_secret
    session_token = b.session_token

    from services.broker_router import _live_response
    import random

    def _mock_fill():
        slip = price * random.uniform(-0.0005, 0.0005)
        return {
            "broker_order_id": f"MU-MOCK-{mu.id[:6].upper()}",
            "status": "FILLED",
            "fill_price": round(price + slip, 2),
            "filled_at": datetime.now(timezone.utc).isoformat(),
            "mode": "mock-managed",
        }

    if LOCAL_ONLY or force_mock or broker_name == "mock":
        return _mock_fill()

    try:
        if "alice" in broker_name:
            from pya3 import Aliceblue
            user_id_val = creds.get("user_id") or b.account_number
            alice = Aliceblue(user_id=user_id_val, api_key=api_key, session_id=session_token)
            # Build instrument token for the symbol
            from services.instrument_map import ALICEBLUE_TOKENS
            instrument_token = next((k for k, sym in ALICEBLUE_TOKENS.items() if sym == symbol), f"NSE|{symbol}")
            result = alice.place_order(
                transaction_type=alice.TransactionType.Buy if side.upper() == "BUY" else alice.TransactionType.Sell,
                instrument=alice.get_instrument_by_token("NSE", int(instrument_token.split("|")[-1])) if "|" in instrument_token else None,
                quantity=qty,
                order_type=alice.OrderType.Market if order_type == "MARKET" else alice.OrderType.Limit,
                product_type=alice.ProductType.Intraday if product == "MIS" else alice.ProductType.Delivery,
                price=price if order_type == "LIMIT" else 0,
            )
            if result and isinstance(result, dict) and result.get("NOrdNo"):
                return _live_response(result["NOrdNo"], price, "live-aliceblue-managed")
            raise Exception(f"AliceBlue managed order failed: {result}")

        elif "angel" in broker_name:
            from services.brokers.angel_client import AngelClient
            client_code = creds.get("client_code") or b.account_number
            pin = creds.get("pin") or b.account_password
            totp_secret = creds.get("totp_secret") or b.api_secret
            client = AngelClient(
                api_key=api_key, client_code=client_code, pin=pin,
                totp_secret=totp_secret, auth_token=session_token,
            )
            from services.instrument_map import ANGEL_TOKENS
            token = next((tok for tok, sym in ANGEL_TOKENS.items() if sym == symbol), None)
            if not token:
                raise Exception(f"Angel: no token for {symbol}")
            order_id = client.place_order(
                tradingsymbol=f"{symbol}-EQ", exchange="NSE",
                transaction_type=side.upper(), quantity=int(qty),
                symbol_token=token, order_type=order_type,
                product="INTRADAY" if product == "MIS" else "DELIVERY",
                price=price if order_type == "LIMIT" else None,
            )
            if order_id:
                return _live_response(order_id, price, "live-angel-managed")
            raise Exception("Angel managed order returned no order ID")

        elif "zerodha" in broker_name or "kite" in broker_name:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(session_token)
            order_id = kite.place_order(
                tradingsymbol=symbol, exchange="NSE",
                transaction_type=side.upper(), quantity=int(qty),
                order_type=order_type, product=product, variety="regular",
                price=price if order_type == "LIMIT" else None,
            )
            return _live_response(order_id, price, "live-zerodha-managed")

        elif "icici" in broker_name or "breeze" in broker_name:
            from breeze_connect import BreezeConnect
            breeze = BreezeConnect(api_key=api_key)
            breeze.generate_session(api_secret=api_secret, session_token=session_token)
            order_id = breeze.place_order(
                stock_code=symbol, exchange_code="NSE",
                transaction_type=side.upper(), quantity=int(qty),
                order_type=order_type,
                product="margin" if product == "MIS" else "cash",
                price=price if order_type == "LIMIT" else None,
            )
            if order_id:
                return _live_response(order_id, price, "live-breeze-managed")
            raise Exception("Breeze managed order returned no order ID")

        elif "upstox" in broker_name:
            from services.brokers.upstox_client import UpstoxClient
            client = UpstoxClient(access_token=session_token)
            from services.instrument_map import UPSTOX_KEYS
            instrument_key = next((k for k, sym in UPSTOX_KEYS.items() if sym == symbol), None)
            if not instrument_key:
                raise Exception(f"Upstox: no instrument_key for {symbol}")
            order_id = client.place_order(
                instrument_token=instrument_key,
                transaction_type=side.upper(), quantity=int(qty),
                order_type=order_type,
                product="I" if product == "MIS" else "D",
                price=price if order_type == "LIMIT" else None,
            )
            if order_id:
                return _live_response(order_id, price, "live-upstox-managed")
            raise Exception("Upstox managed order returned no order ID")

        else:
            # Unknown broker
            logger.warning("[mirror] Unknown broker '%s' for managed user %s", b.broker, mu.id)
            return {"status": "rejected", "fill_price": price, "mode": "unknown-broker"}

    except Exception as e:
        logger.warning("[mirror] Live order failed for managed user %s (%s): %s", mu.id, b.broker, e)
        return {"status": "rejected", "fill_price": price, "mode": "failed"}


# ---------------------------------------------------------------------------
# Main mirror engine
# ---------------------------------------------------------------------------

async def mirror_order_to_managed_users(db, trader_id: str, master_order: Order) -> None:
    """Fire-and-forget: mirrors a completed trader order to all eligible managed users.

    Called as asyncio.create_task(...) so failures don't affect the trader's order.
    """
    try:
        eligible: list[tuple[ManagedUser, ManagedUserBroker]] = []

        async for doc in db.managed_users.find({"trader_id": trader_id}):
            mu = ManagedUser.from_mongo(doc)

            # Gate 1: place_order must be True
            if not mu.place_order:
                logger.info("[mirror] SKIP user=%s name=%s — place_order=False", mu.id, mu.name)
                continue

            # Gate 2: account must be active
            if mu.account_status != "active":
                logger.info("[mirror] SKIP user=%s name=%s — account_status=%s", mu.id, mu.name, mu.account_status)
                continue

            brokers = getattr(mu, "brokers", [])

            # Handle legacy single-broker format
            if not brokers and hasattr(mu, "broker") and getattr(mu, "broker"):
                from models import ManagedUserBroker as MUB
                legacy_b = MUB(
                    broker=getattr(mu, "broker"),
                    api_key=getattr(mu, "api_key", ""),
                    api_secret=getattr(mu, "api_secret", ""),
                    account_number=getattr(mu, "account_number", ""),
                    account_password=getattr(mu, "account_password", ""),
                    session_token=getattr(mu, "session_token", ""),
                    session_generated=getattr(mu, "session_generated", False),
                )
                brokers = [legacy_b]

            has_any_eligible_broker = False
            for b in brokers:
                # Gate 3 + 4: session generated + credentials valid
                is_valid, reason = validate_broker_credentials(b)
                if not is_valid:
                    logger.info(
                        "[mirror] SKIP broker=%s for user=%s name=%s — %s",
                        b.broker, mu.id, mu.name, reason
                    )
                    continue
                eligible.append((mu, b))
                has_any_eligible_broker = True

            if not has_any_eligible_broker:
                logger.info("[mirror] SKIP user=%s name=%s — no eligible brokers", mu.id, mu.name)

        if not eligible:
            logger.info("[mirror] No eligible managed users for trader=%s", trader_id)
            return

        logger.info("[mirror] Dispatching to %d managed user/broker combos for trader=%s", len(eligible), trader_id)

        async def _place_for_user(mu: ManagedUser, b: ManagedUserBroker):
            try:
                fill = await _route_for_managed_user_broker(
                    db, mu, b,
                    symbol=master_order.symbol,
                    side=master_order.side,
                    qty=master_order.qty,
                    price=master_order.price,
                    order_type=master_order.order_type,
                    product=master_order.product,
                    force_mock=(master_order.broker == "mock")
                )
                mirrored = Order(
                    user_id=mu.id,
                    broker=b.broker,
                    symbol=master_order.symbol,
                    side=master_order.side,
                    qty=master_order.qty,
                    price=fill.get("fill_price", master_order.price),
                    order_type=master_order.order_type,
                    product=master_order.product,
                    status=fill.get("status", "FILLED"),
                    source="mirrored",
                    filled_at=datetime.now(timezone.utc),
                    pnl=0.0,
                )
                await db.orders.insert_one(mirrored.to_mongo())
                logger.info(
                    "[mirror] ✅ Order placed for managed user=%s name=%s broker=%s — %s @ ₹%s",
                    mu.id, mu.name, b.broker, master_order.side, fill.get("fill_price", master_order.price)
                )

                # Notify the managed user
                from models import Notification
                notif = Notification(
                    user_id=mu.id, kind="order",
                    title=f"Order executed: {mirrored.side} {mirrored.symbol}",
                    message=(
                        f"{mirrored.qty} @ ₹{mirrored.price} via {b.broker} "
                        f"({fill.get('mode', 'managed')})"
                    ),
                    severity="success",
                )
                await db.notifications.insert_one(notif.to_mongo())

            except Exception as e:
                logger.error(
                    "[mirror] ❌ Failed for managed user=%s name=%s broker=%s: %s",
                    mu.id, mu.name, b.broker, e
                )

        await asyncio.gather(*[_place_for_user(mu, b) for mu, b in eligible])

    except Exception as e:
        logger.error("[mirror] Fatal error in mirror engine for trader=%s: %s", trader_id, e)


# ---------------------------------------------------------------------------
# Eligibility report (used by the API endpoint)
# ---------------------------------------------------------------------------

async def get_eligibility_report(db, trader_id: str) -> list[dict]:
    """Return per-user eligibility breakdown for the trader UI."""
    report = []
    async for doc in db.managed_users.find({"trader_id": trader_id}):
        mu = ManagedUser.from_mongo(doc)
        user_entry = {
            "id": mu.id,
            "name": mu.name,
            "phone": mu.phone,
            "place_order": mu.place_order,
            "account_status": mu.account_status,
            "eligible": False,
            "skip_reason": None,
            "brokers": [],
        }

        if not mu.place_order:
            user_entry["skip_reason"] = "place_order is No"
        elif mu.account_status != "active":
            user_entry["skip_reason"] = f"account_status is {mu.account_status}"
        else:
            brokers = getattr(mu, "brokers", [])
            all_broker_issues = []
            has_eligible = False
            for b in brokers:
                is_valid, reason = validate_broker_credentials(b)
                user_entry["brokers"].append({
                    "broker": b.broker,
                    "session_generated": b.session_generated,
                    "eligible": is_valid,
                    "skip_reason": reason if not is_valid else None,
                })
                if is_valid:
                    has_eligible = True
                else:
                    all_broker_issues.append(f"{b.broker}: {reason}")

            if has_eligible:
                user_entry["eligible"] = True
            else:
                user_entry["skip_reason"] = "; ".join(all_broker_issues) or "no brokers configured"

        report.append(user_entry)
    return report
