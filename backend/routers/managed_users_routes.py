"""Managed Users — Trader-only CRUD + multi-broker session generation + User portal endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import get_current_user, get_current_trader, hash_password, verify_password, create_access_token
from db import db
from models import (
    ManagedUser, ManagedUserBroker, ManagedUserCreate, ManagedUserPublic, ManagedUserUpdate,
    User, Order
)
from services.broker_schemas import BROKER_SCHEMAS

router = APIRouter(prefix="/managed-users", tags=["managed-users"])


def _to_public(mu: ManagedUser) -> ManagedUserPublic:
    brokers = getattr(mu, "brokers", [])
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if not brokers and hasattr(mu, "broker") and getattr(mu, "broker"):
        session_generated = getattr(mu, "session_generated", False)
        session_date = getattr(mu, "session_date", "")
        if session_date != today_str:
            session_generated = False
        brokers = [
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
        for b in brokers:
            if getattr(b, "session_date", "") != today_str:
                b.session_generated = False

    return ManagedUserPublic(
        id=mu.id, trader_id=mu.trader_id, name=mu.name, phone=mu.phone,
        bank_account=getattr(mu, "bank_account", ""),
        brokers=brokers, place_order=mu.place_order,
        profit_pct=mu.profit_pct, account_status=mu.account_status,
        created_at=mu.created_at,
    )


# ---- Broker schemas for managed user credential forms ----
# These are SEPARATE from the trader broker_schemas used by /api/brokers.
# Keys use the managed-user convention: alice_blue, icici, zerodha, angel, upstox, fyers.
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


@router.post("", response_model=ManagedUserPublic)
async def create_managed_user(body: ManagedUserCreate, trader: User = Depends(get_current_trader)):
    """Trader creates a new managed user account with one or more brokers."""
    if not body.name or not body.phone or not body.password:
        raise HTTPException(status_code=400, detail="Name, Phone and Password are required")

    if not body.brokers or len(body.brokers) == 0:
        raise HTTPException(status_code=400, detail="At least one broker must be added")

    # Check phone uniqueness
    existing = await db.managed_users.find_one({"phone": body.phone})
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
            )
        )

    mu = ManagedUser(
        trader_id=trader.id,
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
        bank_account=body.bank_account,
        brokers=broker_objs,
        place_order=body.place_order,
        profit_pct=body.profit_pct,
        account_status=body.account_status,
    )
    await db.managed_users.insert_one(mu.to_mongo())
    return _to_public(mu)


@router.get("")
async def list_managed_users(trader: User = Depends(get_current_trader)):
    """List all managed users for this trader."""
    out = []
    async for doc in db.managed_users.find({"trader_id": trader.id}).sort("created_at", -1):
        out.append(_to_public(ManagedUser.from_mongo(doc)).model_dump())
    return {"users": out}


@router.patch("/{user_id}", response_model=ManagedUserPublic)
async def update_managed_user(user_id: str, body: ManagedUserUpdate, trader: User = Depends(get_current_trader)):
    """Edit a managed user's details and broker credentials."""
    doc = await db.managed_users.find_one({"_id": user_id, "trader_id": trader.id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    update_dict = {}
    if body.name is not None:
        update_dict["name"] = body.name
    if body.phone is not None:
        # Verify phone uniqueness — but exclude the current user being edited
        existing_phone = await db.managed_users.find_one({"phone": body.phone})
        if existing_phone and str(existing_phone.get("_id")) != user_id:
            raise HTTPException(status_code=409, detail="Phone number already registered by another user")
        update_dict["phone"] = body.phone
    if body.password:
        update_dict["password_hash"] = hash_password(body.password)
    if body.place_order is not None:
        update_dict["place_order"] = body.place_order
    if body.profit_pct is not None:
        update_dict["profit_pct"] = body.profit_pct
    if body.account_status is not None:
        update_dict["account_status"] = body.account_status
    if body.bank_account is not None:
        update_dict["bank_account"] = body.bank_account

    if body.brokers is not None:
        existing_mu = ManagedUser.from_mongo(doc)
        existing_map = {b.broker.lower(): b for b in getattr(existing_mu, "brokers", [])}

        new_brokers = []
        for b in body.brokers:
            b_key = b.broker.lower()
            old = existing_map.get(b_key)
            # Start with the old credentials and only overwrite with new non-empty values
            merged_creds = dict(old.credentials if old else {})
            incoming_creds = dict(b.credentials or {})
            # Only overwrite a credential field if the new value is non-empty
            for k, v in incoming_creds.items():
                if v and v.strip():
                    merged_creds[k] = v
            # Also handle top-level fields
            if b.api_key and b.api_key.strip():
                merged_creds["api_key"] = b.api_key
            if b.api_secret and b.api_secret.strip():
                merged_creds["api_secret"] = b.api_secret

            new_brokers.append(
                ManagedUserBroker(
                    broker=b.broker,
                    api_key=merged_creds.get("api_key", old.api_key if old else ""),
                    api_secret=merged_creds.get("api_secret", old.api_secret if old else ""),
                    account_number=merged_creds.get("account_number", merged_creds.get("user_id", merged_creds.get("client_code", old.account_number if old else ""))),
                    account_password=merged_creds.get("account_password", merged_creds.get("pin", old.account_password if old else "")),
                    credentials=merged_creds,
                    session_token=old.session_token if old else "",
                    session_generated=old.session_generated if old else False,
                    session_date=old.session_date if old else "",
                ).model_dump()
            )
        update_dict["brokers"] = new_brokers

    if update_dict:
        await db.managed_users.update_one({"_id": user_id}, {"$set": update_dict})

    new_doc = await db.managed_users.find_one({"_id": user_id})
    return _to_public(ManagedUser.from_mongo(new_doc))


@router.delete("/{user_id}")
async def delete_managed_user(user_id: str, trader: User = Depends(get_current_trader)):
    """Delete a managed user."""
    res = await db.managed_users.delete_one({"_id": user_id, "trader_id": trader.id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}


@router.get("/eligibility")
async def get_eligibility_report(trader: User = Depends(get_current_trader)):
    """Return per-user eligibility report for order mirroring.

    Shows which gate each managed user fails (place_order, account_status,
    session_generated, credentials) so traders can diagnose issues quickly.
    """
    from services.managed_order_engine import get_eligibility_report
    report = await get_eligibility_report(db, trader.id)
    return {"report": report}


@router.get("/me/brokers")
async def get_my_brokers(current_user: User = Depends(get_current_user)):
    """Get list of brokers and session status for logged in managed user."""
    if current_user.role != "managed_user":
        raise HTTPException(status_code=403, detail="Only managed users can access this")

    doc = await db.managed_users.find_one({"_id": current_user.id})
    if not doc:
        raise HTTPException(status_code=404, detail="Managed user record not found")

    mu = ManagedUser.from_mongo(doc)
    public = _to_public(mu)
    return {"brokers": [b.model_dump() for b in public.brokers], "user": public.model_dump()}


@router.post("/{user_id}/get-session/{broker_name}")
async def generate_broker_session(
    user_id: str,
    broker_name: str,
    current_user: User = Depends(get_current_user)
):
    """Generate session token for a specific broker belonging to a managed user."""
    target_id = current_user.id if current_user.role == "managed_user" else user_id
    doc = await db.managed_users.find_one({"_id": target_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    mu = ManagedUser.from_mongo(doc)
    if mu.account_status != "active":
        raise HTTPException(status_code=400, detail="Account is deactivated")

    brokers = getattr(mu, "brokers", [])
    matched_idx = -1
    matched_b = None
    for idx, b in enumerate(brokers):
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

    brokers[matched_idx] = matched_b

    await db.managed_users.update_one(
        {"_id": mu.id},
        {"$set": {"brokers": [b.model_dump() for b in brokers]}}
    )

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
    current_user: User = Depends(get_current_user)
):
    """Save manually submitted session token/code for a broker."""
    target_id = current_user.id if current_user.role == "managed_user" else user_id
    doc = await db.managed_users.find_one({"_id": target_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    mu = ManagedUser.from_mongo(doc)
    brokers = getattr(mu, "brokers", [])
    matched_idx = -1
    for idx, b in enumerate(brokers):
        if b.broker.lower().replace(" ", "_") == broker_name.lower().replace(" ", "_"):
            matched_idx = idx
            break

    if matched_idx == -1:
        raise HTTPException(status_code=404, detail="Broker not found")

    brokers[matched_idx].session_token = req.session_token.strip()
    brokers[matched_idx].session_generated = True
    brokers[matched_idx].session_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await db.managed_users.update_one(
        {"_id": mu.id},
        {"$set": {"brokers": [b.model_dump() for b in brokers]}}
    )
    return {"ok": True, "message": "Session saved successfully"}



@router.get("/me/orders")
async def get_my_orders(current_user: User = Depends(get_current_user)):
    """Get orders with calculated P&L for the logged in managed user."""
    if current_user.role != "managed_user":
        raise HTTPException(status_code=403, detail="Only managed users can access this")

    # Fetch all orders sorted oldest-first for FIFO P&L matching
    cur = db.orders.find({"user_id": current_user.id}).sort("placed_at", 1)
    raw_orders = []
    async for d in cur:
        raw_orders.append(Order.from_mongo(d).model_dump())

    from services.market_data import tick_engine

    # FIFO buy queue per symbol to match against sells
    buys_by_symbol: dict = {}
    orders_with_pnl = []

    for o in raw_orders:
        sym = o.get("symbol", "")
        side = (o.get("side") or "").upper()
        qty = int(o.get("qty") or 0)
        price = float(o.get("price") or 0)
        is_filled = (o.get("status") or "").upper() in ("FILLED", "COMPLETE", "COMPLETED")

        computed_pnl = None  # None = not yet matched

        if is_filled and qty > 0 and price > 0:
            if side == "BUY":
                if sym not in buys_by_symbol:
                    buys_by_symbol[sym] = []
                buys_by_symbol[sym].append({"qty": qty, "price": price, "order_idx": len(orders_with_pnl)})
                # Unrealized: current price vs buy price
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
                    # Update unrealized on the matched BUY order
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

    # Clean up internal ref field and sort newest first
    for o in orders_with_pnl:
        o.pop("_buy_queue_ref", None)
    orders_with_pnl.sort(key=lambda x: str(x.get("placed_at", "")), reverse=True)

    return {"orders": orders_with_pnl}


async def _execute_broker_session(b: ManagedUserBroker) -> tuple[str, str]:
    """Execute session generation for a broker. Returns (session_token, login_url)."""
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
                 raise HTTPException(status_code=400, detail="Missing Angel credentials (Client ID, PIN, or TOTP Secret)")
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

