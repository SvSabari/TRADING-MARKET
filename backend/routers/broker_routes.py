"""Broker connection management — generic schema-driven UX."""
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import RedirectResponse

from auth import get_current_user
from constants import BROKERS
from db import db
from models import (
    BrokerConnection, BrokerConnectionPublic, BrokerConnectionUpsert, User,
)
from services.broker_schemas import BROKER_SCHEMAS
from services.crypto import decrypt_str, encrypt_str
from services.kite_client import KiteService

router = APIRouter(prefix="/brokers", tags=["brokers"])

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3000")

# all brokers exposed (mock route is always available + the explicit list)
ALL_BROKERS = list(BROKER_SCHEMAS.keys())


def _to_public(b: BrokerConnection) -> BrokerConnectionPublic:
    creds = b.credentials or {}
    return BrokerConnectionPublic(
        id=b.id, broker=b.broker, connected=b.connected,
        is_data_feed=b.is_data_feed,
        is_order_exec=b.is_order_exec,
        mock_mode=b.mock_mode,
        has_keys=bool(b.api_key) or any(creds.values()),
        has_access_token=bool(b.access_token),
        session_date=b.session_date or "",
        fields_filled=sorted([k for k, v in creds.items() if v]),
    )


@router.get("/schemas")
async def broker_schemas(user: User = Depends(get_current_user)):
    """Field schemas describing what each broker needs."""
    return {"schemas": BROKER_SCHEMAS, "brokers": ALL_BROKERS}


@router.get("")
async def list_connections(user: User = Depends(get_current_user)):
    cur = db.broker_connections.find({"user_id": user.id})
    out = []
    async for d in cur:
        out.append(_to_public(BrokerConnection.from_mongo(d)).model_dump())
    return {"connections": out, "available": ALL_BROKERS, "schemas": BROKER_SCHEMAS}


@router.post("")
async def upsert(body: BrokerConnectionUpsert, user: User = Depends(get_current_user)):
    if body.broker not in ALL_BROKERS:
        raise HTTPException(status_code=400, detail="Unknown broker")
    existing = await db.broker_connections.find_one({"user_id": user.id, "broker": body.broker})
    # Encrypt any new credential values; keep existing for blank fields
    incoming_creds: Dict[str, Any] = dict(body.credentials or {})
    if body.api_key:
        incoming_creds.setdefault("api_key", body.api_key)
    if body.api_secret:
        incoming_creds.setdefault("api_secret", body.api_secret)
    existing_creds = (existing or {}).get("credentials", {}) if existing else {}
    merged_creds: Dict[str, str] = {**(existing_creds or {})}
    for k, v in incoming_creds.items():
        if v not in (None, "", False):
            merged_creds[k] = encrypt_str(str(v))
    api_key_enc = merged_creds.get("api_key", "")
    api_secret_enc = merged_creds.get("api_secret", "")
    connected = bool(api_key_enc or any(merged_creds.values())) or body.mock_mode
    
    # Enforce exclusivity: if this broker is set to be the data feed, un-set all others
    if body.is_data_feed is True:
        await db.broker_connections.update_many(
            {"user_id": user.id, "broker": {"$ne": body.broker}},
            {"$set": {"is_data_feed": False}}
        )
    # Same for order execution
    if body.is_order_exec is True:
        await db.broker_connections.update_many(
            {"user_id": user.id, "broker": {"$ne": body.broker}},
            {"$set": {"is_order_exec": False}}
        )

    if existing:
        update_doc = {
            "api_key": api_key_enc,
            "api_secret": api_secret_enc,
            "credentials": merged_creds,
            "connected": connected,
        }
        if body.is_data_feed is not None:
            update_doc["is_data_feed"] = body.is_data_feed
        if body.is_order_exec is not None:
            update_doc["is_order_exec"] = body.is_order_exec
        if body.mock_mode is not None:
            update_doc["mock_mode"] = body.mock_mode

        await db.broker_connections.update_one(
            {"_id": existing["_id"]},
            {"$set": update_doc},
        )
        from services.live_feed_manager import live_feed_manager
        await live_feed_manager.force_reconnect()
        d = await db.broker_connections.find_one({"_id": existing["_id"]})
        return _to_public(BrokerConnection.from_mongo(d)).model_dump()
    conn = BrokerConnection(
        user_id=user.id, broker=body.broker,
        api_key=api_key_enc, api_secret=api_secret_enc,
        credentials=merged_creds,
        is_data_feed=body.is_data_feed if body.is_data_feed is not None else False,
        is_order_exec=body.is_order_exec if body.is_order_exec is not None else False,
        mock_mode=body.mock_mode if body.mock_mode is not None else True, connected=connected,
    )
    await db.broker_connections.insert_one(conn.to_mongo())
    from services.live_feed_manager import live_feed_manager
    await live_feed_manager.force_reconnect()
    return _to_public(conn).model_dump()


