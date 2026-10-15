"""Managed Users — Trader-only CRUD + multi-broker session generation + User portal endpoints."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import get_current_user, get_current_trader, hash_password, verify_password, create_access_token
from db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert, delete, desc, asc
from models import ManagedUser as ManagedUserModel, User as UserModel, Order as OrderModel
from schemas import (
    ManagedUserCreate, ManagedUserPublic, ManagedUserUpdate, UserPublic, ManagedUserBroker
)
from services.broker_schemas import BROKER_SCHEMAS

router = APIRouter(prefix="/managed-users", tags=["managed-users"])


def _to_public(mu: ManagedUserModel) -> ManagedUserPublic:
    brokers = getattr(mu, "brokers", [])
    if not isinstance(brokers, list):
        brokers = []
    
    # brokers is a list of dicts because it's JSON from SQLAlchemy
    # We parse it to ManagedUserBroker
    parsed_brokers = []
    for b in brokers:
        if isinstance(b, dict):
            parsed_brokers.append(ManagedUserBroker(**b))
        else:
            parsed_brokers.append(b)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if not parsed_brokers and hasattr(mu, "broker") and getattr(mu, "broker"):
        session_generated = getattr(mu, "session_generated", False)
        session_date = getattr(mu, "session_date", "")
        if session_date != today_str:
            session_generated = False
        parsed_brokers = [
            ManagedUserBroker(
                broker=getattr(mu, "broker"),
                api_key=getattr(mu, "api_key", ""),
                api_secret=getattr(mu, "api_secret", ""),
                account_number=getattr(mu, "account_number", ""),
                account_password=getattr(mu, "account_password", ""),
                credentials={
                    "api_key": getattr(mu, "api_key", ""),
                    "api_secret": getattr(mu, "api_secret", ""),
                    "account_number": getattr(mu, "account_number", ""),
                    "account_password": getattr(mu, "account_password", ""),
                },
                session_token=getattr(mu, "session_token", ""),
                session_generated=session_generated,
                session_date=session_date,
            )
        ]
    else:
        for b in parsed_brokers:
            if getattr(b, "session_date", "") != today_str:
                b.session_generated = False

    enrollment_date = None
    if mu.created_at:
        enrollment_date = mu.created_at.strftime("%Y-%m-%d")

    alloc_pct = getattr(mu, "capital_allocation_pct", 100.0)
    if alloc_pct is None:
        alloc_pct = 100.0

    return ManagedUserPublic(
        id=mu.id, trader_id=mu.trader_id, name=mu.name, phone=getattr(mu, "phone", "") or getattr(mu, "email", ""), # model uses email
        bank_account=getattr(mu, "bank_account", ""),
        brokers=parsed_brokers, place_order=getattr(mu, "place_order", True),
        profit_pct=getattr(mu, "profit_pct", 0.0), account_status=getattr(mu, "account_status", "active"),
        capital_allocation_pct=float(alloc_pct),
        enrollment_date=enrollment_date,
        created_at=mu.created_at or datetime.now(timezone.utc),
    )


# ---- Broker schemas for managed user credential forms ----
MANAGED_USER_BROKER_SCHEMAS = {
    "alice_blue": {
        "name": "Alice Blue",
        "fields": [
            {"name": "user_id", "label": "User ID / Client ID", "type": "text", "required": True,
             "placeholder": "e.g. AB12345", "help": "Your Alice Blue Client Code"},
            {"name": "api_key", "label": "API Key (App Code)", "type": "text", "required": True,
             "placeholder": "App Code from Developer Portal"},
            {"name": "api_secret", "label": "API Secret", "type": "password", "required": True,
             "placeholder": "App Secret Key"},
        ],
    },
    "zerodha": {
        "name": "Zerodha Kite Connect",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "text", "required": True,
             "placeholder": "From Kite Developer Console"},
            {"name": "api_secret", "label": "API Secret", "type": "password", "required": True,
             "placeholder": "Shown on Kite App Creation"},
        ],
    },
    "icici": {
        "name": "ICICI Direct (Breeze)",
        "fields": [
            {"name": "api_key", "label": "App Key / API Key", "type": "text", "required": True,
             "placeholder": "Breeze App Key"},
            {"name": "api_secret", "label": "Secret Key", "type": "password", "required": True,
             "placeholder": "Breeze Secret Key"},
            {"name": "session_token", "label": "Session Token", "type": "password", "required": True,
             "placeholder": "Daily Session Token"},
        ],
    },
    "angel": {
        "name": "Angel One (SmartAPI)",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "text", "required": True,
             "placeholder": "Angel SmartAPI Key"},
            {"name": "client_code", "label": "Client Code", "type": "text", "required": True,
             "placeholder": "Your Angel Client Code"},
            {"name": "pin", "label": "PIN / Password", "type": "password", "required": True,
             "placeholder": "Account PIN"},
            {"name": "totp_secret", "label": "TOTP Secret Key", "type": "password", "required": True,
             "placeholder": "Authenticator TOTP Secret"},
        ],
    },
    "upstox": {
        "name": "Upstox",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "text", "required": True,
             "placeholder": "Upstox API Key"},
            {"name": "api_secret", "label": "API Secret", "type": "password", "required": True,
             "placeholder": "Upstox Secret Key"},
        ],
    },
    "fyers": {
        "name": "Fyers",
        "fields": [
            {"name": "api_key", "label": "App ID / Client ID", "type": "text", "required": True,
             "placeholder": "Fyers App ID"},
            {"name": "api_secret", "label": "Secret ID", "type": "password", "required": True,
             "placeholder": "Fyers Secret ID"},
        ],
    },
}


@router.get("/schemas")
async def get_broker_schemas():
    """Returns managed-user broker field schemas (separate from the trader /api/brokers schemas)."""
    return {"schemas": MANAGED_USER_BROKER_SCHEMAS}


@router.post("")
async def create_managed_user(body: ManagedUserCreate, trader: UserPublic = Depends(get_current_trader), db: AsyncSession = Depends(get_db)):
    """Trader creates a new managed user account with one or more brokers."""
    if not body.name or not body.phone or not body.password:
        raise HTTPException(status_code=400, detail="Name, Phone and Password are required")

    if not body.brokers or len(body.brokers) == 0:
        raise HTTPException(status_code=400, detail="At least one broker must be added")

    # Check phone uniqueness (email mapped to phone in SQLAlchemy model)
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.email == body.phone))
    existing = res.scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Phone number already registered")

    broker_objs = []
    for b in body.brokers:
        creds = dict(b.credentials or {})
        if b.api_key: creds.setdefault("api_key", b.api_key)
        if b.api_secret: creds.setdefault("api_secret", b.api_secret)
        if b.account_number: creds.setdefault("account_number", b.account_number)
        if b.account_password: creds.setdefault("account_password", b.account_password)

        broker_objs.append(
            ManagedUserBroker(
                broker=b.broker,
                api_key=creds.get("api_key", b.api_key or ""),
                api_secret=creds.get("api_secret", b.api_secret or ""),
                account_number=creds.get("account_number", creds.get("user_id", creds.get("client_code", b.account_number or ""))),
                account_password=creds.get("account_password", creds.get("pin", creds.get("totp_secret", b.account_password or ""))),
                credentials=creds,
                session_generated=False,
            ).model_dump()
        )

    mu_id = str(uuid.uuid4())
    mu = ManagedUserModel(
        id=mu_id,
        trader_id=trader.id,
        name=body.name,
        email=body.phone,  # mapped phone -> email
        phone=body.phone,
        password_hash=hash_password(body.password),
        profit_pct=body.profit_pct,
        bank_account=body.bank_account,
        place_order=body.place_order,
        account_status=body.account_status,
        capital_allocation_pct=body.capital_allocation_pct if body.capital_allocation_pct is not None else 100.0,
        brokers=broker_objs,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(mu)
    await db.commit()
    await db.refresh(mu)
    
    # We will inject the missing properties onto the object so _to_public works
    mu.phone = body.phone
    mu.place_order = getattr(body, "place_order", True)
    mu.profit_pct = getattr(body, "profit_pct", 0.0)
    mu.account_status = getattr(body, "account_status", "active")
    mu.capital_allocation_pct = getattr(body, "capital_allocation_pct", 100.0)
    
    return _to_public(mu)


@router.get("")
async def list_managed_users(trader: UserPublic = Depends(get_current_trader), db: AsyncSession = Depends(get_db)):
    """List all managed users for this trader."""
    out = []
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.trader_id == trader.id).order_by(desc(ManagedUserModel.created_at)))
    docs = res.scalars().all()
    for doc in docs:
        out.append(_to_public(doc).model_dump())
    return {"users": out}


@router.patch("/{user_id}")
async def update_managed_user(user_id: str, body: ManagedUserUpdate, trader: UserPublic = Depends(get_current_trader), db: AsyncSession = Depends(get_db)):
    """Edit a managed user's details and broker credentials."""
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == user_id, ManagedUserModel.trader_id == trader.id))
    doc = res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name is not None:
        doc.name = body.name
    if body.phone is not None:
        res2 = await db.execute(select(ManagedUserModel).where(ManagedUserModel.email == body.phone))
        existing_phone = res2.scalars().first()
        if existing_phone and existing_phone.id != user_id:
            raise HTTPException(status_code=409, detail="Phone number already registered by another user")
        doc.email = body.phone
        doc.phone = body.phone
    if body.password:
        doc.password_hash = hash_password(body.password)
    if body.bank_account is not None:
        doc.bank_account = body.bank_account
    if body.place_order is not None:
        doc.place_order = body.place_order
    if body.profit_pct is not None:
        doc.profit_pct = body.profit_pct
    if body.account_status is not None:
        doc.account_status = body.account_status
    if body.capital_allocation_pct is not None:
        doc.capital_allocation_pct = body.capital_allocation_pct

    if body.brokers is not None:
        existing_brokers = getattr(doc, "brokers", []) or []
        existing_map = {b.get("broker").lower(): b for b in existing_brokers if isinstance(b, dict)}
        if not existing_map and existing_brokers:
             existing_map = {b.broker.lower(): b for b in existing_brokers if not isinstance(b, dict)}

        new_brokers = []
        for b in body.brokers:
            b_key = b.broker.lower()
            old = existing_map.get(b_key) or {}
            if not isinstance(old, dict):
                old = old.model_dump() if hasattr(old, "model_dump") else {}
                
            merged_creds = dict(old.get("credentials", {}) if old else {})
            incoming_creds = dict(b.credentials or {})
            for k, v in incoming_creds.items():
                if v and str(v).strip():
                    merged_creds[k] = v
                    
            if b.api_key and b.api_key.strip():
                merged_creds["api_key"] = b.api_key
            if b.api_secret and b.api_secret.strip():
                merged_creds["api_secret"] = b.api_secret

            new_brokers.append(
                ManagedUserBroker(
                    broker=b.broker,
                    api_key=merged_creds.get("api_key", old.get("api_key", "") if old else ""),
                    api_secret=merged_creds.get("api_secret", old.get("api_secret", "") if old else ""),
                    account_number=merged_creds.get("account_number", merged_creds.get("user_id", merged_creds.get("client_code", old.get("account_number", "") if old else ""))),
                    account_password=merged_creds.get("account_password", merged_creds.get("pin", old.get("account_password", "") if old else "")),
                    credentials=merged_creds,
                    session_token=old.get("session_token", "") if old else "",
                    session_generated=old.get("session_generated", False) if old else False,
                    session_date=old.get("session_date", "") if old else "",
                ).model_dump()
            )
        doc.brokers = new_brokers

    await db.commit()
    await db.refresh(doc)
    return _to_public(doc)


