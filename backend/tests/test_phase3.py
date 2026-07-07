"""Phase-3 pytest suite for Algonid backend.

Covers:
 - GET /api/brokers/schemas (7 brokers, expected field counts/names)
 - GET /api/brokers returns inline schemas + fields_filled
 - POST /api/brokers angel with full credentials → fields_filled + Fernet-encrypted at rest
 - Kite disconnect + order with broker=zerodha still falls back to mock
 - Per-user tv_webhook_secret on /login, /me, /webhook-secret/rotate, /tradingview/webhook-info
 - Per-user TV webhook: wrong secret → 403, real secret → 200, other user's secret → 403
 - Telegram platform bot fallback (chat_id only, no token)
 - Option-chain rows have non-zero ce_iv/pe_iv + greeks dicts with sensible ranges
 - /analytics/greeks/{strike} valid & invalid
 - Backtester real parquet: RELIANCE 1d → data_source='parquet', bars/ticks counts
 - Backtester synthetic fallback: ZZZZZ → data_source='synthetic', reason='no_parquet_data'
 - All 5 strategy_kinds on HDFCBANK return valid metrics + non-empty equity_curve
"""
from __future__ import annotations

import os
import uuid
import asyncio
import pytest
import requests

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


# ---------- 1. Broker schemas ----------
EXPECTED_FIELD_COUNTS = {
    "zerodha": (2, {"api_key", "api_secret"}),
    "breeze": (3, {"api_key", "api_secret", "session_token"}),
    "angel": (4, {"api_key", "client_code", "pin", "totp_secret"}),
    "fyers": (2, {"api_key", "api_secret"}),
    "upstox": (2, {"api_key", "api_secret"}),
    "dhan": (2, {"client_id", "access_token"}),
    "mock": (0, set()),
}


