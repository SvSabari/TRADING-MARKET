"""End-to-end pytest suite for the Algonid (algo-trading) FastAPI backend.

Covers:
 - /api/health, auth (register, login, /me)
 - market data (symbols, snapshot, history, top-movers)
 - strategies CRUD + toggle
 - orders (place, list, positions, pnl-summary)
 - TradingView webhook-info, test-fire, raw webhook
 - signals/live, backtest/run
 - option chain analytics, OI heatmap, IV smile
 - brokers (connect zerodha mock + disconnect)
 - parquet status/files/preview
 - notifications (list, mark-all-read)
 - AI /ai/explain streaming (Claude Sonnet 4.5)
"""

import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback to reading frontend/.env directly
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
BASE_URL = (BASE_URL or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

TV_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "tv-webhook-secret-123")


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def demo_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "demo@trader.io", "password": "demo123"})
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data and "user" in data
    return data


@pytest.fixture(scope="session")
def auth_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token['access_token']}"}


@pytest.fixture(scope="session")
def user_id(demo_token):
    return demo_token["user"]["id"]


# ---------- Health ----------
def test_health(session):
    r = session.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["ticks_running"] is True


# ---------- Auth ----------
def test_register_and_login_new_user(session):
    email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
    r = session.post(f"{BASE_URL}/api/auth/register",
                     json={"email": email, "name": "Test User", "password": "pw123456"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["email"] == email
    assert data["access_token"]
    # login again
    r2 = session.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": "pw123456"})
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == email


def test_auth_me(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "demo@trader.io"


def test_auth_me_no_token(session):
    r = session.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code in (401, 403)


def test_login_bad_credentials(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "demo@trader.io", "password": "wrong"})
    assert r.status_code in (400, 401, 403)


# ---------- Market data ----------
def test_market_symbols(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/market/symbols", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    syms = body.get("symbols") or body.get("nifty50") or []
    assert len(syms) >= 40


def test_market_snapshot_50(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/market/snapshot", headers=auth_headers)
    assert r.status_code == 200
    ticks = r.json().get("ticks", [])
    assert len(ticks) == 50, f"expected 50 ticks got {len(ticks)}"
    t0 = ticks[0]
    for k in ("symbol", "ltp"):
        assert k in t0


def test_market_history(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/market/history/RELIANCE", headers=auth_headers)
    assert r.status_code == 200
    candles = r.json().get("candles", []) or r.json().get("history", [])
    assert isinstance(candles, list)
    assert len(candles) > 0


def test_top_movers(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/market/top-movers", headers=auth_headers)
    assert r.status_code == 200
    j = r.json()
    assert "gainers" in j and "losers" in j
    assert len(j["gainers"]) > 0 and len(j["losers"]) > 0


# ---------- Strategies CRUD ----------
def test_strategies_crud(session, auth_headers):
    # list initial
    r0 = session.get(f"{BASE_URL}/api/strategies", headers=auth_headers)
    assert r0.status_code == 200
    # create
    body = {"name": "TEST_EMA_RELI", "kind": "ema_crossover",
            "enabled": False, "params": {"fast": 9, "slow": 21},
            "symbols": ["RELIANCE", "HDFCBANK"]}
    r = session.post(f"{BASE_URL}/api/strategies", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    created = r.json()
    sid = created.get("id") or created.get("_id")
    assert sid, f"no id/_id in create response: {created}"
    # toggle enabled
    r2 = session.patch(f"{BASE_URL}/api/strategies/{sid}",
                       json={"enabled": True}, headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["enabled"] is True
    # delete
    r3 = session.delete(f"{BASE_URL}/api/strategies/{sid}", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["deleted"] == 1


# ---------- Orders + Positions + PnL ----------
def test_place_order_and_position(session, auth_headers):
    snap = session.get(f"{BASE_URL}/api/market/snapshot", headers=auth_headers).json()["ticks"]
    sym = next((t["symbol"] for t in snap if t["symbol"] == "RELIANCE"), snap[0]["symbol"])
    price = next(t["ltp"] for t in snap if t["symbol"] == sym)
    body = {"broker": "mock", "symbol": sym, "side": "BUY", "qty": 5,
            "price": price, "order_type": "MARKET", "product": "MIS"}
    r = session.post(f"{BASE_URL}/api/orders", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["status"].upper() in ("FILLED", "COMPLETE", "OPEN")
    assert order["symbol"] == sym
    # positions
    rp = session.get(f"{BASE_URL}/api/orders/positions", headers=auth_headers)
    assert rp.status_code == 200
    positions = rp.json()["positions"]
    assert any(p["symbol"] == sym and p["qty"] != 0 for p in positions)
    # pnl
    rs = session.get(f"{BASE_URL}/api/orders/pnl-summary", headers=auth_headers)
    assert rs.status_code == 200
    s = rs.json()
    for k in ("unrealized_pnl", "realized_pnl", "total_pnl", "trades"):
        assert k in s
    assert s["trades"] >= 1


def test_orders_list(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/orders", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json().get("orders"), list)


# ---------- TradingView ----------
def test_tv_webhook_info(session, auth_headers, user_id):
    r = session.get(f"{BASE_URL}/api/tradingview/webhook-info", headers=auth_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["user_id"] == user_id
    assert user_id in j["webhook_path"]
    assert j["secret"] == TV_SECRET


def test_tv_test_fire(session, auth_headers):
    payload = {"symbol": "RELIANCE", "side": "BUY", "price": 2890.5,
               "qty": 1, "strategy": "TEST_strategy"}
    r = session.post(f"{BASE_URL}/api/tradingview/test-fire",
                     json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True and "order_id" in j and "signal_id" in j


def test_tv_webhook_with_secret(session, user_id):
    payload = {"symbol": "HDFCBANK", "side": "SELL", "price": 1500.0,
               "qty": 2, "strategy": "TEST_webhook"}
    url = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret={TV_SECRET}"
    r = session.post(url, json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_tv_webhook_bad_secret(session, user_id):
    payload = {"symbol": "INFY", "side": "BUY", "price": 1500.0, "qty": 1}
    url = f"{BASE_URL}/api/tradingview/webhook/{user_id}?secret=bad"
    r = session.post(url, json=payload)
    assert r.status_code == 403


def test_tv_signals_list(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/tradingview/signals", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json().get("signals"), list)


# ---------- Signals + Backtest ----------
def test_signals_live(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/signals/live", headers=auth_headers)
    assert r.status_code == 200
    assert "signals" in r.json()


def test_backtest_run(session, auth_headers):
    body = {"strategy_kind": "ema_crossover", "symbol": "RELIANCE",
            "period_days": 30, "params": {"fast": 9, "slow": 21}}
    r = session.post(f"{BASE_URL}/api/backtest/run", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "metrics" in j and "equity_curve" in j
    assert isinstance(j["equity_curve"], list) and len(j["equity_curve"]) > 0


# ---------- Option chain ----------
def test_option_chain(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/analytics/option-chain", headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("spot", "atm", "pcr", "max_pain", "rows"):
        assert k in j, f"missing {k}"
    assert len(j["rows"]) == 31, f"expected 31 strikes got {len(j['rows'])}"


def test_oi_heatmap(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/analytics/oi-heatmap", headers=auth_headers)
    assert r.status_code == 200


def test_iv_smile(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/analytics/iv-smile", headers=auth_headers)
    assert r.status_code == 200


# ---------- Brokers ----------
def test_broker_connect_disconnect(session, auth_headers):
    r = session.post(f"{BASE_URL}/api/brokers",
                     json={"broker": "zerodha", "mock_mode": True,
                           "api_key": "", "api_secret": ""},
                     headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["broker"] == "zerodha" and j["connected"] is True
    rl = session.get(f"{BASE_URL}/api/brokers", headers=auth_headers)
    assert rl.status_code == 200
    assert any(c["broker"] == "zerodha" for c in rl.json()["connections"])
    rd = session.delete(f"{BASE_URL}/api/brokers/zerodha", headers=auth_headers)
    assert rd.status_code == 200
    assert rd.json()["deleted"] == 1


# ---------- Parquet ----------
def test_parquet_status(session, auth_headers):
    r = session.get(f"{BASE_URL}/api/parquet/status", headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("running") is True
    assert j.get("interval_seconds") == 5


def test_parquet_files_and_preview(session, auth_headers):
    # wait a moment to ensure flush happened
    time.sleep(6)
    r = session.get(f"{BASE_URL}/api/parquet/files", headers=auth_headers)
    assert r.status_code == 200
    files = r.json()["files"]
    if not files:
        pytest.skip("No parquet files yet (capture may be warming up)")
    p = files[0]["path"]
    rp = session.get(f"{BASE_URL}/api/parquet/preview",
                     params={"path": p, "limit": 5}, headers=auth_headers)
    assert rp.status_code == 200, rp.text
    assert "rows" in rp.json()


# ---------- Notifications ----------
def test_notifications_flow(session, auth_headers):
    # ensure at least one notification by firing a TV test alert
    session.post(f"{BASE_URL}/api/tradingview/test-fire",
                 json={"symbol": "TCS", "side": "BUY", "price": 4000.0,
                       "qty": 1, "strategy": "TEST_notif"},
                 headers=auth_headers)
    r = session.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
    assert r.status_code == 200
    j = r.json()
    assert "notifications" in j or "items" in j or isinstance(j, list)
    # mark all read
    r2 = session.post(f"{BASE_URL}/api/notifications/read-all", headers=auth_headers)
    assert r2.status_code == 200
    # verify unread=0
    r3 = session.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
    assert r3.status_code == 200
    body = r3.json()
    if isinstance(body, dict) and "unread" in body:
        assert body["unread"] == 0


# ---------- AI streaming ----------
def test_ai_explain_stream(auth_headers):
    url = f"{BASE_URL}/api/ai/explain"
    body = {"prompt": "Explain Nifty 50 in one short sentence."}
    r = requests.post(url, json=body, headers={**auth_headers, "Content-Type": "application/json"},
                      stream=True, timeout=60)
    assert r.status_code == 200, r.text[:200]
    chunks = []
    for chunk in r.iter_content(chunk_size=64, decode_unicode=True):
        if chunk:
            chunks.append(chunk)
        if sum(len(c) for c in chunks) > 20:
            break
    r.close()
    text = "".join(chunks)
    assert len(text) > 0, "AI returned empty stream"
