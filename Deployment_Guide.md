# Deployment Architecture & Project Guide

## 1. Project Directory Structure
This project uses a separated Backend (Python) and Frontend (React) architecture.

### `/backend` (Python FastAPI Server)
- **`server.py`**: The main entry point that starts the server and background tasks (tick engine, market data capture).
- **`/routers`**: Contains all the API endpoints (e.g., `/orders`, `/auth`, `/market`).
- **`/services`**: Contains the core algorithmic logic:
  - `live_feed_manager.py`: Manages WebSocket connections to brokers.
  - `market_data.py`: The Tick Engine that broadcasts live prices to the app.
  - `premium_matcher.py`: Matches Call and Put options based on user criteria.
  - `backtest.py`: The historical strategy backtesting engine.
- **`models.py` & `schemas.py`**: Defines the MySQL database tables and data validation structures.

### `/frontend` (React + Vite App)
- **`src/pages`**: Contains all the main UI screens (Dashboard, Strategies, Options Chain, etc.).
- **`src/components`**: Reusable UI elements (Status Bar, Modals, Tables).
- **`src/lib`**: Helper functions and API connection logic to talk to the backend.

---

## 2. Server Requirements for Hostinger VPS
To run this perfectly on a Hostinger VPS, you need a Linux server (Ubuntu 22.04 or 24.04 recommended) with the following installed:

1. **MySQL 8.0**
   - Create a database named `algo_trading_db`.
   - Update `backend/db.py` with the correct MySQL user/password.
2. **Python 3.11+**
   - Install backend requirements: `pip install -r backend/requirements.txt`.
   - Run the server using `uvicorn server:app --host 0.0.0.0 --port 8001`.
3. **Node.js 20+**
   - Install dependencies: `npm install` inside the `frontend` folder.
   - Build the static files: `npm run build`.
4. **Nginx**
   - Configure Nginx to serve the `frontend/dist` folder on port `80` (or `443` with SSL).
   - Configure an Nginx reverse proxy to forward any request starting with `/api` to the Python backend on `http://127.0.0.1:8001`.
5. **PM2 or Systemd**
   - Use PM2 (or a systemd service file) to run the Python backend in the background so it restarts automatically if the server reboots.

---

## 3. Resolving the Alice Blue IP Restriction
The error `{'stat': 'Not_Ok', 'emsg': 'IP restriction: You are not allowed to place the order'}` happens because Alice Blue requires your server's static IP to be whitelisted for API access.
Once your Hostinger server is set up, log into the [A3 Developer Portal](https://a3.aliceblueonline.com), go to your App settings, and add the **Hostinger VPS IPv4 address**.
