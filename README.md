# Trader Pro - Architecture
Welcome to the Trader Pro repository. This project is built using modern, industry-standard full-stack architecture: a React.js frontend and a Python FastAPI backend.

## =ÿ¬‹ Project Organization
The repository is structured to strictly separate concerns:

### 1. /frontend (The User Interface)
Contains the entire React web application.
* /frontend/src/pages: Main screen layouts (Dashboard, Strategies, etc).
* /frontend/src/components: Reusable UI elements (QuickOrderPanel, Ticker).
* /frontend/public: Static assets (index.html with Trader Pro title).

### 2. /backend (The Engine & API)
Contains the Python FastAPI application (MongoDB, trading logic, broker connections).
* /backend/routers/: API endpoints.
* /backend/services/: Core business logic (live_feed_manager, strategy_scheduler, broker_router).

### 3. Other Folders
* /docs: Documentation, design guidelines, test reports.
* /data: Local data storage.
* /logs: System execution logs.

## =ÿ‡ﬁ Why is it structured this way?
This Frontend/Backend split is an industry requirement.
1. Security: The backend securely holds the API keys. The frontend only holds UI code.
2. Performance: Python processes high-frequency ticks and complex math (PYRO ALGO) in the background without freezing the UI.
