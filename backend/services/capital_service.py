"""Capital calculation and allocation enforcement service for managed users.

Rules:
1. Enrollment Date: Stored at user creation, immutable across edits.
2. Capital Allocation (%): Configured by trader (0-100%).
3. Allocated Amount (₹): (Available Account Funds * Capital Allocation %) / 100.
4. Amount Used (₹): Capital currently committed to open positions and pending orders.
5. Available Amount (₹): max(0.0, Allocated Amount - Amount Used).
6. Pre-trade validation: Reject orders if required funds exceed Available Amount.
7. Pending order reservations: Pending orders count against Amount Used; when cancelled or rejected, reservation is naturally freed.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from sqlalchemy import select
from models import ManagedUser, Position, Order

logger = logging.getLogger("capital-service")


async def get_user_broker_funds(session, mu: ManagedUser) -> float:
    """Fetch live available cash funds from user's connected broker.
    Uses actual broker cash margin wherever available.
    """
    brokers = mu.brokers or []
    
    # 1. Check AliceBlue
    alice_broker = next(
        (b for b in brokers if isinstance(b, dict) and "alice" in str(b.get("broker", "")).lower()),
        None
    )
    if alice_broker and alice_broker.get("session_token"):
        try:
            from pya3 import Aliceblue
            creds = alice_broker.get("credentials") or {}
            user_id_val = creds.get("user_id") or creds.get("client_code") or alice_broker.get("account_number")
            api_key = creds.get("api_key") or alice_broker.get("api_key")
            client = Aliceblue(user_id=user_id_val, api_key=api_key, session_id=alice_broker.get("session_token"))
            balance_resp = client.get_balance()
            if isinstance(balance_resp, list) and len(balance_resp) > 0:
                first = balance_resp[0]
                cash = float(first.get("cashmarginavailable") or first.get("net") or first.get("cash") or 0.0)
                return max(0.0, cash)
            elif isinstance(balance_resp, dict):
                cash = float(balance_resp.get("cashmarginavailable") or balance_resp.get("net") or balance_resp.get("cash") or 0.0)
                return max(0.0, cash)
        except Exception as e:
            logger.warning("[capital] AliceBlue balance fetch failed for user %s: %s", mu.id, e)

    # 2. Check ICICI Breeze
    breeze_broker = next(
        (b for b in brokers if isinstance(b, dict) and "icici" in str(b.get("broker", "")).lower()),
        None
    )
    if breeze_broker and breeze_broker.get("session_token"):
        try:
            from services.brokers.breeze_client import BreezeClient
            creds = breeze_broker.get("credentials") or {}
            api_key = creds.get("api_key") or breeze_broker.get("api_key")
            secret_key = creds.get("api_secret") or breeze_broker.get("api_secret")
            session_token = breeze_broker.get("session_token")
            client = BreezeClient(api_key=api_key, secret_key=secret_key, session_token=session_token)
            if client._session_ok:
                funds_resp = client._b.get_funds()
                if isinstance(funds_resp, dict):
                    success = funds_resp.get("Success", {})
                    cash = float(success.get("bank_balance") or success.get("allocated_funds") or 0.0)
                    return max(0.0, cash)
        except Exception as e:
            logger.warning("[capital] Breeze balance fetch failed for user %s: %s", mu.id, e)

    # Fallback to max_allocation if broker has not reported funds yet
    fallback = float(getattr(mu, "max_allocation", 0.0) or 0.0)
    return max(0.0, fallback)


async def compute_user_amount_used(session, user_id: str) -> float:
    """Compute actual capital currently committed to open positions and pending orders.
    - Open positions: abs(qty) * avg_price
    - Pending / Open / Trigger pending orders: qty * price
    """
    total_used = 0.0

    # 1. Open positions
    pos_res = await session.execute(
        select(Position).where(Position.user_id == user_id, Position.qty != 0)
    )
    positions = pos_res.scalars().all()
    for p in positions:
        total_used += abs(p.qty) * float(p.avg_price or 0.0)

    # 2. Pending orders reserving funds
    order_res = await session.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.status.in_(["PENDING", "OPEN", "TRIGGER_PENDING"])
        )
    )
    orders = order_res.scalars().all()
    for o in orders:
        total_used += abs(o.qty) * float(o.price or 0.0)

    return round(total_used, 2)


async def get_managed_user_capital_metrics(session, mu: ManagedUser) -> Dict[str, Any]:
    """Calculate all 5 capital metrics for a given managed user:
    - enrollment_date: string YYYY-MM-DD
    - capital_allocation_pct: float
    - total_account_funds: float (cash in broker)
    - allocated_amount: float
    - amount_used: float
    - available_amount: float
    """
    pct = float(getattr(mu, "capital_allocation_pct", 100.0) if getattr(mu, "capital_allocation_pct", None) is not None else 100.0)
    funds = await get_user_broker_funds(session, mu)
    allocated_amount = round(funds * (pct / 100.0), 2)
    amount_used = await compute_user_amount_used(session, mu.id)
    available_amount = max(0.0, round(allocated_amount - amount_used, 2))

    enrollment_date = None
    if mu.created_at:
        enrollment_date = mu.created_at.strftime("%Y-%m-%d")

    return {
        "user_id": mu.id,
        "enrollment_date": enrollment_date,
        "capital_allocation_pct": pct,
        "total_account_funds": funds,
        "allocated_amount": allocated_amount,
        "amount_used": amount_used,
        "available_amount": available_amount,
    }


def calculate_required_funds(symbol: str, side: str, qty: int, price: float, product: str = "MIS") -> float:
    """Calculate the required funds / margin for an order.
    For options and leveraged trades (MIS), use applicable margin requirements.
    """
    sym = (symbol or "").upper()
    total_val = abs(qty) * float(price or 0.0)

    # If it is an option (e.g. NIFTY26OCT25000CE or contains CE/PE):
    # Option BUY requires 100% premium paid upfront.
    # Option SELL (writing) requires margin (typically 20% span + exposure or ~1.5L for index).
    is_option = sym.endswith("CE") or sym.endswith("PE") or " CE" in sym or " PE" in sym
    if is_option:
        if side.upper() == "BUY":
            return round(total_val, 2)
        else:
            # Option writing margin requirement is typically at least 20% of strike/exposure or 5x premium
            return round(max(total_val * 5.0, 100000.0), 2)

    # Intraday (MIS) equity leverage in India is typically up to 5x (20% margin requirement)
    if product.upper() in ["MIS", "INTRADAY", "I"]:
        return round(total_val * 0.20, 2)

    # Delivery / CNC: 100% of order value
    return round(total_val, 2)
