# Algonid · Algo Trading Platform — PRD

_Last updated: 2026-02-06_

## Problem statement (verbatim from user)
> I want to build a Algo trading App which uses my customised Tradingview indicator
> alerts for buy and sell, and the option to backup the volume of individual nifty 50
> stocks in a 5 secs timeframe separately in a folder as a paraquet file for data
> analysis. Full architecture (broker abstraction, indicators, signals, strategies,
> execution, portfolio, options analytics, backtesting, AI engine, alerts) was provided.

## User choices (Phase-1)
1. **Scope** — All features (lightweight depth)
2. **Brokers** — Broker-agnostic / hybrid; all routed to MockBroker for now
3. **Market data** — Mock tick generator (broker WebSocket pluggable later)
4. **TradingView alerts** — Webhook accepting JSON `{symbol, side, price, qty, strategy}`
5. **AI** — Claude Sonnet 4.5 via Emergent universal LLM key
6. **Alerts** — In-app notifications only
7. **Auth** — Multi-user JWT login

## Architecture (built)
- **Backend** FastAPI + Motor (MongoDB), all routes under `/api`.
  - `services/market_data.py` — `TickEngine` (1s random-walk ticks for 50 Nifty stocks)
  - `services/parquet_capture.py` — 5-sec OHLCV → `/app/data/parquet/<DATE>/<SYMBOL>.parquet`
  - `services/broker_router.py` — pluggable broker abstraction (all mocked)
  - `services/options_analytics.py` — synthetic option chain + PCR + max-pain + OI / IV
  - `services/signals.py` — buildup / trap / breakout / reversal heuristic engine
  - `services/backtest.py` — synthetic walk-forward backtester
  - `services/ai_engine.py` — Claude Sonnet 4.5 streaming via `emergentintegrations`
  - Routers: auth, market, tradingview, orders, strategies, analytics, signals,
    backtest, brokers, parquet, notifications, ai
- **Frontend** React + craco, Tailwind, recharts, phosphor-icons, sonner.
  Routes: `/login`, `/register`, `/` Dashboard, `/signals`, `/tradingview`,
  `/strategies`, `/option-chain`, `/positions`, `/orders`, `/backtest`,
  `/parquet`, `/ai`, `/brokers`, `/settings`, `/notifications`.
  Theme: Neo-Brutalist financial terminal — pure-black canvas, grain grid,
  Chivo + IBM Plex Sans + JetBrains Mono, neon-green buy / red sell accents.

## What's been implemented (2026-06-09)
- [x] JWT auth (register, login, /auth/me) + persistent React AuthContext
- [x] Sidebar / Topbar / StatusBar layout with live Nifty ticker
- [x] Tick engine running on FastAPI lifespan (1s ticks for 50 symbols)
- [x] Parquet capture running on lifespan (5-sec buckets, 50 files/day, ~720 rows/day)
- [x] Parquet file browser + preview + download
- [x] TradingView webhook endpoint + test-fire button + signal history
- [x] Manual order pad + executions feed
- [x] Live positions + total P&L (recomputed every 2s against latest LTPs)
- [x] Option chain (ATM ± 15 strikes), OI heatmap, IV smile, PCR, Max Pain
- [x] Live signal engine (buildups, traps, breakouts, reversals)
- [x] Strategy manager (create, toggle, delete) — 5 strategy kinds
- [x] Backtest lab with equity curve + metrics + history
- [x] Broker connections page (Zerodha / Breeze / Angel, mock mode)
- [x] AI assistant with streaming Claude Sonnet 4.5 responses
- [x] In-app notifications with unread counter
- [x] 27/27 backend pytest tests passing; UI smoke-tested end-to-end

## Phase 2 (2026-06-09)
- [x] **Zerodha Kite Connect** — OAuth flow (`/api/brokers/kite/login-url`, `/api/brokers/kite/callback`), per-user encrypted (Fernet) credentials, daily access-token storage, automatic fallback to MockBroker when not connected. `route_order()` chooses Kite vs Mock per call.
- [x] **Live option chain** — `services/options_analytics.py` tries Kite `quote()` for NIFTY ATM±15 weekly strikes first; falls back to synthetic. Endpoint returns a `source` field (kite-live / synthetic).
- [x] **Strategy execution scheduler** — `services/strategy_scheduler.py` background loop. Each strategy carries `params.interval_seconds` (configurable per strategy, min 5, default 15). When toggled RUNNING, the scheduler fires paper orders + notifications + Telegram messages. `fire_count` + `last_fire_at` tracked.
- [x] **Telegram alerts** — `services/telegram.py` via httpx; per-user `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` saved encrypted; Settings page UI with BotFather instructions, test-send button. Hooked into TV alerts, manual orders, and strategy fires.
- [x] **Idempotency** — `services/idempotency.py`: uses TV payload's `alert_id` field with smart fallback to `symbol+side+price+minute`. Backed by Mongo unique index + 24h TTL. Duplicate POSTs return `{duplicate:true}` with the original signal/order ids — no double-execution.
- [x] 16/16 new phase-2 tests passing + 27/27 phase-1 regression. Encryption-at-rest verified (`gAAAA…` Fernet tokens in DB).