@router.delete("/{user_id}")
async def delete_managed_user(user_id: str, trader: UserPublic = Depends(get_current_trader), db: AsyncSession = Depends(get_db)):
    """Delete a managed user."""
    res = await db.execute(delete(ManagedUserModel).where(ManagedUserModel.id == user_id, ManagedUserModel.trader_id == trader.id))
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await db.commit()
    return {"deleted": True}


@router.get("/capital-metrics")
async def get_all_capital_metrics(
    trader: UserPublic = Depends(get_current_trader),
    db: AsyncSession = Depends(get_db)
):
    """Fetch live capital metrics for all managed users belonging to trader."""
    from services.capital_service import get_managed_user_capital_metrics
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.trader_id == trader.id))
    users = res.scalars().all()
    metrics_map = {}
    for u in users:
        try:
            m = await get_managed_user_capital_metrics(db, u)
            metrics_map[u.id] = m
        except Exception as e:
            metrics_map[u.id] = {
                "user_id": u.id,
                "enrollment_date": u.created_at.strftime("%Y-%m-%d") if u.created_at else None,
                "capital_allocation_pct": getattr(u, "capital_allocation_pct", 100.0) or 100.0,
                "total_account_funds": 0.0,
                "allocated_amount": 0.0,
                "amount_used": 0.0,
                "available_amount": 0.0,
                "error": str(e)
            }
    return {"metrics": metrics_map}


