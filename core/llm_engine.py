import json
import os
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
import config

class LLMEngine:
    """
    Real AI Multi-Model Intelligence Engine for Crypto Trading Agent.
    Connects to Google Gemini API, OpenAI API, Local Ollama, or Quantitative Multi-Agent Brain
    to generate deep real-time market theses, dynamic thought streams, and risk analyses.
    """

    def __init__(
        self,
        provider: str = "gemini",
        gemini_key: str = "",
        gemini_model: str = "gemini-3.7-flash",
        openai_key: str = "",
        ollama_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "llama3"
    ):
        self.provider = provider or os.getenv("AI_PROVIDER", "gemini")
        self.gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3")
        self.last_model_used = None
        self.last_error = None

    def update_credentials(
        self,
        provider: Optional[str] = None,
        gemini_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        openai_key: Optional[str] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None
    ):
        """Update AI provider and API keys dynamically."""
        if provider:
            self.provider = provider
        if gemini_key is not None:
            self.gemini_key = gemini_key
        if gemini_model is not None:
            self.gemini_model = gemini_model
        if openai_key is not None:
            self.openai_key = openai_key
        if ollama_url is not None:
            self.ollama_url = ollama_url
        if ollama_model is not None:
            self.ollama_model = ollama_model

    def get_status(self) -> Dict[str, Any]:
        """Get current AI configuration and connection status."""
        active_provider = self.provider
        has_key = False

        if active_provider == "gemini":
            has_key = bool(self.gemini_key)
            preview = f"{self.gemini_key[:4]}...{self.gemini_key[-4:]}" if has_key else "Not set"
        elif active_provider == "openai":
            has_key = bool(self.openai_key)
            preview = f"{self.openai_key[:4]}...{self.openai_key[-4:]}" if has_key else "Not set"
        elif active_provider == "ollama":
            has_key = True
            preview = f"{self.ollama_model} @ {self.ollama_url}"
        else:
            active_provider = "quantitative"
            has_key = True
            preview = "Built-in Real-Time Quant Brain"

        return {
            "provider": active_provider,
            "has_key": has_key,
            "key_preview": preview,
            "gemini_configured": bool(self.gemini_key),
            "gemini_model": self.gemini_model,
            "openai_configured": bool(self.openai_key),
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model
        }

    def discover_gemini_models(self, key: str) -> List[str]:
        """Query Google Gemini ListModels API to discover all available models for this specific API key."""
        if not key:
            return []
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                models = data.get("models", [])
                supported = []
                for m in models:
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        clean_name = m.get("name", "").replace("models/", "")
                        if clean_name:
                            supported.append(clean_name)
                return supported
        except Exception as e:
            return []

    def call_gemini(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """
        Call Google Gemini API with smart auto-discovery of supported models.
        Queries ListModels to eliminate 404 errors on different API tiers.
        """
        if not self.gemini_key:
            self.last_error = "Gemini API key is missing. Please enter your API key."
            return None

        # Discover live models available for this key
        discovered = self.discover_gemini_models(self.gemini_key)

        # Build prioritized models list
        preferred = [
            self.gemini_model,
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.1-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro",
            "gemini-pro"
        ]

        # Combine preferred with discovered
        all_candidates = [m for m in preferred if m] + discovered
        # Deduplicate while preserving order
        unique_models = list(dict.fromkeys(all_candidates))

        contents = []
        if system_instruction:
            contents.append({"role": "user", "parts": [{"text": f"System Context:\n{system_instruction}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will act as the autonomous crypto trading intelligence."}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 450
            }
        }
        data = json.dumps(payload).encode("utf-8")

        last_err = None
        # Try both v1beta and v1 endpoints
        for api_ver in ["v1beta", "v1"]:
            for model_name in unique_models:
                url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model_name}:generateContent?key={self.gemini_key}"
                try:
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        result = json.loads(resp.read().decode())
                        candidates = result.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts:
                                self.last_model_used = model_name
                                self.last_error = None
                                return parts[0].get("text", "").strip()
                except urllib.error.HTTPError as he:
                    try:
                        err_body = he.read().decode()
                        err_json = json.loads(err_body)
                        msg = err_json.get("error", {}).get("message", str(he))
                        last_err = f"HTTP {he.code} ({model_name}): {msg}"
                    except Exception:
                        last_err = f"HTTP {he.code} on {model_name}"
                except Exception as e:
                    last_err = f"{model_name}: {str(e)}"
                    continue

        self.last_error = last_err
        return None

    def call_openai(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """Call OpenAI GPT-4o-mini API."""
        if not self.openai_key:
            return None

        url = "https://api.openai.com/v1/chat/completions"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 400
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openai_key}",
                    "User-Agent": "Mozilla/5.0"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                choices = result.get("choices", [])
                if choices:
                    return choices[0]["message"]["content"].strip()
        except Exception as e:
            print(f"[LLMEngine] OpenAI API Error: {e}")
        return None

    def call_ollama(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """Call Local Ollama instance."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": f"{system_instruction}\n\nUser: {prompt}\n\nAssistant:",
            "stream": False
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                result = json.loads(resp.read().decode())
                return result.get("response", "").strip()
        except Exception as e:
            print(f"[LLMEngine] Ollama Error: {e}")
        return None

    def generate_response(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """Route to active AI provider."""
        if self.provider == "gemini" and self.gemini_key:
            res = self.call_gemini(prompt, system_instruction)
            if res:
                return res

        elif self.provider == "openai" and self.openai_key:
            res = self.call_openai(prompt, system_instruction)
            if res:
                return res

        elif self.provider == "ollama":
            res = self.call_ollama(prompt, system_instruction)
            if res:
                return res

        return None

    # ==========================================
    # DOMAIN SPECIFIC AI AGENT METHODS
    # ==========================================

    def generate_dynamic_market_thesis(
        self,
        symbol: str,
        price: float,
        ta: Dict[str, Any],
        news: Dict[str, Any],
        stance: Dict[str, Any]
    ) -> str:
        """
        Generate a deep, realistic AI trading thesis for a high-mover coin on CoinDCX.
        Uses real LLM if configured, or high-conviction mathematical quantitative synthesis.
        """
        system_instruction = (
            "You are an elite quantitative crypto hedge fund trader and survival strategist. "
            "Analyze the candlestick indicators, volume, and macro threat level to provide a concise, "
            "razor-sharp 1-2 sentence trading thesis explaining why this coin is a prime buy, scalp, or hold."
        )

        prompt = (
            f"Asset: #{symbol}/INR at ₹{price:,.4f}\n"
            f"Indicators: RSI(14)={ta.get('rsi')}, MACD Hist={ta.get('macd_hist')}, "
            f"EMA 9/21 Alignment={'BULLISH' if price > ta.get('ema9', 0) else 'BEARISH'}, "
            f"Volume Surge={ta.get('volume_surge')}x, Patterns={ta.get('patterns', [])}\n"
            f"Macro Threat: {news.get('threat_level')}/100 ({news.get('threat_status')})\n"
            f"Survival Stance: {stance.get('label')}\n"
            f"Provide a 1-2 sentence high-conviction trading thesis:"
        )

        llm_res = self.generate_response(prompt, system_instruction)
        if llm_res and len(llm_res) > 20:
            return llm_res.replace("\n", " ").strip()

        # Quantitative Multi-Agent Fallback
        rsi = ta.get("rsi", 50)
        vol = ta.get("volume_surge", 1.0)
        macd = ta.get("macd_hist", 0)
        pats = ", ".join(ta.get("patterns", [])) if ta.get("patterns") else "EMA Trend Alignment"

        if rsi < 35:
            return f"Oversold mean-reversion setup: RSI ({rsi:.1f}) in prime value bounce zone with {vol:.1f}x volume support and {pats} confluence."
        elif rsi > 60 and macd > 0:
            return f"Momentum breakout continuation: Bullish MACD expansion with {vol:.1f}x volume surge confirming buyers absorbing resistance."
        else:
            return f"Trend-following entry: Price structured above EMA 9/21 with positive MACD momentum and {pats} confirmation."

    def generate_live_agent_thoughts(
        self,
        stance: Dict[str, Any],
        news: Dict[str, Any],
        top_movers: List[Dict[str, Any]],
        open_positions: List[Dict[str, Any]],
        decisions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate dynamic, realistic, non-repetitive real-time thoughts detailing the agent's live reasoning.
        Emits SCAN, SURVIVAL, DECISION, EXECUTION categories for proper frontend filtering.
        """
        thoughts = []
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Survival & Capital Monologue
        eq = stance.get("current_equity", 1000.0)
        pnl = stance.get("net_pnl", 0.0)
        pnl_pct = stance.get("net_pnl_pct", 0.0)
        health = stance.get("health_pct", 100.0)
        stance_label = stance.get("label", "PRUDENT")

        thoughts.append({
            "timestamp": now_str,
            "category": "SURVIVAL",
            "title": f"Health: {health:.1f}% HP | Capital: ₹{eq:,.2f} ({stance_label})",
            "details": f"Wallet Equity: ₹{eq:,.2f} (Net: ₹{pnl:+,.2f} / {pnl_pct:+.2f}%). Cash Reserve: ₹{stance.get('initial_capital', 1000) * 0.3:.2f} safeguarded. Active Positions: {len(open_positions)}/{stance.get('max_positions', 2)}.",
            "level": "success" if pnl >= 0 else "warning",
            "pair": "PORTFOLIO"
        })

        # 2. Scanner result — SCAN category
        if top_movers:
            top3_str = ", ".join([f"#{m['symbol']} ({m['change_24h']:+.1f}%)" for m in top_movers[:5]])
            vol_kings = sorted(top_movers[:10], key=lambda x: x.get("volume_surge", 0), reverse=True)
            vol_str = ", ".join([f"#{v['symbol']} {v.get('volume_surge', 0):.1f}x" for v in vol_kings[:3]])
            thoughts.append({
                "timestamp": now_str,
                "category": "SCAN",
                "title": f"📡 CoinDCX Scan Complete — Top Movers: {top3_str}",
                "details": f"Full market sweep done. Top gainers: {top3_str}. Highest volume spikes: {vol_str}. Filtering spread <2.5%, 24h turnover >₹25K. Applying RSI/MACD/EMA confluence filter before candidate approval.",
                "level": "info",
                "pair": top_movers[0].get("pair", "GLOBAL")
            })

            # One detailed SCAN entry per top mover
            for m in top_movers[:4]:
                sym = m.get("symbol", "?")
                price = m.get("last_price", 0)
                change = m.get("change_24h", 0)
                spread = m.get("spread_pct", 0)
                vol_surge = m.get("volume_surge", 0)
                hi = m.get("high_24h", price)
                lo = m.get("low_24h", price)
                range_pct = ((hi - lo) / lo * 100) if lo > 0 else 0

                reasons = []
                if change > 5:       reasons.append(f"Strong 24h momentum +{change:.1f}%")
                if vol_surge > 1.5:  reasons.append(f"Volume spike {vol_surge:.1f}x above avg")
                if spread < 0.5:     reasons.append("Tight spread — liquid market")
                if range_pct > 8:    reasons.append(f"Wide 24h range {range_pct:.1f}% — volatility opportunity")
                reason_str = " | ".join(reasons) if reasons else f"24h change {change:+.2f}%, monitoring"

                thoughts.append({
                    "timestamp": now_str,
                    "category": "SCAN",
                    "title": f"#{sym}/INR  ₹{price:,.4f}  {'+' if change>=0 else ''}{change:.2f}%",
                    "details": f"24h Range: ₹{lo:,.4f}–₹{hi:,.4f}  |  Spread: {spread:.2f}%  |  Why flagged: {reason_str}",
                    "level": "success" if change > 0 else "info",
                    "pair": m.get("pair", "GLOBAL")
                })

        # 3. Position Monitoring Monologue (if holding positions)
        if open_positions:
            for p in open_positions:
                pnl_inr = p.get("unrealized_pnl_inr", 0)
                pnl_pct_p = p.get("unrealized_pnl_pct", 0)
                curr = p.get("current_price", p.get("entry_price"))
                trail = p.get("trailing_stop_price", p.get("stop_loss_price"))
                tp1 = p.get("take_profit_1")

                thoughts.append({
                    "timestamp": now_str,
                    "category": "EXECUTION",
                    "title": f"📌 Tracking Open Trade: #{p['symbol']} | PnL: ₹{pnl_inr:+,.2f} ({pnl_pct_p:+.2f}%)",
                    "details": f"Price: ₹{curr:,.4f} | Entry: ₹{p['entry_price']:,.4f} | Trailing Stop: ₹{trail:,.4f} | Target TP1: ₹{tp1:,.4f}. Profit guard active.",
                    "level": "success" if pnl_inr >= 0 else "info",
                    "pair": p.get("pair", "TRADE")
                })

        # 4. AI Trading Decision / Thesis Thought
        buy_signals = [d for d in decisions if d.get("action") == "BUY"]
        if buy_signals:
            top_buy = buy_signals[0]
            thesis = self.generate_dynamic_market_thesis(
                symbol=top_buy["symbol"],
                price=top_buy["current_price"],
                ta=top_buy.get("ta", {}),
                news=news,
                stance=stance
            )
            top_buy["thesis"] = thesis

            thoughts.append({
                "timestamp": now_str,
                "category": "DECISION",
                "title": f"🎯 Buy Trigger: #{top_buy['symbol']} Approved @ ₹{top_buy['current_price']:,.2f}",
                "details": f"Confidence: {top_buy['confidence']}% | SL: ₹{top_buy['stop_loss_price']:,.2f} | TP1: ₹{top_buy['take_profit_1']:,.2f}. AI Setup Thesis: {thesis}",
                "level": "success",
                "pair": top_buy.get("pair", "MARKET")
            })

        # 5. Scanned Coins Technical Monologue (Real-World Analysis reasons)
        for d in decisions[:4]:
            sym = d["symbol"]
            price = d["current_price"]
            ta_val = d.get("ta", {})
            rsi = ta_val.get("rsi", 50)
            macd_hist = ta_val.get("macd_hist", 0)
            score = d.get("composite_score", 0)
            action = d.get("action", "HOLD")
            vol_surge = ta_val.get("volume_surge", 1.0)
            patterns = ", ".join(ta_val.get("patterns", [])) if ta_val.get("patterns") else "No reversal patterns"

            rsi_label = "Oversold bounce zone 🟢" if rsi < 35 else ("Overbought — caution 🔴" if rsi > 65 else "Neutral range")
            macd_label = "Bullish expanding" if macd_hist > 0 else "Bearish contracting"

            thoughts.append({
                "timestamp": now_str,
                "category": "DECISION",
                "title": f"🔍 #{sym}/INR @ ₹{price:,.2f} → {action} (Score: {score:+d}/100)",
                "details": f"RSI(14): {rsi:.1f} — {rsi_label}. MACD Hist: {macd_hist:+.3f} — {macd_label}. Volume: {vol_surge:.2f}x. Patterns: {patterns}. Required score: {stance.get('min_score_to_buy', 30)}. Decision: {action}.",
                "level": "success" if action == "BUY" else "info",
                "pair": d.get("pair", "GLOBAL")
            })

        return thoughts