@router.delete("/{broker}")
async def disconnect(broker: str, user: User = Depends(get_current_user)):
    doc = await db.broker_connections.find_one({"user_id": user.id, "broker": broker})
    if not doc:
        return {"deleted": 0}
        
    was_primary = doc.get("is_data_feed", False)
    was_secondary = doc.get("is_order_exec", False)

    
    res = await db.broker_connections.delete_one({"_id": doc["_id"]})
    
    # Auto-fallback for primary: pick a connected broker that is NOT the secondary and NOT mock
    if was_primary:
        fallback = await db.broker_connections.find_one({
            "user_id": user.id, 
            "connected": True, 
            "broker": {"$ne": "mock"},
            "is_order_exec": {"$ne": True}
        })
        if fallback:
            await db.broker_connections.update_one({"_id": fallback["_id"]}, {"$set": {"is_data_feed": True}})
            
    # Auto-fallback for secondary: pick a connected broker that is NOT the primary
    if was_secondary:
        fallback = await db.broker_connections.find_one({
            "user_id": user.id, 
            "connected": True, 
            "is_data_feed": {"$ne": True}
        })
        if fallback:
            await db.broker_connections.update_one({"_id": fallback["_id"]}, {"$set": {"is_order_exec": True}})
            
    from services.live_feed_manager import live_feed_manager
    await live_feed_manager.force_reconnect()
    return {"deleted": res.deleted_count}


# ---- Zerodha Kite OAuth (only broker with redirect today) ----

@router.get("/kite/login-url")
async def kite_login_url(user: User = Depends(get_current_user)):
    doc = await db.broker_connections.find_one({"user_id": user.id, "broker": "zerodha"})
    if not doc or not doc.get("api_key"):
        raise HTTPException(status_code=400, detail="Save your Kite API key + secret first (mock_mode off).")
    api_key = decrypt_str(doc["api_key"])
    svc = KiteService(api_key=api_key)
    redirect_params = f"user_id={user.id}"
    url = svc.login_url(redirect_params=redirect_params)
    callback = f"{APP_BASE_URL}/api/brokers/kite/callback"
    return {
        "login_url": url,
        "expected_redirect_url": callback,
        "note": (
            "Set this exact Redirect URL in your Kite developer console: "
            f"{callback}. After login, Zerodha posts back the request_token to that URL."
        ),
    }


@router.get("/kite/callback")
async def kite_callback(request_token: str = Query(...),
                       status: str = Query("success"),
                       redirect_params: str = Query("")):
    user_id = ""
    for pair in (redirect_params or "").split("&"):
        k, _, v = pair.partition("=")
        if k == "user_id":
            user_id = v
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id missing in redirect_params")
    doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "zerodha"})
    if not doc:
        raise HTTPException(status_code=404, detail="No Kite connection record")
    api_key = decrypt_str(doc["api_key"])
    api_secret = decrypt_str(doc.get("api_secret", ""))
    svc = KiteService(api_key=api_key)
    try:
        data = svc.generate_session(request_token=request_token, api_secret=api_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Kite session exchange failed — invalid or expired request token")
    today_ist = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.broker_connections.update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "access_token": encrypt_str(data["access_token"]),
            "session_date": today_ist,
            "mock_mode": False,
            "connected": True,
        }},
    )
    return RedirectResponse(url=f"{APP_BASE_URL}/brokers?kite=connected", status_code=302)


