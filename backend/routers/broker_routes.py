"""Broker connection management — generic schema-driven UX with SQLAlchemy async."""
import csv
import datetime as dt_module
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from auth import get_current_user
from constants import BROKERS
from db import get_db
from models import BrokerConnection, User, ManagedUser
from schemas import BrokerConnectionPublic, BrokerConnectionUpsert
from services.broker_schemas import BROKER_SCHEMAS
from services.crypto import decrypt_str, encrypt_str
from services.kite_client import KiteService

router = APIRouter(prefix="/brokers", tags=["brokers"])

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3000")

# all brokers exposed (mock route is always available + the explicit list)
ALL_BROKERS = list(BROKER_SCHEMAS.keys())


def _to_public(b: BrokerConnection) -> BrokerConnectionPublic:
    creds = b.credentials or {}
    api_key = creds.get("api_key") or getattr(b, "api_key", None)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    has_token = bool(b.access_token)
    session_date = b.session_date or ""
    
    if not has_token or not session_date:
        session_status = "not_generated"
    elif session_date != today:
        session_status = "expired"
    else:
        session_status = "active"

    error_msg = None
    if not b.connected and (has_token or bool(api_key) or any(creds.values()) or b.is_data_feed or b.is_order_exec):
        if session_status == "not_generated":
            error_msg = "Daily session not generated"
        elif session_status == "expired":
            error_msg = f"Session expired on {session_date}"
        else:
            error_msg = "Broker disconnected"

    return BrokerConnectionPublic(
        id=str(b.id),
        broker=str(b.broker),
        connected=bool(b.connected and session_status == "active"),
        is_data_feed=bool(b.is_data_feed),
        is_order_exec=bool(b.is_order_exec),
        mock_mode=bool(b.mock_mode) if b.mock_mode is not None else True,
        has_keys=bool(api_key) or any(creds.values()),
        has_access_token=has_token,
        session_date=session_date,
        session_status=session_status,
        last_error=error_msg,
        fields_filled=sorted([k for k, v in creds.items() if v]),
    )


@router.get("/schemas")
async def broker_schemas(user: User = Depends(get_current_user)):
    """Field schemas describing what each broker needs."""
    return {"schemas": BROKER_SCHEMAS, "brokers": ALL_BROKERS}


