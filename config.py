import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# File Paths for Persistence
STATE_FILE = DATA_DIR / "agent_state.json"
TRADE_HISTORY_FILE = DATA_DIR / "trade_history.json"
THOUGHT_LOGS_FILE = DATA_DIR / "thought_logs.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# CoinDCX API Endpoints
COINDCX_BASE_URL = "https://api.coindcx.com"
COINDCX_PUBLIC_URL = "https://public.coindcx.com"

# API Credentials (can be set via environment or loaded from settings)
COINDCX_API_KEY = os.getenv("COINDCX_API_KEY", "")
COINDCX_API_SECRET = os.getenv("COINDCX_API_SECRET", "")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8249092590:AAH66Fgi5Q8s9B09NH5DQxfJ3vE9-QwJgcI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_NOTIFICATIONS_ENABLED = True

# Real AI Provider Configuration (Gemini, OpenAI, Ollama, Quantitative)
AI_PROVIDER = os.getenv("AI_PROVIDER", "quantitative")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Default Trading & Survival Settings
DEFAULT_INITIAL_CAPITAL = 1000.0  # ₹1,000 INR starting capital
DEFAULT_TRADING_MODE = "paper"     # "paper" or "live"
DEFAULT_CYCLE_INTERVAL = 30        # Seconds between analysis/trading cycles

# Dynamic Scanner Configuration
DYNAMIC_SCANNER_ENABLED = True
SCANNER_MIN_24H_VOLUME_INR = 25000.0  # Filter out illiquid markets (min ₹25K 24h volume)
SCANNER_MAX_CANDIDATES = 12           # Top N high-momentum candidate pairs evaluated per cycle

# CoinDCX Official Fee Schedule & Indian Crypto Tax Rules (https://coindcx.com/fees/0 and /fees/1)
COINDCX_SPOT_MAKER_FEE = 0.002        # 0.20% Spot Maker Fee
COINDCX_SPOT_TAKER_FEE = 0.002        # 0.20% Spot Taker Fee
COINDCX_GST_ON_FEE = 0.18             # 18% GST applied on platform trading fees
COINDCX_EFFECTIVE_FEE = 0.00236       # 0.20% * (1 + 0.18) = 0.236% total trading fee per order
COINDCX_TDS_ON_SELL = 0.01            # 1.0% Indian Govt TDS on gross crypto sell orders (Section 194S)
COINDCX_INR_WITHDRAWAL_FEE = 0.0      # INR Bank Withdrawals are FREE (Min withdrawal ₹100)
COINDCX_MIN_INR_WITHDRAWAL = 100.0    # Min INR withdrawal amount

# Crypto Network Withdrawal Fees (https://coindcx.com/fees/1)
COINDCX_CRYPTO_WITHDRAWAL_FEES = {
    "BTC": 0.0005,
    "ETH": 0.003,
    "SOL": 0.01,
    "XRP": 0.25,
    "DOGE": 5.0,
    "ADA": 1.0,
    "USDT": 1.0,
}

# Default Risk Management & Profit Compounding
DEFAULT_MAX_RISK_PER_TRADE = 0.15  # Max 15% of current equity per trade (dynamic compounding)
DEFAULT_MIN_ORDER_INR = 100.0      # Minimum CoinDCX order notional is ₹100 INR
DEFAULT_STOP_LOSS_PCT = 0.02       # 2.0% Stop Loss
DEFAULT_TAKE_PROFIT_1_PCT = 0.04   # 4.0% TP1 (1:2 RR)
DEFAULT_TAKE_PROFIT_2_PCT = 0.08   # 8.0% TP2 (1:4 RR)
DEFAULT_TRAILING_STOP_PCT = 0.015  # 1.5% Trailing Stop

# Futures / Short Selling Configuration (CoinDCX Derivatives)
ENABLE_FUTURES_SHORTING = False     # Default: UNCHECKED / DISABLED (100% Spot preservation by default)
FUTURES_DEFAULT_LEVERAGE = 2        # Default 2x leverage when enabled
FUTURES_MAX_LEVERAGE = 5            # Cap at 5x for safety
FUTURES_MAX_SHORT_ALLOCATION = 0.15 # Max 15% equity per short trade
COINDCX_FUTURES_TAKER_FEE = 0.0005  # 0.05% Futures Taker Fee


# Base Tracked CoinDCX INR Trading Pairs (Major anchors)
BASE_TRACKED_PAIRS = [
    {"market": "BTCINR", "pair": "I-BTC_INR", "name": "Bitcoin", "symbol": "BTC"},
    {"market": "ETHINR", "pair": "I-ETH_INR", "name": "Ethereum", "symbol": "ETH"},
    {"market": "SOLINR", "pair": "I-SOL_INR", "name": "Solana", "symbol": "SOL"},
    {"market": "DOGEINR", "pair": "I-DOGE_INR", "name": "Dogecoin", "symbol": "DOGE"},
    {"market": "XRPINR", "pair": "I-XRP_INR", "name": "Ripple", "symbol": "XRP"},
    {"market": "ADAINR", "pair": "I-ADA_INR", "name": "Cardano", "symbol": "ADA"},
]

TRACKED_PAIRS = BASE_TRACKED_PAIRS.copy()

# RSS News Feeds
NEWS_FEEDS = {
    "crypto_cointelegraph": "https://cointelegraph.com/rss",
    "crypto_google": "https://news.google.com/rss/search?q=crypto+bitcoin+ethereum&hl=en-IN&gl=IN&ceid=IN:en",
    "geopolitics_conflict": "https://news.google.com/rss/search?q=global+conflict+war+geopolitics+sanctions+oil&hl=en-IN&gl=IN&ceid=IN:en",
    "macro_finance": "https://news.google.com/rss/search?q=inflation+interest+rates+fed+rbi+economy&hl=en-IN&gl=IN&ceid=IN:en",
}
