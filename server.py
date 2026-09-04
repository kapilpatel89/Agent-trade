import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import config
from core.trading_engine import TradingEngine

app = FastAPI(title="CoinDCX Crypto Survival Trading Agent", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Engine
engine = TradingEngine(initial_capital=config.DEFAULT_INITIAL_CAPITAL)

# Request Models
class SettingsUpdate(BaseModel):
    trading_mode: Optional[str] = None
    initial_capital: Optional[float] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    cycle_interval: Optional[int] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    ai_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None

class AITestRequest(BaseModel):
    provider: Optional[str] = None
    gemini_key: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_key: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None

class TelegramTestRequest(BaseModel):
    token: Optional[str] = None
    chat_id: Optional[str] = None

class ManualTradeRequest(BaseModel):
    market: str
    pair: str
    symbol: str
    side: str  # "buy" or "sell"
    position_id: Optional[str] = None

class OpportunityExecutionRequest(BaseModel):
    opportunity_id: str

class RadarAlertTestRequest(BaseModel):
    alert_type: str = "seller_overlap"  # "seller_overlap", "war_news", "correlation"

# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.get("/api/status")
def get_status():
    """Get complete dashboard overview state."""
    current_equity = engine.get_total_equity()
    total_trades = len(engine.trade_history)
    wins = len([t for t in engine.trade_history if t.get("net_pnl_inr", 0) > 0])
    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

    total_profit_inr = sum(t.get("net_pnl_inr", 0) for t in engine.trade_history)
    total_fees_inr = sum(t.get("fees_inr", 0) for t in engine.trade_history)

    stance = engine.latest_stance or engine.survival.determine_stance(
        current_equity=current_equity,
        threat_level=engine.latest_news_data.get("threat_level", 0),
        crypto_sentiment=engine.latest_news_data.get("crypto_sentiment", 0),
        win_rate=win_rate
    )

    return {
        "status": "online",
        "is_running": engine.is_running,
        "trading_mode": engine.trading_mode,
        "inr_cash": round(engine.inr_cash, 2),
        "total_equity": current_equity,
        "initial_capital": engine.survival.initial_capital,
        "net_pnl_inr": round(current_equity - engine.survival.initial_capital, 2),
        "net_pnl_pct": round(((current_equity - engine.survival.initial_capital) / engine.survival.initial_capital) * 100.0, 2),
        "health_pct": stance.get("health_pct", 100.0),
        "drawdown_pct": stance.get("drawdown_pct", 0.0),
        "stance": stance,
        "open_positions_count": len(engine.open_positions),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "total_profit_inr": round(total_profit_inr, 2),
        "total_fees_inr": round(total_fees_inr, 2),
        "last_cycle_time": engine.last_cycle_time,
        "tracked_pairs": config.TRACKED_PAIRS
    }

@app.get("/api/market/tickers")
def get_tickers():
    """Get active INR tickers from CoinDCX."""
    tickers = engine.coindcx.get_tickers()
    inr_tickers = [t for t in tickers if t.get("market", "").endswith("INR")]
    return {"tickers": inr_tickers, "all_count": len(tickers)}

@app.get("/api/market/candles")
def get_candles(pair: str = "I-BTC_INR", interval: str = "1h", limit: int = 60):
    """Fetch candlestick data for charting."""
    candles = engine.coindcx.get_candles(pair=pair, interval=interval, limit=limit)
    return {"pair": pair, "interval": interval, "candles": candles}

@app.get("/api/market/analysis")
def get_market_analysis():
    """Get latest technical analysis & decision breakdown."""
    return {
        "decisions": engine.latest_decisions,
        "stance": engine.latest_stance,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/api/news")
def get_news(force_refresh: bool = False):
    """Get real-time Geopolitical conflict & Crypto news radar."""
    news = engine.brain.news_engine.analyze(force_refresh=force_refresh)
    return news

@app.get("/api/thoughts")
def get_thoughts(limit: int = 50):
    """Get the live scrolling stream of agent thoughts."""
    thoughts = engine.brain.thought_history[-limit:]
    return {"thoughts": list(reversed(thoughts))}

@app.get("/api/positions")
def get_positions():
    """Get all active open positions."""
    return {"positions": engine.open_positions, "total_equity": engine.get_total_equity()}

@app.get("/api/trades")
def get_trades(limit: int = 50):
    """Get closed trade history and performance journal."""
    return {"trades": engine.trade_history[:limit]}

@app.post("/api/control/cycle")
def run_cycle_now():
    """Trigger an immediate analysis and trading cycle."""
    result = engine.run_cycle()
    return {"success": True, "result": result}

@app.post("/api/control/toggle-loop")
def toggle_loop():
    """Start or Stop the autonomous background runner."""
    if engine.is_running:
        engine.stop_background_loop()
    else:
        engine.start_background_loop()
    return {"is_running": engine.is_running}

@app.post("/api/control/emergency-liquidate")
def emergency_liquidate():
    """Emergency close all positions to 100% INR cash."""
    closed = engine.emergency_liquidate_all()
    return {"success": True, "closed_positions": closed, "inr_cash": engine.inr_cash}

@app.post("/api/control/reset-wallet")
def reset_wallet(payload: Optional[Dict[str, float]] = None):
    """Reset paper trading balance to ₹1,000 INR."""
    cap = payload.get("capital", 1000.0) if payload else 1000.0
    engine.reset_paper_capital(capital=cap)
    return {"success": True, "inr_cash": engine.inr_cash}

@app.get("/api/market/movers")
def get_market_movers(force_refresh: bool = False):
    """Get live scanned top gainers, volume leaders, and high-opportunity coins."""
    return engine.scanner.scan_all_inr_markets(force_refresh=force_refresh)

@app.get("/api/radar/overview")
def get_radar_overview(force_refresh: bool = False):
    """Get comprehensive Market Radar overview with orderbook depth, correlation, live sticks, and sentiment."""
    return engine.radar.build_radar_overview(force_refresh=force_refresh)

@app.get("/api/radar/opportunities")
def get_radar_opportunities(category: str = "all"):
    """
    Get categorized trade opportunities.
    Filters: all | correlation | orderbook | news_social | momentum | live_sticks
    """
    radar = engine.radar.build_radar_overview()
    all_opps = radar.get("opportunities", [])
    if category == "all" or not category:
        return {"category": "all", "total": len(all_opps), "opportunities": all_opps}
    
    filtered = [o for o in all_opps if o.get("category") == category]
    return {"category": category, "total": len(filtered), "opportunities": filtered}

@app.post("/api/trades/execute-opportunity")
def execute_opportunity(payload: OpportunityExecutionRequest):
    """1-Click execution for an opportunity identified by the Market Radar."""
    res = engine.execute_opportunity_trade(payload.opportunity_id)
    return res

@app.post("/api/radar/test-alert")
def trigger_radar_test_alert(payload: Optional[RadarAlertTestRequest] = None):
    """Trigger an instant smart Telegram alert (Seller Overlap, War News, or Correlation Opportunity)."""
    alert_type = payload.alert_type if payload else "seller_overlap"
    
    if alert_type == "seller_overlap":
        engine.telegram.send_orderbook_watchout_alert(
            symbol="BTC",
            status="SELLER_OVERLAPPING_BUYER",
            ask_pct=73.5,
            bid_pct=26.5,
            message="Ask walls actively pressing down into bid levels. Large sell blocks consuming buyers."
        )
        return {"success": True, "message": "Triggered Telegram alert: 'Bitcoin Seller Overlapping Buyer'"}
    
    elif alert_type == "war_news":
        engine.telegram.send_social_war_news_alert(
            headline="Geopolitical conflict & military defense mobilization spreading on X.com",
            threat_level=68,
            bias="DOWNWARD_BIAS",
            down_prob=76,
            advice="Capital preservation protocol active. Tighten stops, maintain INR cash reserves."
        )
        return {"success": True, "message": "Triggered Telegram alert: 'War News Spreading on X.com'"}
    
    elif alert_type == "correlation":
        engine.telegram.send_correlation_opportunity_alert(
            lead_coin="BTC",
            target_coin="SOL",
            lag_pct=2.45,
            target_price=14650.0,
            stop_loss=13900.0
        )
        return {"success": True, "message": "Triggered Telegram alert: 'SOL Sympathy Catch-up Opportunity'"}
    
    return {"success": False, "message": f"Unknown alert type: {alert_type}"}

@app.get("/api/telegram/status")
def get_telegram_status():
    """Check Telegram connection status."""
    has_token = bool(engine.telegram.bot_token)
    has_chat = bool(engine.telegram.chat_id)
    return {
        "bot_username": "@antigravitycode_bot",
        "has_token": has_token,
        "token_preview": f"{engine.telegram.bot_token[:8]}...{engine.telegram.bot_token[-6:]}" if has_token else "",
        "chat_id": engine.telegram.chat_id,
        "is_configured": has_token and has_chat
    }

@app.post("/api/telegram/detect-chat-id")
def detect_chat_id(payload: Optional[TelegramTestRequest] = None):
    """Auto-detect chat ID from recent messages sent to @antigravitycode_bot."""
    token = payload.token if payload and payload.token else engine.telegram.bot_token
    detected = engine.telegram.auto_detect_chat_id(token=token)
    if detected:
        engine.save_state()
        return {"success": True, "chat_id": detected, "message": f"Successfully detected Telegram Chat ID: {detected}"}
    return {
        "success": False,
        "message": "No messages found yet. Please open @antigravitycode_bot in Telegram and send /start or any message, then click Detect again."
    }

@app.post("/api/telegram/test")
def send_telegram_test(payload: Optional[TelegramTestRequest] = None):
    """Send test message to user's Telegram using provided or active credentials."""
    token = payload.token if payload and payload.token else engine.telegram.bot_token
    chat_id = payload.chat_id if payload and payload.chat_id else engine.telegram.chat_id

    result = engine.telegram.test_connection(token=token, chat_id=chat_id)
    if result.get("success"):
        engine.save_state()
    return result

@app.get("/api/ai/status")
def get_ai_status():
    """Get current AI brain provider status."""
    return engine.brain.llm.get_status()

@app.post("/api/ai/test")
def test_ai_connection(payload: Optional[AITestRequest] = None):
    """Test AI LLM generation with active or provided form credentials."""
    llm = engine.brain.llm

    provider = payload.provider if (payload and payload.provider) else llm.provider
    gemini_key = payload.gemini_key if (payload and payload.gemini_key is not None) else llm.gemini_key
    gemini_model = payload.gemini_model if (payload and payload.gemini_model is not None) else llm.gemini_model
    openai_key = payload.openai_key if (payload and payload.openai_key is not None) else llm.openai_key
    ollama_url = payload.ollama_url if (payload and payload.ollama_url is not None) else llm.ollama_url
    ollama_model = payload.ollama_model if (payload and payload.ollama_model is not None) else llm.ollama_model

    from core.llm_engine import LLMEngine
    tester = LLMEngine(
        provider=provider,
        gemini_key=gemini_key,
        gemini_model=gemini_model,
        openai_key=openai_key,
        ollama_url=ollama_url,
        ollama_model=ollama_model
    )

    test_prompt = "Explain in 1 razor-sharp sentence why trailing stop losses protect capital in high-volatility crypto swings."
    res = tester.generate_response(test_prompt)
    if res:
        model_used = tester.last_model_used or gemini_model or provider
        return {
            "success": True,
            "provider": provider,
            "model_used": model_used,
            "response": res
        }

    err_msg = tester.last_error or f"Could not connect to {provider.upper()} API. Please check your API key and connection."
    return {
        "success": False,
        "provider": provider,
        "message": err_msg
    }

@app.get("/api/settings")
def get_settings():
    """Get current configuration (without exposing secrets)."""
    has_keys = bool(engine.coindcx.api_key and engine.coindcx.api_secret)
    ai_status = engine.brain.llm.get_status()
    return {
        "trading_mode": engine.trading_mode,
        "initial_capital": engine.survival.initial_capital,
        "cycle_interval": engine.cycle_interval,
        "has_api_keys": has_keys,
        "api_key_preview": f"{engine.coindcx.api_key[:4]}...{engine.coindcx.api_key[-4:]}" if engine.coindcx.api_key else "",
        "telegram_bot_token": engine.telegram.bot_token,
        "telegram_chat_id": engine.telegram.chat_id,
        "ai_status": ai_status,
        "ai_provider": engine.brain.llm.provider,
        "gemini_api_key": engine.brain.llm.gemini_key,
        "gemini_model": engine.brain.llm.gemini_model,
        "openai_api_key": engine.brain.llm.openai_key,
        "ollama_url": engine.brain.llm.ollama_url,
        "ollama_model": engine.brain.llm.ollama_model
    }

@app.post("/api/control/settings")
def update_settings(settings: SettingsUpdate):
    """Update settings dynamically."""
    if settings.trading_mode:
        engine.trading_mode = settings.trading_mode
    if settings.initial_capital:
        engine.survival.initial_capital = settings.initial_capital
    if settings.cycle_interval:
        engine.cycle_interval = max(10, settings.cycle_interval)
    if settings.api_key and settings.api_secret:
        engine.coindcx.set_credentials(settings.api_key, settings.api_secret)
    if settings.telegram_bot_token is not None:
        engine.telegram.bot_token = settings.telegram_bot_token
        config.TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
    if settings.telegram_chat_id is not None:
        engine.telegram.chat_id = settings.telegram_chat_id
        config.TELEGRAM_CHAT_ID = settings.telegram_chat_id

    # Update Real AI Provider & Keys
    engine.brain.llm.update_credentials(
        provider=settings.ai_provider,
        gemini_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
        openai_key=settings.openai_api_key,
        ollama_url=settings.ollama_url,
        ollama_model=settings.ollama_model
    )

    engine.save_state()
    return {"success": True, "message": "Settings & AI Configuration updated successfully"}

# Mount Static Files for Dashboard Web UI
STATIC_DIR = config.BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.on_event("startup")
def startup_event():
    """Run an initial cycle on server boot and launch background loop."""
    print("[+] CoinDCX Crypto Trading & Survival Agent Server Starting...")
    engine.run_cycle()
    engine.start_background_loop()
