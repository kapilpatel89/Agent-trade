import sys
import os
import unittest
from pathlib import Path

# Set UTF-8 encoding for standard output if supported
if sys.platform == "win32":
    os.system("")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.coindcx_client import CoinDCXClient
from core.ta_engine import TechnicalAnalysisEngine
from core.news_engine import NewsAndConflictEngine
from core.survival_manager import SurvivalManager
from core.trading_engine import TradingEngine
import config

class TestCryptoSurvivalAgent(unittest.TestCase):

    def setUp(self):
        self.coindcx = CoinDCXClient()
        self.ta_engine = TechnicalAnalysisEngine()
        self.news_engine = NewsAndConflictEngine()
        self.survival = SurvivalManager(initial_capital=1000.0)

    def test_coindcx_public_tickers(self):
        """Verify CoinDCX public tickers endpoint returns active markets."""
        tickers = self.coindcx.get_tickers()
        self.assertIsInstance(tickers, list)
        self.assertGreater(len(tickers), 100, "Should fetch over 100 tickers from CoinDCX")
        
        # Verify BTCINR exists
        btcinr = [t for t in tickers if t.get("market") == "BTCINR"]
        self.assertEqual(len(btcinr), 1, "BTCINR ticker should exist")
        self.assertIn("last_price", btcinr[0])
        print(f"[OK] CoinDCX Tickers: Found {len(tickers)} tickers. BTCINR Price: Rs.{btcinr[0]['last_price']}")

    def test_coindcx_candles(self):
        """Verify CoinDCX candles endpoint returns OHLCV candlestick data."""
        candles = self.coindcx.get_candles(pair="I-BTC_INR", interval="1h", limit=20)
        self.assertIsInstance(candles, list)
        self.assertGreaterEqual(len(candles), 10, "Should fetch at least 10 candles")
        self.assertIn("open", candles[0])
        self.assertIn("close", candles[0])
        self.assertIn("high", candles[0])
        self.assertIn("low", candles[0])
        print(f"[OK] CoinDCX Candles: Fetched {len(candles)} candles for I-BTC_INR.")

    def test_technical_analysis(self):
        """Verify TA Engine computes RSI, MACD, Bollinger Bands, ATR, and Technical Score."""
        candles = self.coindcx.get_candles(pair="I-BTC_INR", interval="1h", limit=50)
        ta = self.ta_engine.analyze(candles)
        self.assertEqual(ta["status"], "success")
        self.assertIn("rsi", ta)
        self.assertIn("macd_hist", ta)
        self.assertIn("bb_upper", ta)
        self.assertIn("atr", ta)
        self.assertIn("score", ta)
        self.assertIn("signal", ta)
        print(f"[OK] TA Engine: Score: {ta['score']}, Signal: {ta['signal']}, RSI: {ta['rsi']}, ATR: Rs.{ta['atr']}")

    def test_news_conflict_engine(self):
        """Verify news engine calculates threat level and crypto sentiment."""
        news_data = self.news_engine.analyze(force_refresh=True)
        self.assertIn("threat_level", news_data)
        self.assertIn("crypto_sentiment", news_data)
        self.assertIn("articles", news_data)
        self.assertGreater(news_data["total_articles_scanned"], 0)
        print(f"[OK] News & Conflict: Threat: {news_data['threat_level']}/100, Sentiment: {news_data['crypto_sentiment']}, Articles: {news_data['total_articles_scanned']}")

    def test_survival_manager_stances(self):
        """Verify survival manager switches stances and allocates risk accurately."""
        # 1. Normal Prudent Compounding (Rs. 1,000)
        normal_stance = self.survival.determine_stance(
            current_equity=1000.0,
            threat_level=15,
            crypto_sentiment=10
        )
        self.assertEqual(normal_stance["stance"], SurvivalManager.STANCE_PRUDENT)
        self.assertEqual(normal_stance["health_pct"], 100.0)

        # 2. Defensive Stance (Drawdown to Rs. 870)
        defensive_stance = self.survival.determine_stance(
            current_equity=870.0,
            threat_level=20,
            crypto_sentiment=0
        )
        self.assertEqual(defensive_stance["stance"], SurvivalManager.STANCE_DEFENSIVE)
        self.assertLess(defensive_stance["health_pct"], 90.0)

        # 3. Bunker Stance (High WW3 Threat or Rs. 550 Equity)
        bunker_stance = self.survival.determine_stance(
            current_equity=550.0,
            threat_level=80,
            crypto_sentiment=-70
        )
        self.assertEqual(bunker_stance["stance"], SurvivalManager.STANCE_BUNKER)
        self.assertEqual(bunker_stance["max_positions"], 0)

        # 4. Allocation calculation for Rs. 1,000 wallet
        alloc = self.survival.calculate_order_allocation(
            current_inr_balance=1000.0,
            current_equity=1000.0,
            stance_info=normal_stance,
            market_price=7800000.0  # BTC price in INR
        )
        self.assertTrue(alloc["allowed"], f"Allocation failed: {alloc.get('reason')}")
        self.assertGreaterEqual(alloc["allocated_inr"], 100.0, "Must satisfy CoinDCX Rs. 100 min notional")
        self.assertLessEqual(alloc["allocated_inr"], 200.0, "Must obey survival risk cap")
        print(f"[OK] Survival Manager: Stances & allocation verified (Allocated Rs.{alloc['allocated_inr']}).")

    def test_trading_engine_paper_execution(self):
        """Verify full paper trade lifecycle: Buy -> Trailing Stop Update -> Sell -> Net PnL."""
        engine = TradingEngine(initial_capital=1000.0)
        engine.reset_paper_capital(1000.0)
        self.assertEqual(engine.inr_cash, 1000.0)

        mock_decision = {
            "market": "BTCINR",
            "pair": "I-BTC_INR",
            "symbol": "BTC",
            "action": "BUY",
            "current_price": 7800000.0,
            "stop_loss_price": 7650000.0,
            "take_profit_1": 8100000.0,
            "take_profit_2": 8400000.0,
            "thesis": "Test Buy Setup"
        }

        # Execute Buy
        success = engine.execute_buy(mock_decision)
        self.assertTrue(success, "Paper buy should execute successfully")
        self.assertEqual(len(engine.open_positions), 1)
        self.assertLess(engine.inr_cash, 1000.0)

        # Execute Sell at 5% profit
        pos = engine.open_positions[0]
        sell_price = pos["entry_price"] * 1.05
        engine.execute_sell(pos, sell_price, "TP Target")

        self.assertEqual(len(engine.open_positions), 0)
        self.assertEqual(len(engine.trade_history), 1)
        self.assertGreater(engine.inr_cash, 1000.0, "Account should be in net profit after winning trade")
        print(f"[OK] Trading Engine: Final Cash: Rs.{engine.inr_cash:.2f}, Closed PnL: Rs.{engine.trade_history[0]['net_pnl_inr']:+.2f}")

if __name__ == "__main__":
    unittest.main()