@router.get("/{user_id}/capital-metrics")
async def get_user_capital_metrics(
    user_id: str,
    trader: UserPublic = Depends(get_current_trader),
    db: AsyncSession = Depends(get_db)
):
    """Fetch live capital metrics for a specific managed user."""
    from services.capital_service import get_managed_user_capital_metrics
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == user_id, ManagedUserModel.trader_id == trader.id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    metrics = await get_managed_user_capital_metrics(db, u)
    return {"metrics": metrics}


@router.get("/eligibility")
async def get_eligibility_report(trader: UserPublic = Depends(get_current_trader), db: AsyncSession = Depends(get_db)):
    from services.managed_order_engine import get_eligibility_report
    report = await get_eligibility_report(db, trader.id)
    return {"report": report}


@router.get("/me")
async def get_my_profile(current_user: UserPublic = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role != "managed_user":
        raise HTTPException(status_code=403, detail="Only managed users can access this")
        
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == current_user.id))
    mu = res.scalars().first()
    if not mu:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {
        "id": mu.id,
        "name": mu.name,
        "email": mu.email,
        "phone": mu.phone,
        "place_order": mu.place_order,
        "account_status": getattr(mu, "account_status", "active"),
        "profit_pct": getattr(mu, "profit_pct", 0.0)
    }

