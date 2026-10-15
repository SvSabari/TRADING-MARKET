@echo off
title TRADERS PRO - Starting Services
color 0A

echo ===============================================================================
echo                TRADERS PRO - STARTING SERVICES
echo ===============================================================================
echo.

:: 1. Launch Backend Server in new window
echo [*] Starting Python Backend on http://localhost:8001 ...
start "Traders Pro - Backend API" cmd /k "cd /d "%~dp0backend" && python server.py"

:: 2. Wait 2 seconds
timeout /t 2 /nobreak >nul

:: 3. Launch Frontend Server in new window
echo [*] Starting React Frontend on http://localhost:3000 ...
start "Traders Pro - Frontend Terminal" cmd /k "cd /d "%~dp0frontend" && npm start"

echo.
echo [OK] Both Backend and Frontend have been launched in separate windows!
echo Terminal will be available at: http://localhost:3000
echo.
pause
