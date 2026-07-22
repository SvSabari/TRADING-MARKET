"""Broker connection management — generic schema-driven UX."""
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
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
    if body.is_data_feed:
        await db.broker_connections.update_many(
            {"user_id": user.id, "broker": {"$ne": body.broker}},
            {"$set": {"is_data_feed": False}}
        )
    # Same for order execution
    if body.is_order_exec:
        await db.broker_connections.update_many(
            {"user_id": user.id, "broker": {"$ne": body.broker}},
            {"$set": {"is_order_exec": False}}
        )

    if existing:
        await db.broker_connections.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "api_key": api_key_enc,
                "api_secret": api_secret_enc,
                "credentials": merged_creds,
                "is_data_feed": body.is_data_feed,
                "is_order_exec": body.is_order_exec,
                "mock_mode": body.mock_mode,
                "connected": connected,
            }},
        )
        from services.live_feed_manager import live_feed_manager
        await live_feed_manager.force_reconnect()
        d = await db.broker_connections.find_one({"_id": existing["_id"]})
        return _to_public(BrokerConnection.from_mongo(d)).model_dump()
    conn = BrokerConnection(
        user_id=user.id, broker=body.broker,
        api_key=api_key_enc, api_secret=api_secret_enc,
        credentials=merged_creds,
        is_data_feed=body.is_data_feed,
        is_order_exec=body.is_order_exec,
        mock_mode=body.mock_mode, connected=connected,
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
async def aliceblue_callback(authCode: str = Query(...), userId: str = Query(...)):
    import httpx
    import hashlib
    # Find the user's connection by userId (since state is not passed in the URL by Aliceblue)
    # We will search across all connections to find one matching this userId.
    doc = None
    async for conn in db.broker_connections.find({"broker": "aliceblue"}):
        creds = conn.get("credentials") or {}
        if decrypt_str(creds.get("user_id", "")) == userId:
            doc = conn
            break
    
    if not doc:
        raise HTTPException(status_code=404, detail="No Alice Blue connection record found for this userId.")
        
    creds = doc.get("credentials") or {}
    api_secret = decrypt_str(creds.get("api_secret", ""))
    
    # Checksum: userId + authCode + apiSecret
    raw_str = f"{userId.strip()}{authCode.strip()}{api_secret.strip()}"
    checksum = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
    
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://a3.aliceblueonline.com/open-api/od/v1/vendor/getUserDetails",
            json={"checkSum": checksum}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Alice Blue token exchange failed: {resp.text[:200]}")
        data = resp.json()
        
    if data.get("stat") != "Ok":
        raise HTTPException(status_code=400, detail=f"Alice Blue error: {data.get('emsg', 'Unknown')}")
        
    userSession = data.get("userSession") or data.get("sessionID")
    if not userSession:
        raise HTTPException(status_code=400, detail=f"Alice Blue returned no userSession. Raw data: {data}")
        
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.broker_connections.update_one(
        {"_id": doc["_id"]},
        {"$set": {"access_token": encrypt_str(userSession),
                  "session_date": today, "mock_mode": False, "connected": True}},
    )
    return RedirectResponse(url=f"{APP_BASE_URL}/brokers?aliceblue=connected", status_code=302)
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