@router.patch("/me/place_order")
async def toggle_my_place_order(
    body: dict,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "managed_user":
        raise HTTPException(status_code=403, detail="Only managed users can access this")
        
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == current_user.id))
    mu = res.scalars().first()
    if not mu:
        raise HTTPException(status_code=404, detail="User not found")
        
    mu.place_order = body.get("place_order", False)
    await db.commit()
    return {"status": "success", "place_order": mu.place_order}

@router.get("/me/brokers")
async def get_my_brokers(current_user: UserPublic = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get list of brokers and session status for logged in managed user."""
    if current_user.role != "managed_user":
        raise HTTPException(status_code=403, detail="Only managed users can access this")

    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == current_user.id))
    doc = res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Managed user record not found")

    public = _to_public(doc)
    return {"brokers": [b.model_dump() for b in public.brokers], "user": public.model_dump()}


@router.post("/{user_id}/get-session/{broker_name}")
async def generate_broker_session(
    user_id: str,
    broker_name: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_id = current_user.id if current_user.role == "managed_user" else user_id
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == target_id))
    mu = res.scalars().first()
    if not mu:
        raise HTTPException(status_code=404, detail="User not found")

    # Assuming account_status not in model, default active
    account_status = getattr(mu, "account_status", "active")
    if account_status != "active":
        raise HTTPException(status_code=400, detail="Account is deactivated")

    brokers = getattr(mu, "brokers", []) or []
    # parse
    parsed_brokers = []
    for b in brokers:
        if isinstance(b, dict):
            parsed_brokers.append(ManagedUserBroker(**b))
        else:
            parsed_brokers.append(b)
            
    matched_idx = -1
    matched_b = None
    for idx, b in enumerate(parsed_brokers):
        if b.broker.lower().replace(" ", "_") == broker_name.lower().replace(" ", "_"):
            matched_idx = idx
            matched_b = b
            break

    if not matched_b:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_name}' not configured for this user")

    session_token, login_url = await _execute_broker_session(matched_b)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    matched_b.session_token = session_token
    matched_b.session_generated = True if session_token else False
    matched_b.session_date = today_str if session_token else ""

    parsed_brokers[matched_idx] = matched_b
    mu.brokers = [b.model_dump() for b in parsed_brokers]
    await db.commit()

    return {
        "ok": True,
        "broker": matched_b.broker,
        "session_generated": matched_b.session_generated,
        "session_date": today_str,
        "login_url": login_url or ""
    }


class SaveSessionRequest(BaseModel):
    session_token: str

@router.post("/{user_id}/save-session/{broker_name}")
async def save_broker_session(
    user_id: str,
    broker_name: str,
    req: SaveSessionRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_id = current_user.id if current_user.role == "managed_user" else user_id
    res = await db.execute(select(ManagedUserModel).where(ManagedUserModel.id == target_id))
    mu = res.scalars().first()
    if not mu:
        raise HTTPException(status_code=404, detail="User not found")

    brokers = getattr(mu, "brokers", []) or []
    parsed_brokers = []
    for b in brokers:
        if isinstance(b, dict):
            parsed_brokers.append(ManagedUserBroker(**b))
        else:
            parsed_brokers.append(b)

    matched_idx = -1
    for idx, b in enumerate(parsed_brokers):
        if b.broker.lower().replace(" ", "_") == broker_name.lower().replace(" ", "_"):
            matched_idx = idx
            break

    if matched_idx == -1:
        raise HTTPException(status_code=404, detail="Broker not found")

    parsed_brokers[matched_idx].session_token = req.session_token.strip()
    parsed_brokers[matched_idx].session_generated = True
    parsed_brokers[matched_idx].session_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    mu.brokers = [b.model_dump() for b in parsed_brokers]
    await db.commit()
    
    return {"ok": True, "message": "Session saved successfully"}


@router.get("/me/orders")
async def get_my_orders(current_user: UserPublic = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role != "managed_user":
        raise HTTPException(status_code=403, detail="Only managed users can access this")

    res = await db.execute(select(OrderModel).where(OrderModel.user_id == current_user.id).order_by(asc(OrderModel.placed_at)))
    docs = res.scalars().all()
    
    raw_orders = []
    for d in docs:
        raw_orders.append({
            "id": d.id,
            "user_id": d.user_id,
            "broker": d.broker,
            "symbol": d.symbol,
            "side": d.side,
            "qty": d.qty,
            "price": d.price,
            "order_type": d.order_type,
            "product": d.product,
            "status": d.status,
            "placed_at": d.placed_at,
            "filled_at": d.filled_at,
            "pnl": d.pnl,
            "reject_reason": d.reject_reason,
            "is_mock": d.is_mock
        })

    from services.market_data import tick_engine

    buys_by_symbol: dict = {}
    orders_with_pnl = []

    for o in raw_orders:
        sym = o.get("symbol", "")
        side = (o.get("side") or "").upper()
        qty = int(o.get("qty") or 0)
        price = float(o.get("price") or 0)
        is_filled = (o.get("status") or "").upper() in ("FILLED", "COMPLETE", "COMPLETED")

        computed_pnl = None

        if is_filled and qty > 0 and price > 0:
            if side == "BUY":
                if sym not in buys_by_symbol:
                    buys_by_symbol[sym] = []
                buys_by_symbol[sym].append({"qty": qty, "price": price, "order_idx": len(orders_with_pnl)})
                current_ltp = tick_engine.prices.get(sym, 0.0)
                if current_ltp > 0:
                    computed_pnl = round(qty * (current_ltp - price), 2)
                else:
                    computed_pnl = 0.0
            elif side == "SELL":
                remaining = qty
                realized = 0.0
                buy_queue = buys_by_symbol.get(sym, [])
                while remaining > 0 and buy_queue:
                    oldest = buy_queue[0]
                    match_qty = min(remaining, oldest["qty"])
                    realized += match_qty * (price - oldest["price"])
                    for prev_o in orders_with_pnl:
                        if prev_o.get("_buy_queue_ref") == oldest.get("order_idx"):
                            prev_o["pnl"] = round(match_qty * (price - oldest["price"]), 2)
                            prev_o["unrealized"] = False
                            break
                    oldest["qty"] -= match_qty
                    remaining -= match_qty
                    if oldest["qty"] == 0:
                        buy_queue.pop(0)
                buys_by_symbol[sym] = buy_queue
                computed_pnl = round(realized, 2)

        o["pnl"] = computed_pnl if computed_pnl is not None else 0.0
        o["unrealized"] = side == "BUY" and is_filled
        o["_buy_queue_ref"] = len(orders_with_pnl) if side == "BUY" else None
        orders_with_pnl.append(o)

    for o in orders_with_pnl:
        o.pop("_buy_queue_ref", None)
    orders_with_pnl.sort(key=lambda x: str(x.get("placed_at", "")), reverse=True)

    return {"orders": orders_with_pnl}


async def _execute_broker_session(b: ManagedUserBroker) -> tuple[str, str]:
    b_name = b.broker.lower().replace(" ", "_")
    creds = b.credentials or {}

    api_key = creds.get("api_key") or b.api_key
    api_secret = creds.get("api_secret") or b.api_secret
    user_id = creds.get("user_id") or creds.get("client_code") or b.account_number
    pin = creds.get("pin") or creds.get("account_password") or b.account_password
    totp_secret = creds.get("totp_secret") or creds.get("api_secret") or b.api_secret
    session_token = creds.get("session_token") or b.session_token

    if not api_key:
        raise HTTPException(status_code=400, detail=f"API Key missing for {b.broker}. Please configure properly.")

    try:
        if "alice" in b_name:
            url = f"https://ant.aliceblueonline.com/?appcode={api_key}"
            return "", url
        elif "angel" in b_name:
            if not user_id or not pin or not totp_secret:
                 raise HTTPException(status_code=400, detail="Missing Angel credentials")
            from services.brokers.angel_client import AngelClient
            client = AngelClient(
                api_key=api_key,
                client_code=user_id,
                pin=pin,
                totp_secret=totp_secret,
            )
            tokens = client.login()
            return tokens.get("auth_token", ""), ""
        elif "zerodha" in b_name or "kite" in b_name:
            url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
            return "", url
        elif "upstox" in b_name:
            url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri=http://localhost:3000/user-dashboard"
            return "", url
        elif "icici" in b_name or "breeze" in b_name:
            url = f"https://api.icicidirect.com/apiuser/login?api_key={api_key}"
            return "", url
        else:
            raise HTTPException(status_code=400, detail=f"Unknown broker type: {b.broker}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Broker login error: {e}")

