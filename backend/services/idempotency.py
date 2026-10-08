"""Idempotency for TradingView webhooks & orders.

Dedupe key strategy (as confirmed by the user):
- prefer the optional `alert_id` from the payload
- fall back to `symbol+side+price+minute`

Keys live in DB `idempotency` with a 24h TTL.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update, insert, delete
from sqlalchemy.exc import IntegrityError
from db import AsyncSessionLocal
from models import Idempotency

TTL_HOURS = 24


def derive_key(payload: dict) -> str:
    alert_id = payload.get("alert_id") or payload.get("id")
    if alert_id:
        return f"alert:{alert_id}"
    sym = payload.get("symbol", "?")
    side = payload.get("side", "?")
    price = payload.get("price", "?")
    bucket = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    return f"sig:{sym}:{side}:{price}:{bucket}"


async def ensure_indexes() -> None:
    # SQLAlchemy schema handles indexes, this can be a no-op or removed,
    # but we'll leave it as a no-op to not break the caller.
    pass


async def claim(user_id: str, key: str) -> tuple[bool, Optional[str]]:
    """Return (is_new, existing_signal_id).

    If `key` already exists for this user, returns (False, existing signal id).
    Otherwise atomically inserts the key and returns (True, None).
    """
    async with AsyncSessionLocal() as session:
        try:
            idem = Idempotency(
                user_id=user_id,
                key=key,
                created_at=datetime.utcnow()
            )
            session.add(idem)
            await session.commit()
            return True, None
        except IntegrityError:
            await session.rollback()
            existing = (await session.execute(
                select(Idempotency).where(Idempotency.user_id == user_id, Idempotency.key == key)
            )).scalar_one_or_none()
            return False, existing.signal_id if existing else None


async def attach_signal(user_id: str, key: str, signal_id: str) -> None:
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(
            select(Idempotency).where(Idempotency.user_id == user_id, Idempotency.key == key)
        )).scalar_one_or_none()
        if existing:
            existing.signal_id = signal_id
            await session.commit()
