@echo off
echo ===================================================
echo   Traders Pro - Installation and Setup Script
echo ===================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.11+ and try again.
    pause
    exit /b
)

echo [INFO] Python found. Installing required backend packages...
cd backend
python -m pip install --upgrade pip
pip install fastapi uvicorn motor pymongo httpx python-dotenv pydantic pydantic-settings websockets sqlalchemy aiomysql pymysql pyjwt
cd ..

echo.
echo [INFO] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo ===================================================
echo   Setup Complete!
echo   To run the app:
echo   1. Start your local MySQL database (XAMPP/WAMP)
echo   2. Open one terminal and run: cd backend ^&^& python server.py
echo   3. Open another terminal and run: cd frontend ^&^& npm run dev
echo ===================================================
pause
