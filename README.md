# Traders Pro - Trading Terminal & Algorithmic Trading Platform

Traders Pro is an enterprise-grade algorithmic and discretionary trading platform built with a modern full-stack architecture featuring a high-performance **Python FastAPI backend** and a responsive **React.js frontend** styled with the signature Dark Charcoal (`#131722`) theme.

---

## 🚀 Quick Start (One-Click)

### Prerequisites
1. **Python 3.11+**: [Download Python](https://www.python.org/downloads/) *(Ensure "Add Python to PATH" is checked during install)*
2. **Node.js 18+ (LTS)**: [Download Node.js](https://nodejs.org/)
3. **MySQL Server**: (via XAMPP, WAMP, or standalone MySQL service) running on port `3306` with database `algo_trading_db`.

---

### Step 1: Install Dependencies
Double-click:
```bat
install.bat
```
*What this does automatically:*
- Verifies Python and Node.js versions.
- Generates `backend/.env` from template if not present.
- Upgrades `pip` and installs all backend Python packages from `backend/requirements.txt`.
- Installs all frontend npm packages with `--legacy-peer-deps`.
- Builds and prepares the frontend.

---

### Step 2: Launch the Terminal
Double-click:
```bat
run_app.bat
```
*What this does:*
- Spawns the **FastAPI Backend Server** at `http://localhost:8001` (Interactive API docs at `http://localhost:8001/docs`).
- Spawns the **React Frontend Application** at `http://localhost:3000`.

---

## 📁 Repository Structure

```
TRADING-TERMINAL-main/
├── install.bat                 # One-click installer for all dependencies
├── run_app.bat                 # One-click startup script for both servers
├── .gitignore                  # Git exclusion rules
│
├── backend/                    # Python FastAPI Engine
│   ├── server.py               # Main API application entrypoint
│   ├── requirements.txt        # Production Python dependencies
│   ├── .env.example            # Environment variables template
│   ├── config.py               # Configuration & settings
│   ├── database.py             # Database engine & session management
│   ├── models/                 # SQLAlchemy ORM models
│   ├── routers/                # API route controllers
│   ├── services/               # Core business services & broker connectors
│   └── data/                   # Market data files (CSVs, Parquets)
│
└── frontend/                   # React.js Terminal UI
    ├── package.json            # Node.js dependencies & scripts
    ├── public/                 # Static assets & index.html
    └── src/
        ├── App.js              # Application entry & navigation
        ├── components/         # Reusable widgets, tables, modals
        ├── pages/              # Module screens (TradingView, Option Chain, Scalping, etc.)
        └── services/           # Frontend API and WebSocket clients
```

---

## 🛠 Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, SQLAlchemy, aiomysql, PyMySQL, WebSockets, Pandas, PyArrow
- **Brokers Supported**: Alice Blue (`pya3`), Zerodha Kite (`kiteconnect`), Angel One (`smartapi-python`), Breeze (`breeze_connect`), Upstox, Dhan
- **Frontend**: React 18, React Router, Lucide Icons, Lightweight Charts, Tailwind CSS
- **Database**: MySQL (`algo_trading_db`)
