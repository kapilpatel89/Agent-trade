@echo off
title Nexus Crypto Survival Agent - Installation Setup
color 0B

echo ======================================================================
echo    NEXUS CRYPTO SURVIVAL AGENT - AUTOMATED INSTALLATION SETUP
echo ======================================================================
echo.

:: 1. Verify Python Installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [!] ERROR: Python is not detected in your system PATH.
    echo [!] Please install Python 3.10 or newer from https://www.python.org/
    echo [!] Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [*] Python detected:
python --version
echo.

:: 2. Upgrade pip
echo [*] Upgrading pip to latest version...
python -m pip install --upgrade pip --quiet
echo [+] pip is up to date.
echo.

:: 3. Install Requirements
echo [*] Installing required Python libraries from requirements.txt...
echo     - FastAPI ^& Uvicorn (Web Server ^& REST APIs)
echo     - Requests ^& BeautifulSoup4 (CoinDCX Market Data ^& Macro News Scraping)
echo     - Pandas ^& NumPy (High-Performance Technical Analysis ^& RSI/MACD)
echo     - Pydantic ^& Python-Dotenv (Validation ^& Configuration Management)
echo.

python -m pip install -r requirements.txt --disable-pip-version-check
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [!] Installation encountered errors. Please check your internet connection.
    pause
    exit /b 1
)

echo.
:: 4. Verify Essential Modules
echo [*] Verifying module imports...
python -c "import fastapi, uvicorn, requests, pandas, numpy, bs4, pydantic; print('[+] All core dependencies verified successfully!')"
if %errorlevel% neq 0 (
    color 0C
    echo [!] Verification failed. Some packages were not imported correctly.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo [+] INSTALLATION COMPLETE!
echo.
echo  To start the trading agent ^& dashboard, simply run:
echo      run.bat
echo.
echo  To connect via MCP (Model Context Protocol):
echo      python mcp_server.py
echo ======================================================================
echo.
pause
