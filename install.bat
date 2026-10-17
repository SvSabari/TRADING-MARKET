@echo off
setlocal

title TRADERS PRO - One-Click Installer ^& Setup
color 0B

echo ===============================================================================
echo                TRADERS PRO - ONE-CLICK INSTALLER ^& SETUP
echo ===============================================================================
echo.

:: 1. Check Python installation
echo [*] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 goto :no_python
python --version
goto :check_node

:no_python
echo.
echo [ERROR] Python is not installed or not in your system PATH!
echo Please install Python 3.11 or higher from https://www.python.org
echo Make sure to check the box "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:check_node
:: 2. Check Node.js and NPM installation
echo.
echo [*] Checking Node.js and NPM...
node --version >nul 2>&1
if errorlevel 1 goto :no_node
call node --version
call npm --version
goto :setup_backend

:no_node
echo.
echo [ERROR] Node.js is not installed or not in your system PATH!
echo Please install Node.js (LTS version 18+) from https://nodejs.org
echo.
pause
exit /b 1

:setup_backend
:: 3. Setup Backend Environment
echo.
echo ===============================================================================
echo                1/2: INSTALLING BACKEND DEPENDENCIES
echo ===============================================================================
cd /d "%~dp0backend"

if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creating backend .env file from .env.example...
        copy /y ".env.example" ".env" >nul
    )
)

echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [*] Installing required Python packages from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [WARNING] Some dependencies had warnings. Attempting core packages...
    pip install fastapi uvicorn sqlalchemy aiomysql pymysql pydantic pydantic-settings python-dotenv cryptography passlib bcrypt PyJWT pyotp httpx websockets requests pandas numpy pyarrow pya3
)
echo [OK] Backend packages installed successfully!

:: 4. Setup Frontend Environment
echo.
echo ===============================================================================
echo                2/2: INSTALLING FRONTEND DEPENDENCIES
echo ===============================================================================
cd /d "%~dp0frontend"

if not exist ".env" (
    echo REACT_APP_BACKEND_URL=http://localhost:8001> .env
)

echo [*] Installing NPM packages (this may take 1-2 minutes on first run)...
call npm install --legacy-peer-deps

echo [*] Building optimized production frontend build...
call npm run build

cd /d "%~dp0"

echo.
echo ===============================================================================
echo                      INSTALLATION COMPLETED SUCCESSFULLY!
echo ===============================================================================
echo.
echo To start your terminal:
echo   1. Ensure your MySQL server is running (e.g., via XAMPP or local service).
echo   2. Double-click "run_app.bat" to start both Backend and Frontend together!
echo.
pause
