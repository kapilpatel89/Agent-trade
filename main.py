import sys
import os
import time
import webbrowser
import threading

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn

def open_browser():
    """Wait 1.5s for server to start, then open the browser."""
    time.sleep(1.5)
    url = "http://127.0.0.1:8000"
    print(f"\n[+] Opening Nexus Survival Agent Dashboard at: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not automatically open browser: {e}")

def main():
    print("""
    ======================================================================
    [+] NEXUS CRYPTO SURVIVAL AGENT | CoinDCX Autonomous Intelligence [+]
    ======================================================================
    * Host          : http://127.0.0.1:8000
    * Exchange API  : CoinDCX Spot & Public Market Data
    * Default Budget: Rs. 1,000 INR (Paper Simulation Mode)
    * News Feeds    : Geopolitical Conflict Radar & Crypto Breaking Feeds
    * Risk Model    : Survival-First Dynamic Trailing Stops (1:2.5 RR)
    ======================================================================
    """)

    # Launch browser thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Uvicorn Server
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    main()
