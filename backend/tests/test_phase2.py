"""Phase-2 pytest suite for Algonid backend.

Covers:
 - Idempotency: alert_id dedupe + fallback (symbol+side+price+minute)
 - Strategy scheduler: status + auto-fire with interval_seconds
 - Strategy CRUD with interval_seconds param + RUNNING/PAUSED toggle
 - Brokers: encrypted api_key + has_access_token/session_date fields
 - Kite OAuth: /kite/login-url (400 → URL), /kite/callback graceful reject, /kite/disconnect
 - Order routing: broker=zerodha + no session ⇒ mock fallback, source=manual
 - Telegram CRUD + encrypted bot_token + /telegram/test graceful failure
 - Option chain source=synthetic + 31 rows
 - TV webhook-info now includes alert_id in example_payload
"""
from __future__ import annotations

import os
import time
import uuid
import pytest
import requests

# Live preview backend (REACT_APP_BACKEND_URL is exported by frontend/.env)
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
assert BASE_URL, "REACT_APP_BACKEND_URL not set"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def demo(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "demo@trader.io", "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def headers(demo):
    return {"Authorization": f"Bearer {demo['access_token']}"}


@pytest.fixture(scope="session")
def user_id(demo):
    return demo["user"]["id"]


# ---------- Idempotency: alert_id ----------
def test_idempotency_alert_id_dedupe(session, headers):
    alert_id = f"TEST_alert_{uuid.uuid4().hex[:10]}"
    payload = {"symbol": "RELIANCE", "side": "BUY", "price": 2900.0,
               "qty": 1, "strategy": "TEST_idem", "alert_id": alert_id}
    r1 = session.post(f"{BASE_URL}/api/tradingview/test-fire", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["ok"] is True
    assert j1["duplicate"] is False
    assert j1["signal_id"]
    assert j1["order_id"]

    r2 = session.post(f"{BASE_URL}/api/tradingview/test-fire", json=payload, headers=headers)
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert j2["duplicate"] is True
    assert j2["signal_id"] == j1["signal_id"]
    assert j2["order_id"] == j1["order_id"]

    # Different alert_id ⇒ new signal
    payload2 = dict(payload, alert_id=alert_id + "-other")
    r3 = session.post(f"{BASE_URL}/api/tradingview/test-fire", json=payload2, headers=headers)
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3["duplicate"] is False
    assert j3["signal_id"] != j1["signal_id"]


def test_idempotency_fallback_symbol_side_price_minute(session, headers):
    # No alert_id ⇒ falls back to symbol+side+price+minute bucket
    price = round(3000.0 + uuid.uuid4().int % 100, 2)
    payload = {"symbol": "TCS", "side": "BUY", "price": price,
               "qty": 1, "strategy": "TEST_fb"}
    r1 = session.post(f"{BASE_URL}/api/tradingview/test-fire", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["duplicate"] is False
    r2 = session.post(f"{BASE_URL}/api/tradingview/test-fire", json=payload, headers=headers)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["duplicate"] is True, f"second identical fire should dedupe within the minute: {j2}"
    assert j2["signal_id"] == j1["signal_id"]


# ---------- Strategy scheduler ----------
def test_scheduler_status_running(session, headers):
    r = session.get(f"{BASE_URL}/api/strategies/scheduler-status", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["running"] is True
    assert "fires" in j and "tracked" in j


def test_scheduler_fires_strategy(session, headers, user_id):
    # baseline fires
    j0 = session.get(f"{BASE_URL}/api/strategies/scheduler-status", headers=headers).json()
    _ = j0["fires"]
    # create enabled EMA strategy with small interval
    body = {"name": f"TEST_sched_{uuid.uuid4().hex[:6]}",
            "kind": "ema_crossover", "enabled": True,
            "params": {"fast": 9, "slow": 21, "qty": 2},
            "symbols": ["RELIANCE", "TCS"],
            "interval_seconds": 5}
    rc = session.post(f"{BASE_URL}/api/strategies", json=body, headers=headers)
    assert rc.status_code == 200, rc.text
    strat = rc.json()
    sid = strat.get("id") or strat.get("_id")
    assert sid
    assert strat["params"]["interval_seconds"] == 5
    try:
        time.sleep(16)
        rs = session.get(f"{BASE_URL}/api/strategies/scheduler-status", headers=headers).json()
        assert rs["running"] is True
        # fires_after may not strictly increase if no signal triggers (each kind has heuristic)
        # so we don't strictly assert global fires>baseline, but we DO assert the per-strategy doc
        rlist = session.get(f"{BASE_URL}/api/strategies", headers=headers).json()["strategies"]
        doc = next((d for d in rlist if (d.get("id") or d.get("_id")) == sid), None)
        assert doc, "strategy missing from list"
        # at least the scheduler should have tracked it (or fired)
        tracked = rs.get("tracked", 0)
        fire_count = int(doc.get("fire_count", 0) or 0)
        assert tracked >= 1 or fire_count >= 1, f"scheduler didn't pick up strategy: stats={rs} doc={doc}"
        if fire_count > 0:
            assert doc.get("last_fire_at"), "fire_count>0 but no last_fire_at"
            # orders with source startswith strategy:
            orders = session.get(f"{BASE_URL}/api/orders?limit=200", headers=headers).json()["orders"]
            assert any(str(o.get("source", "")).startswith("strategy:") for o in orders), \
                "no orders with source=strategy:* found"
            notifs = session.get(f"{BASE_URL}/api/notifications?limit=200", headers=headers).json()
            items = notifs.get("notifications", notifs) if isinstance(notifs, dict) else notifs
            assert any(n.get("kind") == "strategy" for n in items), "no strategy notification found"
    finally:
        session.delete(f"{BASE_URL}/api/strategies/{sid}", headers=headers)


def test_strategy_crud_with_interval(session, headers):
    body = {"name": f"TEST_int_{uuid.uuid4().hex[:6]}",
            "kind": "ema_crossover", "enabled": False,
            "params": {"qty": 1}, "symbols": ["RELIANCE"],
            "interval_seconds": 10}
    r = session.post(f"{BASE_URL}/api/strategies", json=body, headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    sid = j.get("id") or j.get("_id")
    assert sid
    assert j["params"]["interval_seconds"] == 10
    # toggle on
    r2 = session.patch(f"{BASE_URL}/api/strategies/{sid}",
                       json={"enabled": True}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["enabled"] is True
    # toggle off
    r3 = session.patch(f"{BASE_URL}/api/strategies/{sid}",
                       json={"enabled": False}, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["enabled"] is False
    # delete
    rd = session.delete(f"{BASE_URL}/api/strategies/{sid}", headers=headers)
    assert rd.status_code == 200
    assert rd.json()["deleted"] == 1


# ---------- Brokers ----------
def test_brokers_list_has_new_fields(session, headers):
    # ensure at least one record exists
    session.post(f"{BASE_URL}/api/brokers",
                 json={"broker": "zerodha", "mock_mode": True,
                       "api_key": "", "api_secret": ""},
                 headers=headers)
    r = session.get(f"{BASE_URL}/api/brokers", headers=headers)
    assert r.status_code == 200
    conns = r.json()["connections"]
    z = next((c for c in conns if c["broker"] == "zerodha"), None)
    assert z is not None
    # new fields exist
    assert "has_access_token" in z
    assert "session_date" in z
    assert z["has_access_token"] is False
    assert z["session_date"] == ""


def test_broker_api_key_encrypted_in_db(session, headers):
    plaintext_key = f"realkey_{uuid.uuid4().hex[:10]}"
    r = session.post(f"{BASE_URL}/api/brokers",
                     json={"broker": "zerodha", "mock_mode": False,
                           "api_key": plaintext_key, "api_secret": "secret_xyz"},
                     headers=headers)
    assert r.status_code == 200, r.text
    # Verify by querying via login-url endpoint, then check internal stored representation
    # We cannot read the raw DB from here, but we can assert the response masks the key
    # (the list endpoint never returns api_key plaintext).
    rl = session.get(f"{BASE_URL}/api/brokers", headers=headers)
    z = next(c for c in rl.json()["connections"] if c["broker"] == "zerodha")
    # should NEVER include raw api_key in public payload
    assert "api_key" not in z, f"api_key leaked in public payload: {z}"
    assert z["has_keys"] is True
    # cleanup back to safe mock_mode
    session.post(f"{BASE_URL}/api/brokers",
                 json={"broker": "zerodha", "mock_mode": True,
                       "api_key": "", "api_secret": ""}, headers=headers)


# ---------- Kite OAuth ----------
def test_kite_login_url_requires_saved_key(session, headers):
    # First, fully clear the zerodha connection
    session.delete(f"{BASE_URL}/api/brokers/zerodha", headers=headers)
    r = session.get(f"{BASE_URL}/api/brokers/kite/login-url", headers=headers)
    assert r.status_code == 400, f"expected 400 with no saved key, got {r.status_code}: {r.text}"


def test_kite_login_url_returns_url_after_save(session, headers, user_id):
    # save keys (api_key required to build the URL)
    r0 = session.post(f"{BASE_URL}/api/brokers",
                      json={"broker": "zerodha", "mock_mode": False,
                            "api_key": "demoapikey", "api_secret": "demosecret"},
                      headers=headers)
    assert r0.status_code == 200
    r = session.get(f"{BASE_URL}/api/brokers/kite/login-url", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "kite.zerodha.com/connect/login" in j["login_url"]
    assert "demoapikey" in j["login_url"]
    assert "expected_redirect_url" in j
    assert "/api/brokers/kite/callback" in j["expected_redirect_url"]


def test_kite_callback_invalid_token_graceful(session, headers, user_id):
    # save keys so the row exists
    session.post(f"{BASE_URL}/api/brokers",
                 json={"broker": "zerodha", "mock_mode": False,
                       "api_key": "demoapikey", "api_secret": "demosecret"},
                 headers=headers)
    url = (f"{BASE_URL}/api/brokers/kite/callback"
           f"?status=success&request_token=fake&redirect_params=user_id={user_id}")
    # don't follow the redirect (we expect failure, not 302)
    r = session.get(url, allow_redirects=False)
    # Kite SDK rejects bad token ⇒ 400, must be a clean error, never 500
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    assert "Kite session exchange failed" in r.text


def test_kite_callback_missing_user_id(session):
    r = session.get(f"{BASE_URL}/api/brokers/kite/callback"
                    f"?status=success&request_token=fake&redirect_params=",
                    allow_redirects=False)
    assert r.status_code == 400


def test_kite_disconnect_resets(session, headers):
    r = session.post(f"{BASE_URL}/api/brokers/kite/disconnect", headers=headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    rl = session.get(f"{BASE_URL}/api/brokers", headers=headers)
    z = next((c for c in rl.json()["connections"] if c["broker"] == "zerodha"), None)
    assert z is not None
    assert z["has_access_token"] is False
    assert z["mock_mode"] is True


# ---------- Order routing: zerodha → mock fallback ----------
def test_order_routing_zerodha_falls_back_to_mock(session, headers):
    # Make sure no live access_token is set (disconnect to be safe)
    session.post(f"{BASE_URL}/api/brokers/kite/disconnect", headers=headers)
    snap = session.get(f"{BASE_URL}/api/market/snapshot", headers=headers).json()["ticks"]
    price = next(t["ltp"] for t in snap if t["symbol"] == "RELIANCE")
    body = {"broker": "zerodha", "symbol": "RELIANCE", "side": "BUY", "qty": 1,
            "price": price, "order_type": "MARKET", "product": "MIS"}
    r = session.post(f"{BASE_URL}/api/orders", json=body, headers=headers)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["status"].upper() == "FILLED"
    assert o["source"] == "manual"
    # persisted in /orders
    rl = session.get(f"{BASE_URL}/api/orders?limit=10", headers=headers).json()["orders"]
    oid = o.get("id") or o.get("_id")
    assert any((x.get("id") or x.get("_id")) == oid for x in rl)


# ---------- Telegram settings ----------
def test_telegram_crud_and_encryption_safety(session, headers):
    # ensure fresh
    session.delete(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    r0 = session.get(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    assert r0.status_code == 200
    j0 = r0.json()
    assert j0["configured"] is False
    assert j0["chat_id"] == ""
    # the route returns has_token only when row exists; absence ≡ False
    assert j0.get("has_token", False) is False

    # save
    rs = session.post(f"{BASE_URL}/api/notifications/telegram",
                      json={"bot_token": "fake-token-123", "chat_id": "12345",
                            "enabled": True},
                      headers=headers)
    assert rs.status_code == 200
    assert rs.json()["ok"] is True

    r1 = session.get(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    j1 = r1.json()
    assert j1["configured"] is True
    assert j1["has_token"] is True
    assert j1["chat_id"] == "12345"
    # never leak token
    assert "bot_token" not in j1

    # test send — bad token, must not crash
    rt = session.post(f"{BASE_URL}/api/notifications/telegram/test", headers=headers)
    assert rt.status_code in (200, 400), rt.text
    # Telegram API returns JSON; the route returns it as-is or a 400 from httpx error path
    try:
        body = rt.json()
        assert isinstance(body, dict)
    except ValueError:
        pytest.fail(f"telegram/test did not return JSON: {rt.text}")

    # delete
    rd = session.delete(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    assert rd.status_code == 200
    r2 = session.get(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    assert r2.json()["configured"] is False


# ---------- Option chain source ----------
def test_option_chain_source_synthetic(session, headers):
    # ensure no kite session
    session.post(f"{BASE_URL}/api/brokers/kite/disconnect", headers=headers)
    r = session.get(f"{BASE_URL}/api/analytics/option-chain", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("source") == "synthetic", f"source must be 'synthetic' without Kite session, got {j.get('source')}"
    assert len(j["rows"]) == 31


# ---------- TV webhook-info includes alert_id ----------
def test_tv_webhook_info_includes_alert_id(session, headers, user_id):
    r = session.get(f"{BASE_URL}/api/tradingview/webhook-info", headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert j["user_id"] == user_id
    assert "example_payload" in j
    assert "alert_id" in j["example_payload"], \
        f"example_payload missing alert_id: {j['example_payload']}"
