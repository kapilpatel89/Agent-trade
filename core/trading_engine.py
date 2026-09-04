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
from core.market_radar import MarketRadarEngine
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
        self.radar = MarketRadarEngine(client=self.coindcx, news_engine=self.brain.news_engine)
        self.telegram = TelegramNotifier(bot_token=config.TELEGRAM_BOT_TOKEN, chat_id=config.TELEGRAM_CHAT_ID)

        # Settings
        self.trading_mode = config.DEFAULT_TRADING_MODE  # "paper" or "live"
        self.enable_futures_shorting = config.ENABLE_FUTURES_SHORTING
        self.futures_leverage = config.FUTURES_DEFAULT_LEVERAGE
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
        self.latest_radar: Dict[str, Any] = {}
        self.alert_cooldowns: Dict[str, float] = {}  # Throttle Telegram alerts

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
                    self.enable_futures_shorting = bool(data.get("enable_futures_shorting", config.ENABLE_FUTURES_SHORTING))
                    self.futures_leverage = int(data.get("futures_leverage", config.FUTURES_DEFAULT_LEVERAGE))
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
                "enable_futures_shorting": self.enable_futures_shorting,
                "futures_leverage": self.futures_leverage,
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

    def execute_short(self, decision: Dict[str, Any], market_detail: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute Futures Short Selling order (CoinDCX Derivatives).
        Only active if self.enable_futures_shorting is True.
        """
        if not self.enable_futures_shorting:
            self.brain.log_thought(
                category="EXECUTION",
                title=f"🛑 SHORT Rejected for {decision.get('symbol')}",
                details="Futures Short Selling is disabled in Settings. Preserving 100% spot capital in cash.",
                level="warning"
            )
            return False

        pair = decision["pair"]
        market = decision["market"]
        symbol = decision["symbol"]
        price = decision["current_price"]

        if price <= 0:
            return False

        current_equity = self.get_total_equity()
        # Max short allocation = 15% of equity or remaining cash
        max_margin = round(current_equity * config.FUTURES_MAX_SHORT_ALLOCATION, 2)
        margin_inr = min(self.inr_cash, max_margin)

        if margin_inr < 50.0:  # Min margin threshold
            self.brain.log_thought(
                category="EXECUTION",
                title=f"❌ SHORT Cancelled for {symbol}",
                details=f"Insufficient cash for derivative margin (Have: ₹{self.inr_cash:.2f}, Need: ₹50.00).",
                level="warning",
                pair=pair
            )
            return False

        leverage = self.futures_leverage
        notional_inr = round(margin_inr * leverage, 2)
        qty = round(notional_inr / price, 6)
        if qty <= 0:
            return False

        futures_fee_inr = round(notional_inr * config.COINDCX_FUTURES_TAKER_FEE, 2)
        total_deduct = margin_inr + futures_fee_inr

        # Hard stop loss above entry (e.g. +2.5%)
        stop_loss_price = decision.get("stop_loss_price") or round(price * 1.025, 2)
        # Take profits below entry (e.g. -4% and -8%)
        tp1 = decision.get("take_profit_1") or round(price * 0.96, 2)
        tp2 = decision.get("take_profit_2") or round(price * 0.92, 2)
        # Liquidation price (at 2x leverage ~ 45% pump)
        liq_price = round(price * (1.0 + (0.9 / leverage)), 2)

        if self.trading_mode == "paper":
            self.inr_cash -= total_deduct
            position_id = str(uuid.uuid4())[:8]
            position = {
                "id": position_id,
                "market": market,
                "pair": pair,
                "symbol": symbol,
                "side": "SHORT",
                "leverage": leverage,
                "quantity": qty,
                "entry_price": price,
                "cost_inr": margin_inr,
                "margin_inr": margin_inr,
                "notional_inr": notional_inr,
                "fees_inr": futures_fee_inr,
                "current_price": price,
                "current_value_inr": margin_inr,
                "unrealized_pnl_inr": 0.0,
                "unrealized_pnl_pct": 0.0,
                "lowest_price_seen": price,
                "stop_loss_price": stop_loss_price,
                "trailing_stop_price": stop_loss_price,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "liquidation_price": liq_price,
                "tp1_reached": False,
                "opened_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "thesis": decision.get("thesis", f"Futures Short Breakdown ({leverage}x leverage)")
            }
            self.open_positions.append(position)
            self.save_state()

            self.brain.log_thought(
                category="EXECUTION",
                title=f"🔴 SHORT Position Opened: {qty} {symbol} @ ₹{price:,.2f} ({leverage}x)",
                details=f"Margin: ₹{margin_inr:.2f} | Notional: ₹{notional_inr:.2f}. Downside TP1: ₹{tp1:,.2f} (-4%), Stop: ₹{stop_loss_price:,.2f} (+2.5%), Est Liq: ₹{liq_price:,.2f}.",
                level="warning",
                pair=pair
            )

            # Send Telegram Short Alert with inline cover/exit button
            self.telegram.send_short_alert(position, self.trading_mode)
            return True

        else:
            # Live CoinDCX Futures Order
            res = self.coindcx.create_order(
                market=market,
                side="sell",
                order_type="market_order",
                total_quantity=qty
            )
            if res.get("error"):
                self.brain.log_thought(
                    category="EXECUTION",
                    title=f"❌ LIVE SHORT Order Failed for {symbol}",
                    details=f"CoinDCX API Error: {res.get('message')}",
                    level="danger",
                    pair=pair
                )
                return False
            self.telegram.send_short_alert({
                "symbol": symbol, "quantity": qty, "entry_price": price,
                "cost_inr": margin_inr, "leverage": leverage, "stop_loss_price": stop_loss_price,
                "take_profit_1": tp1, "take_profit_2": tp2, "liquidation_price": liq_price,
                "thesis": decision.get("thesis", "")
            }, self.trading_mode)
            return True

    def execute_cover_short(self, position: Dict[str, Any], exit_price: float, reason: str) -> bool:
        """
        Close an existing SHORT position (Buy to Cover).
        Profit if exit_price < entry_price.
        Loss if exit_price > entry_price.
        """
        qty = position["quantity"]
        symbol = position["symbol"]
        entry_price = position["entry_price"]
        margin_inr = position["cost_inr"]
        leverage = position.get("leverage", 2)
        notional_inr = position.get("notional_inr", margin_inr * leverage)

        # Price difference: positive when price went down (profit)
        price_diff = entry_price - exit_price
        gross_pnl = round(price_diff * qty, 2)

        # Exit futures fee (0.05%)
        close_futures_fee = round(notional_inr * config.COINDCX_FUTURES_TAKER_FEE, 2)
        cumulative_fees = round(position.get("fees_inr", 0.0) + close_futures_fee, 2)

        net_pnl = round(gross_pnl - close_futures_fee, 2)
        net_pnl_pct = round((net_pnl / margin_inr) * 100.0, 2)
        net_return = round(margin_inr + net_pnl, 2)

        if self.trading_mode == "paper":
            self.inr_cash += max(0.0, net_return)
            trade_record = {
                "id": position["id"],
                "market": position["market"],
                "pair": position["pair"],
                "symbol": symbol,
                "side": "SHORT",
                "leverage": leverage,
                "quantity": qty,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "cost_inr": margin_inr,
                "gross_return_inr": round(margin_inr + gross_pnl, 2),
                "net_return_inr": net_return,
                "net_pnl_inr": net_pnl,
                "net_pnl_pct": net_pnl_pct,
                "fees_inr": cumulative_fees,
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
                title=f"💰 COVERED SHORT {symbol} ({reason}) | Net PnL: ₹{net_pnl:+.2f} ({net_pnl_pct:+.2f}%)",
                details=f"Entry: ₹{entry_price:,.2f} -> Exit: ₹{exit_price:,.2f}. Margin: ₹{margin_inr:.2f} -> Net Return: ₹{net_return:.2f}. Cash: ₹{self.inr_cash:.2f}.",
                level=level,
                pair=position["pair"]
            )

            # Send Telegram Alert
            self.telegram.send_sell_alert(trade_record, self.get_total_equity(), self.trading_mode)
            return True
        else:
            # Live cover
            res = self.coindcx.create_order(
                market=position["market"],
                side="buy",
                order_type="market_order",
                total_quantity=qty
            )
            return not bool(res.get("error"))

    def manage_open_positions(self, current_prices: Dict[str, float], stance_info: Dict[str, Any]):
        """
        Evaluate trailing stops, take-profit triggers, and hard stop losses for all open positions (Long & Short).
        """
        trailing_pct = stance_info.get("trailing_stop_pct", 0.015)
        for pos in list(self.open_positions):
            market = pos["market"]
            current_price = current_prices.get(market)
            if not current_price or current_price <= 0:
                continue

            entry_price = pos["entry_price"]
            qty = pos["quantity"]
            side = pos.get("side", "BUY")

            if side == "SHORT":
                # SHORT POSITION MANAGEMENT
                margin_inr = pos["cost_inr"]
                leverage = pos.get("leverage", 2)
                diff = entry_price - current_price  # Positive when price drops
                gross_pnl = round(diff * qty, 2)
                futures_fee = round((margin_inr * leverage) * config.COINDCX_FUTURES_TAKER_FEE, 2)
                net_pnl = round(gross_pnl - futures_fee, 2)
                net_pnl_pct = round((net_pnl / margin_inr) * 100.0, 2)

                pos["current_price"] = current_price
                pos["unrealized_pnl_inr"] = net_pnl
                pos["unrealized_pnl_pct"] = net_pnl_pct
                pos["current_value_inr"] = max(0.0, round(margin_inr + net_pnl, 2))

                # Update low water mark for trailing stop
                if current_price < pos.get("lowest_price_seen", entry_price):
                    pos["lowest_price_seen"] = current_price
                    new_trailing_stop = round(current_price * (1.0 + trailing_pct), 2)
                    # For short, trailing stop only moves DOWN, never up
                    if new_trailing_stop < pos.get("trailing_stop_price", 999999999):
                        pos["trailing_stop_price"] = new_trailing_stop

                # Check TP1 Trigger -> Lock in partial downside gain
                if not pos.get("tp1_reached", False) and current_price <= pos["take_profit_1"]:
                    pos["tp1_reached"] = True
                    pos["trailing_stop_price"] = min(pos.get("trailing_stop_price", 999999999), entry_price * 0.995)
                    self.brain.log_thought(
                        category="EXECUTION",
                        title=f"🎯 SHORT TP1 Reached for {pos['symbol']} @ ₹{current_price:,.2f}",
                        details=f"Unrealized Short PnL: +{net_pnl_pct:.2f}%. Stop-loss automatically adjusted to Breakeven (+0.5% buffer).",
                        level="success",
                        pair=pos["pair"]
                    )

                # Check TP2 Trigger -> Complete Take Profit on Short
                if current_price <= pos["take_profit_2"]:
                    self.execute_cover_short(pos, current_price, "Short TP2 Target Reached (Max Downside Gain)")
                    continue

                # Check Trailing Stop Hit (price rebounded up to trailing stop)
                if current_price >= pos.get("trailing_stop_price", 999999999):
                    self.execute_cover_short(pos, current_price, "Short Trailing Stop Triggered (Profit Guard)")
                    continue

                # Check Hard Stop Loss Hit
                if current_price >= pos["stop_loss_price"]:
                    self.execute_cover_short(pos, current_price, "Short Stop Loss Triggered (Risk Cap)")
                    continue

            else:
                # SPOT LONG POSITION MANAGEMENT
                gross_val = round(qty * current_price, 2)
                exit_friction = round(gross_val * (config.COINDCX_EFFECTIVE_FEE + config.COINDCX_TDS_ON_SELL), 2)
                net_estimated_val = round(gross_val - exit_friction, 2)

                pos["current_price"] = current_price
                pos["current_value_inr"] = gross_val
                pos["net_estimated_value_inr"] = net_estimated_val
                pos["unrealized_pnl_inr"] = round(net_estimated_val - pos["cost_inr"], 2)
                pos["unrealized_pnl_pct"] = round(((net_estimated_val - pos["cost_inr"]) / pos["cost_inr"]) * 100.0, 2)

                # Update high water mark for trailing stop
                if current_price > pos.get("highest_price_seen", entry_price):
                    pos["highest_price_seen"] = current_price
                    new_trailing_stop = round(current_price * (1.0 - trailing_pct), 2)
                    if new_trailing_stop > pos.get("trailing_stop_price", 0):
                        pos["trailing_stop_price"] = new_trailing_stop

                # Check TP1 Trigger
                if not pos.get("tp1_reached", False) and current_price >= pos["take_profit_1"]:
                    pos["tp1_reached"] = True
                    pos["trailing_stop_price"] = max(pos.get("trailing_stop_price", 0), entry_price * 1.005)
                    self.brain.log_thought(
                        category="EXECUTION",
                        title=f"🎯 TP1 Reached for {pos['symbol']} @ ₹{current_price}",
                        details=f"Unrealized PnL: +{pos['unrealized_pnl_pct']:.2f}%. Stop-loss automatically adjusted to Breakeven (+0.5%) to guarantee capital safety.",
                        level="success",
                        pair=pos["pair"]
                    )

                # Check TP2 Trigger
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
        """Instantly liquidate all open positions (Long & Short) and secure 100% cash."""
        closed_count = 0
        prices = current_prices or {}
        for pos in list(self.open_positions):
            exit_price = prices.get(pos["market"], pos.get("current_price", pos["entry_price"]))
            if pos.get("side") == "SHORT":
                self.execute_cover_short(pos, exit_price, "EMERGENCY MANUAL LIQUIDATION")
            else:
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

            # 8. Build Comprehensive Market Radar & Trade Opportunities
            radar_data = self.radar.build_radar_overview(enable_futures=self.enable_futures_shorting)
            self.latest_radar = radar_data

            # 9. Smart Telegram Alerts with Throttling Cooldown (15 minutes per alert type)
            now_ts = time.time()
            for w in radar_data.get("orderbook_watchouts", []):
                sym = w["symbol"]
                if w.get("overlap_flag"):
                    cooldown_key = f"overlap_{sym}"
                    if now_ts - self.alert_cooldowns.get(cooldown_key, 0) > 900:  # 15 min cooldown
                        self.alert_cooldowns[cooldown_key] = now_ts
                        self.telegram.send_orderbook_watchout_alert(
                            symbol=sym,
                            status=w["status"],
                            ask_pct=w["ask_pressure_pct"],
                            bid_pct=w["bid_pressure_pct"],
                            message=w["summary"]
                        )

            # Check for Macro War / Geopolitical Social Spikes
            if news_analysis.get("threat_level", 0) >= 55:
                cooldown_key = "war_news_alert"
                if now_ts - self.alert_cooldowns.get(cooldown_key, 0) > 1800:  # 30 min cooldown
                    self.alert_cooldowns[cooldown_key] = now_ts
                    social_sb = news_analysis.get("social_buzz_alerts", [{}])[0]
                    dir_info = news_analysis.get("direction_probability", {})
                    self.telegram.send_social_war_news_alert(
                        headline=social_sb.get("headline", "War headlines spreading on social feeds"),
                        threat_level=news_analysis["threat_level"],
                        bias=dir_info.get("bias", "DOWNWARD_BIAS"),
                        down_prob=dir_info.get("down_prob", 70),
                        advice=social_sb.get("suggested_action", "Hold cash in INR, tighten stops.")
                    )

            # 10. Execute Authorized BUYs / SHORTs (if any and risk allows)
            if stance_info["stance"] != SurvivalManager.STANCE_BUNKER:
                buy_candidates = [d for d in decisions if d.get("action") == "BUY"]
                # Sort by composite score / confidence descending
                buy_candidates.sort(key=lambda d: (d.get("composite_score", 0), d.get("confidence", 0)), reverse=True)

                for cand in buy_candidates:
                    if len(self.open_positions) < stance_info["max_positions"]:
                        market_detail = self.coindcx.get_market_detail(cand["market"])
                        self.execute_buy(cand, market_detail)

                # If Futures Shorting is enabled, also execute high-conviction SHORT candidates
                if self.enable_futures_shorting:
                    short_candidates = [d for d in decisions if d.get("action") == "SHORT"]
                    short_candidates.sort(key=lambda d: (d.get("composite_score", 0), d.get("confidence", 0)), reverse=True)
                    for cand in short_candidates:
                        if len(self.open_positions) < stance_info["max_positions"]:
                            market_detail = self.coindcx.get_market_detail(cand["market"])
                            self.execute_short(cand, market_detail)

            # 11. Save State
            self.save_state()

            return {
                "status": "success",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "equity": self.get_total_equity(),
                "stance": stance_info,
                "news": news_analysis,
                "decisions": decisions,
                "open_positions": self.open_positions,
                "movers": scanned_data,
                "radar": radar_data
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

    def execute_opportunity_trade(self, opportunity_id: str) -> Dict[str, Any]:
        """
        1-Click Execution for an identified Trade Opportunity (Correlation, Orderbook, Live Stick, Short Setup, etc.).
        """
        radar_opps = self.latest_radar.get("opportunities", [])
        if not radar_opps:
            radar_data = self.radar.build_radar_overview(enable_futures=self.enable_futures_shorting)
            radar_opps = radar_data.get("opportunities", [])

        target_opp = next((o for o in radar_opps if o.get("id") == opportunity_id), None)
        if not target_opp:
            return {"success": False, "message": f"Opportunity '{opportunity_id}' not found or expired."}

        market = target_opp["market"]
        symbol = target_opp["symbol"]
        pair = target_opp["pair"]
        signal = target_opp.get("signal", "BUY").upper()
        price = float(target_opp.get("current_price", 0) or 0)
        target_price = float(target_opp.get("target_price", price * 1.04) or (price * 1.04))
        stop_price = float(target_opp.get("stop_loss_price", price * 0.98) or (price * 0.98))

        if price <= 0:
            # Refresh price from ticker
            t = self.coindcx.get_ticker_by_market(market)
            if t:
                price = float(t.get("last_price", 0) or 0)

        market_detail = self.coindcx.get_market_detail(market)

        if signal == "SHORT":
            if not self.enable_futures_shorting:
                return {
                    "success": False,
                    "message": "Futures Short Selling is currently disabled in Settings. Check 'Futures Short Selling' to enable short positions."
                }
            # Execute Short
            short_decision = {
                "pair": pair,
                "market": market,
                "symbol": symbol,
                "action": "SHORT",
                "confidence": target_opp.get("confidence", 80),
                "composite_score": 60,
                "current_price": price,
                "stop_loss_price": stop_price if stop_price > price else round(price * 1.025, 2),
                "take_profit_1": target_price if target_price < price else round(price * 0.96, 2),
                "take_profit_2": round(price * 0.92, 2),
                "thesis": f"[{target_opp.get('category_label', 'SHORT SETUP')}] {target_opp.get('headline')}. {target_opp.get('narrative')[:120]}"
            }
            success = self.execute_short(short_decision, market_detail)
            if success:
                self.save_state()
                return {
                    "success": True,
                    "message": f"Successfully opened FUTURES SHORT for #{symbol} at ₹{price:,.2f} INR ({self.futures_leverage}x leverage).",
                    "opportunity": target_opp
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to open Short for #{symbol}. Check position limits or cash margin balance."
                }
        else:
            # Execute Buy
            decision = {
                "pair": pair,
                "market": market,
                "symbol": symbol,
                "action": "BUY",
                "confidence": target_opp.get("confidence", 80),
                "composite_score": 50,
                "ta_score": 40,
                "current_price": price,
                "stop_loss_price": stop_price,
                "take_profit_1": target_price,
                "take_profit_2": round(price * 1.06, 2),
                "thesis": f"[{target_opp.get('category_label', 'OPPORTUNITY')}] {target_opp.get('headline')}. {target_opp.get('narrative')[:120]}"
            }
            success = self.execute_buy(decision, market_detail)
            if success:
                self.save_state()
                return {
                    "success": True,
                    "message": f"Successfully executed BUY for #{symbol} at ₹{price:,.2f} INR.",
                    "opportunity": target_opp
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to execute trade for #{symbol}. Check position limits or cash balance."
                }

    def manual_buy_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Execute manual or 1-tap Buy order for a symbol (e.g. BTC, SOL, DOGE).
        """
        clean_sym = symbol.strip().upper().replace("#", "").replace("/INR", "").replace("INR", "")
        market_detail = self.coindcx.get_market_detail(clean_sym)
        if not market_detail:
            return {"success": False, "message": f"Coin #{clean_sym} / INR market not found on CoinDCX."}

        market = market_detail.get("coindcx_name") or f"{clean_sym}INR"
        pair = market_detail.get("pair") or market_detail.get("symbol") or market

        # Fetch live price
        ticker = self.coindcx.get_ticker_by_market(market)
        price = float(ticker.get("last_price", 0) or 0) if ticker else 0.0
        if price <= 0:
            return {"success": False, "message": f"Unable to fetch live price for #{clean_sym}."}

        stop_loss = round(price * 0.96, 2)
        tp1 = round(price * 1.04, 2)
        tp2 = round(price * 1.08, 2)

        decision = {
            "pair": pair,
            "market": market,
            "symbol": clean_sym,
            "action": "BUY",
            "confidence": 85,
            "composite_score": 60,
            "current_price": price,
            "stop_loss_price": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "thesis": f"Manual Telegram command trigger for #{clean_sym} / INR."
        }

        success = self.execute_buy(decision, market_detail)
        if success:
            self.save_state()
            return {
                "success": True,
                "message": f"Executed BUY order for #{clean_sym} at ₹{price:,.2f} INR.",
                "price": price,
                "stop_loss": stop_loss,
                "take_profit": tp1
            }
        else:
            return {
                "success": False,
                "message": f"Failed to buy #{clean_sym}. Check capital allocation or position limits."
            }

    def manual_short_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Open a manual Futures Short position for a symbol (e.g. BTC, SOL, ETH).
        Only permitted when enable_futures_shorting is True.
        """
        if not self.enable_futures_shorting:
            return {
                "success": False,
                "message": "Futures Short Selling is currently DISABLED in Settings. Enable it in Settings to short."
            }

        clean_sym = symbol.strip().upper().replace("#", "").replace("/INR", "").replace("INR", "")
        market_detail = self.coindcx.get_market_detail(clean_sym)
        if not market_detail:
            return {"success": False, "message": f"Coin #{clean_sym} / INR market not found on CoinDCX."}

        market = market_detail.get("coindcx_name") or f"{clean_sym}INR"
        pair = market_detail.get("pair") or market_detail.get("symbol") or market

        # Fetch live price
        ticker = self.coindcx.get_ticker_by_market(market)
        price = float(ticker.get("last_price", 0) or 0) if ticker else 0.0
        if price <= 0:
            return {"success": False, "message": f"Unable to fetch live price for #{clean_sym}."}

        stop_loss = round(price * 1.025, 2)
        tp1 = round(price * 0.96, 2)
        tp2 = round(price * 0.92, 2)

        decision = {
            "pair": pair,
            "market": market,
            "symbol": clean_sym,
            "action": "SHORT",
            "confidence": 85,
            "composite_score": 65,
            "current_price": price,
            "stop_loss_price": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "thesis": f"Manual Telegram/UI command trigger for Futures SHORT #{clean_sym} / INR."
        }

        success = self.execute_short(decision, market_detail)
        if success:
            self.save_state()
            return {
                "success": True,
                "message": f"Executed Futures SHORT for #{clean_sym} at ₹{price:,.2f} INR ({self.futures_leverage}x).",
                "price": price,
                "stop_loss": stop_loss,
                "take_profit": tp1
            }
        else:
            return {
                "success": False,
                "message": f"Failed to short #{clean_sym}. Check capital allocation or position limits."
            }

    def manual_sell_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Close an existing open position for a symbol (Long Sell or Short Cover).
        """
        clean_sym = symbol.strip().upper().replace("#", "").replace("/INR", "").replace("INR", "")
        pos = next((p for p in self.open_positions if p.get("symbol", "").upper() == clean_sym), None)
        if not pos:
            return {"success": False, "message": f"No open position found for #{clean_sym}."}

        market = pos["market"]
        ticker = self.coindcx.get_ticker_by_market(market)
        price = float(ticker.get("last_price", 0) or 0) if ticker else float(pos.get("current_price", pos["entry_price"]))

        if pos.get("side") == "SHORT":
            success = self.execute_cover_short(pos, price, "Manual Close/Cover Command")
            action_desc = "covered SHORT"
        else:
            success = self.execute_sell(pos, price, "Manual Sell Command")
            action_desc = "sold SPOT"

        if success:
            return {
                "success": True,
                "message": f"Successfully {action_desc} for #{clean_sym} at ₹{price:,.2f} INR.",
                "price": price
            }
        else:
            return {"success": False, "message": f"Failed to execute exit for #{clean_sym}."}


