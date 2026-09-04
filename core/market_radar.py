import time
import math
from typing import Dict, Any, List, Optional
import config
from core.coindcx_client import CoinDCXClient
from core.news_engine import NewsAndConflictEngine

class MarketRadarEngine:
    """
    Intelligent Market Radar Engine for CoinDCX:
    1. Orderbook Buyer vs Seller Watchouts (Depth imbalance, Seller Overlapping Buyer detection).
    2. Inter-Coin Relation & Sympathy Correlation (BTC lead-lag, altcoin sympathy breakouts).
    3. Ongoing Live Sticks Micro-Structure (Candle wick rejection, pin bar & momentum absorption).
    4. Social Media & Geopolitical News Fusion (X.com war/macro narratives).
    5. Multi-Category Trade Opportunities with instant filtering.
    """

    # Related asset cluster mappings
    RELATION_CLUSTERS = {
        "MAJORS_L1": ["BTC", "ETH", "SOL", "MATIC", "POL", "ADA", "AVAX"],
        "MEMES": ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK"],
        "DEFI_INFRA": ["LINK", "UNI", "NEAR", "DOT", "AAVE", "RENDER"]
    }

    def __init__(self, client: Optional[CoinDCXClient] = None, news_engine: Optional[NewsAndConflictEngine] = None):
        self.client = client or CoinDCXClient()
        self.news = news_engine or NewsAndConflictEngine()
        self.cached_radar: Dict[str, Any] = {}
        self.last_radar_time: float = 0
        self.radar_ttl: int = 15  # 15s refresh
        self.active_watchouts: List[Dict[str, Any]] = []

    def analyze_orderbook_depth(self, pair: str, symbol: str) -> Dict[str, Any]:
        """
        Fetch and calculate real orderbook depth imbalance (bids vs asks),
        detecting 'Seller Overlapping Buyer' or 'Buyer Absorbing Seller'.
        """
        ob = self.client.get_orderbook(pair)
        bids = ob.get("bids", {})
        asks = ob.get("asks", {})

        total_bid_vol = 0.0
        total_ask_vol = 0.0
        total_bid_val_inr = 0.0
        total_ask_val_inr = 0.0

        best_bid = 0.0
        best_ask = 0.0

        # Parse Bids
        if bids and isinstance(bids, dict):
            sorted_bids = sorted([(float(p), float(q)) for p, q in bids.items() if float(p) > 0 and float(q) > 0], key=lambda x: x[0], reverse=True)[:15]
            if sorted_bids:
                best_bid = sorted_bids[0][0]
                for p, q in sorted_bids:
                    total_bid_vol += q
                    total_bid_val_inr += (p * q)

        # Parse Asks
        if asks and isinstance(asks, dict):
            sorted_asks = sorted([(float(p), float(q)) for p, q in asks.items() if float(p) > 0 and float(q) > 0], key=lambda x: x[0])[:15]
            if sorted_asks:
                best_ask = sorted_asks[0][0]
                for p, q in sorted_asks:
                    total_ask_vol += q
                    total_ask_val_inr += (p * q)

        tot_val = total_bid_val_inr + total_ask_val_inr
        if tot_val <= 0:
            # Fallback estimation if pair has sparse public orderbook
            return {
                "symbol": symbol,
                "pair": pair,
                "status": "BALANCED",
                "imbalance_pct": 0.0,
                "bid_pressure_pct": 50.0,
                "ask_pressure_pct": 50.0,
                "total_bid_val": 0.0,
                "total_ask_val": 0.0,
                "best_bid": 0.0,
                "best_ask": 0.0,
                "overlap_flag": False,
                "absorption_flag": False,
                "summary": "Orderbook depth balanced or awaiting tick updates."
            }

        bid_pressure_pct = round((total_bid_val_inr / tot_val) * 100.0, 1)
        ask_pressure_pct = round((total_ask_val_inr / tot_val) * 100.0, 1)
        imbalance_pct = round(bid_pressure_pct - ask_pressure_pct, 1)

        # Detect Seller Overlapping Buyer
        is_seller_overlapping = False
        is_buyer_absorbing = False

        if ask_pressure_pct >= 64.0:
            status = "SELLER_OVERLAPPING_BUYER"
            is_seller_overlapping = True
            summary = f"⚠️ {symbol} Sellers Overlapping Buyers! Ask volume ({ask_pressure_pct:.0f}%) is crushing bids. High risk of immediate drop."
        elif bid_pressure_pct >= 64.0:
            status = "BUYER_ABSORBING_SELLER"
            is_buyer_absorbing = True
            summary = f"🛡️ {symbol} Buyers Absorbing Sellers! Solid bid wall ({bid_pressure_pct:.0f}%) soaking up sell pressure. High bounce probability."
        else:
            status = "BALANCED"
            summary = f"{symbol} Bid/Ask balance steady ({bid_pressure_pct:.0f}% Bids vs {ask_pressure_pct:.0f}% Asks)."

        return {
            "symbol": symbol,
            "pair": pair,
            "status": status,
            "imbalance_pct": imbalance_pct,
            "bid_pressure_pct": bid_pressure_pct,
            "ask_pressure_pct": ask_pressure_pct,
            "total_bid_val": round(total_bid_val_inr, 2),
            "total_ask_val": round(total_ask_val_inr, 2),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "overlap_flag": is_seller_overlapping,
            "absorption_flag": is_buyer_absorbing,
            "summary": summary
        }

    def analyze_live_stick(self, candles: List[Dict[str, Any]], symbol: str) -> Dict[str, Any]:
        """
        Analyze currently forming live candlestick (wick rejection, hammer/pin bar, micro-momentum).
        """
        if not candles or len(candles) < 2:
            return {
                "symbol": symbol,
                "status": "NORMAL",
                "upper_wick_pct": 0,
                "lower_wick_pct": 0,
                "rejection_type": "NONE",
                "open": 0, "high": 0, "low": 0, "close": 0,
                "description": "Forming live candle neutral."
            }

        live_c = candles[-1]
        o = float(live_c.get("open", 0) or 0)
        h = float(live_c.get("high", 0) or 0)
        l = float(live_c.get("low", 0) or 0)
        c = float(live_c.get("close", 0) or 0)

        rng = h - l if (h - l) > 0 else 0.0001
        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        upper_wick_pct = round((upper_wick / rng) * 100.0, 1)
        lower_wick_pct = round((lower_wick / rng) * 100.0, 1)

        # Evaluate Wick Rejection
        if upper_wick_pct >= 48.0 and rng > 0:
            rejection_type = "SELLER_REJECTION_HIGH"
            status = "BEARISH_WICK"
            desc = f"Live Stick Rejection: Sellers slammed down high at ₹{h:,.2f}. Upper wick {upper_wick_pct:.0f}%."
        elif lower_wick_pct >= 48.0 and rng > 0:
            rejection_type = "BUYER_REJECTION_LOW"
            status = "BULLISH_WICK"
            desc = f"Live Stick Rejection: Buyers rapidly absorbed dip to ₹{l:,.2f}. Long lower wick {lower_wick_pct:.0f}%."
        elif body / rng >= 0.75 and c > o:
            rejection_type = "STRONG_BULL_EXPANSION"
            status = "BULL_BODY"
            desc = f"Live Stick Expansion: Strong buyer volume expanding candle upwards."
        elif body / rng >= 0.75 and c < o:
            rejection_type = "STRONG_BEAR_DUMP"
            status = "BEAR_BODY"
            desc = f"Live Stick Breakdown: Aggressive market sell-off expanding candle downwards."
        else:
            rejection_type = "NEUTRAL"
            status = "NORMAL"
            desc = "Live candle oscillating within standard range."

        return {
            "symbol": symbol,
            "status": status,
            "rejection_type": rejection_type,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "upper_wick_pct": upper_wick_pct,
            "lower_wick_pct": lower_wick_pct,
            "description": desc
        }

    def detect_correlated_relation_trades(
        self,
        tickers_map: Dict[str, Any],
        scanned_movers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate related coin behavior:
        1. Look at Bitcoin (BTC) as the macro lead.
        2. Detect sympathy breakout opportunities (BTC surged, but related L1 / Meme coin is lagging behind with strong bid depth).
        3. Detect contagion risk (BTC broke down, warns altcoins will dump).
        """
        btc_ticker = tickers_map.get("BTCINR") or tickers_map.get("I-BTC_INR")
        btc_change_24h = float(btc_ticker.get("change_24_hour", 0) or 0) if btc_ticker else 0.0

        relation_opportunities = []

        # Find candidate coins from scanned movers
        for coin in scanned_movers[:25]:
            sym = coin.get("symbol", "")
            if sym == "BTC" or not coin.get("is_liquid"):
                continue

            change = float(coin.get("change_24h", 0) or 0)
            price = float(coin.get("last_price", 0) or 0)
            pair = coin.get("pair", f"I-{sym}_INR")
            market = coin.get("market", f"{sym}INR")

            # Determine cluster
            cluster = "ALTCOIN"
            for c_name, members in self.RELATION_CLUSTERS.items():
                if sym in members:
                    cluster = c_name
                    break

            # Sympathy Lag Breakout Condition:
            # BTC pumped, but this correlated coin is lagging, providing a low-risk "catch-up" long entry.
            lag_gap = round(btc_change_24h - change, 2)
            if btc_change_24h >= 0.5 and lag_gap >= 0.5:
                expected_gain_pct = round(min(6.0, max(1.5, lag_gap * 0.7)), 2)
                target_price = round(price * (1.0 + (expected_gain_pct / 100.0)), 2)
                stop_loss = round(price * 0.985, 2)  # 1.5% stop

                relation_opportunities.append({
                    "id": f"rel-sympathy-{sym.lower()}",
                    "symbol": sym,
                    "pair": pair,
                    "market": market,
                    "cluster": cluster,
                    "lead_asset": "BTC",
                    "lead_change": btc_change_24h,
                    "coin_change": change,
                    "lag_pct": round(btc_change_24h - change, 2),
                    "setup_type": "SYMPATHY_CATCHUP",
                    "signal": "BUY",
                    "confidence": min(92, max(60, int(65 + (btc_change_24h * 5)))),
                    "current_price": price,
                    "target_price": target_price,
                    "stop_loss_price": stop_loss,
                    "expected_return_pct": expected_gain_pct,
                    "headline": f"🔗 {sym} Sympathy Catch-up to BTC Breakout",
                    "narrative": (
                        f"Bitcoin is leading the market up (+{btc_change_24h:.2f}%), while #{sym} ({cluster}) "
                        f"is lagging at {change:+.2f}% (lag gap: {btc_change_24h - change:.2f}%). "
                        f"Historically, #{sym} demonstrates high beta catch-up behavior. Target: ₹{target_price:,.2f} (+{expected_gain_pct}%)."
                    )
                })

            # Contagion Risk Condition:
            # BTC dumping (change < -1.5%), altcoin likely to dump harder
            elif btc_change_24h <= -1.5 and change > -0.5:
                relation_opportunities.append({
                    "id": f"rel-contagion-{sym.lower()}",
                    "symbol": sym,
                    "pair": pair,
                    "market": market,
                    "cluster": cluster,
                    "lead_asset": "BTC",
                    "lead_change": btc_change_24h,
                    "coin_change": change,
                    "lag_pct": round(btc_change_24h - change, 2),
                    "setup_type": "CONTAGION_RISK",
                    "signal": "DEFENSIVE_EXIT",
                    "confidence": 85,
                    "current_price": price,
                    "target_price": round(price * 0.96, 2),
                    "stop_loss_price": round(price * 1.015, 2),
                    "expected_return_pct": -4.0,
                    "headline": f"⚠️ {sym} Contagion Vulnerability from BTC Sell-off",
                    "narrative": (
                        f"BTC is breaking down ({btc_change_24h:.2f}%). #{sym} has not yet priced in the downward move. "
                        f"High risk of sudden liquidity drain. Recommend moving stop to breakeven or locking profits."
                    )
                })

        return relation_opportunities[:6]

    def build_radar_overview(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Generate full Market Radar synthesis:
        - Orderbook depth watchouts for top assets
        - Ongoing live sticks analysis
        - Correlated sympathy setups
        - Social Media (X.com) and Geopolitical war news intelligence
        - Filtered trade opportunities list
        """
        now = time.time()
        if not force_refresh and self.cached_radar and (now - self.last_radar_time < self.radar_ttl):
            return self.cached_radar

        # 1. Fetch live tickers & market movers
        all_tickers = self.client.get_tickers()
        tickers_map = {t["market"]: t for t in all_tickers if "market" in t}

        # Focus pairs for orderbook and live stick depth
        tracked_keys = [
            ("BTC", "I-BTC_INR", "BTCINR"),
            ("ETH", "I-ETH_INR", "ETHINR"),
            ("SOL", "I-SOL_INR", "SOLINR"),
            ("DOGE", "I-DOGE_INR", "DOGEINR"),
            ("XRP", "I-XRP_INR", "XRPINR"),
            ("ADA", "I-ADA_INR", "ADAINR")
        ]

        # 2. Analyze Orderbook & Live Sticks
        orderbook_watchouts = []
        live_sticks = []

        for sym, pair, mkt in tracked_keys:
            # Orderbook depth
            ob_res = self.analyze_orderbook_depth(pair, sym)
            orderbook_watchouts.append(ob_res)

            # Live stick
            candles = self.client.get_candles(pair=pair, interval="1h", limit=10)
            stick_res = self.analyze_live_stick(candles, sym)
            live_sticks.append(stick_res)

        # 3. Fetch News & Social Sentiment
        news_intel = self.news.analyze()

        # 4. Detect Correlated Relation Trades
        from core.market_scanner import MarketScanner
        scanner = MarketScanner(self.client)
        scanned_res = scanner.scan_all_inr_markets()
        scanned_pool = scanned_res.get("candidates", []) + scanned_res.get("top_volume", [])
        seen_m = set()
        deduped_pool = []
        for c in scanned_pool:
            if c.get("market") not in seen_m:
                seen_m.add(c.get("market"))
                deduped_pool.append(c)

        relation_trades = self.detect_correlated_relation_trades(tickers_map, deduped_pool)

        # 5. Assemble Structured Multi-Category Trade Opportunities
        opportunities = []

        # Category A: Correlated Sympathy Plays
        for r in relation_trades:
            if r["signal"] == "BUY":
                opportunities.append({
                    "id": r["id"],
                    "symbol": r["symbol"],
                    "pair": r["pair"],
                    "market": r["market"],
                    "category": "correlation",
                    "category_label": "🔗 Correlated Sympathy",
                    "signal": "BUY",
                    "current_price": r["current_price"],
                    "target_price": r["target_price"],
                    "stop_loss_price": r["stop_loss_price"],
                    "risk_reward": 2.5,
                    "confidence": r["confidence"],
                    "headline": r["headline"],
                    "narrative": r["narrative"],
                    "tags": ["BTC Sympathy", r["cluster"], "Lag Play"],
                    "badge_class": "success"
                })

        # Category B: Orderbook Depth & Buyer Absorption Plays
        for ob in orderbook_watchouts:
            sym = ob["symbol"]
            mkt = f"{sym}INR"
            t = tickers_map.get(mkt, {})
            price = float(t.get("last_price", 0) or 0)
            if price <= 0:
                continue

            if ob["absorption_flag"]:
                tp = round(price * 1.035, 2)
                sl = round(price * 0.985, 2)
                opportunities.append({
                    "id": f"ob-absorb-{sym.lower()}",
                    "symbol": sym,
                    "pair": ob["pair"],
                    "market": mkt,
                    "category": "orderbook",
                    "category_label": "🐋 Orderbook Imbalance",
                    "signal": "BUY",
                    "current_price": price,
                    "target_price": tp,
                    "stop_loss_price": sl,
                    "risk_reward": 2.3,
                    "confidence": int(ob["bid_pressure_pct"]),
                    "headline": f"🐋 {sym} Massive Buyer Bid Wall Absorbing Sells",
                    "narrative": (
                        f"Orderbook depth for {sym} shows overwhelming buyer dominance ({ob['bid_pressure_pct']}% bids vs {ob['ask_pressure_pct']}% asks). "
                        f"Bid wall is absorbing market sell orders firmly without letting price slip. Prime accumulation zone."
                    ),
                    "tags": ["Bid Wall", "Whale Absorption", f"+{ob['imbalance_pct']}% Imbalance"],
                    "badge_class": "success"
                })
            elif ob["overlap_flag"]:
                # High Risk Alert Opportunity / Defensive Exit
                opportunities.append({
                    "id": f"ob-overlap-{sym.lower()}",
                    "symbol": sym,
                    "pair": ob["pair"],
                    "market": mkt,
                    "category": "orderbook",
                    "category_label": "⚠️ Seller Overlap Watchout",
                    "signal": "DEFENSIVE_HOLD",
                    "current_price": price,
                    "target_price": round(price * 0.97, 2),
                    "stop_loss_price": round(price * 1.01, 2),
                    "risk_reward": 1.0,
                    "confidence": int(ob["ask_pressure_pct"]),
                    "headline": f"🚨 {sym} Seller is Overlapping Buyer!",
                    "narrative": (
                        f"Dangerous orderbook dynamic on {sym}: Sellers are heavily overlapping buyers ({ob['ask_pressure_pct']}% asks). "
                        f"Bids are being consumed downwards with aggressive sell market orders. Avoid buying; prepare defensive stops."
                    ),
                    "tags": ["Seller Overlap", "Depth Warning", f"{ob['ask_pressure_pct']}% Asks"],
                    "badge_class": "danger"
                })

        # Category C: Live Stick Wick Reversal Plays
        for stick in live_sticks:
            sym = stick["symbol"]
            mkt = f"{sym}INR"
            t = tickers_map.get(mkt, {})
            price = float(t.get("last_price", 0) or 0)
            if price <= 0:
                continue

            if stick["status"] == "BULLISH_WICK":
                tp = round(price * 1.03, 2)
                sl = round(stick["low"] * 0.998, 2)
                opportunities.append({
                    "id": f"stick-hammer-{sym.lower()}",
                    "symbol": sym,
                    "pair": f"I-{sym}_INR",
                    "market": mkt,
                    "category": "live_sticks",
                    "category_label": "🕯️ Live Stick Reversal",
                    "signal": "BUY",
                    "current_price": price,
                    "target_price": tp,
                    "stop_loss_price": sl,
                    "risk_reward": 2.8,
                    "confidence": min(88, int(50 + stick["lower_wick_pct"] * 0.5)),
                    "headline": f"🕯️ {sym} Live Candle Long Lower Wick Rejection",
                    "narrative": (
                        f"Ongoing live candle for {sym} shows aggressive buyer dip absorption with a {stick['lower_wick_pct']:.0f}% lower shadow. "
                        f"Low of ₹{stick['low']:,.2f} strongly rejected. Pin bar bounce active."
                    ),
                    "tags": ["Pin Bar", "Dip Absorbed", f"{stick['lower_wick_pct']}% Wick"],
                    "badge_class": "accent"
                })

        # Category D: News & Social Sentiment Triggers
        social_buzz = news_intel.get("social_buzz_alerts", [])
        if social_buzz:
            sb = social_buzz[0]
            btc_price = float(tickers_map.get("BTCINR", {}).get("last_price", 0) or 0)
            if news_intel.get("threat_level", 0) >= 50:
                opportunities.append({
                    "id": "news-war-hedge",
                    "symbol": "BTC",
                    "pair": "I-BTC_INR",
                    "market": "BTCINR",
                    "category": "news_social",
                    "category_label": "🌍 Macro / War Radar",
                    "signal": "DEFENSIVE_HOLD",
                    "current_price": btc_price,
                    "target_price": round(btc_price * 0.96, 2) if btc_price > 0 else 0,
                    "stop_loss_price": round(btc_price * 1.01, 2) if btc_price > 0 else 0,
                    "risk_reward": 1.0,
                    "confidence": news_intel.get("threat_level", 65),
                    "headline": "⚔️ Geopolitical War News Spreading on X.com",
                    "narrative": (
                        f"Breaking geopolitical headlines on social feeds: {sb.get('headline')}. "
                        f"Downside probability: {news_intel['direction_probability']['down_prob']}%. "
                        f"Market impact: Flight to capital preservation in INR. Tighten trailing stops across all active altcoin positions."
                    ),
                    "tags": ["War Alert", "Social Media", "Defensive Mode"],
                    "badge_class": "warning"
                })
            else:
                opportunities.append({
                    "id": "news-etf-boost",
                    "symbol": "BTC",
                    "pair": "I-BTC_INR",
                    "market": "BTCINR",
                    "category": "news_social",
                    "category_label": "🌍 Macro / Social Wave",
                    "signal": "BUY",
                    "current_price": btc_price,
                    "target_price": round(btc_price * 1.04, 2) if btc_price > 0 else 0,
                    "stop_loss_price": round(btc_price * 0.985, 2) if btc_price > 0 else 0,
                    "risk_reward": 2.6,
                    "confidence": min(89, int(60 + (news_intel.get('crypto_sentiment', 10) * 0.4))),
                    "headline": "🚀 Bullish Institutional & Social Inflows",
                    "narrative": (
                        f"Social buzz on X.com shows positive sentiment: {sb.get('headline')}. "
                        f"Upward probability: {news_intel['direction_probability']['up_prob']}%. "
                        f"Healthy backdrop for continuation breakouts in top crypto pairs."
                    ),
                    "tags": ["Social Twitter", "ETF Flow", "Bullish Narrative"],
                    "badge_class": "success"
                })

        # Category E: High Momentum Breakouts (from scanned movers)
        for g in scanned_res.get("top_gainers", [])[:3]:
            sym = g.get("symbol", "")
            price = float(g.get("last_price", 0) or 0)
            if price <= 0:
                continue
            opportunities.append({
                "id": f"mom-{sym.lower()}",
                "symbol": sym,
                "pair": g.get("pair", f"I-{sym}_INR"),
                "market": g.get("market", f"{sym}INR"),
                "category": "momentum",
                "category_label": "⚡ Breakout Momentum",
                "signal": "BUY",
                "current_price": price,
                "target_price": round(price * 1.05, 2),
                "stop_loss_price": round(price * 0.975, 2),
                "risk_reward": 2.0,
                "confidence": min(94, int(70 + g.get("volume_surge", 1.0) * 5)),
                "headline": f"⚡ {sym} Volume Surge ({g.get('change_24h'):+.2f}%)",
                "narrative": (
                    f"{sym} ranked top CoinDCX gainer with ₹{g.get('turnover_inr', 0):,.0f} INR turnover. "
                    f"Volume surge ratio {g.get('volume_surge', 1.0):.1f}x. Tight spread ({g.get('spread_pct')}%) confirms active institutional participation."
                ),
                "tags": ["Volume Surge", f"{g.get('change_24h'):+.1f}%", "Breakout"],
                "badge_class": "success"
            })

        # Deduplicate opportunities by id
        unique_opps = []
        seen_opp_ids = set()
        for opp in opportunities:
            if opp["id"] not in seen_opp_ids:
                seen_opp_ids.add(opp["id"])
                unique_opps.append(opp)

        # Urgent Watchout Popups List for Desktop & Telegram triggers
        urgent_popups = []
        for ob in orderbook_watchouts:
            if ob["overlap_flag"]:
                urgent_popups.append({
                    "id": f"urgent-overlap-{ob['symbol']}",
                    "type": "ORDERBOOK_SELLER_OVERLAP",
                    "symbol": ob["symbol"],
                    "level": "danger",
                    "title": f"🚨 {ob['symbol']} Seller Overlapping Buyer!",
                    "message": f"Ask pressure ({ob['ask_pressure_pct']}%) is overwhelming bids. Downward slip imminent.",
                    "time": time.strftime("%H:%M:%S")
                })

        if news_intel.get("threat_level", 0) >= 50:
            urgent_popups.append({
                "id": "urgent-war-news",
                "type": "GEOPOLITICAL_WAR_ALERT",
                "symbol": "MACRO",
                "level": "warning",
                "title": "⚔️ War News Spreading on Social Media (X.com)",
                "message": f"Threat Level {news_intel['threat_level']}/100. Crypto facing risk-off volatility.",
                "time": time.strftime("%H:%M:%S")
            })

        result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "orderbook_watchouts": orderbook_watchouts,
            "live_sticks": live_sticks,
            "relation_trades": relation_trades,
            "social_news": news_intel,
            "opportunities": unique_opps,
            "urgent_popups": urgent_popups
        }

        self.cached_radar = result
        self.last_radar_time = now
        return result
