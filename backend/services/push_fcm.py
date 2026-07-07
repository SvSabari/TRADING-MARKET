"""Firebase Cloud Messaging sender for push notifications.

Uses the legacy server-key HTTP API (simplest setup). To enable:
  1. Create a Firebase project at https://console.firebase.google.com
  2. Project settings → Cloud Messaging → "Server key" (legacy)
  3. Paste it in backend/.env as FCM_SERVER_KEY

When FCM_SERVER_KEY is missing the service silently no-ops so the rest of
the app keeps working.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)
FCM_SERVER_KEY = os.environ.get("FCM_SERVER_KEY", "")
FCM_URL = "https://fcm.googleapis.com/fcm/send"
LOCAL_ONLY = os.environ.get("LOCAL_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    return bool(FCM_SERVER_KEY) and not LOCAL_ONLY


async def send_to_tokens(tokens: List[str], title: str, body: str,
                         data: Optional[dict] = None) -> dict:
    if LOCAL_ONLY:
        return {"ok": False, "skipped": True, "reason": "local_only"}
    if not FCM_SERVER_KEY or not tokens:
        return {"ok": False, "skipped": True}
    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "registration_ids": tokens,
        "notification": {"title": title, "body": body, "sound": "default"},
        "data": data or {},
        "priority": "high",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(FCM_URL, json=payload, headers=headers)
            return r.json()
    except Exception as e:
        logger.warning("fcm send failed: %s", e)
        return {"ok": False, "error": str(e)}


async def send_for_user(db, user_id: str, title: str, body: str,
                        data: Optional[dict] = None) -> Optional[dict]:
    """Fetch the user's registered devices and push to all of them."""
    if LOCAL_ONLY:
        return None
    pref = await db.push_settings.find_one({"user_id": user_id})
    if not pref or not pref.get("enabled", False):
        return None
    cur = db.push_tokens.find({"user_id": user_id})
    tokens = [d["token"] async for d in cur]
    if not tokens:
        return None
    return await send_to_tokens(tokens, title, body, data)