@router.post("/kite/disconnect")
async def kite_disconnect(user: User = Depends(get_current_user)):
    await db.broker_connections.update_one(
        {"user_id": user.id, "broker": "zerodha"},
        {"$set": {"access_token": "", "session_date": "", "mock_mode": True, "connected": False}},
    )
    return {"ok": True}


# ---- Angel One — TOTP-based login (no external redirect) ----

@router.post("/angel/login")
async def angel_login(user: User = Depends(get_current_user)):
    """Trigger Angel TOTP login. Uses creds the user already saved.

    Stores the returned `auth_token` + `feed_token` (encrypted) so the
    live WebSocket feed + order placement can use them for the session.
    """
    doc = await db.broker_connections.find_one({"user_id": user.id, "broker": "angel"})
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Angel credentials first.")
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    client_code = decrypt_str(creds.get("client_code", ""))
    pin = decrypt_str(creds.get("pin", ""))
    totp_secret = decrypt_str(creds.get("totp_secret", ""))
    if not (api_key and client_code and pin and totp_secret):
        raise HTTPException(status_code=400, detail="Missing Angel API key / client code / PIN / TOTP secret.")
    try:
        from services.brokers.angel_client import AngelClient
        client = AngelClient(
            api_key=api_key, client_code=client_code,
            pin=pin, totp_secret=totp_secret,
        )
        tokens = client.login()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Angel login failed: {e}")
    today_ist = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_creds = {**creds,
                 "auth_token": encrypt_str(tokens["auth_token"]),
                 "refresh_token": encrypt_str(tokens.get("refresh_token", "")),
                 "feed_token": encrypt_str(tokens.get("feed_token", ""))}
    await db.broker_connections.update_one(
        {"_id": doc["_id"]},
        {"$set": {"credentials": new_creds, "session_date": today_ist,
                  "mock_mode": False, "connected": True,
                  "access_token": encrypt_str(tokens["auth_token"])}},
    )
    return {"ok": True, "session_date": today_ist}


# ---- Upstox OAuth ----

UPSTOX_OAUTH_BASE = "https://api.upstox.com/v2/login/authorization/dialog"


@router.get("/upstox/login-url")
async def upstox_login_url(user: User = Depends(get_current_user)):
    doc = await db.broker_connections.find_one({"user_id": user.id, "broker": "upstox"})
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Upstox API key + secret first.")
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    if not api_key:
        raise HTTPException(status_code=400, detail="Upstox API key missing.")
    redirect_uri = f"{APP_BASE_URL}/api/brokers/upstox/callback"
    state = user.id
    url = f"{UPSTOX_OAUTH_BASE}?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}&state={state}"
    return {"login_url": url, "expected_redirect_url": redirect_uri,
            "note": "Set this exact Redirect URL in your Upstox developer console."}


@router.get("/upstox/callback")
async def upstox_callback(code: str = Query(...), state: str = Query("")):
    import httpx
    if not state:
        raise HTTPException(status_code=400, detail="state (user_id) missing in callback.")
    doc = await db.broker_connections.find_one({"user_id": state, "broker": "upstox"})
    if not doc:
        raise HTTPException(status_code=404, detail="No Upstox connection record.")
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    api_secret = decrypt_str(creds.get("api_secret", ""))
    redirect_uri = f"{APP_BASE_URL}/api/brokers/upstox/callback"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={
                "code": code, "client_id": api_key, "client_secret": api_secret,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code",
            },
            headers={"accept": "application/json",
                     "Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400,
                                detail=f"Upstox token exchange failed: {resp.text[:200]}")
        data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Upstox returned no access_token.")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.broker_connections.update_one(
        {"_id": doc["_id"]},
        {"$set": {"access_token": encrypt_str(access_token),
                  "session_date": today, "mock_mode": False, "connected": True}},
    )
    return RedirectResponse(url=f"{APP_BASE_URL}/brokers?upstox=connected", status_code=302)


# ---- Alice Blue OAuth ----

