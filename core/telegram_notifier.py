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
    Features:
    - Persistent Reply Keyboard (Mobile & Desktop menu buttons)
    - Telegram "/" command list registration (setMyCommands)
    - Dynamic Inline Action Keyboards attached underneath messages & alerts (Buy, Sell, Help, Radar)
    - Interactive Callback Query listener (1-tap Buy, 1-tap Sell, Panic Liquidate, Navigation)
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

    # ==========================================
    # KEYBOARD BUILDERS
    # ==========================================

    @staticmethod
    def get_main_menu_keyboard() -> Dict[str, Any]:
        """
        Persistent custom bottom Reply Keyboard for mobile and desktop Telegram.
        Allows instant 1-tap navigation without typing commands.
        """
        return {
            "keyboard": [
                [{"text": "📊 Status"}, {"text": "⚡ Smart Radar"}],
                [{"text": "🎯 Opportunities"}, {"text": "🚨 Watchouts"}],
                [{"text": "🔗 Relations"}, {"text": "💼 Positions"}],
                [{"text": "🛑 Panic Sell"}, {"text": "❓ Help"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    @staticmethod
    def create_inline_keyboard(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
        """Wrap rows of buttons into a Telegram inline_keyboard structure."""
        return {"inline_keyboard": rows}

    def set_bot_menu_commands(self, token: Optional[str] = None) -> bool:
        """
        Register commands with Telegram via setMyCommands.
        Configures the native '/' Command Menu button on Telegram clients.
        """
        active_token = token or self.bot_token
        if not active_token:
            return False

        url = f"https://api.telegram.org/bot{active_token}/setMyCommands"
        commands = [
            {"command": "status", "description": "Portfolio equity, health %, & net PnL"},
            {"command": "radar", "description": "War news & social (X.com) intelligence"},
            {"command": "opportunities", "description": "Top trade opportunities & 1-tap Buy"},
            {"command": "watchouts", "description": "Buyer vs Seller depth overlap warnings"},
            {"command": "relations", "description": "Correlated sympathy & BTC lag setups"},
            {"command": "positions", "description": "Active open trades & trailing stops"},
            {"command": "buy", "description": "Manual / 1-tap Buy (e.g. /buy BTC)"},
            {"command": "sell", "description": "Manual Sell / Exit (e.g. /sell BTC)"},
            {"command": "cycle", "description": "Run immediate autonomous trading cycle"},
            {"command": "liquidate", "description": "Emergency 100% INR cash exit"},
            {"command": "help", "description": "Show interactive guide & menu"}
        ]

        try:
            data = json.dumps({"commands": commands}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode())
                return res.get("ok", False)
        except Exception as e:
            print(f"[TelegramNotifier] Error setting bot commands: {e}")
            return False

    def answer_callback_query(self, callback_query_id: str, text: str = "", show_alert: bool = False) -> bool:
        """
        Acknowledge an inline button click via answerCallbackQuery to stop the loading spinner.
        """
        if not self.bot_token:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                res = json.loads(resp.read().decode())
                return res.get("ok", False)
        except Exception as e:
            print(f"[TelegramNotifier] Error answering callback query: {e}")
            return False

    # ==========================================
    # MESSAGE SENDER
    # ==========================================

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """Send message via Telegram Bot API with optional inline or reply keyboard."""
        target_chat = chat_id or self.chat_id
        if not self.bot_token or not target_chat:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

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
        Test bot token and send a verification test alert with menu buttons and inline buttons.
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

        # Step 2: Register Commands Menu
        self.set_bot_menu_commands(active_token)

        # Step 3: If Chat ID is missing, attempt auto-detect
        if not active_chat:
            detected = self.auto_detect_chat_id(active_token)
            if detected:
                active_chat = detected
            else:
                return {
                    "success": False,
                    "chat_id": None,
                    "bot_username": bot_username,
                    "message": f"Bot is online ({bot_username}), but no chat room found! Open Telegram, send /start to {bot_username}, then click Test again."
                }

        # Step 4: Send Test Message with persistent menu keyboard and inline buttons
        test_msg = (
            f"⚡ <b>NEXUS SURVIVAL AGENT VERIFICATION</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Connection Status:</b> ONLINE & VERIFIED\n"
            f"🤖 <b>Bot:</b> {bot_username}\n"
            f"🆔 <b>Linked Chat ID:</b> <code>{active_chat}</code>\n"
            f"🚀 <i>Interactive Menu Buttons & Quick Action Buttons are now activated!</i>\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )

        inline_buttons = self.create_inline_keyboard([
            [
                {"text": "📊 Portfolio Status", "callback_data": "status"},
                {"text": "⚡ Smart Radar", "callback_data": "radar"}
            ],
            [
                {"text": "🎯 Opportunities", "callback_data": "opportunities"},
                {"text": "❓ Help & Guide", "callback_data": "help"}
            ]
        ])

        # Send test message with inline keyboard
        sent_ok = self.send_message(test_msg, reply_markup=inline_buttons, chat_id=active_chat)
        if sent_ok:
            # Also send persistent reply menu keyboard so user always has bottom buttons
            menu_msg = "💡 <b>Quick Menu Buttons Enabled:</b> Tap any button below to query your trading agent instantly."
            self.send_message(menu_msg, reply_markup=self.get_main_menu_keyboard(), chat_id=active_chat)

            self.bot_token = active_token
            self.chat_id = str(active_chat)
            config.TELEGRAM_BOT_TOKEN = active_token
            config.TELEGRAM_CHAT_ID = str(active_chat)
            return {
                "success": True,
                "chat_id": str(active_chat),
                "bot_username": bot_username,
                "message": f"Test message with interactive buttons delivered successfully to Telegram chat ({active_chat})!"
            }
        else:
            return {
                "success": False,
                "chat_id": str(active_chat),
                "message": "Failed to send message via Telegram API. Check bot token and chat ID."
            }

    # ==========================================
    # ALERT FORMATTERS WITH INLINE ACTION BUTTONS
    # ==========================================

    def send_buy_alert(self, pos: Dict[str, Any], trading_mode: str = "paper"):
        """Send formatted Buy Order Alert with instant SELL / EXIT and POSITIONS inline buttons."""
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

        markup = self.create_inline_keyboard([
            [
                {"text": f"🔴 SELL #{symbol} NOW", "callback_data": f"sell:{symbol}"},
                {"text": "💼 Open Positions", "callback_data": "positions"}
            ],
            [
                {"text": "⚡ Smart Radar", "callback_data": "radar"},
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ])
        self.send_message(msg, reply_markup=markup)

    def send_sell_alert(self, trade: Dict[str, Any], total_equity: float, trading_mode: str = "paper"):
        """Send formatted Sell / PnL Report Alert with Opportunities and Status buttons."""
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

        markup = self.create_inline_keyboard([
            [
                {"text": "🎯 New Opportunities", "callback_data": "opportunities"},
                {"text": "📊 Portfolio Status", "callback_data": "status"}
            ],
            [
                {"text": "⚡ Smart Radar", "callback_data": "radar"},
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ])
        self.send_message(msg, reply_markup=markup)

    def send_survival_alert(self, stance_info: Dict[str, Any]):
        """Send Survival Stance change alert with quick action buttons."""
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

        markup = self.create_inline_keyboard([
            [
                {"text": "📊 Portfolio Status", "callback_data": "status"},
                {"text": "⚡ Smart Radar", "callback_data": "radar"}
            ],
            [
                {"text": "🎯 Opportunities", "callback_data": "opportunities"},
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ])
        self.send_message(msg, reply_markup=markup)

    def send_orderbook_watchout_alert(self, symbol: str, status: str, ask_pct: float, bid_pct: float, message: str):
        """Send smart Buyer/Seller Orderbook Watchout alert with BUY / SELL buttons."""
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

        if is_danger:
            buttons = [
                [
                    {"text": f"🔴 SELL #{symbol} NOW", "callback_data": f"sell:{symbol}"},
                    {"text": "🛑 Panic Sell All", "callback_data": "panic_liquidate"}
                ],
                [
                    {"text": "🚨 All Depth Watchouts", "callback_data": "watchouts"},
                    {"text": "❓ Help", "callback_data": "help"}
                ]
            ]
        else:
            buttons = [
                [
                    {"text": f"🟢 BUY DIP #{symbol}", "callback_data": f"buy:{symbol}"},
                    {"text": "🎯 Opportunities", "callback_data": "opportunities"}
                ],
                [
                    {"text": "🚨 All Depth Watchouts", "callback_data": "watchouts"},
                    {"text": "❓ Help", "callback_data": "help"}
                ]
            ]

        self.send_message(msg, reply_markup=self.create_inline_keyboard(buttons))

    def send_social_war_news_alert(self, headline: str, threat_level: int, bias: str, down_prob: int, advice: str):
        """Send Geopolitical War News alert with Panic Liquidate and Radar buttons."""
        msg = (
            f"⚔️ <b>WAR / GEOPOLITICAL NEWS SPREADING (X.COM)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📰 <b>Headline:</b> <i>{headline}</i>\n"
            f"⚠️ <b>Macro Threat Level:</b> <b>{threat_level}/100</b>\n"
            f"📉 <b>Market Bias:</b> {bias} ({down_prob}% downside probability)\n"
            f"🛡️ <b>Protective Strategy:</b> <i>{advice}</i>\n"
            f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )

        markup = self.create_inline_keyboard([
            [
                {"text": "🛑 EMERGENCY LIQUIDATE TO INR", "callback_data": "panic_liquidate"}
            ],
            [
                {"text": "⚡ Smart Radar", "callback_data": "radar"},
                {"text": "📊 Status", "callback_data": "status"}
            ],
            [
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ])
        self.send_message(msg, reply_markup=markup)

    def send_correlation_opportunity_alert(self, lead_coin: str, target_coin: str, lag_pct: float, target_price: float, stop_loss: float):
        """Send Inter-Asset Relation alert with 1-tap Buy button for the lagging coin."""
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

        markup = self.create_inline_keyboard([
            [
                {"text": f"🟢 BUY #{target_coin} (Target: ₹{target_price:,.0f})", "callback_data": f"buy:{target_coin}"}
            ],
            [
                {"text": "🔗 All Relations", "callback_data": "relations"},
                {"text": "⚡ Smart Radar", "callback_data": "radar"}
            ],
            [
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ])
        self.send_message(msg, reply_markup=markup)

    # ==========================================
    # INTERACTIVE COMMAND & CALLBACK LISTENER
    # ==========================================

    def start_command_listener(self, trading_engine):
        """Start polling loop for incoming Telegram user commands and inline button callbacks."""
        if self.is_listener_running or not self.bot_token:
            return

        self.is_listener_running = True

        # Register Telegram menu commands on startup
        self.set_bot_menu_commands()

        def _poll():
            print("[TelegramNotifier] Interactive command & inline button listener started.")
            while self.is_listener_running:
                try:
                    url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get("ok"):
                            for update in data.get("result", []):
                                self.last_update_id = update["update_id"]

                                # 1. Check for Inline Button Callbacks
                                cb = update.get("callback_query")
                                if cb:
                                    cb_id = cb.get("id")
                                    cb_data = cb.get("data", "")
                                    cb_msg = cb.get("message", {})
                                    chat_id = str(cb_msg.get("chat", {}).get("id") or cb.get("from", {}).get("id") or self.chat_id)

                                    if not self.chat_id or self.chat_id != chat_id:
                                        self.chat_id = chat_id
                                        config.TELEGRAM_CHAT_ID = chat_id

                                    # Acknowledge callback query
                                    self.answer_callback_query(cb_id, text=f"Processing action...")
                                    self._handle_callback(cb_data, chat_id, trading_engine)
                                    continue

                                # 2. Check for Text Messages / Menu Button Taps
                                msg = update.get("message")
                                if msg and "text" in msg:
                                    chat_id = str(msg["chat"]["id"])
                                    text = msg["text"].strip()

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

    def _handle_callback(self, cb_data: str, chat_id: str, engine):
        """Route inline button callbacks to appropriate engine actions."""
        data = cb_data.strip()

        # Handle 1-tap Buy
        if data.startswith("buy:"):
            symbol = data.split(":", 1)[1].upper()
            self._execute_manual_buy(symbol, chat_id, engine)
            return

        # Handle 1-tap Sell
        if data.startswith("sell:"):
            symbol = data.split(":", 1)[1].upper()
            self._execute_manual_sell(symbol, chat_id, engine)
            return

        # Handle Opportunity Execution by ID
        if data.startswith("opp:"):
            opp_id = data.split(":", 1)[1]
            res = engine.execute_opportunity_trade(opp_id)
            if res.get("success"):
                markup = self.create_inline_keyboard([
                    [{"text": "💼 View Positions", "callback_data": "positions"}, {"text": "📊 Status", "callback_data": "status"}],
                    [{"text": "❓ Help", "callback_data": "help"}]
                ])
                self.send_message(f"✅ {res.get('message')}", reply_markup=markup, chat_id=chat_id)
            else:
                markup = self.create_inline_keyboard([
                    [{"text": "📊 Check Balance", "callback_data": "status"}, {"text": "❓ Help", "callback_data": "help"}]
                ])
                self.send_message(f"❌ {res.get('message')}", reply_markup=markup, chat_id=chat_id)
            return

        # Handle Panic Liquidate
        if data == "panic_liquidate":
            closed = engine.emergency_liquidate_all()
            markup = self.create_inline_keyboard([
                [{"text": "📊 Portfolio Status", "callback_data": "status"}, {"text": "⚡ Smart Radar", "callback_data": "radar"}]
            ])
            self.send_message(
                f"🚨 <b>EMERGENCY LIQUIDATION COMPLETED:</b> Closed {closed} positions.\n"
                f"Secured INR Cash: ₹{engine.inr_cash:,.2f} (100% Capital Preserved).",
                reply_markup=markup,
                chat_id=chat_id
            )
            return

        # Navigation shortcuts
        cmd_map = {
            "status": "/status",
            "radar": "/radar",
            "opportunities": "/opportunities",
            "watchouts": "/watchouts",
            "relations": "/relations",
            "positions": "/positions",
            "help": "/help",
            "cycle": "/cycle"
        }
        if data in cmd_map:
            self._handle_command(cmd_map[data], chat_id, engine)

    def _execute_manual_buy(self, symbol: str, chat_id: str, engine):
        """Helper to execute manual buy from Telegram and send confirmation with action buttons."""
        self.send_message(f"⏳ <i>Executing BUY order for #{symbol} / INR on CoinDCX...</i>", chat_id=chat_id)
        res = engine.manual_buy_symbol(symbol)
        if res.get("success"):
            markup = self.create_inline_keyboard([
                [
                    {"text": f"🔴 SELL #{symbol} NOW", "callback_data": f"sell:{symbol}"},
                    {"text": "💼 View Positions", "callback_data": "positions"}
                ],
                [
                    {"text": "📊 Status", "callback_data": "status"},
                    {"text": "❓ Help", "callback_data": "help"}
                ]
            ])
            self.send_message(
                f"✅ <b>MANUAL BUY ORDER EXECUTED!</b>\n"
                f"🪙 <b>Coin:</b> #{symbol} / INR\n"
                f"💵 <b>Price:</b> ₹{res.get('price', 0):,.2f}\n"
                f"🛑 <b>Stop Loss:</b> ₹{res.get('stop_loss', 0):,.2f}\n"
                f"🎯 <b>Target:</b> ₹{res.get('take_profit', 0):,.2f}\n"
                f"🛡️ <i>Trailing stop & profit guards are now active.</i>",
                reply_markup=markup,
                chat_id=chat_id
            )
        else:
            markup = self.create_inline_keyboard([
                [{"text": "📊 Check Balance", "callback_data": "status"}, {"text": "🎯 Opportunities", "callback_data": "opportunities"}],
                [{"text": "❓ Help", "callback_data": "help"}]
            ])
            self.send_message(f"❌ <b>BUY Order Failed:</b> {res.get('message')}", reply_markup=markup, chat_id=chat_id)

    def _execute_manual_sell(self, symbol: str, chat_id: str, engine):
        """Helper to close position from Telegram and send confirmation."""
        self.send_message(f"⏳ <i>Closing position for #{symbol} / INR...</i>", chat_id=chat_id)
        res = engine.manual_sell_symbol(symbol)
        if res.get("success"):
            markup = self.create_inline_keyboard([
                [
                    {"text": "🎯 New Opportunities", "callback_data": "opportunities"},
                    {"text": "📊 Portfolio Status", "callback_data": "status"}
                ],
                [
                    {"text": "⚡ Smart Radar", "callback_data": "radar"},
                    {"text": "❓ Help", "callback_data": "help"}
                ]
            ])
            self.send_message(
                f"✅ <b>MANUAL EXIT COMPLETED!</b>\n"
                f"🪙 <b>Coin:</b> #{symbol} / INR\n"
                f"🏁 <b>Exit Price:</b> ₹{res.get('price', 0):,.2f}\n"
                f"💵 <i>Net proceeds returned safely to INR cash wallet.</i>",
                reply_markup=markup,
                chat_id=chat_id
            )
        else:
            markup = self.create_inline_keyboard([
                [{"text": "💼 View Positions", "callback_data": "positions"}, {"text": "❓ Help", "callback_data": "help"}]
            ])
            self.send_message(f"❌ <b>SELL Failed:</b> {res.get('message')}", reply_markup=markup, chat_id=chat_id)

    # ==========================================
    # COMMAND DISPATCHER
    # ==========================================

    def _handle_command(self, cmd_text: str, chat_id: str, engine):
        """Handle individual commands and text menu button clicks."""
        clean_text = cmd_text.strip()
        parts = clean_text.split()
        first_token = parts[0].lower() if parts else ""

        # Map text menu taps to commands
        menu_text_map = {
            "📊 status": "/status",
            "status": "/status",
            "⚡ smart radar": "/radar",
            "smart radar": "/radar",
            "radar": "/radar",
            "🎯 opportunities": "/opportunities",
            "opportunities": "/opportunities",
            "🚨 watchouts": "/watchouts",
            "watchouts": "/watchouts",
            "🔗 relations": "/relations",
            "relations": "/relations",
            "💼 positions": "/positions",
            "positions": "/positions",
            "🛑 panic sell": "/liquidate",
            "panic sell": "/liquidate",
            "liquidate": "/liquidate",
            "❓ help": "/help",
            "help": "/help",
            "menu": "/help"
        }

        cmd = menu_text_map.get(clean_text.lower(), first_token)

        # ----------------------------------------------------
        # /buy <symbol> Command
        # ----------------------------------------------------
        if cmd in ["/buy", "buy"]:
            if len(parts) < 2:
                markup = self.create_inline_keyboard([
                    [{"text": "🟢 BUY BTC", "callback_data": "buy:BTC"}, {"text": "🟢 BUY SOL", "callback_data": "buy:SOL"}],
                    [{"text": "🟢 BUY ETH", "callback_data": "buy:ETH"}, {"text": "🎯 Opportunities", "callback_data": "opportunities"}]
                ])
                self.send_message("ℹ️ <b>Usage:</b> <code>/buy &lt;symbol&gt;</code> (e.g. <code>/buy BTC</code> or <code>/buy SOL</code>)", reply_markup=markup, chat_id=chat_id)
                return
            target_symbol = parts[1].upper()
            self._execute_manual_buy(target_symbol, chat_id, engine)
            return

        # ----------------------------------------------------
        # /sell <symbol> Command
        # ----------------------------------------------------
        if cmd in ["/sell", "sell"]:
            if len(parts) < 2:
                if not engine.open_positions:
                    self.send_message("💼 <b>No open positions to sell.</b> 100% in INR cash.", chat_id=chat_id)
                    return
                # Build inline buttons for each open position
                pos_buttons = []
                for p in engine.open_positions:
                    pos_buttons.append([{"text": f"🔴 SELL #{p['symbol']} (Entry ₹{p['entry_price']:,.0f})", "callback_data": f"sell:{p['symbol']}"}])
                pos_buttons.append([{"text": "🛑 Panic Sell All", "callback_data": "panic_liquidate"}])
                self.send_message("🪙 <b>Select a position to close:</b>", reply_markup=self.create_inline_keyboard(pos_buttons), chat_id=chat_id)
                return
            target_symbol = parts[1].upper()
            self._execute_manual_sell(target_symbol, chat_id, engine)
            return

        # ----------------------------------------------------
        # /start or /help
        # ----------------------------------------------------
        if cmd in ["/start", "/help"]:
            reply = (
                f"⚡ <b>NEXUS CRYPTO SURVIVAL AGENT</b> ⚡\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Autonomous CoinDCX Intelligence & Capital Defense.\n\n"
                f"<b>Interactive Menu Options:</b>\n"
                f"• <b>/status</b> - Balance, Equity, Health % & Net PnL\n"
                f"• <b>/radar</b> - War news, social (X.com) & macro bias\n"
                f"• <b>/opportunities</b> - Scanned setups with 1-tap Buy buttons\n"
                f"• <b>/watchouts</b> - Buyer vs Seller depth overlap warnings\n"
                f"• <b>/relations</b> - Sympathy rally & BTC lag trades\n"
                f"• <b>/positions</b> - Open positions & trailing stop guards\n"
                f"• <b>/buy &lt;symbol&gt;</b> - Instant 1-tap buy (e.g. <code>/buy BTC</code>)\n"
                f"• <b>/sell &lt;symbol&gt;</b> - Close position (e.g. <code>/sell BTC</code>)\n"
                f"• <b>/liquidate</b> - Emergency 100% exit to INR cash\n"
            )
            inline_buttons = self.create_inline_keyboard([
                [
                    {"text": "📊 Status", "callback_data": "status"},
                    {"text": "⚡ Smart Radar", "callback_data": "radar"}
                ],
                [
                    {"text": "🎯 Opportunities", "callback_data": "opportunities"},
                    {"text": "🚨 Watchouts", "callback_data": "watchouts"}
                ],
                [
                    {"text": "🔗 Relations", "callback_data": "relations"},
                    {"text": "💼 Positions", "callback_data": "positions"}
                ],
                [
                    {"text": "🛑 Panic Sell All", "callback_data": "panic_liquidate"}
                ]
            ])
            # Send with persistent reply keyboard attached so bottom buttons stay visible
            self.send_message(reply, reply_markup=inline_buttons, chat_id=chat_id)
            self.send_message("💡 <i>Use the buttons below or tap the '/' command menu anytime:</i>", reply_markup=self.get_main_menu_keyboard(), chat_id=chat_id)

        # ----------------------------------------------------
        # /status
        # ----------------------------------------------------
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
                f"💵 <b>Cash Balance:</b> ₹{engine.inr_cash:,.2f} INR\n"
                f"💎 <b>Total Equity:</b> ₹{eq:,.2f} INR\n"
                f"📈 <b>Net PnL:</b> <b>₹{pnl:+,.2f} ({pnl_pct:+.2f}%)</b>\n"
                f"❤️ <b>Survival Health:</b> {health:.1f}% HP\n"
                f"💼 <b>Open Positions:</b> {len(engine.open_positions)}\n"
                f"📜 <b>Total Trades:</b> {trades_count}\n"
                f"🛡️ <b>Survival Stance:</b> {engine.latest_stance.get('label', 'PRUDENT')}\n"
                f"⏱️ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
            )
            markup = self.create_inline_keyboard([
                [
                    {"text": "⚡ Smart Radar", "callback_data": "radar"},
                    {"text": "🎯 Opportunities", "callback_data": "opportunities"}
                ],
                [
                    {"text": "💼 Positions", "callback_data": "positions"},
                    {"text": "🛑 Panic Sell All", "callback_data": "panic_liquidate"}
                ],
                [
                    {"text": "❓ Help", "callback_data": "help"}
                ]
            ])
            self.send_message(reply, reply_markup=markup, chat_id=chat_id)

        # ----------------------------------------------------
        # /positions
        # ----------------------------------------------------
        elif cmd in ["/positions"]:
            if not engine.open_positions:
                markup = self.create_inline_keyboard([
                    [{"text": "🎯 Find Opportunities", "callback_data": "opportunities"}, {"text": "⚡ Smart Radar", "callback_data": "radar"}],
                    [{"text": "❓ Help", "callback_data": "help"}]
                ])
                self.send_message("💼 <b>No open positions.</b> 100% capital safely preserved in INR cash.", reply_markup=markup, chat_id=chat_id)
                return

            reply_lines = ["💼 <b>ACTIVE OPEN POSITIONS:</b>\n━━━━━━━━━━━━━━━━━━"]
            inline_rows = []
            for p in engine.open_positions:
                pnl = p.get("unrealized_pnl_inr", 0)
                pct = p.get("unrealized_pnl_pct", 0)
                sym = p["symbol"]
                reply_lines.append(
                    f"🪙 <b>#{sym}</b>: Qty {p['quantity']} | Entry ₹{p['entry_price']:,.2f}\n"
                    f"  Current: ₹{p.get('current_price', p['entry_price']):,.2f} | Stop: ₹{p.get('trailing_stop_price', p['stop_loss_price']):,.2f}\n"
                    f"  PnL: <b>₹{pnl:+,.2f} ({pct:+.2f}%)</b>\n"
                )
                inline_rows.append([{"text": f"🔴 SELL #{sym} NOW", "callback_data": f"sell:{sym}"}])

            inline_rows.append([
                {"text": "🛑 Panic Close All", "callback_data": "panic_liquidate"},
                {"text": "🎯 Opportunities", "callback_data": "opportunities"}
            ])
            inline_rows.append([{"text": "❓ Help", "callback_data": "help"}])

            self.send_message("\n".join(reply_lines), reply_markup=self.create_inline_keyboard(inline_rows), chat_id=chat_id)

        # ----------------------------------------------------
        # /opportunities
        # ----------------------------------------------------
        elif cmd in ["/opportunities", "/opps"]:
            radar_data = engine.radar.build_radar_overview(force_refresh=True)
            opps = radar_data.get("opportunities", [])
            if not opps:
                markup = self.create_inline_keyboard([
                    [{"text": "⚡ Smart Radar", "callback_data": "radar"}, {"text": "❓ Help", "callback_data": "help"}]
                ])
                self.send_message("🎯 <b>No high-conviction opportunities detected right now.</b> Cash preserved.", reply_markup=markup, chat_id=chat_id)
                return

            reply_lines = ["🎯 <b>TOP MARKET TRADE OPPORTUNITIES:</b>\n━━━━━━━━━━━━━━━━━━"]
            inline_rows = []
            for o in opps[:4]:
                sym = o["symbol"]
                curr = o.get("current_price", 0)
                tp = o.get("target_price", curr * 1.04)
                sl = o.get("stop_loss_price", curr * 0.98)
                gain = o.get("expected_return_pct", 4.0)

                reply_lines.append(
                    f"🚀 <b>#{sym}</b> [{o.get('category_label', 'OPPORTUNITY')}]\n"
                    f"  Entry: ₹{curr:,.2f} -> Target: ₹{tp:,.2f} (+{gain:.1f}%)\n"
                    f"  Stop: ₹{sl:,.2f} | Score: {o.get('composite_score', 80)}/100\n"
                    f"  <i>{o.get('headline')}</i>\n"
                )
                inline_rows.append([
                    {"text": f"🟢 BUY #{sym} (Target ₹{tp:,.0f})", "callback_data": f"buy:{sym}"}
                ])

            inline_rows.append([
                {"text": "⚡ Smart Radar", "callback_data": "radar"},
                {"text": "❓ Help", "callback_data": "help"}
            ])
            self.send_message("\n".join(reply_lines), reply_markup=self.create_inline_keyboard(inline_rows), chat_id=chat_id)

        # ----------------------------------------------------
        # /watchouts
        # ----------------------------------------------------
        elif cmd in ["/watchouts", "/depth"]:
            radar_data = engine.radar.build_radar_overview(force_refresh=True)
            w_list = radar_data.get("orderbook_watchouts", [])
            reply_lines = ["🐋 <b>BUYER VS. SELLER ORDERBOOK DEPTH:</b>\n━━━━━━━━━━━━━━━━━━"]
            inline_rows = []

            for ob in w_list:
                status_icon = "🚨" if ob["overlap_flag"] else ("🛡️" if ob["absorption_flag"] else "⚖️")
                sym = ob["symbol"]
                reply_lines.append(
                    f"{status_icon} <b>#{sym}</b>: {ob['status']}\n"
                    f"  Depth: <b>{ob['bid_pressure_pct']}% Bids</b> vs <b>{ob['ask_pressure_pct']}% Asks</b>\n"
                    f"  <i>{ob['summary']}</i>\n"
                )
                if ob["absorption_flag"]:
                    inline_rows.append([{"text": f"🟢 BUY DIP #{sym}", "callback_data": f"buy:{sym}"}])
                elif ob["overlap_flag"]:
                    inline_rows.append([{"text": f"🔴 SELL / EXIT #{sym}", "callback_data": f"sell:{sym}"}])

            inline_rows.append([
                {"text": "⚡ Refresh Watchouts", "callback_data": "watchouts"},
                {"text": "🎯 Opportunities", "callback_data": "opportunities"}
            ])
            inline_rows.append([{"text": "❓ Help", "callback_data": "help"}])

            self.send_message("\n".join(reply_lines), reply_markup=self.create_inline_keyboard(inline_rows), chat_id=chat_id)

        # ----------------------------------------------------
        # /relations
        # ----------------------------------------------------
        elif cmd in ["/relations", "/correlation", "/sympathy"]:
            radar_data = engine.radar.build_radar_overview(force_refresh=True)
            rel_list = radar_data.get("relation_trades", [])
            if not rel_list:
                markup = self.create_inline_keyboard([
                    [{"text": "⚡ Smart Radar", "callback_data": "radar"}, {"text": "❓ Help", "callback_data": "help"}]
                ])
                self.send_message("🔗 <b>Correlations Steady:</b> No extreme sympathy lag gaps detected right now.", reply_markup=markup, chat_id=chat_id)
                return

            reply_lines = ["🔗 <b>INTER-COIN RELATION & SYMPATHY SETUPS:</b>\n━━━━━━━━━━━━━━━━━━"]
            inline_rows = []
            for r in rel_list:
                sym = r["symbol"]
                icon = "🚀" if r["signal"] == "BUY" else "⚠️"
                reply_lines.append(
                    f"{icon} <b>#{sym}</b> (Lag vs BTC: {r['lag_pct']:+.2f}%)\n"
                    f"  Current: ₹{r['current_price']:,.2f} -> Target: ₹{r['target_price']:,.2f} (+{r.get('expected_return_pct', 0)}%)\n"
                    f"  <i>{r['headline']}</i>\n"
                )
                if r["signal"] == "BUY":
                    inline_rows.append([{"text": f"🟢 BUY LAGGING #{sym}", "callback_data": f"buy:{sym}"}])

            inline_rows.append([
                {"text": "⚡ Smart Radar", "callback_data": "radar"},
                {"text": "❓ Help", "callback_data": "help"}
            ])
            self.send_message("\n".join(reply_lines), reply_markup=self.create_inline_keyboard(inline_rows), chat_id=chat_id)

        # ----------------------------------------------------
        # /radar
        # ----------------------------------------------------
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
            markup = self.create_inline_keyboard([
                [
                    {"text": "🚨 Depth Watchouts", "callback_data": "watchouts"},
                    {"text": "🔗 Relations", "callback_data": "relations"}
                ],
                [
                    {"text": "🎯 Opportunities", "callback_data": "opportunities"},
                    {"text": "🛑 Panic Liquidate", "callback_data": "panic_liquidate"}
                ],
                [
                    {"text": "❓ Help", "callback_data": "help"}
                ]
            ])
            self.send_message(reply, reply_markup=markup, chat_id=chat_id)

        # ----------------------------------------------------
        # /scan
        # ----------------------------------------------------
        elif cmd in ["/scan", "/movers"]:
            from core.market_scanner import MarketScanner
            scanner = MarketScanner(engine.coindcx)
            movers = scanner.scan_all_inr_markets(force_refresh=True)

            reply_lines = [
                f"🔥 <b>TOP COINDCX HIGH MOVERS SCANNED:</b>\n"
                f"Scanned {movers['total_scanned']} INR pairs.\n━━━━━━━━━━━━━━━━━━"
            ]
            inline_rows = []
            for g in movers["top_gainers"][:6]:
                sym = g['symbol']
                reply_lines.append(
                    f"🚀 <b>#{sym}</b> ({g['name']}): <b>{g['change_24h']:+.2f}%</b> (₹{g['last_price']:,.4f})\n"
                    f"  24h Vol: ₹{g['turnover_inr']:,.0f} INR | Spread: {g['spread_pct']}%\n"
                )
                inline_rows.append([{"text": f"🟢 BUY #{sym}", "callback_data": f"buy:{sym}"}])

            inline_rows.append([{"text": "⚡ Smart Radar", "callback_data": "radar"}, {"text": "❓ Help", "callback_data": "help"}])
            self.send_message("\n".join(reply_lines), reply_markup=self.create_inline_keyboard(inline_rows), chat_id=chat_id)

        # ----------------------------------------------------
        # /cycle
        # ----------------------------------------------------
        elif cmd in ["/cycle"]:
            self.send_message("⏳ <i>Executing autonomous cycle on CoinDCX...</i>", chat_id=chat_id)
            res = engine.run_cycle()
            markup = self.create_inline_keyboard([
                [{"text": "📊 Status", "callback_data": "status"}, {"text": "💼 Positions", "callback_data": "positions"}],
                [{"text": "🎯 Opportunities", "callback_data": "opportunities"}, {"text": "❓ Help", "callback_data": "help"}]
            ])
            self.send_message(f"✅ <b>Cycle Completed!</b> Total Equity: ₹{res.get('equity', engine.get_total_equity()):,.2f}", reply_markup=markup, chat_id=chat_id)

        # ----------------------------------------------------
        # /liquidate
        # ----------------------------------------------------
        elif cmd in ["/liquidate"]:
            closed = engine.emergency_liquidate_all()
            markup = self.create_inline_keyboard([
                [{"text": "📊 Portfolio Status", "callback_data": "status"}, {"text": "⚡ Smart Radar", "callback_data": "radar"}]
            ])
            self.send_message(f"🚨 <b>EMERGENCY LIQUIDATION:</b> Closed {closed} positions. Secured INR Cash: ₹{engine.inr_cash:,.2f}", reply_markup=markup, chat_id=chat_id)
