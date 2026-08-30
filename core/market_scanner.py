import time
from typing import Dict, Any, List, Optional
import config
from core.coindcx_client import CoinDCXClient

class MarketScanner:
    """
    Dynamic High-Momentum Market Scanner for CoinDCX.
    Scans all 340+ INR trading pairs, filters out illiquid markets,
    ranks top movers and breakout candidates, and supplies high-opportunity setups.
    """

    def __init__(self, client: Optional[CoinDCXClient] = None):
        self.client = client or CoinDCXClient()
        self.cached_movers: Dict[str, Any] = {}
        self.last_scan_time: float = 0
        self.cache_ttl: int = 15  # Cache scan for 15 seconds

    def scan_all_inr_markets(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Scan all 340+ INR markets on CoinDCX.
        Returns:
            - top_gainers: List of coins with highest 24h % gain
            - top_volume: List of coins with highest 24h turnover (INR)
            - top_candidates: Curated top candidate pairs for agent trading
            - total_scanned: Total count of active INR markets
        """
        now = time.time()
        if not force_refresh and self.cached_movers and (now - self.last_scan_time < self.cache_ttl):
            return self.cached_movers

        # Fetch market details and live tickers
        all_details = self.client.get_markets_details()
        all_tickers = self.client.get_tickers()

        tickers_map = {t["market"]: t for t in all_tickers if "market" in t}

        # Filter active INR markets
        inr_markets = [
            m for m in all_details
            if m.get("base_currency_short_name") == "INR" and m.get("status") == "active"
        ]

        scanned_coins = []

        for m in inr_markets:
            symbol = m.get("symbol")  # e.g. "BTCINR"
            t = tickers_map.get(symbol)
            if not t:
                continue

            last_price = float(t.get("last_price", 0) or 0)
            if last_price <= 0:
                continue

            change_24h = float(t.get("change_24_hour", 0) or 0)
            volume_24h = float(t.get("volume", 0) or 0)  # Volume in base or target
            high_24h = float(t.get("high", 0) or 0)
            low_24h = float(t.get("low", 0) or 0)
            bid = float(t.get("bid", 0) or 0)
            ask = float(t.get("ask", 0) or 0)

            # Calculate Spread
            spread_pct = 0.0
            if ask > 0 and bid > 0:
                spread_pct = round(((ask - bid) / ask) * 100.0, 2)

            # Approximate 24h turnover in INR
            turnover_inr = volume_24h * last_price if volume_24h < 1000000 else volume_24h

            # Filter: Spread should be reasonable (< 2.5%) and min volume threshold
            is_liquid = (turnover_inr >= config.SCANNER_MIN_24H_VOLUME_INR or volume_24h >= 10000) and spread_pct <= 2.5

            # Volume surge: simple ratio of 24h volume to a baseline (coins > 1000 INR price usually have lower unit volumes)
            # We use a fixed baseline estimate per price tier for liquidity comparison
            vol_baseline = max(1, last_price * 0.001)  # rough estimate
            vol_surge = round(min(volume_24h / vol_baseline / 100.0, 10.0), 2) if vol_baseline > 0 else 1.0
            # Cap vol_surge at 10x for display
            vol_surge = max(0.1, min(vol_surge, 10.0))

            coin_data = {
                "market": symbol,
                "pair": m.get("pair", f"I-{m.get('target_currency_short_name')}_INR"),
                "symbol": m.get("target_currency_short_name", ""),
                "name": m.get("target_currency_name", m.get("target_currency_short_name")),
                "last_price": last_price,
                "change_24h": round(change_24h, 2),
                "volume_24h": round(volume_24h, 2),
                "turnover_inr": round(turnover_inr, 2),
                "high_24h": high_24h,
                "low_24h": low_24h,
                "spread_pct": spread_pct,
                "volume_surge": vol_surge,
                "is_liquid": is_liquid,
                "min_notional": float(m.get("min_notional", 100) or 100),
                "step": float(m.get("step", 1e-5) or 1e-5),
                "precision": int(m.get("target_currency_precision", 4) or 4)
            }
            scanned_coins.append(coin_data)


        # Sort by 24h % Gain
        liquid_coins = [c for c in scanned_coins if c["is_liquid"]]
        top_gainers = sorted(liquid_coins, key=lambda x: x["change_24h"], reverse=True)[:15]

        # Sort by Turnover (Volume)
        top_volume = sorted(liquid_coins, key=lambda x: x["turnover_inr"], reverse=True)[:15]

        # Assemble Curated Candidate List for the Decision Brain:
        # Include base majors (BTC, ETH, SOL, DOGE) + Top 8 High Momentum Gainers + Top 4 Volume Leaders
        candidate_markets = set()
        curated_candidates = []

        # 1. Base Major Coins
        for base in config.BASE_TRACKED_PAIRS:
            found = next((c for c in scanned_coins if c["market"] == base["market"]), None)
            if found:
                candidate_markets.add(found["market"])
                curated_candidates.append(found)

        # 2. Add Top Gainers
        for g in top_gainers:
            if g["market"] not in candidate_markets and len(curated_candidates) < config.SCANNER_MAX_CANDIDATES:
                candidate_markets.add(g["market"])
                curated_candidates.append(g)

        # 3. Add Top Volume Leaders
        for v in top_volume:
            if v["market"] not in candidate_markets and len(curated_candidates) < config.SCANNER_MAX_CANDIDATES:
                candidate_markets.add(v["market"])
                curated_candidates.append(v)

        result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_scanned": len(scanned_coins),
            "liquid_count": len(liquid_coins),
            "top_gainers": top_gainers,
            "top_volume": top_volume,
            "candidates": curated_candidates
        }

        self.cached_movers = result
        self.last_scan_time = now
        return result
