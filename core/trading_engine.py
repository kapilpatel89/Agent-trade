import json
import time
import uuid
import threading
from typing import Dict, Any, List, Optional
import config
from core.coindcx_client import CoinDCXClient
from core.survival_manager import SurvivalManager
from core.agent_brain import AgentBrain
from core.market_scanner import MarketScanner
from core.telegram_notifier import TelegramNotifier

class TradingEngine:
    """
    Core Trading Execution, Paper Simulation, Dynamic Market Scanner,
    Trailing Stop Guard, and Telegram Bot Notification Loop.
    """

    def __init__(self, initial_capital: float = config.DEFAULT_INITIAL_CAPITAL):
        self.coindcx = CoinDCXClient()
        self.survival = SurvivalManager(initial_capital=initial_capital)
        self.brain = AgentBrain(survival_manager=self.survival)
        self.scanner = MarketScanner(client=self.coindcx)
        self.telegram = TelegramNotifier(bot_token=config.TELEGRAM_BOT_TOKEN, chat_id=config.TELEGRAM_CHAT_ID)

        # Settings
        self.trading_mode = config.DEFAULT_TRADING_MODE  # "paper" or "live"
        self.is_running = False
        self.cycle_interval = config.DEFAULT_CYCLE_INTERVAL
        self._loop_thread: Optional[threading.Thread] = None

        # State storage
        self.inr_cash = initial_capital
        self.open_positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.last_cycle_time: float = 0
        self.latest_news_data: Dict[str, Any] = {}
        self.latest_decisions: List[Dict[str, Any]] = []
        self.latest_stance: Dict[str, Any] = {}
        self.latest_movers: Dict[str, Any] = {}

        # Load persisted state if exists
        self.load_state()

    def get_total_equity(self) -> float:
        """Calculate total account equity = Cash INR + current value of open positions."""
        position_val = sum(p.get("current_value_inr", p.get("cost_inr", 0)) for p in self.open_positions)
        return round(self.inr_cash + position_val, 2)

    def load_state(self):
        """Load state from local JSON files."""
        if config.STATE_FILE.exists():
            try:
                with open(config.STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.inr_cash = float(data.get("inr_cash", self.survival.initial_capital))
                    self.survival.initial_capital = float(data.get("initial_capital", config.DEFAULT_INITIAL_CAPITAL))
                    self.survival.peak_equity = float(data.get("peak_equity", self.inr_cash))
                    self.trading_mode = data.get("trading_mode", config.DEFAULT_TRADING_MODE)
                    self.open_positions = data.get("open_positions", [])
            except Exception as e:
                print(f"[TradingEngine] Error loading state: {e}")

        if config.TRADE_HISTORY_FILE.exists():
            try:
                with open(config.TRADE_HISTORY_FILE, "r") as f:
                    self.trade_history = json.load(f)
            except Exception as e:
                print(f"[TradingEngine] Error loading trade history: {e}")

        if config.THOUGHT_LOGS_FILE.exists():
            try:
                with open(config.THOUGHT_LOGS_FILE, "r") as f:
                    self.brain.thought_history = json.load(f)
            except Exception as e:
                print(f"[TradingEngine] Error loading thought logs: {e}")

    def save_state(self):
        """Persist state to local JSON files."""
        try:
            state_data = {
                "inr_cash": round(self.inr_cash, 2),
                "initial_capital": round(self.survival.initial_capital, 2),
                "peak_equity": round(self.survival.peak_equity, 2),
                "trading_mode": self.trading_mode,
                "open_positions": self.open_positions,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(config.STATE_FILE, "w") as f:
                json.dump(state_data, f, indent=2)

            with open(config.TRADE_HISTORY_FILE, "w") as f:
                json.dump(self.trade_history, f, indent=2)

            with open(config.THOUGHT_LOGS_FILE, "w") as f:
                json.dump(self.brain.thought_history, f, indent=2)
        except Exception as e:
            print(f"[TradingEngine] Error saving state: {e}")

    def reset_paper_capital(self, capital: float = 1000.0):
        """Reset simulated paper capital and clear active positions."""
        self.inr_cash = capital
        self.survival.initial_capital = capital
        self.survival.peak_equity = capital
        self.open_positions = []
        self.trade_history = []
        self.save_state()
        self.brain.log_thought(
            category="SURVIVAL",
            title=f"Bankroll Reset to ₹{capital:.2f} INR",
            details="Paper trading wallet reset. Survival metrics re-initialized at 100% health.",
            level="info"
        )

    def execute_buy(self, decision: Dict[str, Any], market_detail: Optional[Dict[str, Any]] = None) -> bool:
        """Execute buy order in paper or live mode."""
        market = decision["market"]
        symbol = decision["symbol"]
        pair = decision["pair"]
        price = decision["current_price"]
        current_equity = self.get_total_equity()

        stance = self.latest_stance
        if not stance or "stance" not in stance:
            stance = self.survival.determine_stance(current_equity=current_equity, threat_level=0, crypto_sentiment=0)
            self.latest_stance = stance

        # Allocation check with survival manager
        alloc = self.survival.calculate_order_allocation(
            current_inr_balance=self.inr_cash,
            current_equity=current_equity,
            stance_info=stance,
            market_price=price,
            market_detail=market_detail
        )

        if not alloc.get("allowed"):
            self.brain.log_thought(
                category="EXECUTION",
                title=f"❌ BUY Cancelled for {symbol}",
                details=f"Allocation rejected: {alloc.get('reason')}",
                level="warning",
                pair=pair
            )
            return False

        qty = alloc["quantity"]
        cost_inr = alloc["allocated_inr"]
        
        # CoinDCX Official Spot Fee Structure: 0.20% Trading Fee + 18% GST on Fee = 0.236% Total Buy Fee
        trading_fee_inr = round(cost_inr * config.COINDCX_SPOT_TAKER_FEE, 2)
        gst_on_fee_inr = round(trading_fee_inr * config.COINDCX_GST_ON_FEE, 2)
        total_buy_fee_inr = round(trading_fee_inr + gst_on_fee_inr, 2)
        total_spent = cost_inr + total_buy_fee_inr

        if self.trading_mode == "paper":
            # Paper execution
            self.inr_cash -= total_spent
            position_id = str(uuid.uuid4())[:8]
            position = {
                "id": position_id,
                "market": market,
                "pair": pair,
                "symbol": symbol,
                "side": "BUY",
                "quantity": qty,
                "entry_price": price,
                "cost_inr": cost_inr,
                "fees_inr": total_buy_fee_inr,
                "buy_fee_breakdown": {
                    "trading_fee": trading_fee_inr,
                    "gst_18pct": gst_on_fee_inr,
                    "total": total_buy_fee_inr
                },
                "current_price": price,
                "current_value_inr": cost_inr,
                "unrealized_pnl_inr": 0.0,
                "unrealized_pnl_pct": 0.0,
                "highest_price_seen": price,
                "stop_loss_price": decision["stop_loss_price"],
                "trailing_stop_price": decision["stop_loss_price"],
                "take_profit_1": decision["take_profit_1"],
                "take_profit_2": decision["take_profit_2"],
                "tp1_reached": False,
                "opened_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "thesis": decision.get("thesis", "")
            }
            self.open_positions.append(position)
            self.save_state()

            self.brain.log_thought(
                category="EXECUTION",
                title=f"🚀 PAPER BUY Executed: {qty} {symbol} @ ₹{price}",
                details=f"Principal: ₹{cost_inr:.2f} | CoinDCX Fee: ₹{trading_fee_inr:.2f} + 18% GST: ₹{gst_on_fee_inr:.2f} (Total Fee: ₹{total_buy_fee_inr:.2f}). Initial Stop: ₹{decision['stop_loss_price']} | TP1: ₹{decision['take_profit_1']}.",
                level="success",
                pair=pair
            )

            # Send Telegram Buy Alert
            self.telegram.send_buy_alert(position, self.trading_mode)
            return True

        else:
            # Live CoinDCX Order
            res = self.coindcx.create_order(
                market=market,
                side="buy",
                order_type="market_order",
                total_quantity=qty
            )
            if res.get("error"):
                self.brain.log_thought(
                    category="EXECUTION",
                    title=f"❌ LIVE BUY Order Failed for {symbol}",
                    details=f"CoinDCX API Error: {res.get('message')}",
                    level="danger",
                    pair=pair
                )
                return False

            self.brain.log_thought(
                category="EXECUTION",
                title=f"🚀 LIVE BUY Order Placed: {qty} {symbol}",
                details=f"CoinDCX Response: {res}",
                level="success",
                pair=pair
            )
            self.telegram.send_buy_alert({
                "symbol": symbol, "quantity": qty, "entry_price": price,
                "cost_inr": cost_inr, "stop_loss_price": decision.get("stop_loss_price", 0),
                "take_profit_1": decision.get("take_profit_1", 0), "take_profit_2": decision.get("take_profit_2", 0),
                "thesis": decision.get("thesis", "")
            }, self.trading_mode)
            return True

    def execute_sell(self, position: Dict[str, Any], exit_price: float, reason: str) -> bool:
        """
        Execute sell order / close position with exact CoinDCX Fee & Indian Govt TDS rules:
        - 0.20% Spot Taker Fee
        - 18% GST on trading fee (Total fee: 0.236%)
        - 1.0% Indian Govt TDS on gross crypto sell value (Section 194S)
        """
        qty = position["quantity"]
        symbol = position["symbol"]
        cost_inr = position["cost_inr"]
        buy_fee_inr = position.get("fees_inr", 0.0)

        # Gross sell proceeds
        gross_return = round(qty * exit_price, 2)

        # 1. CoinDCX Sell Trading Fee (0.20%) + 18% GST
        sell_trading_fee = round(gross_return * config.COINDCX_SPOT_TAKER_FEE, 2)
        sell_gst_fee = round(sell_trading_fee * config.COINDCX_GST_ON_FEE, 2)
        total_sell_fee = round(sell_trading_fee + sell_gst_fee, 2)

        # 2. Indian Government 1% TDS on Gross Sale Value (Section 194S)
        tds_1pct = round(gross_return * config.COINDCX_TDS_ON_SELL, 2)

        # Net cash returned to wallet after exchange fee and tax deduction
        net_return = round(gross_return - total_sell_fee - tds_1pct, 2)

        # Total cumulative fees & TDS paid on this complete round-trip trade
        cumulative_fees_and_tax = round(buy_fee_inr + total_sell_fee + tds_1pct, 2)

        # Net PnL = Net cash returned - initial cost
        net_pnl = round(net_return - cost_inr, 2)
        net_pnl_pct = round((net_pnl / cost_inr) * 100.0, 2)

        if self.trading_mode == "paper":
            self.inr_cash += net_return
            trade_record = {
                "id": position["id"],
                "market": position["market"],
                "pair": position["pair"],
                "symbol": symbol,
                "quantity": qty,
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "cost_inr": cost_inr,
                "gross_return_inr": gross_return,
                "net_return_inr": net_return,
                "net_pnl_inr": net_pnl,
                "net_pnl_pct": net_pnl_pct,
                "fees_inr": cumulative_fees_and_tax,
                "fee_breakdown": {
                    "buy_fee_with_gst": buy_fee_inr,
                    "sell_fee_with_gst": total_sell_fee,
                    "tds_1pct_deducted": tds_1pct,
                    "total_friction": cumulative_fees_and_tax
                },
                "opened_at": position["opened_at"],
                "closed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "exit_reason": reason,
                "thesis": position.get("thesis", "")
            }
            self.trade_history.insert(0, trade_record)
            self.open_positions = [p for p in self.open_positions if p["id"] != position["id"]]
            self.save_state()

            level = "success" if net_pnl >= 0 else "danger"
            self.brain.log_thought(
                category="EXECUTION",
                title=f"💰 CLOSED {symbol} ({reason}) | Net PnL: ₹{net_pnl:+.2f} ({net_pnl_pct:+.2f}%)",
                details=f"Gross: ₹{gross_return:.2f} -> Net: ₹{net_return:.2f} (CoinDCX Fee+GST: ₹{total_sell_fee:.2f}, 1% TDS: ₹{tds_1pct:.2f}). Cash: ₹{self.inr_cash:.2f}.",
                level=level,
                pair=position["pair"]
            )

            # Send Telegram Sell / PnL Alert
            self.telegram.send_sell_alert(trade_record, self.get_total_equity(), self.trading_mode)
            return True
        else:

            # Live Order Execution
            res = self.coindcx.create_order(
                market=position["market"],
                side="sell",
                order_type="market_order",
                total_quantity=qty
            )
            if res.get("error"):
                self.brain.log_thought(
                    category="EXECUTION",
                    title=f"❌ LIVE SELL Failed for {symbol}",
                    details=f"CoinDCX Error: {res.get('message')}",
                    level="danger",
                    pair=position["pair"]
                )
                return False
            return True

    def manage_open_positions(self, current_prices: Dict[str, float], stance_info: Dict[str, Any]):
        """
        Evaluate trailing stops, take-profit triggers, and hard stop losses for all open positions.
        """
        trailing_pct = stance_info.get("trailing_stop_pct", 0.015)
        for pos in list(self.open_positions):
            market = pos["market"]
            current_price = current_prices.get(market)
            if not current_price or current_price <= 0:
                continue

            entry_price = pos["entry_price"]
            qty = pos["quantity"]
            pos["current_price"] = current_price
            gross_val = round(qty * current_price, 2)
            
            # Net estimated valuation after 0.236% CoinDCX exit fee & 1.0% TDS
            exit_friction = round(gross_val * (config.COINDCX_EFFECTIVE_FEE + config.COINDCX_TDS_ON_SELL), 2)
            net_estimated_val = round(gross_val - exit_friction, 2)
            
            pos["current_value_inr"] = gross_val
            pos["net_estimated_value_inr"] = net_estimated_val
            pos["unrealized_pnl_inr"] = round(net_estimated_val - pos["cost_inr"], 2)
            pos["unrealized_pnl_pct"] = round(((net_estimated_val - pos["cost_inr"]) / pos["cost_inr"]) * 100.0, 2)


            # Update high water mark for trailing stop
            if current_price > pos.get("highest_price_seen", entry_price):
                pos["highest_price_seen"] = current_price
                new_trailing_stop = round(current_price * (1.0 - trailing_pct), 2)
                # Only move trailing stop UP, never down
                if new_trailing_stop > pos.get("trailing_stop_price", 0):
                    pos["trailing_stop_price"] = new_trailing_stop

            # Check TP1 Trigger -> Lock in partial gain / move stop to breakeven
            if not pos.get("tp1_reached", False) and current_price >= pos["take_profit_1"]:
                pos["tp1_reached"] = True
                pos["trailing_stop_price"] = max(pos.get("trailing_stop_price", 0), entry_price * 1.005) # Breakeven+
                self.brain.log_thought(
                    category="EXECUTION",
                    title=f"🎯 TP1 Reached for {pos['symbol']} @ ₹{current_price}",
                    details=f"Unrealized PnL: +{pos['unrealized_pnl_pct']:.2f}%. Stop-loss automatically adjusted to Breakeven (+0.5%) to guarantee capital safety.",
                    level="success",
                    pair=pos["pair"]
                )

            # Check TP2 Trigger -> Complete Take Profit
            if current_price >= pos["take_profit_2"]:
                self.execute_sell(pos, current_price, "TP2 Target Reached (Max Gain)")
                continue

            # Check Trailing Stop Hit
            if current_price <= pos.get("trailing_stop_price", 0):
                self.execute_sell(pos, current_price, "Trailing Stop Triggered (Profit Guard)")
                continue

            # Check Hard Initial Stop Loss Hit
            if current_price <= pos["stop_loss_price"]:
                self.execute_sell(pos, current_price, "Stop Loss Triggered (Capital Preservation)")
                continue

    def emergency_liquidate_all(self, current_prices: Optional[Dict[str, float]] = None) -> int:
        """Instantly liquidate all open positions and secure 100% cash."""
        closed_count = 0
        prices = current_prices or {}
        for pos in list(self.open_positions):
            exit_price = prices.get(pos["market"], pos.get("current_price", pos["entry_price"]))
            self.execute_sell(pos, exit_price, "EMERGENCY MANUAL LIQUIDATION")
            closed_count += 1
        return closed_count

    def run_cycle(self) -> Dict[str, Any]:
        """
        Execute one full autonomous analysis and trading cycle.
        """
        self.last_cycle_time = time.time()
        try:
            # 1. Fetch Market Tickers
            all_tickers = self.coindcx.get_tickers()
            tickers_map = {t["market"]: t for t in all_tickers if "market" in t}
            current_prices = {t["market"]: float(t.get("last_price", 0) or 0) for t in all_tickers if "market" in t}

            # 2. Fetch Macro & Conflict News
            news_analysis = self.brain.news_engine.analyze()
            self.latest_news_data = news_analysis

            # 3. Calculate Account Equity & Survival Stance
            current_equity = self.get_total_equity()
            total_closed = len(self.trade_history)
            wins = len([t for t in self.trade_history if t.get("net_pnl_inr", 0) > 0])
            win_rate = (wins / total_closed * 100.0) if total_closed > 0 else 50.0

            stance_info = self.survival.determine_stance(
                current_equity=current_equity,
                threat_level=news_analysis.get("threat_level", 0),
                crypto_sentiment=news_analysis.get("crypto_sentiment", 0),
                win_rate=win_rate
            )
            self.latest_stance = stance_info

            # 4. Manage Open Positions (Trailing stops & Take Profits)
            self.manage_open_positions(current_prices, stance_info)

            # 5. Dynamic Market Scanner across all 340+ CoinDCX INR pairs
            scanned_data = self.scanner.scan_all_inr_markets()
            self.latest_movers = scanned_data
            candidate_pairs = scanned_data.get("candidates", config.TRACKED_PAIRS)

            # 6. Evaluate Candidate Pairs (Base Majors + Top Gainers + Volume Breakouts)
            decisions = []
            for pair_info in candidate_pairs:
                market = pair_info["market"]
                pair = pair_info["pair"]

                # Fetch Candles for Technical Analysis (1h interval)
                candles = self.coindcx.get_candles(pair=pair, interval="1h", limit=50)
                ticker = tickers_map.get(market)
                orderbook = {}

                dec = self.brain.evaluate_pair(
                    pair_info=pair_info,
                    candles=candles,
                    ticker=ticker,
                    orderbook=orderbook,
                    news_analysis=news_analysis,
                    stance_info=stance_info,
                    open_positions=self.open_positions
                )
                decisions.append(dec)

            self.latest_decisions = decisions

            # 7. Synthesize Thought Stream using Real AI Brain
            self.brain.generate_cycle_thought(
                stance_info=stance_info,
                news_analysis=news_analysis,
                decisions=decisions,
                open_positions=self.open_positions,
                top_movers=scanned_data.get("top_gainers", [])
            )

            # 8. Execute Authorized BUYs (if any and risk allows)
            if stance_info["stance"] != SurvivalManager.STANCE_BUNKER:
                buy_candidates = [d for d in decisions if d.get("action") == "BUY"]
                # Sort by composite score / confidence descending
                buy_candidates.sort(key=lambda d: (d.get("composite_score", 0), d.get("confidence", 0)), reverse=True)

                for cand in buy_candidates:
                    if len(self.open_positions) < stance_info["max_positions"]:
                        market_detail = self.coindcx.get_market_detail(cand["market"])
                        self.execute_buy(cand, market_detail)

            # 9. Save State
            self.save_state()

            return {
                "status": "success",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "equity": self.get_total_equity(),
                "stance": stance_info,
                "news": news_analysis,
                "decisions": decisions,
                "open_positions": self.open_positions,
                "movers": scanned_data
            }

        except Exception as e:
            print(f"[TradingEngine] Cycle error: {e}")
            self.brain.log_thought(
                category="DECISION",
                title="⚠️ Cycle Execution Exception",
                details=str(e),
                level="danger"
            )
            return {"status": "error", "message": str(e)}

    def start_background_loop(self):
        """Start autonomous loop thread and Telegram interactive listener."""
        if self.is_running:
            return

        self.is_running = True

        # Start Telegram interactive bot command listener
        self.telegram.start_command_listener(self)

        def _loop():
            print("[TradingEngine] Background autonomous trading loop started.")
            while self.is_running:
                self.run_cycle()
                # Sleep interval
                for _ in range(self.cycle_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)

        self._loop_thread = threading.Thread(target=_loop, daemon=True)
        self._loop_thread.start()

    def stop_background_loop(self):
        """Stop background loop and Telegram listener."""
        self.is_running = False
        self.telegram.stop_command_listener()
        print("[TradingEngine] Background autonomous trading loop stopped.")
