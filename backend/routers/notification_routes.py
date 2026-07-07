"""In-app notifications feed + per-user Telegram settings."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from db import db
from models import Notification, User
from services.crypto import decrypt_str, encrypt_str
from services.push_fcm import is_configured as fcm_configured, send_to_tokens
from services.telegram import PLATFORM_TOKEN, send_message, resolve_token

router = APIRouter(prefix="/notifications", tags=["notifications"])


class TelegramSettings(BaseModel):
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True


class PushRegister(BaseModel):
    token: str
    platform: str = "android"


class PushPreference(BaseModel):
    enabled: bool


@router.get("")
async def list_notifications(limit: int = 50, user: User = Depends(get_current_user)):
    cur = db.notifications.find({"user_id": user.id}).sort("created_at", -1).limit(limit)
    out = []
    async for d in cur:
        out.append(Notification.from_mongo(d).model_dump())
    unread = await db.notifications.count_documents({"user_id": user.id, "read": False})
    return {"notifications": out, "unread": unread}


@router.post("/{notif_id}/read")
async def mark_read(notif_id: str, user: User = Depends(get_current_user)):
    await db.notifications.update_one(
        {"_id": notif_id, "user_id": user.id}, {"$set": {"read": True}},
    )
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(user: User = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user.id}, {"$set": {"read": True}})
    return {"ok": True}


# ---- Telegram settings ----

@router.get("/telegram")
async def telegram_get(user: User = Depends(get_current_user)):
    doc = await db.telegram_settings.find_one({"user_id": user.id})
    has_platform = bool(PLATFORM_TOKEN)
    if not doc:
        return {
            "configured": False, "enabled": False, "chat_id": "",
            "has_token": False, "platform_bot_available": has_platform,
            "using_platform_bot": False,
        }
    return {
        "configured": bool(doc.get("bot_token")) or (has_platform and bool(doc.get("chat_id"))),
        "enabled": bool(doc.get("enabled", True)),
        "chat_id": doc.get("chat_id", ""),
        "has_token": bool(doc.get("bot_token")),
        "platform_bot_available": has_platform,
        "using_platform_bot": (not bool(doc.get("bot_token"))) and bool(doc.get("chat_id")) and has_platform,
    }


@router.post("/telegram")
async def telegram_save(body: TelegramSettings, user: User = Depends(get_current_user)):
    existing = await db.telegram_settings.find_one({"user_id": user.id})
    token_enc = encrypt_str(body.bot_token) if body.bot_token else (existing or {}).get("bot_token", "")
    update = {
        "user_id": user.id,
        "bot_token": token_enc,
        "chat_id": body.chat_id or (existing or {}).get("chat_id", ""),
        "enabled": body.enabled,
    }
    await db.telegram_settings.update_one(
        {"user_id": user.id}, {"$set": update}, upsert=True,
    )
    return {"ok": True}


@router.post("/telegram/test")
async def telegram_test(user: User = Depends(get_current_user)):
    token, chat_id, via_platform = await resolve_token(db, user.id)
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Add a chat ID (and a bot token if not using the platform bot).")
    res = await send_message(token, chat_id,
                             "*Algonid test message* ✅\nTelegram is wired up." +
                             (" _(via platform bot)_" if via_platform else ""))
    return {"ok": bool(res.get("ok")), "via_platform_bot": via_platform, "telegram_response": res}


@router.delete("/telegram")
async def telegram_delete(user: User = Depends(get_current_user)):
    await db.telegram_settings.delete_one({"user_id": user.id})
    return {"ok": True}


# ---- Push notifications (FCM) ----

@router.get("/push")
async def push_get(user: User = Depends(get_current_user)):
    pref = await db.push_settings.find_one({"user_id": user.id}) or {}
    device_count = await db.push_tokens.count_documents({"user_id": user.id})
    return {
        "enabled": bool(pref.get("enabled", False)),
        "device_count": device_count,
        "fcm_configured": fcm_configured(),
    }


@router.post("/push/preferences")
async def push_set_pref(body: PushPreference, user: User = Depends(get_current_user)):
    await db.push_settings.update_one(
        {"user_id": user.id},
        {"$set": {"user_id": user.id, "enabled": body.enabled}},
        upsert=True,
    )
    return {"ok": True, "enabled": body.enabled}


@router.post("/push/register")
async def push_register(body: PushRegister, user: User = Depends(get_current_user)):
    await db.push_tokens.update_one(
        {"user_id": user.id, "token": body.token},
        {"$set": {
            "user_id": user.id, "token": body.token,
            "platform": body.platform,
        }},
        upsert=True,
    )
    # auto-enable on first device registration
    await db.push_settings.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {"enabled": True}},
        upsert=True,
    )
    return {"ok": True}


@router.post("/push/unregister")
async def push_unregister(user: User = Depends(get_current_user)):
    res = await db.push_tokens.delete_many({"user_id": user.id})
    return {"deleted": res.deleted_count}


@router.post("/push/test")
async def push_test(user: User = Depends(get_current_user)):
    cur = db.push_tokens.find({"user_id": user.id})
    tokens = [d["token"] async for d in cur]
    if not tokens:
        raise HTTPException(status_code=400, detail="No device registered. Open the Android app and toggle push ON.")
    res = await send_to_tokens(tokens, "Algonid test 📡", "Push notifications are working.")
    return {"ok": bool(res.get("success", 0)), "fcm_response": res}
