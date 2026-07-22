"""TradingView webhook endpoint + signal feed (with idempotency + Telegram)."""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request

from auth import get_current_user
from db import db
from models import Notification, Order, TVSignal, TVSignalCreate, User
from services.broker_router import route_order
from services.idempotency import attach_signal, claim, derive_key
from services.telegram import send_for_user

router = APIRouter(prefix="/tradingview", tags=["tradingview"])

TV_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "")


async def _process_signal(user_id: str, sig: TVSignal, broker_name: str = "mock"):
    fill = await route_order(
        db, user_id, broker_name,
        symbol=sig.symbol, side=sig.side, qty=sig.qty, price=sig.price,
    )
    order = Order(
        user_id=user_id, broker=broker_name, symbol=sig.symbol, side=sig.side,
        qty=sig.qty, price=fill.get("fill_price", sig.price),
        order_type="MARKET", product="MIS",
        status=fill["status"], source="tradingview", signal_id=sig.id,
        filled_at=datetime.now(timezone.utc),
    )
    await db.orders.insert_one(order.to_mongo())
    from routers.order_routes import _upsert_position
    await _upsert_position(user_id, order)
    await db.tv_signals.update_one({"_id": sig.id},
                                   {"$set": {"processed": True, "order_id": order.id}})
    n = Notification(
        user_id=user_id, kind="signal",
        title=f"TradingView {sig.side} {sig.symbol}",
        message=f"Auto-executed via {broker_name} ({fill.get('mode')}) at ₹{order.price} (qty {sig.qty}).",
        severity="success" if sig.side.upper() == "BUY" else "warning",
    )
    await db.notifications.insert_one(n.to_mongo())
    await send_for_user(
        db, user_id,
        f"*📡 TradingView alert*\n`{sig.side}` {sig.symbol} × {sig.qty} @ ₹{order.price}\n_via {broker_name} ({fill.get('mode')})_",
    )
    from services.push_fcm import send_for_user as push_for_user
    await push_for_user(
        db, user_id,
        f"TV {sig.side} {sig.symbol}",
        f"× {sig.qty} @ ₹{order.price} via {broker_name}",
        data={"kind": "tv_signal", "signal_id": sig.id, "order_id": order.id},
    )
    return order


async def _ingest_signal(user_id: str, body: TVSignalCreate, raw_payload: dict, broker_name: str = "mock"):
    key = derive_key(raw_payload)
    is_new, existing_sig_id = await claim(user_id, key)
    if not is_new:
        existing = await db.tv_signals.find_one({"_id": existing_sig_id}) if existing_sig_id else None
        return {
            "ok": True, "duplicate": True, "idempotency_key": key,
            "signal_id": existing_sig_id,
            "order_id": (existing or {}).get("order_id"),
        }
    sig = TVSignal(
        user_id=user_id, symbol=body.symbol.upper(), side=body.side.upper(),
        price=float(body.price), qty=int(body.qty), strategy=body.strategy,
        payload=raw_payload,
    )
    await db.tv_signals.insert_one(sig.to_mongo())
    await attach_signal(user_id, key, sig.id)
    order = await _process_signal(user_id, sig, broker_name=broker_name)
    return {
        "ok": True, "duplicate": False, "idempotency_key": key,
        "signal_id": sig.id, "order_id": order.id, "fill_price": order.price,
    }


@router.post("/webhook/{user_id}")
async def webhook(user_id: str, body: TVSignalCreate, request: Request):
    user_doc = await db.users.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    secret = request.query_params.get("secret") or body.secret
    user_secret = user_doc.get("tv_webhook_secret") or ""
    # accept per-user secret; fall back to the global secret only when no per-user one exists
    valid = (user_secret and secret == user_secret) or (not user_secret and secret == TV_SECRET)
    if not valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")
    raw_payload = body.model_dump()
    raw_payload.pop("secret", None)
    return await _ingest_signal(user_id, body, raw_payload)


@router.post("/signals")
async def list_signals_post(limit: int = 50, user: User = Depends(get_current_user)):
    return await list_signals(limit, user)


@router.get("/signals")
async def list_signals(limit: int = 50, user: User = Depends(get_current_user)):
    cur = db.tv_signals.find({"user_id": user.id}).sort("received_at", -1).limit(limit)
    out = []
    async for d in cur:
        out.append(TVSignal.from_mongo(d).model_dump())
    return {"signals": out}


@router.post("/test-fire")
async def test_fire(body: TVSignalCreate, user: User = Depends(get_current_user)):
    raw_payload = body.model_dump()
    raw_payload.pop("secret", None)
    return await _ingest_signal(user.id, body, raw_payload)


@router.get("/webhook-info")
async def webhook_info(user: User = Depends(get_current_user)):
    secret = user.tv_webhook_secret or TV_SECRET
    return {
        "user_id": user.id,
        "webhook_path": f"/api/tradingview/webhook/{user.id}",
        "secret": secret,
        "per_user_secret": bool(user.tv_webhook_secret),
        "example_payload": {
            "symbol": "RELIANCE",
            "side": "BUY",
            "price": 2890.5,
            "qty": 10,
            "strategy": "my-rsi-strategy",
            "alert_id": "{{strategy.order.id}}",
        },
    }