@router.get("")
async def list_connections(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(BrokerConnection).where(BrokerConnection.user_id == user.id)
    result = await session.execute(stmt)
    conns = result.scalars().all()
    out = [_to_public(c).model_dump() for c in conns]
    return {"connections": out, "available": ALL_BROKERS, "schemas": BROKER_SCHEMAS}


@router.post("/auto-renew")
async def trigger_auto_renew(
    user: User = Depends(get_current_user),
):
    """Manually trigger daily session auto-renewal for all configured brokers."""
    from services.auto_session_manager import renew_all_sessions
    summary = await renew_all_sessions(force=True)
    return summary


@router.get("/auto-renew/status")
async def get_auto_renew_status(
    user: User = Depends(get_current_user),
):
    """Get the current status of the morning auto-session renewal scheduler."""
    from services.auto_session_manager import auto_session_scheduler, get_ist_now, get_today_str
    now_ist = get_ist_now()
    return {
        "scheduler_running": auto_session_scheduler.running,
        "last_run_date": auto_session_scheduler.last_run_date,
        "current_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "scheduled_time": "08:30:00 IST (Mon-Fri)",
        "today": get_today_str(),
    }


@router.post("")
async def upsert(
    body: BrokerConnectionUpsert,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    if body.broker not in ALL_BROKERS:
        raise HTTPException(status_code=400, detail="Unknown broker")

    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == body.broker
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    # Encrypt any new credential values; keep existing for blank fields
    incoming_creds: Dict[str, Any] = dict(body.credentials or {})
    if body.api_key:
        incoming_creds.setdefault("api_key", body.api_key)
    if body.api_secret:
        incoming_creds.setdefault("api_secret", body.api_secret)

    existing_creds = existing.credentials if (existing and existing.credentials) else {}
    merged_creds: Dict[str, str] = {**(existing_creds or {})}
    for k, v in incoming_creds.items():
        if v not in (None, "", False):
            merged_creds[k] = encrypt_str(str(v))

    api_key_enc = merged_creds.get("api_key", "")
    has_creds = bool(api_key_enc or any(merged_creds.values()))

    # Enforce exclusivity: if this broker is set to be the data feed, un-set all others
    if body.is_data_feed is True:
        await session.execute(
            update(BrokerConnection)
            .where(
                BrokerConnection.user_id == user.id,
                BrokerConnection.broker != body.broker
            )
            .values(is_data_feed=False)
        )
    # Same for order execution
    if body.is_order_exec is True:
        await session.execute(
            update(BrokerConnection)
            .where(
                BrokerConnection.user_id == user.id,
                BrokerConnection.broker != body.broker
            )
            .values(is_order_exec=False)
        )

    if existing:
        existing.credentials = merged_creds
        flag_modified(existing, "credentials")
        # Preserve OAuth-established connected state + access_token.
        # Only mark connected=True if credentials exist; never downgrade an
        # already-OAuth-connected session just because the user hit Save again.
        if existing.connected and existing.access_token:
            # Already OAuth-connected — keep it connected
            pass
        else:
            existing.connected = has_creds or bool(body.mock_mode)
        if body.is_data_feed is not None:
            existing.is_data_feed = body.is_data_feed
        if body.is_order_exec is not None:
            existing.is_order_exec = body.is_order_exec
        if body.mock_mode is not None:
            existing.mock_mode = body.mock_mode

        await session.commit()
        await session.refresh(existing)
        from services.live_feed_manager import live_feed_manager
        await live_feed_manager.force_reconnect()
        return _to_public(existing).model_dump()

    conn = BrokerConnection(
        id=str(uuid.uuid4()),
        user_id=user.id,
        broker=body.broker,
        credentials=merged_creds,
        is_data_feed=body.is_data_feed if body.is_data_feed is not None else False,
        is_order_exec=body.is_order_exec if body.is_order_exec is not None else False,
        mock_mode=body.mock_mode if body.mock_mode is not None else True,
        connected=has_creds or bool(body.mock_mode),
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    from services.live_feed_manager import live_feed_manager
    await live_feed_manager.force_reconnect()
    return _to_public(conn).model_dump()


@router.delete("/{broker}")
async def disconnect(
    broker: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == broker
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        return {"deleted": 0}

    was_primary = bool(doc.is_data_feed)
    was_secondary = bool(doc.is_order_exec)

    await session.delete(doc)
    await session.commit()

    # Auto-fallback for primary: pick a connected broker that is NOT the secondary and NOT mock
    if was_primary:
        fb_stmt = select(BrokerConnection).where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.connected == True,
            BrokerConnection.broker != "mock",
            BrokerConnection.is_order_exec != True
        ).limit(1)
        fb_res = await session.execute(fb_stmt)
        fallback = fb_res.scalar_one_or_none()
        if fallback:
            fallback.is_data_feed = True
            await session.commit()

    # Auto-fallback for secondary: pick a connected broker that is NOT the primary
    if was_secondary:
        fb_stmt = select(BrokerConnection).where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.connected == True,
            BrokerConnection.is_data_feed != True
        ).limit(1)
        fb_res = await session.execute(fb_stmt)
        fallback = fb_res.scalar_one_or_none()
        if fallback:
            fallback.is_order_exec = True
            await session.commit()

    from services.live_feed_manager import live_feed_manager
    await live_feed_manager.force_reconnect()
    return {"deleted": 1}


# ---- Zerodha Kite OAuth (only broker with redirect today) ----

@router.get("/kite/login-url")
async def kite_login_url(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "zerodha"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit() if doc else {}
    api_key_enc = creds.get("api_key") or getattr(doc, "api_key", "")
    if not doc or not api_key_enc:
        raise HTTPException(status_code=400, detail="Save your Kite API key + secret first (mock_mode off).")
    api_key = decrypt_str(api_key_enc)
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
async def kite_callback(
    request_token: str = Query(...),
    status: str = Query("success"),
    redirect_params: str = Query(""),
    session: AsyncSession = Depends(get_db)
):
    user_id = ""
    for pair in (redirect_params or "").split("&"):
        k, _, v = pair.partition("=")
        if k == "user_id":
            user_id = v
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id missing in redirect_params")

    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user_id,
        BrokerConnection.broker == "zerodha"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="No Kite connection record")

    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit()
    api_key_enc = creds.get("api_key") or getattr(doc, "api_key", "")
    api_secret_enc = creds.get("api_secret") or getattr(doc, "api_secret", "")
    api_key = decrypt_str(api_key_enc)
    api_secret = decrypt_str(api_secret_enc) if api_secret_enc else ""

    svc = KiteService(api_key=api_key)
    try:
        data = svc.generate_session(request_token=request_token, api_secret=api_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Kite session exchange failed — invalid or expired request token")

    today_ist = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc.access_token = encrypt_str(data["access_token"])
    doc.session_date = today_ist
    doc.mock_mode = False
    doc.connected = True
    await session.commit()

    return RedirectResponse(url=f"{APP_BASE_URL}/brokers?kite=connected", status_code=302)


@router.post("/kite/disconnect")
async def kite_disconnect(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        update(BrokerConnection)
        .where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.broker == "zerodha"
        )
        .values(
            access_token="",
            session_date="",
            mock_mode=True,
            connected=False
        )
    )
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}


# ---- Angel One — TOTP-based login (no external redirect) ----

@router.post("/angel/login")
async def angel_login(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Trigger Angel TOTP login. Uses creds the user already saved.

    Stores the returned `auth_token` + `feed_token` (encrypted) so the
    live WebSocket feed + order placement can use them for the session.
    """
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "angel"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Angel credentials first.")

    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit()
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
    new_creds = {
        **creds,
        "auth_token": encrypt_str(tokens["auth_token"]),
        "refresh_token": encrypt_str(tokens.get("refresh_token", "")),
        "feed_token": encrypt_str(tokens.get("feed_token", ""))
    }
    doc.credentials = new_creds
    doc.session_date = today_ist
    doc.mock_mode = False
    doc.connected = True
    doc.access_token = encrypt_str(tokens["auth_token"])
    await session.commit()
    return {"ok": True, "session_date": today_ist}


# ---- Upstox OAuth ----

UPSTOX_OAUTH_BASE = "https://api.upstox.com/v2/login/authorization/dialog"


@router.get("/upstox/login-url")
async def upstox_login_url(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "upstox"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Upstox API key + secret first.")

    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit()
    api_key = decrypt_str(creds.get("api_key", ""))
    if not api_key:
        raise HTTPException(status_code=400, detail="Upstox API key missing.")

    redirect_uri = f"{APP_BASE_URL}/api/brokers/upstox/callback"
    state = user.id
    url = f"{UPSTOX_OAUTH_BASE}?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}&state={state}"
    return {
        "login_url": url,
        "expected_redirect_url": redirect_uri,
        "note": "Set this exact Redirect URL in your Upstox developer console."
    }


@router.get("/upstox/callback")
async def upstox_callback(
    code: str = Query(...),
    state: str = Query(""),
    session: AsyncSession = Depends(get_db)
):
    import httpx
    if not state:
        raise HTTPException(status_code=400, detail="state (user_id) missing in callback.")

    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == state,
        BrokerConnection.broker == "upstox"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="No Upstox connection record.")

    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit()
    api_key = decrypt_str(creds.get("api_key", ""))
    api_secret = decrypt_str(creds.get("api_secret", ""))
    redirect_uri = f"{APP_BASE_URL}/api/brokers/upstox/callback"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={
                "code": code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={
                "accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Upstox token exchange failed: {resp.text[:200]}")
        data = resp.json()

    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Upstox returned no access_token.")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc.access_token = encrypt_str(access_token)
    doc.session_date = today
    doc.mock_mode = False
    doc.connected = True
    await session.commit()

    return RedirectResponse(url=f"{APP_BASE_URL}/brokers?upstox=connected", status_code=302)


# ---- Alice Blue OAuth ----

@router.get("/aliceblue/login-url")
async def aliceblue_login_url(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "aliceblue"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Alice Blue credentials first.")

    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit()
    api_key = decrypt_str(creds.get("api_key", ""))
    if not api_key:
        raise HTTPException(status_code=400, detail="Alice Blue API key (App Code) missing.")

    url = f"https://ant.aliceblueonline.com/?appcode={api_key}"
    return {
        "login_url": url,
        "note": "Login with your Alice Blue credentials, then you will be redirected back."
    }


@router.get("/aliceblue/callback")
async def aliceblue_callback(
    authCode: str = Query(...),
    userId: str = Query(...),
    appcode: str = Query(default=""),
    session: AsyncSession = Depends(get_db)
):
    import hashlib
    import httpx
    import os

    print(f"[AliceBlue Callback] userId={userId} authCode={authCode[:8]}... appcode={appcode}")

    target_conn: Optional[BrokerConnection] = None
    target_mu: Optional[ManagedUser] = None
    is_trader = True
    api_key_dec = ""
    api_secret = ""

    # --- Trader lookup: prefer appcode (api_key) match, fallback to userId ---
    res = await session.execute(
        select(BrokerConnection).where(BrokerConnection.broker == "aliceblue")
    )
    connections = res.scalars().all()
    for conn in connections:
        creds = conn.credentials or {}
        conn_api_key = decrypt_str(creds.get("api_key", ""))
        conn_user_id = decrypt_str(creds.get("user_id", ""))
        # Match by appcode (api_key) if provided, otherwise match by userId
        if appcode and conn_api_key == appcode:
            target_conn = conn
            api_key_dec = conn_api_key
            api_secret = decrypt_str(creds.get("api_secret", ""))
            break
        elif not appcode and conn_user_id == userId:
            target_conn = conn
            api_key_dec = conn_api_key
            api_secret = decrypt_str(creds.get("api_secret", ""))
            break

    matched_idx = -1
    if not target_conn:
        is_trader = False
        mu_res = await session.execute(select(ManagedUser))
        managed_users = mu_res.scalars().all()
        for mu in managed_users:
            brokers = list(mu.brokers or [])
            for idx, b in enumerate(brokers):
                b_dict = b if isinstance(b, dict) else (b.__dict__ if hasattr(b, "__dict__") else {})
                if "alice" in str(b_dict.get("broker", "")).lower():
                    creds = b_dict.get("credentials") or {}
                    b_api_key = creds.get("api_key", b_dict.get("api_key", ""))
                    b_user_id = creds.get("user_id") or creds.get("client_code") or b_dict.get("account_number", "")
                    if (appcode and b_api_key == appcode) or (not appcode and b_user_id == userId):
                        target_mu = mu
                        matched_idx = idx
                        api_secret = creds.get("api_secret") or b_dict.get("api_secret", "")
                        break
            if target_mu:
                break

    if not target_conn and not target_mu:
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

    print('DEBUG_PAYLOAD: ', data)
    userSession = data.get("userSession") or data.get("sessionID")
    if not userSession:
        raise HTTPException(status_code=400, detail=f"Alice Blue returned no userSession. Raw: {data}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_url = os.getenv("APP_BASE_URL", APP_BASE_URL)

    if is_trader and target_conn:
        target_conn.access_token = encrypt_str(userSession)
        target_conn.session_date = today
        target_conn.mock_mode = False
        target_conn.connected = True
        await session.commit()
        print(f"[AliceBlue Callback] Trader session saved for userId={userId}")
        try:
            from services.live_feed_manager import live_feed_manager
            await live_feed_manager.force_reconnect()
            print("[AliceBlue Callback] Live feed manager force-reconnected with new token")
        except Exception as e:
            print(f"[AliceBlue Callback] force_reconnect failed: {e}")
        return RedirectResponse(url=f"{base_url}/brokers?aliceblue=connected", status_code=302)
    elif target_mu:
        brokers = list(target_mu.brokers or [])
        updated_broker = dict(brokers[matched_idx])
        updated_broker["session_token"] = userSession
        updated_broker["session_generated"] = True
        updated_broker["session_date"] = today
        brokers[matched_idx] = updated_broker
        target_mu.brokers = brokers
        flag_modified(target_mu, "brokers")
        await session.commit()
        print(f"[AliceBlue Callback] Managed user session saved for userId={userId}")
        return RedirectResponse(url=f"{base_url}/user-dashboard?aliceblue=connected", status_code=302)


@router.post("/aliceblue/login")
async def aliceblue_login_programmatic(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Trigger Alice Blue programmatic login bypassing the web redirect."""
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "aliceblue"
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=400, detail="Save your Alice Blue credentials first.")

    creds = doc.credentials or {}
    doc.access_token = ''
    doc.session_date = ''
    doc.connected = False
    await session.commit()
    api_key = decrypt_str(creds.get("api_key", ""))
    client_code = decrypt_str(creds.get("user_id", ""))

    if not api_key or not client_code:
        raise HTTPException(status_code=400, detail="Alice Blue API key or Client ID missing.")

    try:
        from pya3 import Aliceblue
        alice = Aliceblue(user_id=client_code, api_key=api_key)
        res = alice.get_session_id()
        if res.get("stat") != "Ok":
            raise Exception(res.get("emsg", "Unknown error"))
        session_id = res["sessionID"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Alice Blue programmatic login failed: {e}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc.access_token = encrypt_str(session_id)
    doc.session_date = today
    doc.mock_mode = False
    doc.connected = True
    await session.commit()

    from services.live_feed_manager import live_feed_manager
    await live_feed_manager.force_reconnect()
    return {"ok": True, "session_date": today}


# ---------- Alice Blue Order Management APIs ----------

async def _get_aliceblue_client(user: User, session: AsyncSession):
    from services.brokers.aliceblue_client import AliceBlueClient
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "aliceblue"
    )
    result = await session.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn or not conn.access_token:
        raise HTTPException(status_code=400, detail="Alice Blue broker not configured or session expired")
    try:
        session_id = decrypt_str(conn.access_token)
        creds = conn.credentials or {}
        user_id_val = decrypt_str(creds.get("user_id", ""))
        api_key_val = decrypt_str(creds.get("api_key", ""))
        return AliceBlueClient(
            client_code=user_id_val,
            api_key=api_key_val,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Alice Blue initialization failed: {e}")


@router.get("/aliceblue/orders")
async def get_aliceblue_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
    try:
        return client.get_order_book()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/aliceblue/orders/{brokerOrderId}/history")
async def get_aliceblue_order_history(
    brokerOrderId: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
    try:
        return client.get_order_history(brokerOrderId)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/aliceblue/orders/{brokerOrderId}")
async def modify_aliceblue_order(
    brokerOrderId: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
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
async def cancel_aliceblue_order(
    brokerOrderId: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
    try:
        return client.cancel_order(brokerOrderId)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/aliceblue/trades")
async def get_aliceblue_trade_book(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
    try:
        return client.get_trade_book()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/aliceblue/margin")
async def get_aliceblue_basket_margin(
    orders: list = Body(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
    try:
        return client.get_basket_margin(orders)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/aliceblue/orders/{brokerOrderId}/exit-bo")
async def exit_aliceblue_bracket_order(
    brokerOrderId: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    client = await _get_aliceblue_client(user, session)
    try:
        return client.exit_bracket_order(
            broker_order_id=brokerOrderId,
            symbol_order_id=payload.get("symbolOrderId", "NA"),
            status=payload.get("status", "open")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/profile")
async def get_profile(
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    target_user_id = user_id if user_id else user.id

    if user.role == "managed_user" or target_user_id != user.id:
        if target_user_id != user.id:
            stmt = select(ManagedUser).where(
                ManagedUser.id == target_user_id,
                ManagedUser.trader_id == user.id
            )
            res = await session.execute(stmt)
            managed = res.scalar_one_or_none()
            if not managed:
                raise HTTPException(403, "Not authorized to view this user")
        else:
            stmt = select(ManagedUser).where(ManagedUser.id == target_user_id)
            res = await session.execute(stmt)
            managed = res.scalar_one_or_none()

        if managed:
            brokers = managed.brokers or []
            alice_broker = next(
                (b for b in brokers if isinstance(b, dict) and "alice" in str(b.get("broker", "")).lower()),
                None
            )
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

            breeze_broker = next(
                (b for b in brokers if isinstance(b, dict) and "icici" in str(b.get("broker", "")).lower()),
                None
            )
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

    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == target_user_id,
        BrokerConnection.is_order_exec == True
    )
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        return {"error": "No execution broker configured."}

    from services.broker_router import get_broker_profile
    profile = await get_broker_profile(session, target_user_id, doc.broker)
    return {"broker": doc.broker, "profile": profile}


@router.get("/funds")
async def get_funds(
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    target_user_id = user_id if user_id else user.id

    if user.role == "managed_user" or target_user_id != user.id:
        if target_user_id != user.id:
            stmt = select(ManagedUser).where(
                ManagedUser.id == target_user_id,
                ManagedUser.trader_id == user.id
            )
            res = await session.execute(stmt)
            managed = res.scalar_one_or_none()
            if not managed:
                raise HTTPException(403, "Not authorized to view this user")
        else:
            stmt = select(ManagedUser).where(ManagedUser.id == target_user_id)
            res = await session.execute(stmt)
            managed = res.scalar_one_or_none()

        if managed:
            brokers = managed.brokers or []
            alice_broker = next(
                (b for b in brokers if isinstance(b, dict) and "alice" in str(b.get("broker", "")).lower()),
                None
            )
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

            breeze_broker = next(
                (b for b in brokers if isinstance(b, dict) and "icici" in str(b.get("broker", "")).lower()),
                None
            )
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

    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == target_user_id,
        BrokerConnection.is_order_exec == True
    )
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        return {"error": "No execution broker configured."}

    from services.broker_router import get_broker_funds
    funds = await get_broker_funds(session, target_user_id, doc.broker)
    return {"broker": doc.broker, "funds": funds}


@router.get("/aliceblue/history/{symbol}")
async def aliceblue_history(
    symbol: str,
    from_datetime: str = Query(...),
    to_datetime: str = Query(...),
    interval: str = Query("1"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    from services.brokers.aliceblue_client import AliceBlueClient

    client = None
    stmt = select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker == "aliceblue"
    )
    res = await session.execute(stmt)
    conn = res.scalar_one_or_none()
    if conn and conn.access_token:
        try:
            session_id = decrypt_str(conn.access_token)
            creds = conn.credentials or {}
            client = AliceBlueClient(
                client_code=decrypt_str(creds.get("user_id", "")),
                api_key=decrypt_str(creds.get("api_key", "")),
                session_id=session_id
            )
        except Exception:
            client = None

    if not client:
        # Check if they are a managed user
        mu_res = await session.execute(select(ManagedUser).where(ManagedUser.id == user.id))
        managed = mu_res.scalar_one_or_none()
        if managed:
            brokers = managed.brokers or []
            alice_broker = next(
                (b for b in brokers if isinstance(b, dict) and "alice" in str(b.get("broker", "")).lower()),
                None
            )
            if alice_broker and alice_broker.get("session_token"):
                creds = alice_broker.get("credentials") or {}
                user_id_val = creds.get("user_id") or alice_broker.get("account_number")
                api_key = creds.get("api_key") or alice_broker.get("api_key")
                client = AliceBlueClient(
                    client_code=user_id_val,
                    api_key=api_key,
                    session_id=alice_broker.get("session_token")
                )

    if not client:
        raise HTTPException(status_code=400, detail="Aliceblue client not connected.")

    try:
        from_dt = dt_module.datetime.fromisoformat(from_datetime.replace("Z", "+00:00"))
        to_dt = dt_module.datetime.fromisoformat(to_datetime.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format.")

    try:
        import httpx

        # Determine exchange and token
        if "|" in symbol:
            exchange, token = symbol.split("|", 1)
        else:
            exchange, token = "NSE", symbol

        # Try to resolve symbol to token if it's not numeric
        if not token.isdigit():
            # Hardcoded Index Tokens for Aliceblue
            INDEX_MAP = {
                "NIFTY": ("26000", "NSE::index"),
                "BANKNIFTY": ("26009", "NSE::index"),
                "FINNIFTY": ("26037", "NSE::index"),
                "MIDCPNIFTY": ("26074", "NSE::index"),
                "SENSEX": ("1", "BSE::index"),
                "NIFTYNXT50": ("26013", "NSE::index"),
            }
            if token.upper() in INDEX_MAP:
                token, exchange = INDEX_MAP[token.upper()]
                resolved = True
            else:
                resolved = False

            if not resolved:
                try:
                    # Try pya3's built-in resolution first
                    instrument = client._alice.get_instrument_by_symbol(
                        exchange,
                        f"{token}-EQ" if exchange == "NSE" and not token.endswith("-EQ") else token
                    )
                    token = str(instrument.token)
                    resolved = True
                except Exception:
                    pass

            # Fallback to reading the CSV directly (pya3 has a bug in some versions that throws 'module' object is not callable)
            if not resolved:
                csv_path = os.path.join(os.getcwd(), f"{exchange}.csv")
                if os.path.exists(csv_path):
                    with open(csv_path, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        target = f"{token}-EQ" if exchange == "NSE" and not token.endswith("-EQ") else token
                        for row in reader:
                            if row.get("Symbol") == token or row.get("Trading Symbol") == target:
                                token = str(row.get("Token"))
                                break

        from_ts = str(int(from_dt.timestamp() * 1000))
        to_ts = str(int(to_dt.timestamp() * 1000))

        payload = {
            "token": token,
            "resolution": interval,
            "from": from_ts,
            "to": to_ts,
            "exchange": exchange,
        }

        # AliceBlue A3 Open API for history with fallback to ANT API
        a3_url = "https://a3.aliceblueonline.com/open-api/od/ChartAPIService/api/chart/history"
        token_to_use = getattr(client, "_a3_token", None) or client._alice.session_id
        headers = {
            "Authorization": f"Bearer {token_to_use}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(a3_url, headers=headers, json=payload)
            data = {}
            try:
                data = resp.json()
            except Exception:
                pass

            # If token exchange or endpoint failed, fallback to ant URL
            if data.get("stat") != "Ok":
                ant_url = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/chart/history"
                ant_headers = {
                    "X-SAS-Version": "2.0",
                    "Authorization": f"Bearer {client._alice.user_id.upper()} {client._alice.session_id}",
                    "Content-Type": "application/json",
                }
                resp = await c.post(ant_url, headers=ant_headers, json=payload)
                try:
                    data = resp.json()
                except Exception:
                    data = {}

            if data.get("stat") != "Ok":
                # Special retry for SENSEX on BSE without ::index
                if "SENSEX" in symbol.upper():
                    payload_alt = dict(payload)
                    payload_alt["exchange"] = "BSE"
                    resp = await c.post(a3_url, headers=headers, json=payload_alt)
                    try:
                        data = resp.json()
                    except Exception:
                        pass

            if data.get("stat") != "Ok":
                raise HTTPException(
                    status_code=400,
                    detail=data.get("emsg", "Failed to load AliceBlue historical data")
                )

            return {"symbol": symbol, "rows": data.get("result", [])}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc())