## Phase 3 (2026-06-09)
- [x] **Generic broker tabs** — `services/broker_schemas.py` defines per-broker field schemas (Zerodha 2 fields, Breeze 3, Angel 4, Fyers 2, Upstox 2, Dhan 2, Mock 0). UI dynamically renders the right form for each broker (`api_key`/`api_secret`/`session_token`/`client_code`/`pin`/`totp_secret`/`client_id`/`access_token`). All credential values encrypted via Fernet at rest in `BrokerConnection.credentials` map.
- [x] **Platform Telegram bot** — `TELEGRAM_BOT_TOKEN` set in `backend/.env`; `services/telegram.resolve_token()` falls back to the platform bot when a user has only provided a `chat_id`. UI shows a green "Platform bot available" hint.
- [x] **Per-user TradingView webhook secret** — `User.tv_webhook_secret` auto-generated at register, returned in login + `/auth/me`. Per-user secret enforced in webhook endpoint. UI exposes rotate-secret button.
- [x] **Black-Scholes IV + Greeks** — `services/greeks.py` Newton-Raphson IV with bisection fallback for deep ITM/OTM strikes; analytical delta/gamma/theta/vega/rho. `_compute_iv_and_greeks` always populates greeks dicts (guaranteed coverage). `GET /api/analytics/greeks/{strike}` exposes per-strike Greeks. UI: Δ columns in chain + ATM Greeks card.
- [x] **Real backtester** — `services/backtest.py` reads `/app/data/parquet/<DATE>/<SYMBOL>.parquet` (5-sec OHLCV), resamples to 1-min, runs per-kind signal generators (EMA crossover, VWAP scalp, OI breakout, smart-money, gamma-scalp ATR fade), simulates next-bar-open fills with full position lifecycle (entry / MTM / exit / pnl). Returns `data_source: parquet|synthetic`, equity_curve (downsampled to ≤200 pts), trades_log (last 50), and Sharpe normalized to 1-min bars. Falls back to synthetic walk-forward when no parquet data.
- [x] 20/21 phase-3 tests passing on first run; testing agent found the deep-ITM/OTM Greeks-missing bug → fixed via bisection fallback. Phase-1 + Phase-2 (43/43) regression all green.

## Phase 4 — Code-review cleanup (2026-06-09)
- [x] **Hardcoded secret removed** — `tests/backend_test.py` now reads `TV_SECRET` from `os.environ.get("TV_WEBHOOK_SECRET", …)`.
- [x] **Server-side logout** — `POST /api/auth/logout` adds the bearer to a `token_blacklist` MongoDB collection with a TTL index on `expires_at`. `get_current_user` rejects revoked tokens with 401 "Token revoked".
- [x] **JWT uniqueness** — `create_access_token` now adds `iat` + `jti=uuid4().hex` so two logins within the same second produce different tokens (fixes the logout-then-immediate-re-login race surfaced by testing agent).
- [x] **Backtest refactor** — `_simulate()` (was 80 lines, cyclomatic-21) split into `SimState` dataclass + `_mark_to_market` / `_close_position` / `_open_position` helpers in `services/backtest.py` + `services/sim_state.py`.
- [x] **Full component refactor** —
   - `Dashboard.jsx` → `LivePriceChart`, `MoversTable`, `SignalsFeed`, `usePolling` hook
   - `Brokers.jsx` → `BrokerForm`, `ConnectionsTable`, `useBrokerManagement` hook
   - `OptionChain.jsx` → `OIHeatmapChart`, `IVSmileChart`, `ChainTable`, `GreeksGrid` (chart-prop memoization via `useMemo`)
- [x] **Error handling** — every `catch (_) { /* ignore */ }` replaced with `catch (e) { console.error(...) }`.
- [x] **Stable React keys** — array-index keys replaced with composite stable keys (e.g. `${s.symbol}-${s.kind}-${s.ts}`).
- [x] 24/24 phase-4 tests pass (logout/blacklist, backtest refactor, 12 strategy/symbol combos, regression). Phase-1 + Phase-2 + Phase-3 (63/64) all still green.