@router.get("/aliceblue/login-url")
async def aliceblue_login_url(user: User = Depends(get_current_user)):
    doc = await db.broker_connections.find_one({"user_id": user.id, "broker": "aliceblue"})
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Alice Blue credentials first.")
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    if not api_key:
        raise HTTPException(status_code=400, detail="Alice Blue API key (App Code) missing.")
    url = f"https://ant.aliceblueonline.com/?appcode={api_key}"
    return {"login_url": url,
            "note": "Login with your Alice Blue credentials, then you will be redirected back."}


@router.get("/aliceblue/callback")
async def aliceblue_callback(
    authCode: str = Query(...),
    userId: str = Query(...),
    appcode: str = Query(default=""),
):
    import httpx
    import hashlib
    import os

    print(f"[AliceBlue Callback] userId={userId} authCode={authCode[:8]}... appcode={appcode}")

    doc = None
    is_trader = True
    api_key_dec = ""
    api_secret = ""

    # --- Trader lookup: prefer appcode (api_key) match, fallback to userId ---
    async for conn in db.broker_connections.find({"broker": "aliceblue"}):
        creds = conn.get("credentials") or {}
        conn_api_key = decrypt_str(creds.get("api_key", ""))
        conn_user_id = decrypt_str(creds.get("user_id", ""))
        # Match by appcode (api_key) if provided, otherwise match by userId
        if appcode and conn_api_key == appcode:
            doc = conn
            api_key_dec = conn_api_key
            api_secret = decrypt_str(creds.get("api_secret", ""))
            break
        elif not appcode and conn_user_id == userId:
            doc = conn
            api_key_dec = conn_api_key
            api_secret = decrypt_str(creds.get("api_secret", ""))
            break

    matched_mu_b = None
    matched_idx = -1
    if not doc:
        is_trader = False
        async for mu in db.managed_users.find():
            brokers = mu.get("brokers", [])
            for idx, b in enumerate(brokers):
                if "alice" in b.get("broker", "").lower():
                    creds = b.get("credentials") or {}
                    b_api_key = creds.get("api_key", b.get("api_key", ""))
                    b_user_id = creds.get("user_id") or creds.get("client_code") or b.get("account_number", "")
                    if (appcode and b_api_key == appcode) or (not appcode and b_user_id == userId):
                        doc = mu
                        matched_mu_b = b
                        matched_idx = idx
                        api_secret = creds.get("api_secret") or b.get("api_secret", "")
                        break
            if doc:
                break

    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"No Alice Blue connection found. userId={userId} appcode={appcode}. Please check that the API Key / App Code saved in Brokers matches what Alice Blue is using."
        )

    if not api_secret:
        raise HTTPException(
            status_code=400,
            detail="Alice Blue API Secret is missing or empty. Please re-save your broker credentials with the correct API Secret."
        )

    raw_str = f"{userId.strip()}{authCode.strip()}{api_secret.strip()}"
    checksum = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
    print(f"[AliceBlue Callback] Checksum computed. userId={userId}, secret_len={len(api_secret)}")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://a3.aliceblueonline.com/open-api/od/v1/vendor/getUserDetails",
            json={"checkSum": checksum}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Alice Blue token exchange failed: {resp.text[:300]}")
        data = resp.json()

    if data.get("stat") != "Ok":
        emsg = data.get("emsg", "Unknown")
        print(f"[AliceBlue Callback] Error from Alice Blue: {emsg}. Raw: {data}")
        raise HTTPException(
            status_code=400,
            detail=f"Alice Blue authentication failed: {emsg}. Please ensure your API Secret in Brokers settings is correct."
        )

    userSession = data.get("userSession") or data.get("sessionID")
    if not userSession:
        raise HTTPException(status_code=400, detail=f"Alice Blue returned no userSession. Raw: {data}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")

    if is_trader:
        await db.broker_connections.update_one(
            {"_id": doc["_id"]},
            {"$set": {"access_token": encrypt_str(userSession),
                      "session_date": today, "mock_mode": False, "connected": True}},
        )
        print(f"[AliceBlue Callback] Trader session saved for userId={userId}")
        return RedirectResponse(url=f"{APP_BASE_URL}/brokers?aliceblue=connected", status_code=302)
    else:
        brokers = doc.get("brokers", [])
        brokers[matched_idx]["session_token"] = userSession
        brokers[matched_idx]["session_generated"] = True
        brokers[matched_idx]["session_date"] = today
        await db.managed_users.update_one(
            {"_id": doc["_id"]},
            {"$set": {"brokers": brokers}}
        )
        print(f"[AliceBlue Callback] Managed user session saved for userId={userId}")
        return RedirectResponse(url=f"{APP_BASE_URL}/user-dashboard?aliceblue=connected", status_code=302)

