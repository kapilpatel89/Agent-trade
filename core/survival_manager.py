import math
from typing import Dict, Any, Optional

class SurvivalManager:
    """
    Capital Preservation & Survival Engine for the Crypto Trading Agent.
    Manages Health Percentage, Capital Runway, Risk Budgeting for ₹1,000 wallet,
    and transitions between 4 distinct Survival Stances.
    """

    STANCE_BUNKER = "BUNKER_MODE"               # 🛡️ 100% Cash preservation, no buys
    STANCE_DEFENSIVE = "DEFENSIVE_MODE"         # ⚖️ Minimal ₹100 sizes, tight stops, ultra-high conviction only
    STANCE_PRUDENT = "PRUDENT_COMPOUNDING"      # 🎯 Standard 10-15% sizing, 1:2.5 RR
    STANCE_EXPANSION = "AGGRESSIVE_EXPANSION"   # 🚀 High confidence momentum scaling (when +30% in profit)

    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.peak_equity = initial_capital

    def update_peak_equity(self, current_equity: float):
        """Update high-water mark."""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

    def calculate_health(self, current_equity: float) -> float:
        """
        Calculate Survival Health Percentage (0% to 100%).
        100% when equity >= initial capital.
        Drops as capital draws down below initial funding.
        """
        if self.initial_capital <= 0:
            return 100.0

        if current_equity >= self.initial_capital:
            # Bonus health up to 100% (or capped at 100)
            return 100.0

        # Linear decay from 100% down to 0% at 0 INR
        health = (current_equity / self.initial_capital) * 100.0
        return max(0.0, min(100.0, round(health, 1)))

    def calculate_drawdown(self, current_equity: float) -> float:
        """Calculate peak-to-trough drawdown percentage."""
        if self.peak_equity <= 0:
            return 0.0
        dd = ((self.peak_equity - current_equity) / self.peak_equity) * 100.0
        return max(0.0, round(dd, 2))

    def determine_stance(
        self,
        current_equity: float,
        threat_level: int,
        crypto_sentiment: int,
        win_rate: float = 50.0
    ) -> Dict[str, Any]:
        """
        Determine current survival stance and active risk parameters.
        """
        self.update_peak_equity(current_equity)
        health = self.calculate_health(current_equity)
        drawdown = self.calculate_drawdown(current_equity)

        # 1. Bunker Mode Conditions (Extreme Capital Threat or WW3/Conflict Alarm)
        if health < 60.0 or threat_level >= 75 or drawdown >= 20.0 or crypto_sentiment <= -60:
            stance = self.STANCE_BUNKER
            label = "BUNKER MODE 🛡️"
            max_positions = 0
            risk_per_trade_pct = 0.0
            stop_loss_pct = 0.01
            trailing_stop_pct = 0.01
            min_score_to_buy = 999  # No buys permitted
            description = "Preserving capital in cash. Severe macro threat or capital drawdown detected."

        # 2. Defensive Mode Conditions (Moderate Risk / Below Initial Capital)
        elif health < 88.0 or threat_level >= 45 or crypto_sentiment <= -20 or drawdown >= 10.0:
            stance = self.STANCE_DEFENSIVE
            label = "DEFENSIVE MODE ⚖️"
            max_positions = 1
            risk_per_trade_pct = 0.10  # ₹100-₹120 max on ₹1K
            stop_loss_pct = 0.015      # 1.5% Stop Loss
            trailing_stop_pct = 0.012  # 1.2% Trailing Stop
            min_score_to_buy = 40      # Grade A++ setups only
            description = "Cautious stance. Small ₹100 allocations with tight trailing stops."

        # 3. Aggressive Expansion (High Profits + Good Market Conditions)
        elif current_equity >= (self.initial_capital * 1.25) and win_rate >= 60.0 and threat_level < 30 and crypto_sentiment >= 25:
            stance = self.STANCE_EXPANSION
            label = "EXPANSION MODE 🚀"
            max_positions = 3
            risk_per_trade_pct = 0.20  # Up to 20%
            stop_loss_pct = 0.025
            trailing_stop_pct = 0.020
            min_score_to_buy = 25
            description = "Capital surplus active. Scaling into high-momentum trend continuations."

        # 4. Standard Prudent Compounding (Normal Operations)
        else:
            stance = self.STANCE_PRUDENT
            label = "PRUDENT COMPOUNDING 🎯"
            max_positions = 2
            risk_per_trade_pct = 0.15  # 15% (₹150 on ₹1,000)
            stop_loss_pct = 0.020      # 2.0% Stop Loss
            trailing_stop_pct = 0.015  # 1.5% Trailing Stop
            min_score_to_buy = 30      # Solid multi-indicator alignment
            description = "Balanced risk-reward compounding with strict capital allocation."

        return {
            "stance": stance,
            "label": label,
            "health_pct": health,
            "drawdown_pct": drawdown,
            "current_equity": round(current_equity, 2),
            "initial_capital": round(self.initial_capital, 2),
            "peak_equity": round(self.peak_equity, 2),
            "net_pnl": round(current_equity - self.initial_capital, 2),
            "net_pnl_pct": round(((current_equity - self.initial_capital) / self.initial_capital) * 100.0, 2),
            "max_positions": max_positions,
            "risk_per_trade_pct": risk_per_trade_pct,
            "stop_loss_pct": stop_loss_pct,
            "trailing_stop_pct": trailing_stop_pct,
            "min_score_to_buy": min_score_to_buy,
            "description": description
        }

    def calculate_order_allocation(
        self,
        current_inr_balance: float,
        current_equity: float,
        stance_info: Dict[str, Any],
        market_price: float,
        market_detail: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate precise order quantity and INR allocation respecting
        CoinDCX min notional (₹100), step size, and survival risk limits.
        """
        if stance_info["stance"] == self.STANCE_BUNKER or stance_info["max_positions"] == 0:
            return {"allowed": False, "reason": "Bunker Mode active - Trading halted"}

        # Target INR allocation based on risk percentage
        target_inr = current_equity * stance_info["risk_per_trade_pct"]

        # Ensure CoinDCX minimum notional of ₹100 INR
        min_notional = 100.0
        min_qty = 1e-6
        step_size = 1e-6
        base_precision = 6

        if market_detail:
            min_notional = float(market_detail.get("min_notional", 100.0) or 100.0)
            min_qty = float(market_detail.get("min_quantity", 1e-6) or 1e-6)
            step_size = float(market_detail.get("step", 1e-6) or 1e-6)
            base_precision = int(market_detail.get("target_currency_precision", 6) or 6)

        allocated_inr = max(target_inr, min_notional)

        # Verify sufficient INR balance
        if current_inr_balance < allocated_inr:
            if current_inr_balance >= min_notional:
                allocated_inr = current_inr_balance * 0.98  # Leave 2% buffer for fees
            else:
                return {
                    "allowed": False,
                    "reason": f"Insufficient INR balance (₹{current_inr_balance:.2f} < Min ₹{min_notional:.2f})"
                }

        # Calculate asset quantity
        if market_price <= 0:
            return {"allowed": False, "reason": "Invalid market price"}

        raw_qty = allocated_inr / market_price

        # Quantize to step size and precision
        if step_size > 0:
            steps = math.floor(raw_qty / step_size)
            final_qty = round(steps * step_size, base_precision)
        else:
            final_qty = round(raw_qty, base_precision)

        if final_qty < min_qty:
            return {
                "allowed": False,
                "reason": f"Calculated quantity {final_qty} below CoinDCX minimum {min_qty}"
            }

        actual_inr_cost = final_qty * market_price

        return {
            "allowed": True,
            "allocated_inr": round(actual_inr_cost, 2),
            "quantity": final_qty,
            "target_inr": round(target_inr, 2),
            "min_notional": min_notional
        }