## Phase 5 — Android app via Capacitor (2026-06-09)
- [x] **Capacitor wrapper** — `frontend/capacitor.config.ts` with `appId=io.algonid.app`. Capacitor packages installed: `@capacitor/{core,cli,android,push-notifications,preferences,app}`.
- [x] **Push notifications (FCM)** — `services/push_fcm.py` posts to FCM HTTP API using `FCM_SERVER_KEY` env var; no-ops gracefully when key absent. `/notifications/push/{register,unregister,preferences,test}` endpoints. Auto-enable on first device registration.
- [x] **User toggle UI** — `Settings.jsx` has a dedicated "Push notifications" panel with: enable/disable checkbox, device-count display, "Send test push" button, FCM-not-configured warning. Toggle is disabled in browser (only enabled when running inside the native Android shell — detected via `window.Capacitor.isNativePlatform()`).
- [x] **Push hooks** — TradingView webhook fires, manual orders, and strategy scheduler now also send FCM pushes alongside Telegram messages.
- [x] **Build instructions** — `/app/android/BUILD.md` covers prereqs (Android Studio, Java 17), Capacitor sync, signed APK generation, and Firebase setup steps for getting `FCM_SERVER_KEY` + `google-services.json`.

## Phase 6 — Biometric login (2026-06-09)
- [x] **`capacitor-native-biometric`** installed and wrapped at `frontend/src/lib/biometric.js`. Credentials stored in the device's AndroidKeystore via the plugin — never sent to the server.
- [x] **Login page** auto-detects biometric availability + saved credentials and shows "Sign in with biometrics" CTA. On first manual login (native only), prompts to enable biometric login by saving creds.
- [x] **Settings** has a dedicated "Biometric login" panel with status, biometry type (fingerprint/face), and "Forget device credentials" button.
- [x] **Logout** clears biometric credentials so a different user can sign in cleanly on the same device.

## Phase 7 — Live broker WS + Claude deep-wire + real-broker scaffolding (2026-02-06)
- [x] **Live broker WebSocket infrastructure** — `services/feeds/{kite,upstox,angel}_feed.py` per-broker adapters with a uniform `LiveFeed` interface (`base.py`). `services/live_feed_manager.py` polls broker_connections every 30s and starts the highest-priority connected feed; pipes ticks into `tick_engine.push_live_tick(symbol, ltp, volume_delta)`. `services/instrument_map.py` carries Nifty 50 token/key maps for Kite/Upstox/Angel.
- [x] **TickEngine fusion** — `TickEngine` now tracks `live_source` + `live_symbols` set. Synthetic loop *skips* any symbol that received a live tick in the last 3s. `GET /api/market/feed-status` exposes current source + symbol count. Snapshot endpoint adds `live:bool` per symbol.
- [x] **Status bar feed indicator** — bottom status bar shows `FEED·SYNTHETIC` (yellow) or `FEED·ZERODHA · 50/50` (green) per current state.
- [x] **Claude trade-explainer** — `services/ai_engine.explain_signal()` returns structured `{reasoning, suggested_sl, suggested_target, risk_reward, confidence_score, side_bias, model}`. `POST /api/ai/explain-signal` exposes it. Frontend: Brain icon on every Signals row + `SignalExplainModal.jsx` overlay. Direction-aware fallback (SELL bias → SL above, target below).
- [x] **Anomaly sweep** — `services/anomaly_sweep.py` background task: every 60s, picks 3 symbols (10-min cooldown each), feeds 30 × 5s bars to Claude via `analyse_window()`. Medium/high severity → Notification row. `GET /api/ai/anomaly-sweep/status` for diagnostics.
- [x] **Real broker SDK wrappers** — `services/brokers/{angel,upstox,dhan,breeze}_client.py`. Angel uses TOTP via `pyotp`. Upstox uses OAuth + Place-Order v3. Dhan uses static token + place_order. Breeze uses generate_session + place_order. All four wired into `services/broker_router.route_order` with mock-fallback if no live creds.
- [x] **Broker UI flows** — `POST /api/brokers/angel/login` runs TOTP session generation; `GET /api/brokers/upstox/login-url` + `/upstox/callback` complete OAuth exchange. UI on `/brokers` page shows "Generate Angel session (TOTP)" and "Complete Upstox OAuth" buttons per active tab.
- [x] **Tests** — `tests/test_phase5.py` 19/19 pass. Frontend end-to-end Claude signal-explain modal verified with real LLM response. All previous regressions green.

## Backlog
### P0 (next user iteration)
- Wire real broker option-chain feeds (Kite OI + IV ladders) into `services/options_analytics.py`
- Position close + bracket orders (SL/target as second-leg orders, not just paper SL)

### P1
- Walk-forward optimizer + per-strategy parameter grid search
- Multi-asset (Bank Nifty, Fin Nifty, individual options instruments)
- Per-user anomaly-sweep targeting (currently notifies the first broker_connections user globally)
- urlencode the Upstox OAuth URL builder (minor — works for ASCII keys)

### P2
- AI signal ranking, anomaly detection, market regime classification
- Greeks calculator (real) + gamma exposure dashboard
- Walk-forward optimizer + strategy parameter grid search
- Docker compose + k8s deployment manifests
- Multi-asset support (Bank Nifty, Fin Nifty, individual options instruments)

## Test credentials
See `/app/memory/test_credentials.md`.