def test_broker_schemas_endpoint(session, headers):
    r = session.get(f"{BASE_URL}/api/brokers/schemas", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    schemas = j["schemas"]
    assert set(schemas.keys()) == set(EXPECTED_FIELD_COUNTS.keys()), \
        f"expected 7 brokers, got {list(schemas.keys())}"
    for broker, (count, names) in EXPECTED_FIELD_COUNTS.items():
        fields = schemas[broker]["fields"]
        assert len(fields) == count, f"{broker} expected {count} fields, got {len(fields)}: {fields}"
        actual_names = {f["name"] for f in fields}
        assert actual_names == names, f"{broker} field name mismatch: {actual_names} vs {names}"


def test_brokers_list_includes_inline_schemas(session, headers):
    r = session.get(f"{BASE_URL}/api/brokers", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "schemas" in j and "connections" in j
    assert set(j["schemas"].keys()) == set(EXPECTED_FIELD_COUNTS.keys())
    for conn in j["connections"]:
        assert "fields_filled" in conn
        assert isinstance(conn["fields_filled"], list)


# ---------- 2. Angel: full credentials → encrypted at rest ----------
def test_angel_credentials_encrypted_in_db(session, headers, user_id):
    # cleanup any prior angel row
    session.delete(f"{BASE_URL}/api/brokers/angel", headers=headers)
    creds = {
        "api_key": f"TEST_angel_key_{uuid.uuid4().hex[:6]}",
        "client_code": f"A{uuid.uuid4().hex[:6].upper()}",
        "pin": "1234",
        "totp_secret": "JBSWY3DPEHPK3PXP",
    }
    r = session.post(f"{BASE_URL}/api/brokers",
                     json={"broker": "angel", "mock_mode": False,
                           "api_key": "", "api_secret": "", "credentials": creds},
                     headers=headers)
    assert r.status_code == 200, r.text
    # GET back, verify fields_filled
    rl = session.get(f"{BASE_URL}/api/brokers", headers=headers)
    assert rl.status_code == 200
    angel_conn = next((c for c in rl.json()["connections"] if c["broker"] == "angel"), None)
    assert angel_conn is not None
    assert set(creds.keys()).issubset(set(angel_conn["fields_filled"])), \
        f"fields_filled missing keys: {angel_conn['fields_filled']}"

    # direct Motor read to verify Fernet encryption (gAAAA prefix)
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "algo_trading_db")

    async def _check():
        client = AsyncIOMotorClient(mongo_url)
        try:
            db = client[db_name]
            doc = await db.broker_connections.find_one({"user_id": user_id, "broker": "angel"})
            assert doc is not None
            stored = doc.get("credentials", {})
            for k in creds.keys():
                assert k in stored, f"missing {k} in stored credentials: {stored}"
                v = stored[k]
                assert isinstance(v, str) and v.startswith("gAAAA"), \
                    f"{k} not Fernet-encrypted: {v[:20]}..."
                # also ensure plaintext is NOT present
                assert v != creds[k], f"{k} stored as plaintext"
        finally:
            client.close()

    asyncio.get_event_loop().run_until_complete(_check())
    # cleanup
    session.delete(f"{BASE_URL}/api/brokers/angel", headers=headers)


# ---------- 3. Kite disconnect → order broker=zerodha still works (mock fallback) ----------
def test_zerodha_order_after_kite_disconnect_falls_back(session, headers):
    session.post(f"{BASE_URL}/api/brokers/kite/disconnect", headers=headers)
    snap = session.get(f"{BASE_URL}/api/market/snapshot", headers=headers).json()["ticks"]
    price = next(t["ltp"] for t in snap if t["symbol"] == "RELIANCE")
    body = {"broker": "zerodha", "symbol": "RELIANCE", "side": "BUY", "qty": 1,
            "price": price, "order_type": "MARKET", "product": "MIS"}
    r = session.post(f"{BASE_URL}/api/orders", json=body, headers=headers)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["status"].upper() == "FILLED"


# ---------- 4. Per-user webhook secret ----------
def test_login_user_has_tv_webhook_secret(demo):
    secret = demo["user"].get("tv_webhook_secret", "")
    assert secret.startswith("tv_"), f"login.user.tv_webhook_secret missing/bad: {secret!r}"
    assert len(secret) > 10


def test_me_has_tv_webhook_secret(session, headers, demo):
    r = session.get(f"{BASE_URL}/api/auth/me", headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert j.get("tv_webhook_secret") == demo["user"]["tv_webhook_secret"]


def test_webhook_secret_rotate_changes_value(session, demo):
    # Use a freshly-registered isolated user to avoid breaking other tests
    email = f"TEST_rotate_{uuid.uuid4().hex[:8]}@example.com"
    r = session.post(f"{BASE_URL}/api/auth/register",
                     json={"email": email, "name": "Rotate", "password": "pw123456"})
    assert r.status_code == 200, r.text
    j = r.json()
    h = {"Authorization": f"Bearer {j['access_token']}"}
    old = j["user"]["tv_webhook_secret"]
    assert old.startswith("tv_")
    r2 = session.post(f"{BASE_URL}/api/auth/webhook-secret/rotate", headers=h)
    assert r2.status_code == 200, r2.text
    new = r2.json()["tv_webhook_secret"]
    assert new.startswith("tv_") and new != old, f"rotation didn't change: {old} vs {new}"
    # /me reflects new value
    r3 = session.get(f"{BASE_URL}/api/auth/me", headers=h)
    assert r3.json()["tv_webhook_secret"] == new


def test_tv_webhook_info_per_user_secret(session, headers, demo, user_id):
    r = session.get(f"{BASE_URL}/api/tradingview/webhook-info", headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert j["user_id"] == user_id
    assert j["per_user_secret"] is True
    assert j["secret"] == demo["user"]["tv_webhook_secret"]


def test_per_user_tv_webhook_secret_enforcement(session, demo, user_id):
    # wrong secret → 403
    payload = {"symbol": "RELIANCE", "side": "BUY", "price": 2900.0,
               "qty": 1, "strategy": "TEST_pus",
               "alert_id": f"TEST_pus_{uuid.uuid4().hex[:8]}"}
    url = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret=wrong-secret-xyz"
    r = session.post(url, json=payload)
    assert r.status_code == 403, f"wrong secret should 403, got {r.status_code} {r.text}"

    # correct per-user secret → 200
    real = demo["user"]["tv_webhook_secret"]
    url_ok = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret={real}"
    payload2 = dict(payload, alert_id=f"TEST_pus_{uuid.uuid4().hex[:8]}")
    r2 = session.post(url_ok, json=payload2)
    assert r2.status_code == 200, r2.text
    assert r2.json()["ok"] is True

    # other user's secret → 403
    other_email = f"TEST_other_{uuid.uuid4().hex[:8]}@example.com"
    ro = session.post(f"{BASE_URL}/api/auth/register",
                      json={"email": other_email, "name": "Other", "password": "pw123456"})
    assert ro.status_code == 200
    other_secret = ro.json()["user"]["tv_webhook_secret"]
    assert other_secret != real
    url_other = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret={other_secret}"
    payload3 = dict(payload, alert_id=f"TEST_pus_{uuid.uuid4().hex[:8]}")
    r3 = session.post(url_other, json=payload3)
    assert r3.status_code == 403, f"other user's secret should 403, got {r3.status_code}"


# ---------- 5. Telegram platform bot fallback ----------
def test_telegram_platform_bot_available(session, headers):
    # clean state
    session.delete(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    r = session.get(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert j["platform_bot_available"] is True, "TELEGRAM_BOT_TOKEN should make platform available"


def test_telegram_using_platform_bot_when_only_chat_id(session, headers):
    session.delete(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    # only chat_id, no token
    rs = session.post(f"{BASE_URL}/api/notifications/telegram",
                      json={"bot_token": "", "chat_id": "123456789", "enabled": True},
                      headers=headers)
    assert rs.status_code == 200
    r = session.get(f"{BASE_URL}/api/notifications/telegram", headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert j["has_token"] is False
    assert j["using_platform_bot"] is True
    assert j["chat_id"] == "123456789"


def test_telegram_test_send_no_crash(session, headers):
    # ensure platform-bot + bad chat_id config exists
    session.post(f"{BASE_URL}/api/notifications/telegram",
                 json={"bot_token": "", "chat_id": "123456789", "enabled": True},
                 headers=headers)
    r = session.post(f"{BASE_URL}/api/notifications/telegram/test", headers=headers)
    assert r.status_code in (200, 400), r.text
    # must be JSON object envelope; Telegram returns ok:false for invalid chat
    try:
        body = r.json()
    except ValueError:
        pytest.fail(f"non-JSON: {r.text}")
    assert isinstance(body, dict)
    # If 200 we expect envelope with telegram_response
    if r.status_code == 200:
        assert "telegram_response" in body or "ok" in body
    # cleanup
    session.delete(f"{BASE_URL}/api/notifications/telegram", headers=headers)


# ---------- 6. Option-chain IV + Greeks ----------
def test_option_chain_greeks_populated(session, headers):
    r = session.get(f"{BASE_URL}/api/analytics/option-chain", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    rows = j["rows"]
    atm = j["atm"]
    assert len(rows) > 0
    # every row has non-zero iv + greeks dicts
    for row in rows:
        assert row.get("ce_iv", 0) > 0, f"ce_iv zero: {row}"
        assert row.get("pe_iv", 0) > 0, f"pe_iv zero: {row}"
        for side in ("ce_greeks", "pe_greeks"):
            g = row.get(side)
            assert isinstance(g, dict), f"{side} missing"
            for k in ("delta", "gamma", "theta", "vega", "rho"):
                assert k in g, f"{side} missing {k}: {g}"
            # gamma always positive
            assert g["gamma"] > 0, f"{side} gamma not positive: {g}"
            # theta should be negative (time decay)
            assert g["theta"] < 0, f"{side} theta not negative: {g}"
    # delta sanity at ATM
    atm_row = next((r_ for r_ in rows if int(r_["strike"]) == int(atm)), None)
    assert atm_row is not None, f"no ATM row for strike {atm}"
    ce_delta = atm_row["ce_greeks"]["delta"]
    pe_delta = atm_row["pe_greeks"]["delta"]
    assert 0.3 <= ce_delta <= 0.7, f"CE@ATM delta out of range: {ce_delta}"
    assert -0.7 <= pe_delta <= -0.3, f"PE@ATM delta out of range: {pe_delta}"


def test_greeks_by_strike_endpoint(session, headers):
    chain = session.get(f"{BASE_URL}/api/analytics/option-chain", headers=headers).json()
    valid_strike = int(chain["atm"])
    r = session.get(f"{BASE_URL}/api/analytics/greeks/{valid_strike}", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["strike"] == valid_strike
    assert "ce" in j and "pe" in j
    assert isinstance(j["ce"]["greeks"], dict)
    assert "delta" in j["ce"]["greeks"]

    r2 = session.get(f"{BASE_URL}/api/analytics/greeks/999999", headers=headers)
    assert r2.status_code == 200
    assert r2.json().get("error") == "strike not found"


# ---------- 7. Backtester: real parquet + synthetic fallback ----------
def test_backtest_real_parquet_reliance(session, headers):
    body = {"strategy_kind": "ema_crossover", "symbol": "RELIANCE",
            "period_days": 1, "params": {"fast": 9, "slow": 21}}
    r = session.post(f"{BASE_URL}/api/backtest/run", json=body, headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("data_source") == "parquet", \
        f"expected parquet data_source, got {j.get('data_source')} reason={j.get('reason')}"
    assert j.get("bars_loaded", 0) > 50, f"bars_loaded too low: {j.get('bars_loaded')}"
    assert j.get("raw_ticks", 0) > 100, f"raw_ticks too low: {j.get('raw_ticks')}"
    assert "metrics" in j and isinstance(j["metrics"], dict)
    assert isinstance(j.get("equity_curve"), list) and len(j["equity_curve"]) > 0


def test_backtest_synthetic_fallback_unknown_symbol(session, headers):
    body = {"strategy_kind": "ema_crossover", "symbol": "ZZZZZ",
            "period_days": 1, "params": {"fast": 9, "slow": 21}}
    r = session.post(f"{BASE_URL}/api/backtest/run", json=body, headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("data_source") == "synthetic", \
        f"expected synthetic for ZZZZZ, got {j.get('data_source')}"
    assert j.get("reason") == "no_parquet_data", f"unexpected reason: {j.get('reason')}"


@pytest.mark.parametrize("kind", [
    "ema_crossover", "vwap_scalping", "oi_breakout", "smart_money", "gamma_scalping",
])
def test_backtest_all_strategies_hdfcbank(session, headers, kind):
    body = {"strategy_kind": kind, "symbol": "HDFCBANK", "period_days": 1, "params": {}}
    r = session.post(f"{BASE_URL}/api/backtest/run", json=body, headers=headers)
    assert r.status_code == 200, f"{kind} failed: {r.status_code} {r.text}"
    j = r.json()
    assert "metrics" in j and isinstance(j["metrics"], dict)
    eq = j.get("equity_curve")
    assert isinstance(eq, list) and len(eq) > 0, f"{kind} empty equity_curve"
