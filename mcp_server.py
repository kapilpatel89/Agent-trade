import sys
import json
import time
from typing import Dict, Any, List, Optional
import config
from core.trading_engine import TradingEngine
from core.market_scanner import MarketScanner
from core.ta_engine import TechnicalAnalysisEngine
from core.news_engine import NewsAndConflictEngine

# Singleton Engine Instance for MCP
engine = TradingEngine(initial_capital=config.DEFAULT_INITIAL_CAPITAL)

TOOLS_METADATA = [
    {
        "name": "get_portfolio_status",
        "description": "Get real-time crypto portfolio equity, cash INR balance, net PnL, survival health HP %, win rate, and active survival risk stance (Bunker/Defensive/Prudent/Expansion).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "scan_top_movers",
        "description": "Scan all 340+ CoinDCX INR crypto markets in real-time to discover top 24h gainers, volume surge leaders, and high-probability breakout momentum pairs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force_refresh": {
                    "type": "boolean",
                    "description": "Force live fetch from CoinDCX ticker API."
                }
            },
            "required": []
        }
    },
    {
        "name": "analyze_crypto_pair",
        "description": "Perform multi-timeframe Technical Analysis (RSI 14, MACD 12/26/9, Bollinger Bands 20/2, EMA Ribbon 9/21/50/200, ATR Stop-Loss, and Candlestick Pattern detection) for any CoinDCX pair (e.g. I-BTC_INR, I-ETH_INR, I-SOL_INR, I-HNT_INR).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pair": {
                    "type": "string",
                    "description": "CoinDCX candlestick pair symbol (e.g., 'I-BTC_INR', 'I-ETH_INR', 'I-SOL_INR', 'I-HNT_INR')."
                },
                "interval": {
                    "type": "string",
                    "description": "Candle timeframe: '1m', '15m', '1h', '1d'. Default is '1h'."
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of candle bars (e.g. 50)."
                }
            },
            "required": ["pair"]
        }
    },
    {
        "name": "get_macro_conflict_radar",
        "description": "Get real-time Geopolitical Conflict Threat Level (0-100) and Crypto Market Sentiment (-100 to +100) analyzed from live RSS news feeds (CoinTelegraph, CoinDesk, Decrypt, Google News).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force_refresh": {
                    "type": "boolean",
                    "description": "Force refresh news feeds."
                }
            },
            "required": []
        }
    },
    {
        "name": "execute_paper_trade",
        "description": "Execute a simulated paper buy trade on a CoinDCX INR pair with dynamic risk allocation, ATR stop-loss, and take-profit targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "CoinDCX market symbol (e.g., 'BTCINR', 'SOLINR', 'HNTINR')."
                },
                "pair": {
                    "type": "string",
                    "description": "Candle pair identifier (e.g., 'I-BTC_INR', 'I-SOL_INR', 'I-HNT_INR')."
                },
                "symbol": {
                    "type": "string",
                    "description": "Base asset symbol (e.g., 'BTC', 'SOL', 'HNT')."
                }
            },
            "required": ["market", "pair", "symbol"]
        }
    },
    {
        "name": "emergency_liquidate",
        "description": "Emergency close all active open positions at market price to convert 100% of capital into safeguarded INR cash.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_thought_stream",
        "description": "Get the live non-repetitive real-time reasoning stream of the agent showing coin-by-coin analysis, trailing stop adjustments, and market theses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent thoughts to retrieve (default 20)."
                }
            },
            "required": []
        }
    }
]

def handle_mcp_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch and process standard MCP JSON-RPC 2.0 requests."""
    method = req.get("method", "")
    msg_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "nexus-crypto-survival-agent",
                    "version": "2.0.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS_METADATA
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        try:
            if tool_name == "get_portfolio_status":
                eq = engine.get_total_equity()
                stance = engine.latest_stance or engine.survival.determine_stance(
                    current_equity=eq,
                    threat_level=engine.latest_news_data.get("threat_level", 10),
                    crypto_sentiment=engine.latest_news_data.get("crypto_sentiment", 10)
                )
                res = {
                    "inr_cash": round(engine.inr_cash, 2),
                    "total_equity": round(eq, 2),
                    "initial_capital": engine.survival.initial_capital,
                    "net_pnl_inr": round(eq - engine.survival.initial_capital, 2),
                    "net_pnl_pct": round(((eq - engine.survival.initial_capital) / engine.survival.initial_capital) * 100.0, 2),
                    "health_pct": stance.get("health_pct", 100.0),
                    "survival_stance": stance.get("label", "PRUDENT"),
                    "open_positions": engine.open_positions,
                    "total_closed_trades": len(engine.trade_history)
                }

            elif tool_name == "scan_top_movers":
                force = args.get("force_refresh", False)
                res = engine.scanner.scan_all_inr_markets(force_refresh=force)

            elif tool_name == "analyze_crypto_pair":
                pair = args.get("pair", "I-BTC_INR")
                interval = args.get("interval", "1h")
                limit = int(args.get("limit", 50))
                candles = engine.coindcx.get_candles(pair=pair, interval=interval, limit=limit)
                ta_engine = TechnicalAnalysisEngine()
                res = ta_engine.analyze(candles)

            elif tool_name == "get_macro_conflict_radar":
                force = args.get("force_refresh", False)
                news_engine = NewsAndConflictEngine()
                res = news_engine.analyze(force_refresh=force)

            elif tool_name == "execute_paper_trade":
                market = args["market"]
                pair = args["pair"]
                symbol = args["symbol"]

                # Fetch live candles
                candles = engine.coindcx.get_candles(pair=pair, interval="1h", limit=40)
                ta = TechnicalAnalysisEngine().analyze(candles)
                price = ta.get("current_price", 100.0)

                order_res = engine.execute_paper_buy(
                    market=market,
                    pair=pair,
                    symbol=symbol,
                    price=price,
                    stop_loss=round(price * 0.98, 2),
                    take_profit_1=round(price * 1.04, 2),
                    take_profit_2=round(price * 1.08, 2),
                    thesis="Executed via MCP Agent Tool"
                )
                res = order_res

            elif tool_name == "emergency_liquidate":
                closed_count = engine.emergency_liquidate_all()
                res = {
                    "status": "success",
                    "closed_positions": closed_count,
                    "final_inr_cash": round(engine.inr_cash, 2)
                }

            elif tool_name == "get_thought_stream":
                limit = int(args.get("limit", 20))
                thoughts = engine.brain.thought_history[-limit:]
                res = {"thoughts": list(reversed(thoughts))}

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found."}
                }

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, indent=2)
                        }
                    ]
                }
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(e)}
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method '{method}' not supported."}
        }

def run_stdio_server():
    """Run standard MCP stdio loop for Antigravity / Claude / agent clients."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            response = handle_mcp_request(req)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    run_stdio_server()
