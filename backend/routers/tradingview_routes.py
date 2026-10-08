"""TradingView webhook endpoint + signal feed (with idempotency + Telegram)."""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth import get_current_user
from db import get_db
from models import Notification, Order, TVSignal, User
from schemas import TVSignalCreate
from services.broker_router import route_order
from services.idempotency import attach_signal, claim, derive_key
from services.telegram import send_for_user

router = APIRouter(prefix="/tradingview", tags=["tradingview"])

TV_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "")


async def _process_signal(session: AsyncSession, user_id: str, sig: TVSignal, broker_name: str = "mock"):
    fill = await route_order(
        session, user_id, broker_name,
        symbol=sig.symbol, side=sig.side, qty=sig.qty, price=sig.price,
    )
    order = Order(
        id=str(uuid.uuid4()),
        user_id=user_id, broker=broker_name, symbol=sig.symbol, side=sig.side,
        qty=sig.qty, price=fill.get("fill_price", sig.price),
        order_type="MARKET", product="MIS",
        status=fill["status"], source="tradingview", signal_id=sig.id,
        filled_at=datetime.now(timezone.utc),
    )
    session.add(order)
    await session.commit()
    
    from routers.order_routes import _upsert_position
    await _upsert_position(session, user_id, order)
    
    sig.processed = True
    sig.order_id = order.id
    await session.commit()
    
    n = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id, kind="signal",
        title=f"TradingView {sig.side} {sig.symbol}",
        message=f"Auto-executed via {broker_name} ({fill.get('mode')}) at ₹{order.price} (qty {sig.qty}).",
        severity="success" if sig.side.upper() == "BUY" else "warning",
        created_at=datetime.now(timezone.utc)
    )
    session.add(n)
    await session.commit()
    
    await send_for_user(
        session, user_id,
        f"*📡 TradingView alert*\n`{sig.side}` {sig.symbol} × {sig.qty} @ ₹{order.price}\n_via {broker_name} ({fill.get('mode')})_",
    )
    from services.push_fcm import send_for_user as push_for_user
    await push_for_user(
        session, user_id,
        f"TV {sig.side} {sig.symbol}",
        f"× {sig.qty} @ ₹{order.price} via {broker_name}",
        data={"kind": "tv_signal", "signal_id": sig.id, "order_id": order.id},
    )
    # Mirror to all eligible managed users (fire-and-forget)
    import asyncio
    from services.managed_order_engine import mirror_order_to_managed_users
    asyncio.create_task(mirror_order_to_managed_users(session, user_id, order))
    return order


async def _ingest_signal(session: AsyncSession, user_id: str, body: TVSignalCreate, raw_payload: dict, broker_name: str = "mock"):
    key = derive_key(raw_payload)
    is_new, existing_sig_id = await claim(session, user_id, key)
    if not is_new:
        existing = None
        if existing_sig_id:
            stmt = select(TVSignal).where(TVSignal.id == existing_sig_id)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            
        return {
            "ok": True, "duplicate": True, "idempotency_key": key,
            "signal_id": existing_sig_id,
            "order_id": existing.order_id if existing else None,
        }
    sig = TVSignal(
        id=str(uuid.uuid4()),
        user_id=user_id, symbol=body.symbol.upper(), side=body.side.upper(),
        price=float(body.price), qty=int(body.qty), strategy=body.strategy,
        payload=raw_payload, received_at=datetime.now(timezone.utc)
    )
    session.add(sig)
    await session.commit()
    
    await attach_signal(session, user_id, key, sig.id)
    order = await _process_signal(session, user_id, sig, broker_name=broker_name)
    return {
        "ok": True, "duplicate": False, "idempotency_key": key,
        "signal_id": sig.id, "order_id": order.id, "fill_price": order.price,
    }


@router.post("/webhook/{user_id}")
async def webhook(user_id: str, body: TVSignalCreate, request: Request, session: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user_doc = result.scalar_one_or_none()
    
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    secret = request.query_params.get("secret") or body.secret
    
    # Check if there is an attribute for tv_webhook_secret in User model. 
    # If not, getattr will safely return None.
    user_secret = getattr(user_doc, "tv_webhook_secret", "") or ""
    
    # accept per-user secret; fall back to the global secret only when no per-user one exists
    valid = (user_secret and secret == user_secret) or (not user_secret and secret == TV_SECRET)
    if not valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")
    raw_payload = body.model_dump()
    raw_payload.pop("secret", None)
    return await _ingest_signal(session, user_id, body, raw_payload)


@router.post("/signals")
async def list_signals_post(limit: int = 50, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await list_signals(limit, user, session)


@router.get("/signals")
async def list_signals(limit: int = 50, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(TVSignal).where(TVSignal.user_id == user.id).order_by(TVSignal.received_at.desc()).limit(limit)
    result = await session.execute(stmt)
    signals = result.scalars().all()
    
    out = []
    for d in signals:
        out.append({
            "id": d.id, "user_id": d.user_id, "symbol": d.symbol, "side": d.side,
            "price": d.price, "qty": d.qty, "strategy": d.strategy, "payload": d.payload,
            "received_at": d.received_at, "processed": d.processed, "order_id": d.order_id
        })
    return {"signals": out}


@router.post("/test-fire")
async def test_fire(body: TVSignalCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    raw_payload = body.model_dump()
    raw_payload.pop("secret", None)
    return await _ingest_signal(session, user.id, body, raw_payload)


@router.get("/webhook-info")
async def webhook_info(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    user_secret = getattr(user, "tv_webhook_secret", "")
    secret = user_secret or TV_SECRET
    return {
        "user_id": user.id,
        "webhook_path": f"/api/tradingview/webhook/{user.id}",
        "secret": secret,
        "per_user_secret": bool(user_secret),
        "example_payload": {
            "symbol": "RELIANCE",
            "side": "BUY",
            "price": 2890.5,
            "qty": 10,
            "strategy": "my-rsi-strategy",
            "alert_id": "{{strategy.order.id}}",
        },
    }
