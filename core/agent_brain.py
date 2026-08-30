import time
from typing import Dict, Any, List, Optional
from core.ta_engine import TechnicalAnalysisEngine
from core.news_engine import NewsAndConflictEngine
from core.survival_manager import SurvivalManager
from core.llm_engine import LLMEngine

class AgentBrain:
    """
    Autonomous Multi-Factor Real AI Decision Brain.
    Synthesizes Real-Time LLM reasoning, Technicals, Macro/Conflict News,
    Orderbook, and Survival Stance to produce intelligent trading signals and live thought logs.
    """

    def __init__(self, survival_manager: SurvivalManager):
        self.survival = survival_manager
        self.ta_engine = TechnicalAnalysisEngine()
        self.news_engine = NewsAndConflictEngine()
        self.llm = LLMEngine()
        self.thought_history: List[Dict[str, Any]] = []

    def log_thought(self, category: str, title: str, details: str, level: str = "info", pair: str = "GLOBAL"):
        """Append a structured thought to the agent's live stream."""
        thought = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,      # "SURVIVAL", "MACRO_NEWS", "TECHNICAL", "DECISION", "EXECUTION"
            "title": title,
            "details": details,
            "level": level,            # "info", "success", "warning", "danger"
            "pair": pair
        }
        self.thought_history.append(thought)
        # Keep last 150 thoughts
        if len(self.thought_history) > 150:
            self.thought_history = self.thought_history[-150:]
        return thought

    def evaluate_pair(
        self,
        pair_info: Dict[str, Any],
        candles: List[Dict[str, Any]],
        ticker: Optional[Dict[str, Any]],
        orderbook: Optional[Dict[str, Any]],
        news_analysis: Dict[str, Any],
        stance_info: Dict[str, Any],
        open_positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Comprehensive multi-step evaluation for a specific crypto pair (e.g. BTCINR).
        """
        market = pair_info["market"]
        pair = pair_info["pair"]
        symbol = pair_info["symbol"]

        # Step 1: Technical Analysis
        ta = self.ta_engine.analyze(candles)
        if ta.get("status") != "success":
            return {
                "pair": pair,
                "market": market,
                "action": "HOLD",
                "confidence": 0,
                "reason": "Insufficient candle data for technical calculation"
            }

        current_price = ta["current_price"]
        ta_score = ta["score"]
        threat_level = news_analysis.get("threat_level", 0)
        crypto_sentiment = news_analysis.get("crypto_sentiment", 0)

        # Check if already holding this pair
        already_holding = any(p.get("market") == market for p in open_positions)

        # Step 2: Macro & Conflict Factor Weighting
        # In elevated threat conditions, penalize technical score
        macro_penalty = 0
        if threat_level >= 70:
            macro_penalty = -40
        elif threat_level >= 45:
            macro_penalty = -20

        # Adjust score with news sentiment
        sentiment_bonus = int(crypto_sentiment * 0.25)
        composite_score = max(-100, min(100, ta_score + macro_penalty + sentiment_bonus))

        # Step 3: Check Orderbook Liquidity & Spread
        spread_ok = True
        bid_ask_spread_pct = 0.0
        if ticker:
            bid = float(ticker.get("bid", 0) or 0)
            ask = float(ticker.get("ask", 0) or 0)
            if bid > 0 and ask > 0:
                bid_ask_spread_pct = round(((ask - bid) / ask) * 100.0, 3)
                if bid_ask_spread_pct > 1.5:  # Spread too wide for safe scalp
                    spread_ok = False

        # Step 4: Survival Stance Decision Gate
        min_required_score = stance_info["min_score_to_buy"]
        current_positions_count = len(open_positions)
        max_allowed_positions = stance_info["max_positions"]

        decision_action = "HOLD"
        confidence = 0
        thesis_points = []

        thesis_points.append(f"📊 Technical Score: {ta_score:+d}/100 (RSI: {ta['rsi']}, MACD: {ta['macd_hist']:+.2f}, EMA: {ta['ema9']:.1f}/{ta['ema21']:.1f})")
        thesis_points.append(f"🌍 Macro Threat Level: {threat_level}/100 ({news_analysis.get('threat_status')}) | Sentiment: {crypto_sentiment:+d}")

        if ta["patterns"]:
            thesis_points.append(f"🕯️ Patterns: {', '.join(ta['patterns'])}")

        # Decision Logic for BUY
        if not already_holding and current_positions_count < max_allowed_positions:
            if stance_info["stance"] == SurvivalManager.STANCE_BUNKER:
                thesis_points.append("🛡️ Bunker Mode Active: All entries blocked for capital defense.")
            elif not spread_ok:
                thesis_points.append(f"⚠️ Bid/Ask spread too wide ({bid_ask_spread_pct:.2f}% > 1.5%) - Skipping.")
            elif composite_score >= min_required_score:
                decision_action = "BUY"
                confidence = min(95, max(50, int(50 + (composite_score * 0.45))))
                thesis_points.append(f"✅ BUY Triggered: Composite score {composite_score:+d} exceeds threshold {min_required_score}.")
            else:
                thesis_points.append(f"⏳ Standby: Composite score {composite_score:+d} below buy threshold {min_required_score}.")
        elif already_holding:
            thesis_points.append("📌 Already holding open position in this asset - Monitoring trailing stops.")

        # Calculate Dynamic Stop Loss & Take Profits using ATR
        atr = ta["atr"]
        stop_pct = stance_info["stop_loss_pct"]
        # Use dynamic ATR if available (1.5x ATR distance, bounded by stop_pct)
        if current_price > 0 and atr > 0:
            atr_pct = (atr * 1.5) / current_price
            stop_pct = max(0.012, min(0.035, atr_pct))

        stop_loss_price = round(current_price * (1 - stop_pct), 2)
        take_profit_1 = round(current_price * (1 + (stop_pct * 2.0)), 2)  # 1:2 Risk-to-Reward
        take_profit_2 = round(current_price * (1 + (stop_pct * 3.5)), 2)  # 1:3.5 Risk-to-Reward

        # Generate Real AI Market Thesis
        thesis = self.llm.generate_dynamic_market_thesis(
            symbol=symbol,
            price=current_price,
            ta=ta,
            news=news_analysis,
            stance=stance_info
        )

        return {
            "pair": pair,
            "market": market,
            "symbol": symbol,
            "action": decision_action,
            "confidence": confidence,
            "composite_score": composite_score,
            "ta_score": ta_score,
            "current_price": current_price,
            "stop_loss_price": stop_loss_price,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "stop_loss_pct": round(stop_pct * 100, 2),
            "spread_pct": bid_ask_spread_pct,
            "thesis": thesis,
            "ta": ta
        }

    def generate_cycle_thought(
        self,
        stance_info: Dict[str, Any],
        news_analysis: Dict[str, Any],
        decisions: List[Dict[str, Any]],
        open_positions: List[Dict[str, Any]],
        top_movers: Optional[List[Dict[str, Any]]] = None
    ):
        """Synthesize overall cycle reasoning using Real LLM Multi-Model Brain."""
        movers = top_movers or []
        dynamic_thoughts = self.llm.generate_live_agent_thoughts(
            stance=stance_info,
            news=news_analysis,
            top_movers=movers,
            open_positions=open_positions,
            decisions=decisions
        )

        for t in dynamic_thoughts:
            self.thought_history.append(t)

        # Keep last 150 thoughts
        if len(self.thought_history) > 150:
            self.thought_history = self.thought_history[-150:]
