@echo off
title Nexus Crypto Survival Agent - Live Trading System
color 0A

echo ======================================================================
echo    NEXUS CRYPTO TRADING ^& SURVIVAL AGENT (COINDCX REAL-WORLD)
echo ======================================================================
echo  * Local Dashboard:  http://127.0.0.1:8000
echo  * Market Coverage:  CoinDCX Spot (340+ INR Pairs Scanned)
echo  * Execution Mode:   Autonomous Paper Trading (Real Market Prices)
echo  * Default Capital:  Rs. 1,000 INR (Compounding Enabled)
echo  * Telegram Bot:     @antigravitycode_bot
echo ======================================================================
echo.

:: Verify Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [!] ERROR: Python is not found in your PATH. Run install.bat first.
    pause
    exit /b 1
)

:: Check if dependencies are installed
python -c "import fastapi, pandas, requests" >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Dependencies not found. Running automated installation...
    call install.bat
)

if "%1"=="--mcp" (
    echo [+] Starting Nexus Model Context Protocol (MCP) Server on stdio...
    python mcp_server.py
) else (
    echo [+] Launching Nexus Web Server, Market Scanner ^& Background Engine...
    python main.py
)

pause