@router.post("/aliceblue/login")
async def aliceblue_login_programmatic(user: User = Depends(get_current_user)):
    """Trigger Alice Blue programmatic login bypassing the web redirect."""
    doc = await db.broker_connections.find_one({"user_id": user.id, "broker": "aliceblue"})
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Alice Blue credentials first.")
    
    creds = doc.get("credentials") or {}
    api_key = decrypt_str(creds.get("api_key", ""))
    client_code = decrypt_str(creds.get("user_id", ""))
    
    if not api_key or not client_code:
        raise HTTPException(status_code=400, detail="Alice Blue API key or Client ID missing.")
    
    try:
        from pya3 import Aliceblue
        alice = Aliceblue(user_id=client_code, api_key=api_key)
        res = alice.get_session_id()
        if res.get('stat') != 'Ok':
            raise Exception(res.get('emsg', 'Unknown error'))
        session_id = res['sessionID']
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Alice Blue programmatic login failed: {e}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.broker_connections.update_one(
        {"_id": doc["_id"]},
        {"$set": {"access_token": encrypt_str(session_id),
                  "session_date": today, "mock_mode": False, "connected": True}},
    )
    from services.live_feed_manager import live_feed_manager
    await live_feed_manager.force_reconnect()
    return {"ok": True, "session_date": today}


# ---------- Alice Blue Order Management APIs ----------

async def _get_aliceblue_client(user: User) -> "AliceBlueClient":
    from services.brokers.aliceblue_client import get_user_aliceblue_client
    client = await get_user_aliceblue_client(db, user.id)
    if not client:
        raise HTTPException(status_code=400, detail="Alice Blue broker not configured or session expired")
    return client

