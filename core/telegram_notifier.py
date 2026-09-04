import json
import time
import threading
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List
import config

class TelegramNotifier:
    """
    Telegram Bot Notification & Interactive Command System for the Trading Agent.
    Sends instant Buy, Sell, and Survival alerts, and handles interactive bot commands.
    """

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.is_listener_running = False
        self.last_update_id = 0
        self._listener_thread: Optional[threading.Thread] = None

    def set_credentials(self, bot_token: str, chat_id: str):
        """Update bot token and chat ID dynamically."""
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message via Telegram Bot API."""
        if not self.bot_token or not self.chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode())
                return res.get("ok", False)
        except Exception as e:
            print(f"[TelegramNotifier] Error sending message: {e}")
            return False

    def auto_detect_chat_id(self, token: Optional[str] = None) -> Optional[str]:
        """
        Poll getUpdates to automatically capture the user's chat_id
        after they send a message to @antigravitycode_bot.
        """
        active_token = token or self.bot_token
        if not active_token:
            return None

        url = f"https://api.telegram.org/bot{active_token}/getUpdates"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode())
                if res.get("ok"):
                    results = res.get("result", [])
                    if results:
                        # Grab the latest message chat id
                        latest = results[-1]
                        msg = latest.get("message") or latest.get("channel_post") or latest.get("edited_message")
                        if msg and "chat" in msg:
                            detected_id = str(msg["chat"]["id"])
                            self.chat_id = detected_id
                            config.TELEGRAM_CHAT_ID = detected_id
                            return detected_id
        except Exception as e:
            print(f"[TelegramNotifier] Error auto-detecting chat ID: {e}")
        return None

    def test_connection(self, token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Test bot token and send a verification test alert to chat_id.
        Automatically attempts chat_id auto-detection if chat_id is empty.
        """
        active_token = token or self.bot_token
        active_chat = chat_id or self.chat_id

        if not active_token:
            return {
                "success": False,
                "message": "Telegram Bot Token is missing. Please enter your bot token."
            }

        # Step 1: Validate Bot Token via getMe
        bot_username = "@antigravitycode_bot"
        try:
            me_url = f"https://api.telegram.org/bot{active_token}/getMe"
            req = urllib.request.Request(me_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                me_data = json.loads(resp.read().decode())
                if not me_data.get("ok"):
                    return {
                        "success": False,
                        "message": "Invalid Bot Token. Please check token format."
                    }
                bot_username = f"@{me_data['result'].get('username', 'antigravitycode_bot')}"
        except Exception as e:
            return {
                "success": False,
                "message": f"Could not connect to Telegram API: {str(e)}"
            }

        # Step 2: If Chat ID is missing, attempt auto-detect
        if not active_chat:
            detected = self.auto_detect_chat_id(active_token)
            if detected:
                active_chat = detected
            else:
                return {
                    "success": False,
                    "chat_id": None,
                    "bot_username": bot_username,
                    "message": f"Bot is online ({bot_username}), but no chat room found! Please open Telegram, send /start to {bot_username}, then click Test again."
                }

        # Step 3: Send Test Message
        test_msg = (
            f"⚡ <b>NEXUS SURVIVAL AGENT TEST ALERT</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Connection Status:</b> ONLINE & VERIFIED\n"
            f"🤖 <b>Bot:</b> {bot_username}\n"
            f"🆔 <b>Linked Chat ID:</b> <code>{active_chat}</code>\n"
            f"🚀 <i>You will receive instant Buy, Sell, and Realized PnL alerts here!</i>\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )

        send_url = f"https://api.telegram.org/bot{active_token}/sendMessage"
        payload = {
            "chat_id": active_chat,
            "text": test_msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                send_url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode())
                if res.get("ok"):
                    self.bot_token = active_token
                    self.chat_id = str(active_chat)
                    config.TELEGRAM_BOT_TOKEN = active_token
                    config.TELEGRAM_CHAT_ID = str(active_chat)
                    return {
                        "success": True,
                        "chat_id": str(active_chat),
                        "bot_username": bot_username,
                        "message": f"Test message delivered successfully to Telegram chat ({active_chat})!"
                    }
                else:
                    err_desc = res.get("description", "Unknown error")
                    return {
                        "success": False,
                        "chat_id": str(active_chat),
                        "message": f"Telegram Error: {err_desc}"
                    }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to send test message to chat ID {active_chat}: {str(e)}"
            }

    # ==========================================
    # ALERT FORMATTERS
    # ==========================================

    def send_buy_alert(self, pos: Dict[str, Any], trading_mode: str = "paper"):
        """Send formatted Buy Order Alert."""
        mode_label = "🧪 PAPER SIMULATION" if trading_mode == "paper" else "⚡ LIVE COINDCX"
        symbol = pos.get("symbol", "")
        qty = pos.get("quantity", 0)
        entry = pos.get("entry_price", 0)
        cost = pos.get("cost_inr", 0)
        sl = pos.get("stop_loss_price", 0)
        tp1 = pos.get("take_profit_1", 0)
        tp2 = pos.get("take_profit_2", 0)
        thesis = pos.get("thesis", "High momentum breakout")

        msg = (
            f"🚀 <b>BUY ORDER EXECUTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💼 <b>Mode:</b> {mode_label}\n"
            f"🪙 <b>Asset:</b> #{symbol} / INR\n"
            f"📊 <b>Entry Price:</b> ₹{entry:,.2f}\n"
            f"🔢 <b>Quantity:</b> {qty} {symbol}\n"
            f"💵 <b>Allocated Capital:</b> ₹{cost:,.2f} INR\n"
            f"🛑 <b>Stop Loss:</b> ₹{sl:,.2f}\n"
            f"🎯 <b>Take Profit 1:</b> ₹{tp1:,.2f} (+4.0%)\n"
            f"🎯 <b>Take Profit 2:</b> ₹{tp2:,.2f} (+8.0%)\n"
            f"🧠 <b>Thesis:</b> <i>{thesis}</i>\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.send_message(msg)

    def send_sell_alert(self, trade: Dict[str, Any], total_equity: float, trading_mode: str = "paper"):
        """Send formatted Sell / PnL Report Alert."""
        pnl = trade.get("net_pnl_inr", 0)
        pnl_pct = trade.get("net_pnl_pct", 0)
        symbol = trade.get("symbol", "")
        entry = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        reason = trade.get("exit_reason", "Target reached")
        fees = trade.get("fees_inr", 0)
        net_ret = trade.get("net_return_inr", 0)

        emoji = "💰" if pnl >= 0 else "🛑"
        pnl_sign = "+" if pnl >= 0 else ""
        pnl_tag = "PROFIT" if pnl >= 0 else "LOSS"

        msg = (
            f"{emoji} <b>POSITION CLOSED ({pnl_tag})</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Asset:</b> #{symbol} / INR\n"
            f"🏁 <b>Exit Price:</b> ₹{exit_price:,.2f} (Entry: ₹{entry:,.2f})\n"
            f"📈 <b>Net Realized PnL:</b> <b>{pnl_sign}₹{pnl:,.2f} ({pnl_sign}{pnl_pct:,.2f}%)</b>\n"
            f"💵 <b>Net Return:</b> ₹{net_ret:,.2f} INR\n"
            f"🧾 <b>Fees & TDS Paid:</b> ₹{fees:,.2f} INR\n"
            f"🎯 <b>Reason:</b> <i>{reason}</i>\n"
            f"💳 <b>Total Wallet Equity:</b> ₹{total_equity:,.2f} INR\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.send_message(msg)

    def send_survival_alert(self, stance_info: Dict[str, Any]):
        """Send Survival Stance change alert."""
        stance_label = stance_info.get("label", "")
        health = stance_info.get("health_pct", 100.0)
        equity = stance_info.get("current_equity", 1000.0)
        pnl = stance_info.get("net_pnl", 0.0)
        desc = stance_info.get("description", "")

        msg = (
            f"🛡️ <b>SURVIVAL STANCE UPDATE</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <b>New Stance:</b> <b>{stance_label}</b>\n"
            f"❤️ <b>Survival Health:</b> {health:.1f}% HP\n"
            f"💰 <b>Total Equity:</b> ₹{equity:,.2f} (Net: ₹{pnl:+,.2f})\n"
            f"📝 <b>Directive:</b> <i>{desc}</i>\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.send_message(msg)

    def send_orderbook_watchout_alert(self, symbol: str, status: str, ask_pct: float, bid_pct: float, message: str):
        """Send smart Buyer/Seller Orderbook Watchout alert (e.g. Seller Overlapping Buyer)."""
        is_danger = "SELLER" in status.upper() or "OVERLAP" in status.upper()
        icon = "🚨" if is_danger else "🛡️"
        tag = "SELLER OVERLAPPING BUYER" if is_danger else "BUYER ABSORBING SELLER"

        msg = (
            f"{icon} <b>MARKET DEPTH WATCHOUT: #{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Condition:</b> <b>{tag}</b>\n"
            f"📊 <b>Orderbook Depth:</b> {ask_pct:.0f}% Asks vs {bid_pct:.0f}% Bids\n"
            f"📉 <b>Dynamic:</b> <i>{message}</i>\n"
            f"🎯 <b>Action:</b> {'Tighten trailing stops / avoid buying' if is_danger else 'Support holding firmly / bounce setup'}\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.send_message(msg)

    def send_social_war_news_alert(self, headline: str, threat_level: int, bias: str, down_prob: int, advice: str):
        """Send Geopolitical War News & Social Media (X.com) narrative alert."""
        msg = (
            f"⚔️ <b>WAR / GEOPOLITICAL NEWS SPREADING (X.COM)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📰 <b>Headline:</b> <i>{headline}</i>\n"
            f"⚠️ <b>Macro Threat Level:</b> <b>{threat_level}/100</b>\n"
            f"📉 <b>Market Bias:</b> {bias} ({down_prob}% downside probability)\n"
            f"🛡️ <b>Protective Strategy:</b> <i>{advice}</i>\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.send_message(msg)

    def send_correlation_opportunity_alert(self, lead_coin: str, target_coin: str, lag_pct: float, target_price: float, stop_loss: float):
        """Send Inter-Asset Relation / Sympathy Lag Opportunity alert."""
        msg = (
            f"🔗 <b>RELATION TRADE OPPORTUNITY</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🚀 <b>Lead Driver:</b> #{lead_coin} Breaking Out\n"
            f"⏳ <b>Lagging Follower:</b> #{target_coin} (Lag gap: <b>+{lag_pct:.2f}%</b>)\n"
            f"🎯 <b>Catch-up Target:</b> ₹{target_price:,.2f}\n"
            f"🛑 <b>Stop Loss:</b> ₹{stop_loss:,.2f}\n"
            f"🧠 <b>Thesis:</b> High probability sympathy rally as liquidity rotates from #{lead_coin} to #{target_coin}.\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.send_message(msg)

    # ==========================================
    # INTERACTIVE COMMAND LISTENER
    # ==========================================

    def start_command_listener(self, trading_engine):
        """Start polling loop for incoming Telegram user commands."""
        if self.is_listener_running or not self.bot_token:
            return

        self.is_listener_running = True

        def _poll():
            print("[TelegramNotifier] Interactive command listener started.")
            while self.is_listener_running:
                try:
                    url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get("ok"):
                            for update in data.get("result", []):
                                self.last_update_id = update["update_id"]
                                msg = update.get("message")
                                if msg and "text" in msg:
                                    chat_id = str(msg["chat"]["id"])
                                    text = msg["text"].strip()

                                    # Auto update active chat id
                                    if not self.chat_id or self.chat_id != chat_id:
                                        self.chat_id = chat_id
                                        config.TELEGRAM_CHAT_ID = chat_id

                                    self._handle_command(text, chat_id, trading_engine)
                except Exception as e:
                    time.sleep(2)

        self._listener_thread = threading.Thread(target=_poll, daemon=True)
        self._listener_thread.start()

    def stop_command_listener(self):
        """Stop polling listener."""
        self.is_listener_running = False

    def _handle_command(self, cmd_text: str, chat_id: str, engine):
        """Handle individual commands from Telegram."""
        cmd = cmd_text.lower().split()[0]

        if cmd in ["/start", "/help"]:
            reply = (
                f"⚡ <b>Nexus Crypto Survival Agent Bot</b> ⚡\n"
                f"Connected to CoinDCX Autonomous Intelligence.\n\n"
                f"<b>Core Portfolio Commands:</b>\n"
                f"• /status - Portfolio equity, health %, and Net PnL\n"
                f"• /positions - Active open trades & trailing stops\n"
                f"• /scan - Top gainers & volume leaders on CoinDCX\n"
                f"• /cycle - Run immediate analysis & trading cycle\n"
                f"• /liquidate - 🚨 Emergency close all to INR cash\n\n"
                f"<b>🧠 Smart Market Radar Commands:</b>\n"
                f"• /watchouts - Buyer vs. Seller depth & Overlapping warnings\n"
                f"• /relations - Correlated sympathy & BTC lag opportunities\n"
                f"• /radar - Social Media (X.com) & Geopolitical War Intelligence\n"
            )
            self.send_message(reply)

        elif cmd in ["/status", "/balance"]:
            eq = engine.get_total_equity()
            init = engine.survival.initial_capital
            pnl = eq - init
            pnl_pct = (pnl / init) * 100.0
            health = engine.survival.calculate_health(eq)
            trades_count = len(engine.trade_history)

            reply = (
                f"📊 <b>AGENT PORTFOLIO STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💵 <b>Cash Balance:</b> ₹{engine.inr_cash:,.2f}\n"
                f"💎 <b>Total Equity:</b> ₹{eq:,.2f}\n"
                f"📈 <b>Net PnL:</b> ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
                f"❤️ <b>Survival Health:</b> {health:.1f}% HP\n"
                f"💼 <b>Open Positions:</b> {len(engine.open_positions)}\n"
                f"📜 <b>Total Trades:</b> {trades_count}\n"
                f"🛡️ <b>Stance:</b> {engine.latest_stance.get('label', 'PRUDENT')}\n"
            )
            self.send_message(reply)

        elif cmd in ["/positions"]:
            if not engine.open_positions:
                self.send_message("💼 <b>No open positions.</b> 100% capital safely preserved in INR.")
                return

            reply_lines = ["💼 <b>ACTIVE OPEN POSITIONS:</b>\n━━━━━━━━━━━━━━━━━━"]
            for p in engine.open_positions:
                pnl = p.get("unrealized_pnl_inr", 0)
                pct = p.get("unrealized_pnl_pct", 0)
                reply_lines.append(
                    f"🪙 <b>#{p['symbol']}</b>: Qty {p['quantity']} | Entry ₹{p['entry_price']:,.2f}\n"
                    f"  Current: ₹{p.get('current_price', p['entry_price']):,.2f} | Stop: ₹{p.get('trailing_stop_price', p['stop_loss_price']):,.2f}\n"
                    f"  PnL: <b>₹{pnl:+,.2f} ({pct:+.2f}%)</b>\n"
                )
            self.send_message("\n".join(reply_lines))

        elif cmd in ["/scan", "/movers"]:
            from core.market_scanner import MarketScanner
            scanner = MarketScanner(engine.coindcx)
            movers = scanner.scan_all_inr_markets(force_refresh=True)

            reply_lines = [
                f"🔥 <b>TOP COINDCX HIGH MOVERS SCANNED:</b>\n"
                f"Scanned {movers['total_scanned']} INR pairs.\n━━━━━━━━━━━━━━━━━━"
            ]
            for g in movers["top_gainers"][:8]:
                reply_lines.append(
                    f"🚀 <b>#{g['symbol']}</b> ({g['name']}): <b>{g['change_24h']:+.2f}%</b> (₹{g['last_price']:,.4f})\n"
                    f"  24h Vol: ₹{g['turnover_inr']:,.0f} INR | Spread: {g['spread_pct']}%\n"
                )
            self.send_message("\n".join(reply_lines))

        elif cmd in ["/watchouts", "/depth"]:
            radar_data = engine.radar.build_radar_overview(force_refresh=True)
            w_list = radar_data.get("orderbook_watchouts", [])
            reply_lines = ["🐋 <b>BUYER VS. SELLER ORDERBOOK DEPTH:</b>\n━━━━━━━━━━━━━━━━━━"]
            for ob in w_list:
                status_icon = "🚨" if ob["overlap_flag"] else ("🛡️" if ob["absorption_flag"] else "⚖️")
                reply_lines.append(
                    f"{status_icon} <b>#{ob['symbol']}</b>: {ob['status']}\n"
                    f"  Depth: <b>{ob['bid_pressure_pct']}% Bids</b> vs <b>{ob['ask_pressure_pct']}% Asks</b>\n"
                    f"  <i>{ob['summary']}</i>\n"
                )
            self.send_message("\n".join(reply_lines))

        elif cmd in ["/relations", "/correlation", "/sympathy"]:
            radar_data = engine.radar.build_radar_overview(force_refresh=True)
            rel_list = radar_data.get("relation_trades", [])
            if not rel_list:
                self.send_message("🔗 <b>Correlations Steady:</b> No extreme sympathy lag gaps detected right now.")
                return

            reply_lines = ["🔗 <b>INTER-COIN RELATION & SYMPATHY SETUPS:</b>\n━━━━━━━━━━━━━━━━━━"]
            for r in rel_list:
                icon = "🚀" if r["signal"] == "BUY" else "⚠️"
                reply_lines.append(
                    f"{icon} <b>#{r['symbol']}</b> (Lag vs BTC: {r['lag_pct']:+.2f}%)\n"
                    f"  Current: ₹{r['current_price']:,.2f} -> Target: ₹{r['target_price']:,.2f} (+{r.get('expected_return_pct', 0)}%)\n"
                    f"  <i>{r['headline']}</i>\n"
                )
            self.send_message("\n".join(reply_lines))

        elif cmd in ["/radar", "/news", "/sentiment"]:
            data = engine.brain.news_engine.analyze(force_refresh=True)
            direction = data.get("direction_probability", {})
            bias_text = direction.get("bias", "NEUTRAL")
            down_p = direction.get("down_prob", 50)
            up_p = direction.get("up_prob", 50)

            reply = (
                f"🌍 <b>GEOPOLITICAL WAR & SOCIAL (X.COM) RADAR</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>Threat Level:</b> {data['threat_level']}/100 ({data['threat_status']})\n"
                f"📈 <b>Crypto Sentiment:</b> {data['crypto_sentiment']:+d} ({data['sentiment_label']})\n"
                f"🎯 <b>Direction Forecast:</b> <b>{bias_text}</b>\n"
                f"  • Downside Risk: {down_p}%\n"
                f"  • Upside Momentum: {up_p}%\n"
                f"📝 <b>Social Narrative:</b> <i>{data.get('social_summary', 'Normal feeds')}</i>\n"
            )
            self.send_message(reply)

        elif cmd in ["/cycle"]:
            self.send_message("⏳ <i>Executing autonomous cycle on CoinDCX...</i>")
            res = engine.run_cycle()
            self.send_message(f"✅ <b>Cycle Completed!</b> Total Equity: ₹{res.get('equity', engine.get_total_equity()):,.2f}")

        elif cmd in ["/liquidate"]:
            closed = engine.emergency_liquidate_all()
            self.send_message(f"🚨 <b>EMERGENCY LIQUIDATION:</b> Closed {closed} positions. Secured INR Cash: ₹{engine.inr_cash:,.2f}")
