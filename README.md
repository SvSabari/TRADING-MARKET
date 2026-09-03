# Trading Terminal

Welcome to the Trading Terminal! This project consists of a React frontend and a FastAPI (Python) backend.

## Prerequisites

Before you begin, ensure you have the following installed on your system:
- **Node.js** (v16 or higher)
- **Yarn** or **npm** (Yarn is recommended)
- **Python** (3.8 or higher)
- **MongoDB** (Running locally on default port 27017)

---

## 1. Environment Setup

1. Copy the `.env.example` file and rename it to `.env` in the root directory:
   ```bash
   cp .env.example .env
   ```
2. Open the newly created `.env` file and fill in any necessary secrets (like `JWT_SECRET`, `ENCRYPTION_KEY`, etc.). The default values should work for local development.

---

## 2. Backend Setup (Local Development)

The backend is built with Python (FastAPI).

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the backend server:
   ```bash
   uvicorn server:app --reload --port 8001
   ```
   *(Ensure you run this from the backend directory, or use `run_backend.bat` if you are on Windows).*

---

## 3. Frontend Setup (Local Development)

The frontend is built with React.

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the Node modules:
   ```bash
   yarn install
   # or
   npm install
   ```
3. Start the frontend development server:
   ```bash
   yarn start
   # or
   npm start
   ```

---

## 4. Production Hosting & Deployment (For IT / Devops)

This application is ready to be hosted on production servers. You can deploy it using Docker (recommended) or manually.

### Option A: Deployment via Docker (Recommended)
The repository includes a `docker-compose.yml` and `Dockerfile`s for both the frontend and backend.
1. Update `docker-compose.yml` to set `REACT_APP_BACKEND_URL` to the public domain/IP of the backend API.
2. Provide secure strings for `JWT_SECRET` and `ENCRYPTION_KEY` in the environment.
3. Run the stack:
   ```bash
   docker-compose up -d --build
   ```
   *Note: This will spin up MongoDB, the FastAPI backend (port 8001), and an Nginx container serving the built React frontend (port 3000).*

### Option B: Manual Server Deployment (Without Docker)
If you are deploying directly to a Linux/Windows server without Docker:

**1. Database:**
Ensure a MongoDB instance is running and update `MONGO_URL` in the `.env` file to point to it.

**2. Backend (FastAPI):**
Instead of using `--reload`, run the backend behind a production WSGI/ASGI server like Gunicorn.
```bash
cd backend
pip install -r requirements.txt
# Run with Gunicorn using Uvicorn workers
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001
```

**3. Frontend (React):**
You must build the static files and serve them using a web server (like Nginx, Apache, or IIS).
```bash
cd frontend
# Set the backend URL for the build
export REACT_APP_BACKEND_URL=https://api.yourdomain.com
yarn install
yarn build
```
Copy the contents of the `frontend/build` folder to your web server's public directory. If using Nginx, ensure you route all traffic to `index.html` to support React Router.
