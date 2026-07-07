"""Phase 5 — Live feed + AI signal explainer + real broker scaffolding.

Coverage matches the review request:
 - Phase A: feed-status, snapshot 'live' flag, history source, parquet still rolling
 - Phase B: /ai/explain-signal, /ai/anomaly-sweep/status
 - Phase C: broker schemas (7), CRUD for angel mock, angel/login w/o creds,
            upstox/login-url w/o creds, broker_router mock fallback for orders
 - Regression: auth, TV webhook, strategies CRUD, options analytics, parquet.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or open("/app/frontend/.env").read().split(
                "REACT_APP_BACKEND_URL=", 1)[1].splitlines()[0]).rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

TV_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "tv-webhook-secret-123")


# ----------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def login(s):
    time.sleep(1.2)  # avoid same-second JWT collision documented in iter-4
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "demo@trader.io", "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def h(login):
    return {"Authorization": f"Bearer {login['access_token']}"}


@pytest.fixture(scope="session")
def uid(login):
    return login["user"]["id"]


# ===================================================== Phase A — Live feed
def test_feed_status_synthetic(s, h):
    r = s.get(f"{BASE_URL}/api/market/feed-status", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["running"] is True
    assert j["source"] == "synthetic"
    assert j.get("active_broker") in (None, "")
    assert j["live_symbol_count"] == 0


def test_snapshot_all_live_false(s, h):
    r = s.get(f"{BASE_URL}/api/market/snapshot", headers=h)
    assert r.status_code == 200
    ticks = r.json()["ticks"]
    assert len(ticks) == 50
    for t in ticks:
        assert "live" in t, f"missing 'live' on {t['symbol']}"
        assert t["live"] is False


def test_history_source_synthetic(s, h):
    r = s.get(f"{BASE_URL}/api/market/history/RELIANCE", headers=h)
    assert r.status_code == 200
    candles = r.json()["candles"]
    assert len(candles) > 0
    # Every record should be synthetic
    for c in candles[-10:]:
        assert c.get("source") in ("synthetic", None) or c["source"] == "synthetic"
    # at least the most-recent ones must explicitly say synthetic
    assert candles[-1]["source"] == "synthetic"


def test_parquet_still_rolling(s, h):
    r = s.get(f"{BASE_URL}/api/parquet/status", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j.get("running") is True


# ===================================================== Phase B — AI
def test_ai_explain_signal_structured(s, h):
    payload = {"symbol": "RELIANCE", "kind": "long_buildup", "price": 2890.5,
               "change_pct": 0.85, "volume_ratio": 2.4, "confidence": 0.78}
    r = s.post(f"{BASE_URL}/api/ai/explain-signal", json=payload,
               headers=h, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("reasoning", "suggested_sl", "suggested_target",
              "risk_reward", "confidence_score", "side_bias", "model"):
        assert k in j, f"missing key {k} in {j}"
    assert isinstance(j["reasoning"], str)
    assert len(j["reasoning"]) <= 400
    assert isinstance(j["suggested_sl"], (int, float))
    assert isinstance(j["suggested_target"], (int, float))
    assert isinstance(j["risk_reward"], (int, float))
    assert 0 <= float(j["confidence_score"]) <= 1
    assert str(j["side_bias"]).upper() in ("BUY", "SELL", "NEUTRAL")
    price = payload["price"]
    if str(j["side_bias"]).upper() == "BUY":
        # SL below entry, target above
        assert j["suggested_sl"] < price, f"BUY SL {j['suggested_sl']} not < {price}"
        assert j["suggested_target"] > price, f"BUY tgt {j['suggested_target']} not > {price}"


def test_anomaly_sweep_status(s, h):
    r = s.get(f"{BASE_URL}/api/ai/anomaly-sweep/status", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["running"] is True
    assert j["interval_seconds"] == 60
    assert j["symbols_per_cycle"] == 3
    assert "last_run_at" in j
    assert "detections_total" in j
    assert isinstance(j["detections_total"], int)
    # backend has been up >60s per server logs; last_run_at should not be None
    assert j["last_run_at"], "anomaly sweep never executed a cycle"


# ===================================================== Phase C — Brokers
def test_broker_schemas_seven(s, h):
    r = s.get(f"{BASE_URL}/api/brokers/schemas", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert "schemas" in j and "brokers" in j
    expected = {"zerodha", "breeze", "angel", "fyers", "upstox", "dhan", "mock"}
    assert set(j["brokers"]) == expected, f"got {set(j['brokers'])}"
    assert set(j["schemas"].keys()) == expected


def test_broker_angel_mock_upsert_list_delete(s, h):
    # cleanup first (idempotent)
    s.delete(f"{BASE_URL}/api/brokers/angel", headers=h)
    # upsert mock angel
    r = s.post(f"{BASE_URL}/api/brokers",
               json={"broker": "angel", "mock_mode": True,
                     "api_key": "", "api_secret": "", "credentials": {}},
               headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["broker"] == "angel"
    assert j["connected"] is True
    assert j["mock_mode"] is True
    # list shows it
    rl = s.get(f"{BASE_URL}/api/brokers", headers=h)
    assert rl.status_code == 200
    conns = rl.json()["connections"]
    assert any(c["broker"] == "angel" for c in conns)
    # delete
    rd = s.delete(f"{BASE_URL}/api/brokers/angel", headers=h)
    assert rd.status_code == 200
    assert rd.json()["deleted"] == 1


def test_angel_login_without_creds(s, h):
    # ensure no angel record
    s.delete(f"{BASE_URL}/api/brokers/angel", headers=h)
    r = s.post(f"{BASE_URL}/api/brokers/angel/login", headers=h)
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "credentials" in detail.lower() or "save" in detail.lower(), \
        f"unexpected error message: {detail}"


def test_upstox_login_url_without_creds(s, h):
    s.delete(f"{BASE_URL}/api/brokers/upstox", headers=h)
    r = s.get(f"{BASE_URL}/api/brokers/upstox/login-url", headers=h)
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "api key" in detail.lower() or "save" in detail.lower(), \
        f"unexpected error message: {detail}"


@pytest.mark.parametrize("broker", ["angel", "upstox", "dhan", "breeze", "zerodha"])
def test_broker_mock_fallback_order(s, h, broker):
    """Each broker should accept a manual mock order via /api/orders."""
    snap = s.get(f"{BASE_URL}/api/market/snapshot", headers=h).json()["ticks"]
    price = snap[0]["ltp"]
    sym = snap[0]["symbol"]
    # ensure a mock connection exists
    s.post(f"{BASE_URL}/api/brokers",
           json={"broker": broker, "mock_mode": True,
                 "api_key": "", "api_secret": "", "credentials": {}},
           headers=h)
    body = {"broker": broker, "symbol": sym, "side": "BUY", "qty": 1,
            "price": price, "order_type": "MARKET", "product": "MIS"}
    r = s.post(f"{BASE_URL}/api/orders", json=body, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    mode = (j.get("mode") or j.get("metadata", {}).get("mode") or "").lower()
    status = (j.get("status") or "").upper()
    assert mode == "mock" or status in ("FILLED", "COMPLETE"), \
        f"broker={broker} order did not fall back to mock: {j}"
    # cleanup
    s.delete(f"{BASE_URL}/api/brokers/{broker}", headers=h)


# ===================================================== Regression — Auth
def test_register_login_me_logout(s):
    email = f"TEST_p5_{uuid.uuid4().hex[:8]}@example.com"
    pw = "pw123456"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "name": "P5 User", "password": pw})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    hh = {"Authorization": f"Bearer {tok}"}
    r2 = s.get(f"{BASE_URL}/api/auth/me", headers=hh)
    assert r2.status_code == 200
    assert r2.json()["email"] == email
    # login again
    time.sleep(1.1)
    r3 = s.post(f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": pw})
    assert r3.status_code == 200
    new_tok = r3.json()["access_token"]
    # logout
    r4 = s.post(f"{BASE_URL}/api/auth/logout",
                headers={"Authorization": f"Bearer {new_tok}"})
    assert r4.status_code == 200
    # /me with logged-out token should now fail
    r5 = s.get(f"{BASE_URL}/api/auth/me",
               headers={"Authorization": f"Bearer {new_tok}"})
    assert r5.status_code in (401, 403)


def test_tv_webhook_regression(s, h, uid):
    # demo trader may have a per-user webhook secret — fetch it first
    info = s.get(f"{BASE_URL}/api/tradingview/webhook-info", headers=h).json()
    secret = info.get("secret") or TV_SECRET
    payload = {"symbol": "INFY", "side": "BUY", "price": 1500.0,
               "qty": 1, "strategy": "TEST_p5_tv"}
    r = s.post(f"{BASE_URL}/api/tradingview/webhook/{uid}?secret={secret}",
               json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_strategies_crud_regression(s, h):
    body = {"name": "TEST_p5_strat", "kind": "ema_crossover",
            "enabled": False, "params": {"fast": 9, "slow": 21},
            "symbols": ["RELIANCE"]}
    r = s.post(f"{BASE_URL}/api/strategies", json=body, headers=h)
    assert r.status_code == 200
    sid = r.json()["id"]
    r2 = s.delete(f"{BASE_URL}/api/strategies/{sid}", headers=h)
    assert r2.status_code == 200


def test_analytics_options_regression(s, h):
    r = s.get(f"{BASE_URL}/api/analytics/option-chain", headers=h)
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 31
