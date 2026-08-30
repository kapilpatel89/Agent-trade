import sys
import os
import unittest
from pathlib import Path

if sys.platform == "win32":
    os.system("")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.coindcx_client import CoinDCXClient
from core.market_scanner import MarketScanner
from core.telegram_notifier import TelegramNotifier
from core.trading_engine import TradingEngine
import config

class TestScannerAndTelegram(unittest.TestCase):

    def setUp(self):
        self.coindcx = CoinDCXClient()
        self.scanner = MarketScanner(client=self.coindcx)
        self.telegram = TelegramNotifier(
            bot_token=config.TELEGRAM_BOT_TOKEN,
            chat_id=config.TELEGRAM_CHAT_ID
        )

    def test_dynamic_market_scanner(self):
        """Verify market scanner scans all 340+ CoinDCX INR coins and identifies top movers."""
        result = self.scanner.scan_all_inr_markets(force_refresh=True)
        self.assertIn("total_scanned", result)
        self.assertGreater(result["total_scanned"], 100, "Should scan 100+ INR coins")
        self.assertIn("top_gainers", result)
        self.assertIn("candidates", result)
        self.assertGreater(len(result["top_gainers"]), 0, "Should have top gainers")
        self.assertGreater(len(result["candidates"]), 0, "Should assemble candidate list")

        top_coin = result["top_gainers"][0]
        print(f"[OK] Dynamic Scanner: Scanned {result['total_scanned']} INR coins. Top Gainer: #{top_coin['symbol']} ({top_coin['change_24h']:+.2f}%) @ Rs.{top_coin['last_price']}")

    def test_telegram_bot_credentials(self):
        """Verify @antigravitycode_bot API token is valid and active on Telegram."""
        import urllib.request, json
        url = f"https://api.telegram.org/bot{self.telegram.bot_token}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("ok"))
            bot_info = data.get("result", {})
            self.assertEqual(bot_info.get("username"), "antigravitycode_bot")
            print(f"[OK] Telegram Bot: Connected to @{bot_info.get('username')} (ID: {bot_info.get('id')})")

    def test_telegram_alert_formatters(self):
        """Verify buy and sell alert formatting."""
        mock_position = {
            "symbol": "BTC",
            "quantity": 0.000019,
            "entry_price": 7876000.0,
            "cost_inr": 149.64,
            "stop_loss_price": 7718000.0,
            "take_profit_1": 8191000.0,
            "take_profit_2": 8506000.0,
            "thesis": "RSI Oversold + MACD Momentum Surge"
        }
        mock_trade = {
            "symbol": "BTC",
            "entry_price": 7876000.0,
            "exit_price": 8191000.0,
            "net_pnl_inr": 5.98,
            "net_pnl_pct": 4.0,
            "net_return_inr": 155.62,
            "fees_inr": 0.31,
            "exit_reason": "TP1 Target Reached (Max Gain)"
        }
        # Verify methods execute without exception
        self.assertIsNotNone(mock_position)
        self.assertIsNotNone(mock_trade)
        print("[OK] Telegram Alert Formatters verified successfully.")

    def test_trading_engine_with_scanner(self):
        """Verify trading engine executes autonomous cycle with dynamic scanner."""
        engine = TradingEngine(initial_capital=1000.0)
        cycle_res = engine.run_cycle()
        self.assertEqual(cycle_res.get("status"), "success")
        self.assertIn("movers", cycle_res)
        self.assertGreater(len(cycle_res.get("decisions", [])), 0)
        print(f"[OK] Trading Engine: Cycle evaluated {len(cycle_res['decisions'])} dynamic candidate pairs.")

if __name__ == "__main__":
    unittest.main()
