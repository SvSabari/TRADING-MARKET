"""In-app notifications feed + per-user Telegram settings."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from auth import get_current_user
from db import get_db
from models import Notification, User, TelegramSettings as TelegramSettingsModel, PushSettings as PushSettingsModel, PushToken
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
async def list_notifications(limit: int = 50, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    notifications = result.scalars().all()
    
    out = []
    for d in notifications:
        out.append({
            "id": d.id, "user_id": d.user_id, "kind": d.kind, "title": d.title,
            "message": d.message, "severity": d.severity, "read": d.read, "created_at": d.created_at
        })
        
    stmt_unread = select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read == False)
    result_unread = await session.execute(stmt_unread)
    unread = result_unread.scalar_one()
    
    return {"notifications": out, "unread": unread}


@router.post("/{notif_id}/read")
async def mark_read(notif_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.id == notif_id, Notification.user_id == user.id)
    result = await session.execute(stmt)
    notif = result.scalar_one_or_none()
    if notif:
        notif.read = True
        await session.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id, Notification.read == False)
    result = await session.execute(stmt)
    notifs = result.scalars().all()
    for notif in notifs:
        notif.read = True
    await session.commit()
    return {"ok": True}


@router.delete("/all")
async def delete_all(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    result = await session.execute(stmt)
    notifs = result.scalars().all()
    for notif in notifs:
        await session.delete(notif)
    await session.commit()
    return {"ok": True}


@router.delete("/{notif_id}")
async def delete_one(notif_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.id == notif_id, Notification.user_id == user.id)
    result = await session.execute(stmt)
    notif = result.scalar_one_or_none()
    if notif:
        await session.delete(notif)
        await session.commit()
    return {"ok": True}


# ---- Telegram settings ----

@router.get("/telegram")
async def telegram_get(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(TelegramSettingsModel).where(TelegramSettingsModel.user_id == user.id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    
    has_platform = bool(PLATFORM_TOKEN)
    if not doc:
        return {
            "configured": False, "enabled": False, "chat_id": "",
            "has_token": False, "platform_bot_available": has_platform,
            "using_platform_bot": False,
        }
    return {
        "configured": bool(doc.bot_token) or (has_platform and bool(doc.chat_id)),
        "enabled": doc.enabled,
        "chat_id": doc.chat_id or "",
        "has_token": bool(doc.bot_token),
        "platform_bot_available": has_platform,
        "using_platform_bot": (not bool(doc.bot_token)) and bool(doc.chat_id) and has_platform,
    }


@router.post("/telegram")
async def telegram_save(body: TelegramSettings, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(TelegramSettingsModel).where(TelegramSettingsModel.user_id == user.id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    
    token_enc = encrypt_str(body.bot_token) if body.bot_token else (existing.bot_token if existing else "")
    chat_id = body.chat_id or (existing.chat_id if existing else "")
    
    if existing:
        existing.bot_token = token_enc
        existing.chat_id = chat_id
        existing.enabled = body.enabled
    else:
        existing = TelegramSettingsModel(
            user_id=user.id,
            bot_token=token_enc,
            chat_id=chat_id,
            enabled=body.enabled
        )
        session.add(existing)
    await session.commit()
    return {"ok": True}


@router.post("/telegram/test")
async def telegram_test(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    token, chat_id, via_platform = await resolve_token(session, user.id)
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Add a chat ID (and a bot token if not using the platform bot).")
    res = await send_message(token, chat_id,
                             "*Algonid test message* ✅\nTelegram is wired up." +
                             (" _(via platform bot)_" if via_platform else ""))
    return {"ok": bool(res.get("ok")), "via_platform_bot": via_platform, "telegram_response": res}


@router.delete("/telegram")
async def telegram_delete(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(TelegramSettingsModel).where(TelegramSettingsModel.user_id == user.id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc:
        await session.delete(doc)
        await session.commit()
    return {"ok": True}


# ---- Push notifications (FCM) ----

@router.get("/push")
async def push_get(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(PushSettingsModel).where(PushSettingsModel.user_id == user.id)
    result = await session.execute(stmt)
    pref = result.scalar_one_or_none()
    
    stmt_count = select(func.count(PushToken.id)).where(PushToken.user_id == user.id)
    result_count = await session.execute(stmt_count)
    device_count = result_count.scalar_one()
    
    return {
        "enabled": pref.enabled if pref else False,
        "device_count": device_count,
        "fcm_configured": fcm_configured(),
    }


@router.post("/push/preferences")
async def push_set_pref(body: PushPreference, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(PushSettingsModel).where(PushSettingsModel.user_id == user.id)
    result = await session.execute(stmt)
    pref = result.scalar_one_or_none()
    if pref:
        pref.enabled = body.enabled
    else:
        pref = PushSettingsModel(user_id=user.id, enabled=body.enabled)
        session.add(pref)
    await session.commit()
    return {"ok": True, "enabled": body.enabled}


@router.post("/push/register")
async def push_register(body: PushRegister, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(PushToken).where(PushToken.user_id == user.id, PushToken.token == body.token)
    result = await session.execute(stmt)
    token_obj = result.scalar_one_or_none()
    
    if token_obj:
        token_obj.platform = body.platform
    else:
        token_obj = PushToken(user_id=user.id, token=body.token, platform=body.platform)
        session.add(token_obj)
        
    stmt_pref = select(PushSettingsModel).where(PushSettingsModel.user_id == user.id)
    result_pref = await session.execute(stmt_pref)
    pref = result_pref.scalar_one_or_none()
    if not pref:
        pref = PushSettingsModel(user_id=user.id, enabled=True)
        session.add(pref)
        
    await session.commit()
    return {"ok": True}


@router.post("/push/unregister")
async def push_unregister(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(PushToken).where(PushToken.user_id == user.id)
    result = await session.execute(stmt)
    tokens = result.scalars().all()
    count = len(tokens)
    for t in tokens:
        await session.delete(t)
    await session.commit()
    return {"deleted": count}


@router.post("/push/test")
async def push_test(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(PushToken).where(PushToken.user_id == user.id)
    result = await session.execute(stmt)
    token_objs = result.scalars().all()
    
    tokens = [t.token for t in token_objs]
    if not tokens:
        raise HTTPException(status_code=400, detail="No device registered. Open the Android app and toggle push ON.")
    res = await send_to_tokens(tokens, "Algonid test 📡", "Push notifications are working.")
    return {"ok": bool(res.get("success", 0)), "fcm_response": res}
