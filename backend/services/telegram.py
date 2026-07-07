"""Telegram bot alert sender.

Two-level token resolution:
  1. per-user `telegram_settings` doc (encrypted bot_token + chat_id)
  2. platform-wide `TELEGRAM_BOT_TOKEN` env var as a fallback (user only
     needs to provide their chat_id)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
TG_API = "https://api.telegram.org"
PLATFORM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
LOCAL_ONLY = os.environ.get("LOCAL_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}


async def send_message(bot_token: str, chat_id: str, text: str,
                       parse_mode: str = "Markdown") -> dict:
    if not bot_token or not chat_id:
        return {"ok": False, "skipped": True, "reason": "no_token_or_chat"}
    if LOCAL_ONLY:
        return {"ok": False, "skipped": True, "reason": "local_only"}
    url = f"{TG_API}/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            return r.json()
    except Exception as e:
        logger.warning("telegram send failed: %s", e)
        return {"ok": False, "error": str(e)}


async def resolve_token(db, user_id: str) -> tuple[str, str, bool]:
    """Return (bot_token, chat_id, used_platform_token)."""
    if LOCAL_ONLY:
        return "", "", False
    from services.crypto import decrypt_str
    doc = await db.telegram_settings.find_one({"user_id": user_id})
    if not doc or not doc.get("enabled", True):
        return "", "", False
    user_token = decrypt_str(doc.get("bot_token", "")) if doc.get("bot_token") else ""
    chat_id = doc.get("chat_id", "")
    if user_token and chat_id:
        return user_token, chat_id, False
    # Fall back to platform-wide bot (only chat_id needed)
    if PLATFORM_TOKEN and chat_id:
        return PLATFORM_TOKEN, chat_id, True
    return "", "", False


async def send_for_user(db, user_id: str, text: str) -> Optional[dict]:
    token, chat_id, _ = await resolve_token(db, user_id)
    if not token or not chat_id:
        return None
    return await send_message(token, chat_id, text)
