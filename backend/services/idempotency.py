"""Idempotency for TradingView webhooks & orders.

Dedupe key strategy (as confirmed by the user):
- prefer the optional `alert_id` from the payload
- fall back to `symbol+side+price+minute`

Keys live in MongoDB collection `idempotency` with a 24h TTL.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from db import db

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
    await db.idempotency.create_index("created_at", expireAfterSeconds=TTL_HOURS * 3600)
    await db.idempotency.create_index([("user_id", 1), ("key", 1)], unique=True)


async def claim(user_id: str, key: str) -> tuple[bool, Optional[str]]:
    """Return (is_new, existing_signal_id).

    If `key` already exists for this user, returns (False, existing signal id).
    Otherwise atomically inserts the key and returns (True, None).
    """
    try:
        await db.idempotency.insert_one({
            "user_id": user_id,
            "key": key,
            "created_at": datetime.now(timezone.utc),
        })
        return True, None
    except Exception:
        existing = await db.idempotency.find_one({"user_id": user_id, "key": key})
        return False, (existing or {}).get("signal_id")


async def attach_signal(user_id: str, key: str, signal_id: str) -> None:
    await db.idempotency.update_one(
        {"user_id": user_id, "key": key},
        {"$set": {"signal_id": signal_id}},
    )