@router.get("/aliceblue/orders")
async def get_aliceblue_orders(user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.get_order_book()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/aliceblue/orders/{brokerOrderId}/history")
async def get_aliceblue_order_history(brokerOrderId: str, user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.get_order_history(brokerOrderId)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/aliceblue/orders/{brokerOrderId}")
async def modify_aliceblue_order(brokerOrderId: str, payload: dict, user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.modify_order(
            broker_order_id=brokerOrderId,
            transaction_type=payload.get("transactionType", "BUY"),
            instrument_token=payload.get("instrumentToken", ""),
            product=payload.get("product", "I"),
            order_type=payload.get("orderType", "MARKET"),
            quantity=int(payload.get("quantity", 0)),
            price=float(payload.get("price", 0.0)),
            trigger_price=float(payload.get("triggerPrice", 0.0))
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/aliceblue/orders/{brokerOrderId}")
async def cancel_aliceblue_order(brokerOrderId: str, user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.cancel_order(brokerOrderId)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/aliceblue/trades")
async def get_aliceblue_trade_book(user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.get_trade_book()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/aliceblue/margin")
async def get_aliceblue_basket_margin(orders: list = Body(...), user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.get_basket_margin(orders)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/aliceblue/orders/{brokerOrderId}/exit-bo")
async def exit_aliceblue_bracket_order(brokerOrderId: str, payload: dict, user: User = Depends(get_current_user)):
    client = await _get_aliceblue_client(user)
    try:
        return client.exit_bracket_order(
            broker_order_id=brokerOrderId,
            symbol_order_id=payload.get("symbolOrderId", "NA"),
            status=payload.get("status", "open")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/profile")
async def get_profile(user_id: str = None, user: User = Depends(get_current_user)):
    target_user_id = user_id if user_id else user.id
    
    if user.role == "managed_user" or target_user_id != user.id:
        if target_user_id != user.id:
            managed = await db.managed_users.find_one({"_id": target_user_id, "trader_id": user.id})
            if not managed:
                raise HTTPException(403, "Not authorized to view this user")
        else:
            managed = await db.managed_users.find_one({"_id": target_user_id})
            
        if managed:
            alice_broker = next((b for b in managed.get("brokers", []) if "alice" in b.get("broker", "").lower()), None)
            if alice_broker and alice_broker.get("session_token"):
                from pya3 import Aliceblue
                creds = alice_broker.get("credentials") or {}
                user_id_val = creds.get("user_id") or alice_broker.get("account_number")
                api_key = creds.get("api_key") or alice_broker.get("api_key")
                client = Aliceblue(user_id=user_id_val, api_key=api_key, session_id=alice_broker.get("session_token"))
                try:
                    return {"broker": "aliceblue", "profile": client.get_profile()}
                except Exception as e:
                    return {"error": str(e)}
            
            breeze_broker = next((b for b in managed.get("brokers", []) if "icici" in b.get("broker", "").lower()), None)
            if breeze_broker and breeze_broker.get("session_token"):
                try:
                    from services.brokers.breeze_client import BreezeClient
                    creds = breeze_broker.get("credentials") or {}
                    api_key = creds.get("api_key") or breeze_broker.get("api_key")
                    secret_key = creds.get("api_secret") or breeze_broker.get("api_secret")
                    session_token = breeze_broker.get("session_token")
                    client = BreezeClient(api_key=api_key, secret_key=secret_key, session_token=session_token)
                    if client._session_ok:
                        return {"broker": "icici", "profile": client._b.get_customer_details()}
                except Exception as e:
                    return {"error": str(e)}
                    
        return {"error": "No broker configured or session token missing."}
            
    doc = await db.broker_connections.find_one({"user_id": target_user_id, "is_order_exec": True})
    if not doc:
        return {"error": "No execution broker configured."}
        
    from services.broker_router import get_broker_profile
    profile = await get_broker_profile(db, target_user_id, doc["broker"])
    return {"broker": doc["broker"], "profile": profile}

@router.get("/funds")
async def get_funds(user_id: str = None, user: User = Depends(get_current_user)):
    target_user_id = user_id if user_id else user.id
    
    if user.role == "managed_user" or target_user_id != user.id:
        if target_user_id != user.id:
            managed = await db.managed_users.find_one({"_id": target_user_id, "trader_id": user.id})
            if not managed:
                raise HTTPException(403, "Not authorized to view this user")
        else:
            managed = await db.managed_users.find_one({"_id": target_user_id})
            
        if managed:
            alice_broker = next((b for b in managed.get("brokers", []) if "alice" in b.get("broker", "").lower()), None)
            if alice_broker and alice_broker.get("session_token"):
                from pya3 import Aliceblue
                creds = alice_broker.get("credentials") or {}
                user_id_val = creds.get("user_id") or alice_broker.get("account_number")
                api_key = creds.get("api_key") or alice_broker.get("api_key")
                client = Aliceblue(user_id=user_id_val, api_key=api_key, session_id=alice_broker.get("session_token"))
                try:
                    return {"broker": "aliceblue", "funds": client.get_balance()}
                except Exception as e:
                    return {"error": str(e)}
            
            breeze_broker = next((b for b in managed.get("brokers", []) if "icici" in b.get("broker", "").lower()), None)
            if breeze_broker and breeze_broker.get("session_token"):
                try:
                    from services.brokers.breeze_client import BreezeClient
                    creds = breeze_broker.get("credentials") or {}
                    api_key = creds.get("api_key") or breeze_broker.get("api_key")
                    secret_key = creds.get("api_secret") or breeze_broker.get("api_secret")
                    session_token = breeze_broker.get("session_token")
                    client = BreezeClient(api_key=api_key, secret_key=secret_key, session_token=session_token)
                    if client._session_ok:
                        return {"broker": "icici", "funds": client._b.get_funds()}
                except Exception as e:
                    return {"error": str(e)}
                    
        return {"error": "No broker configured or session token missing."}
            
    doc = await db.broker_connections.find_one({"user_id": target_user_id, "is_order_exec": True})
    if not doc:
        return {"error": "No execution broker configured."}
        
    from services.broker_router import get_broker_funds
    funds = await get_broker_funds(db, target_user_id, doc["broker"])
    return {"broker": doc["broker"], "funds": funds}


@router.get("/aliceblue/history/{symbol}")
async def aliceblue_history(
    symbol: str,
    from_datetime: str = Query(...),
    to_datetime: str = Query(...),
    interval: str = Query("1"),
    user: User = Depends(get_current_user)
):
    from services.brokers.aliceblue_client import get_user_aliceblue_client
    import datetime

    client = await get_user_aliceblue_client(db, user.id)
    if not client:
        # Check if they are a managed user
        managed = await db.managed_users.find_one({"_id": user.id})
        if managed:
            alice_broker = next((b for b in managed.get("brokers", []) if "alice" in b.get("broker", "").lower()), None)
            if alice_broker and alice_broker.get("session_token"):
                from pya3 import Aliceblue
                from services.brokers.aliceblue_client import AliceBlueClient
                creds = alice_broker.get("credentials") or {}
                user_id_val = creds.get("user_id") or alice_broker.get("account_number")
                api_key = creds.get("api_key") or alice_broker.get("api_key")
                client = AliceBlueClient(client_code=user_id_val, api_key=api_key, session_id=alice_broker.get("session_token"))
        
    if not client:
        raise HTTPException(status_code=400, detail="Aliceblue client not connected.")
        
    try:
        from_dt = datetime.datetime.fromisoformat(from_datetime.replace('Z', '+00:00'))
        to_dt = datetime.datetime.fromisoformat(to_datetime.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format.")
        
    try:
        # User provided API documentation:
        # POST {{BASE_URL}}open-api/od/ChartAPIService/api/chart/history
        # Body: { "token": "1594", "resolution": "1", "from": "1660128489000", "to": "1660221861000", "exchange": "NSE" }
        import httpx
        
        # Determine exchange and token
        if "|" in symbol:
            exchange, token = symbol.split("|", 1)
        else:
            exchange, token = "NSE", symbol
            
        # Try to resolve symbol to token if it's not numeric
        if not token.isdigit():
            resolved = False
            try:
                # Try pya3's built-in resolution first
                instrument = client._alice.get_instrument_by_symbol(exchange, f"{token}-EQ" if exchange == "NSE" and not token.endswith("-EQ") else token)
                token = str(instrument.token)
                resolved = True
            except Exception:
                pass
                
            # Fallback to reading the CSV directly (pya3 has a bug in some versions that throws 'module' object is not callable)
            if not resolved:
                import csv
                import os
                csv_path = os.path.join(os.getcwd(), f"{exchange}.csv")
                if os.path.exists(csv_path):
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        target = f"{token}-EQ" if exchange == "NSE" and not token.endswith("-EQ") else token
                        for row in reader:
                            if row.get('Symbol') == token or row.get('Trading Symbol') == target:
                                token = str(row.get('Token'))
                                break

        from_ts = str(int(from_dt.timestamp() * 1000))
        to_ts = str(int(to_dt.timestamp() * 1000))
        
        payload = {
            "token": token,
            "resolution": interval,
            "from": from_ts,
            "to": to_ts,
            "exchange": exchange
        }

        # Aliceblue base URL for history
        url = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/chart/history"
        headers = {
            "X-SAS-Version": "2.0",
            "Authorization": f"Bearer {client._alice.user_id} {client._alice.session_id}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as c:
            resp = await c.post(url, headers=headers, json=payload)
            
            try:
                data = resp.json()
            except Exception:
                raise HTTPException(status_code=400, detail=f"AliceBlue API failed (Status {resp.status_code}). Please try again after 5:30 PM.")
                
            if "stat" in data and data["stat"] == "Not_Ok":
                raise HTTPException(status_code=400, detail=data.get("emsg", "Failed to load AliceBlue historical data"))
                
            return {"symbol": symbol, "rows": data.get("result", [])}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
