@echo off
echo Starting Trading Terminal Backend...
cd backend
uvicorn server:app --reload --port 8001
pause
