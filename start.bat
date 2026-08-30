@echo off
title Nexus Crypto Survival Agent - CoinDCX & Telegram
color 0A

echo ======================================================================
echo    NEXUS CRYPTO TRADING ^& SURVIVAL AGENT (COINDCX REAL-WORLD)
echo ======================================================================
echo  * Host:            http://127.0.0.1:8000
echo  * Exchange:        CoinDCX Spot (340+ INR Pairs Scanned)
echo  * Telegram Bot:    @antigravitycode_bot
echo  * Mode:            Paper Trading (Real Prices, Realistic Execution)
echo  * Initial Capital: Rs. 1,000 INR (Compounding Enabled)
echo ======================================================================
echo.

:: Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] ERROR: Python is not found in your PATH. Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

echo [+] Checking Python version...
python --version

echo [+] Ensuring required dependencies are installed...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo.
echo ======================================================================
echo [+] Starting Nexus Trading Engine, Dynamic Scanner ^& Telegram Bot...
echo ======================================================================
echo.

if "%1"=="--mcp" (
    echo [+] Starting Nexus MCP Server on stdio...
    python mcp_server.py
) else (
    :: Run main.py which launches FastAPI server, background engine, and browser
    python main.py
)

pause
