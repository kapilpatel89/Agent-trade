import sys
import os
import time
import argparse
from tabulate import tabulate

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from core.coindcx_client import CoinDCXClient
from core.trading_engine import TradingEngine
from core.news_engine import NewsAndConflictEngine

def print_banner():
    print("""
    ================================================================
    [+] NEXUS CRYPTO SURVIVAL AGENT | CoinDCX Autonomous Brain [+]
    ================================================================
    """)

def show_status(engine: TradingEngine):
    equity = engine.get_total_equity()
    health = engine.survival.calculate_health(equity)
    drawdown = engine.survival.calculate_drawdown(equity)
    pnl = equity - engine.survival.initial_capital
    pnl_pct = (pnl / engine.survival.initial_capital) * 100.0

    print("\n--- SURVIVAL STATUS ---")
    print(f"Trading Mode      : {engine.trading_mode.upper()}")
    print(f"Cash INR Balance  : ₹{engine.inr_cash:,.2f}")
    print(f"Total Equity      : ₹{equity:,.2f}")
    print(f"Initial Capital   : ₹{engine.survival.initial_capital:,.2f}")
    print(f"Net PnL           : ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")
    print(f"Survival Health   : {health:.1f}% HP")
    print(f"Drawdown from Peak: {drawdown:.2f}%")
    print(f"Active Positions  : {len(engine.open_positions)}")
    print(f"Total Trades      : {len(engine.trade_history)}")

def show_positions(engine: TradingEngine):
    if not engine.open_positions:
        print("\n[Positions] No open positions. Capital preserved in INR.")
        return

    table = []
    for p in engine.open_positions:
        table.append([
            p["symbol"],
            p["side"],
            p["quantity"],
            f"₹{p['entry_price']:,}",
            f"₹{p.get('current_price', p['entry_price']):,}",
            f"₹{p.get('trailing_stop_price', p['stop_loss_price']):,}",
            f"₹{p.get('unrealized_pnl_inr', 0):+.2f}",
            f"{p.get('unrealized_pnl_pct', 0):+.2f}%"
        ])
    print("\n--- ACTIVE POSITIONS ---")
    print(tabulate(table, headers=["Asset", "Side", "Qty", "Entry", "Current", "Stop/Trail", "PnL (₹)", "PnL (%)"], tablefmt="grid"))

def show_news():
    news_eng = NewsAndConflictEngine()
    data = news_eng.analyze(force_refresh=True)
    print("\n--- GEOPOLITICAL CONFLICT & CRYPTO NEWS RADAR ---")
    print(f"Threat Level    : {data['threat_level']}/100 ({data['threat_status']})")
    print(f"Crypto Sentiment: {data['crypto_sentiment']:+d} ({data['sentiment_label']})")
    print(f"Articles Scanned: {data['total_articles_scanned']}")
    
    print("\nRecent Headlines:")
    for art in data["articles"][:8]:
        print(f"• [{art['badge']}] ({art['source']}) {art['title']}")

def run_cycle_cmd(engine: TradingEngine):
    print("\nExecuting autonomous analysis & decision cycle...")
    res = engine.run_cycle()
    if res.get("status") == "success":
        print(f"✅ Cycle completed. Current Equity: ₹{res['equity']:,.2f}")
        show_status(engine)
        show_positions(engine)
    else:
        print(f"❌ Cycle error: {res.get('message')}")

def main():
    parser = argparse.ArgumentParser(description="Nexus Crypto Survival Trading Agent CLI")
    parser.add_argument("--status", action="store_true", help="Show current survival status and equity")
    parser.add_argument("--positions", action="store_true", help="List active open positions")
    parser.add_argument("--news", action="store_true", help="Fetch breaking conflict and crypto news")
    parser.add_argument("--cycle", action="store_true", help="Run one immediate decision & trading cycle")
    parser.add_argument("--liquidate", action="store_true", help="Emergency liquidate all open positions")
    parser.add_argument("--reset", type=float, help="Reset paper wallet to specified INR amount (e.g. 1000)")

    args = parser.parse_args()
    engine = TradingEngine()

    print_banner()

    if args.status:
        show_status(engine)
    elif args.positions:
        show_positions(engine)
    elif args.news:
        show_news()
    elif args.cycle:
        run_cycle_cmd(engine)
    elif args.liquidate:
        closed = engine.emergency_liquidate_all()
        print(f"🚨 Closed {closed} positions. Secured INR Balance: ₹{engine.inr_cash:,.2f}")
    elif args.reset is not None:
        engine.reset_paper_capital(capital=args.reset)
        print(f"🔄 Wallet reset to ₹{args.reset:,.2f} INR")
    else:
        # Default: show status and run cycle
        show_status(engine)
        show_positions(engine)

if __name__ == "__main__":
    main()
