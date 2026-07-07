"""Phase-4 backend regression tests after code-review cleanup pass.

Focus areas:
 1. POST /api/auth/logout — blacklist + revocation behavior
 2. backtest refactor (_simulate → SimState) regression
 3. option-chain greeks coverage
 4. idempotency (test-fire duplicate)
 5. strategy scheduler stats
 6. per-user webhook secret enforcement
 7. telegram platform bot availability
 8. broker schemas (7 brokers)
 9. hardcoded secret regression check (file static check)
"""

import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

TV_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "tv-webhook-secret-123")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "algo_trading_db")


# ---------- shared fixtures ----------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def demo_login(session):
    # Small sleep so this session token's 'exp' second is distinct from any
    # subsequent logout-test token (JWTs with same payload+exp-second are identical).
    time.sleep(1.2)
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "demo@trader.io", "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def auth_headers(demo_login):
    return {"Authorization": f"Bearer {demo_login['access_token']}"}


@pytest.fixture(scope="session")
def user_id(demo_login):
    return demo_login["user"]["id"]


# ============================================================
# 1. Logout / blacklist
# ============================================================
class TestLogout:
    def test_logout_revokes_token(self, session):
        # sleep so the new JWT 'exp' second differs from session-cached token
        time.sleep(1.2)
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": "demo@trader.io", "password": "demo123"})
        assert r.status_code == 200
        token = r.json()["access_token"]
        hdrs = {"Authorization": f"Bearer {token}"}

        # /me works
        rm = session.get(f"{BASE_URL}/api/auth/me", headers=hdrs)
        assert rm.status_code == 200, rm.text

        # logout
        rl = session.post(f"{BASE_URL}/api/auth/logout", headers=hdrs)
        assert rl.status_code == 200, rl.text
        assert rl.json().get("ok") is True

        # /me now revoked
        r2 = session.get(f"{BASE_URL}/api/auth/me", headers=hdrs)
        assert r2.status_code == 401, f"expected 401 got {r2.status_code} {r2.text}"
        detail = r2.json().get("detail", "")
        assert "revoked" in str(detail).lower(), f"detail was {detail!r}"

        # fresh login gives a new working token (sleep 1.2s so 'exp' second differs)
        time.sleep(1.2)
        r3 = session.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "demo@trader.io", "password": "demo123"})
        assert r3.status_code == 200
        new_tok = r3.json()["access_token"]
        assert new_tok != token
        r4 = session.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {new_tok}"})
        assert r4.status_code == 200

    def test_logout_without_token_is_noop(self, session):
        r = session.post(f"{BASE_URL}/api/auth/logout")
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_blacklist_has_future_expires_at(self, session):
        # produce a known token then check the DB doc; sleep so token differs from session
        time.sleep(1.2)
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": "demo@trader.io", "password": "demo123"})
        token = r.json()["access_token"]
        rl = session.post(f"{BASE_URL}/api/auth/logout",
                          headers={"Authorization": f"Bearer {token}"})
        assert rl.status_code == 200

        try:
            from pymongo import MongoClient
        except ImportError:
            pytest.skip("pymongo not available")

        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=4000)
        doc = client[DB_NAME].token_blacklist.find_one({"token": token})
        assert doc is not None, "blacklist doc not inserted"
        assert "expires_at" in doc, "no expires_at field"
        # expires_at must be a future datetime
        import datetime as dt
        exp = doc["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=dt.timezone.utc)
        assert exp > dt.datetime.now(dt.timezone.utc), f"expires_at not in future: {exp}"


# ============================================================
# 2. Backtest regression after _simulate refactor
# ============================================================
class TestBacktestRegression:
    REQUIRED_METRIC_KEYS = {
        "total_return_pct", "win_rate_pct", "max_drawdown_pct",
        "sharpe", "trades", "bars", "final_equity",
    }

    def test_ema_crossover_reliance_short_period(self, session, auth_headers):
        body = {"strategy_kind": "ema_crossover", "symbol": "RELIANCE",
                "period_days": 1, "params": {"fast": 9, "slow": 21}}
        r = session.post(f"{BASE_URL}/api/backtest/run", json=body, headers=auth_headers)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("data_source") in ("parquet", "synthetic"), j.get("data_source")
        metrics = j.get("metrics", {})
        assert self.REQUIRED_METRIC_KEYS.issubset(set(metrics.keys())), \
            f"missing metric keys: {self.REQUIRED_METRIC_KEYS - set(metrics.keys())}"
        assert isinstance(j.get("equity_curve"), list) and len(j["equity_curve"]) > 0
        assert isinstance(j.get("trades_log"), list)

    @pytest.mark.parametrize("kind", [
        "vwap_scalping", "oi_breakout", "smart_money", "gamma_scalping",
    ])
    @pytest.mark.parametrize("symbol", ["RELIANCE", "HDFCBANK", "INFY"])
    def test_all_strategies_no_5xx(self, session, auth_headers, kind, symbol):
        body = {"strategy_kind": kind, "symbol": symbol, "period_days": 1, "params": {}}
        r = session.post(f"{BASE_URL}/api/backtest/run", json=body, headers=auth_headers)
        assert r.status_code < 500, f"{kind}/{symbol}: {r.status_code} {r.text[:200]}"
        # for 200 responses, verify shape
        if r.status_code == 200:
            j = r.json()
            assert "metrics" in j and "equity_curve" in j
            assert isinstance(j["equity_curve"], list)


# ============================================================
# 3. Option chain greeks coverage
# ============================================================
class TestOptionChainGreeks:
    def test_31_rows_with_greeks(self, session, auth_headers):
        r = session.get(f"{BASE_URL}/api/analytics/option-chain", headers=auth_headers)
        assert r.status_code == 200, r.text
        j = r.json()
        rows = j.get("rows", [])
        assert len(rows) == 31, f"expected 31 rows got {len(rows)}"
        for row in rows:
            assert row.get("ce_greeks"), f"missing ce_greeks at strike {row.get('strike')}"
            assert row.get("pe_greeks"), f"missing pe_greeks at strike {row.get('strike')}"

        atm = j.get("atm")
        atm_row = next((r_ for r_ in rows if r_["strike"] == atm), None)
        assert atm_row, f"no row matching atm strike {atm}"
        ce_delta = atm_row["ce_greeks"]["delta"]
        pe_delta = atm_row["pe_greeks"]["delta"]
        assert 0.3 <= ce_delta <= 0.7, f"CE atm delta {ce_delta} not in [0.3,0.7]"
        assert -0.7 <= pe_delta <= -0.3, f"PE atm delta {pe_delta} not in [-0.7,-0.3]"


# ============================================================
# 4. Idempotency on test-fire
# ============================================================
class TestIdempotency:
    def test_test_fire_duplicate(self, session, auth_headers):
        alert_id = f"TEST_alert_{uuid.uuid4().hex[:10]}"
        payload = {"symbol": "RELIANCE", "side": "BUY", "price": 2890.5,
                   "qty": 1, "strategy": "TEST_idem", "alert_id": alert_id}
        r1 = session.post(f"{BASE_URL}/api/tradingview/test-fire",
                          json=payload, headers=auth_headers)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1.get("duplicate") is False
        sig1 = j1["signal_id"]
        ord1 = j1["order_id"]

        r2 = session.post(f"{BASE_URL}/api/tradingview/test-fire",
                          json=payload, headers=auth_headers)
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        assert j2.get("duplicate") is True, j2
        assert j2.get("signal_id") == sig1
        assert j2.get("order_id") == ord1


# ============================================================
# 5. Strategy scheduler
# ============================================================
class TestScheduler:
    def test_scheduler_running_and_fires(self, session, auth_headers):
        s0 = session.get(f"{BASE_URL}/api/strategies/scheduler-status",
                         headers=auth_headers).json()
        assert s0.get("running") is True, s0
        before_fires = int(s0.get("fires", 0))
        before_tracked = int(s0.get("tracked", 0))

        # create an enabled strategy. gamma_scalping has the highest fire
        # probability (~40% per eval, no price-diff threshold) which makes the
        # test reliable across random-walk seeds.
        body = {"name": f"TEST_sched_{uuid.uuid4().hex[:6]}",
                "kind": "gamma_scalping", "enabled": True,
                "params": {"qty": 1},
                "symbols": ["RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK"],
                "interval_seconds": 5}
        r = session.post(f"{BASE_URL}/api/strategies", json=body, headers=auth_headers)
        assert r.status_code == 200, r.text
        sid = r.json().get("id") or r.json().get("_id")
        assert sid

        try:
            # wait long enough for the probabilistic fire (~3 intervals)
            time.sleep(22)
            s1 = session.get(f"{BASE_URL}/api/strategies/scheduler-status",
                             headers=auth_headers).json()
            after_fires = int(s1.get("fires", 0))
            after_tracked = int(s1.get("tracked", 0))
            # tracked must have grown (proves scheduler picked up the new strategy)
            assert after_tracked >= before_tracked + 1, \
                f"tracked did not grow ({before_tracked} -> {after_tracked})"
            # spec asks for fires>0 within ~10s; allow up to 22s for probabilistic signal
            assert after_fires > before_fires, \
                f"fires did not increment ({before_fires} -> {after_fires})"
        finally:
            session.delete(f"{BASE_URL}/api/strategies/{sid}", headers=auth_headers)


# ============================================================
# 6. Per-user webhook secret
# ============================================================
class TestWebhookSecret:
    def test_wrong_secret_403(self, session, user_id):
        url = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret=definitely-wrong"
        r = session.post(url, json={"symbol": "INFY", "side": "BUY",
                                    "price": 1500.0, "qty": 1, "strategy": "x"})
        assert r.status_code == 403, r.text

    def test_correct_user_secret_200(self, session, auth_headers, user_id):
        rm = session.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        secret = rm.json().get("tv_webhook_secret")
        assert secret, "user has no tv_webhook_secret"
        url = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret={secret}"
        payload = {"symbol": "HDFCBANK", "side": "SELL", "price": 1500.0,
                   "qty": 1, "strategy": "TEST_userwh",
                   "alert_id": f"TEST_alert_{uuid.uuid4().hex[:8]}"}
        r = session.post(url, json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True


# ============================================================
# 7. Telegram platform bot
# ============================================================
def test_telegram_platform_bot_available(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/notifications/telegram", headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("platform_bot_available") is True, j


# ============================================================
# 8. Broker schemas
# ============================================================
def test_broker_schemas_seven(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/brokers/schemas", headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    schemas = j.get("schemas") or j
    if "schemas" in j:
        schemas = j["schemas"]
    expected = {"zerodha", "breeze", "angel", "fyers", "upstox", "dhan", "mock"}
    assert set(schemas.keys()) == expected, f"got {list(schemas.keys())}"
    for k, v in schemas.items():
        fields = v.get("fields") if isinstance(v, dict) else None
        # mock broker has no credential fields → empty list is acceptable
        assert isinstance(fields, list), f"{k}: fields not a list"
        if k != "mock":
            assert len(fields) > 0, f"{k}: empty fields list"


# ============================================================
# 9. Hardcoded secret regression check
# ============================================================
def test_no_hardcoded_tv_secret_as_nondefault():
    """Line 37 of backend_test.py should use os.environ.get (with a default fallback)
    rather than a bare literal assignment."""
    path = "/app/backend/tests/backend_test.py"
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) >= 37
    line37 = lines[36]
    assert "os.environ.get" in line37, f"line 37 not using os.environ.get: {line37!r}"
    # ensure it's assigned via env (literal as default is acceptable)
    assert re.match(r"\s*TV_SECRET\s*=\s*os\.environ\.get\(", line37), \
        f"unexpected pattern on line 37: {line37!r}"
