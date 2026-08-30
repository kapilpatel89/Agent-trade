import hmac
import hashlib
import json
import time
import requests
from typing import Dict, Any, List, Optional
import config

class CoinDCXClient:
    """
    Comprehensive CoinDCX API Client supporting all public and authenticated endpoints.
    Handles HMAC-SHA256 authentication, custom headers, and rate-limit resilience.
    """
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key or config.COINDCX_API_KEY
        self.api_secret = api_secret or config.COINDCX_API_SECRET
        self.base_url = config.COINDCX_BASE_URL
        self.public_url = config.COINDCX_PUBLIC_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        self._markets_cache: Optional[List[Dict[str, Any]]] = None
        self._markets_cache_time: float = 0

    def set_credentials(self, api_key: str, api_secret: str):
        """Update API key and secret dynamically."""
        self.api_key = api_key
        self.api_secret = api_secret

    def _generate_signature(self, json_body: str) -> str:
        """Generate HMAC-SHA256 signature for private CoinDCX API requests."""
        if not self.api_secret:
            raise ValueError("API Secret is required for authenticated requests")
        secret_bytes = bytes(self.api_secret, "utf-8")
        body_bytes = bytes(json_body, "utf-8")
        return hmac.new(secret_bytes, body_bytes, hashlib.sha256).hexdigest()

    def _auth_request(self, endpoint: str, body: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an authenticated POST request to CoinDCX."""
        if not self.api_key or not self.api_secret:
            return {"error": True, "message": "CoinDCX API Key and Secret are not configured."}

        url = f"{self.base_url}{endpoint}"
        payload = body or {}
        # CoinDCX expects timestamp in milliseconds
        if "timestamp" not in payload:
            payload["timestamp"] = int(round(time.time() * 1000))

        json_body = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(json_body)

        headers = {
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature,
            "Content-Type": "application/json"
        }

        try:
            resp = self.session.post(url, data=json_body, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                return {
                    "error": True,
                    "status_code": resp.status_code,
                    "message": resp.text
                }
        except Exception as e:
            return {"error": True, "message": str(e)}

    # ==========================================
    # PUBLIC MARKET DATA ENDPOINTS
    # ==========================================

    def get_tickers(self) -> List[Dict[str, Any]]:
        """Fetch all real-time market tickers."""
        url = f"{self.base_url}/exchange/ticker"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"[CoinDCXClient] Error fetching tickers: {e}")
            return []

    def get_ticker_by_market(self, market: str) -> Optional[Dict[str, Any]]:
        """Get ticker info for a specific market symbol (e.g. 'BTCINR')."""
        tickers = self.get_tickers()
        for t in tickers:
            if t.get("market") == market:
                return t
        return None

    def get_markets_details(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch market details with symbol specifications, min quantity, min notional, etc."""
        now = time.time()
        if not force_refresh and self._markets_cache and (now - self._markets_cache_time < 3600):
            return self._markets_cache

        url = f"{self.base_url}/exchange/v1/markets_details"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    self._markets_cache = data
                    self._markets_cache_time = now
                    return data
            return []
        except Exception as e:
            print(f"[CoinDCXClient] Error fetching markets details: {e}")
            return []

    def get_market_detail(self, symbol_or_market: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific market like BTCINR or I-BTC_INR."""
        details = self.get_markets_details()
        for m in details:
            if m.get("symbol") == symbol_or_market or m.get("coindcx_name") == symbol_or_market or m.get("pair") == symbol_or_market:
                return m
        return None

    def get_candles(self, pair: str, interval: str = "1h", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candlestick data.
        - pair: e.g. 'I-BTC_INR' or 'B-BTC_USDT'
        - interval: '1m', '15m', '1h', '1d'
        - limit: 1-1000
        Returns list of candle dicts with keys: open, high, low, close, volume, time.
        """
        url = f"{self.public_url}/market_data/candles"
        params = {
            "pair": pair,
            "interval": interval,
            "limit": min(limit, 500)
        }
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    # Sort chronological (oldest to newest)
                    return sorted(data, key=lambda c: c.get("time", 0))
            return []
        except Exception as e:
            print(f"[CoinDCXClient] Error fetching candles for {pair}: {e}")
            return []

    def get_orderbook(self, pair: str) -> Dict[str, Any]:
        """Fetch orderbook depth (bids and asks)."""
        url = f"{self.public_url}/market_data/orderbook"
        params = {"pair": pair}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return {"bids": {}, "asks": {}}
        except Exception as e:
            print(f"[CoinDCXClient] Error fetching orderbook for {pair}: {e}")
            return {"bids": {}, "asks": {}}

    def get_trade_history(self, pair: str) -> List[Dict[str, Any]]:
        """Fetch public recent trades for pair."""
        url = f"{self.public_url}/market_data/trade_history"
        params = {"pair": pair}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"[CoinDCXClient] Error fetching trade history for {pair}: {e}")
            return []

    # ==========================================
    # AUTHENTICATED ENDPOINTS (HMAC-SHA256)
    # ==========================================

    def get_balances(self) -> List[Dict[str, Any]]:
        """
        Get all account currency balances.
        Returns list: [{'currency': 'INR', 'balance': 1500.5, 'locked_balance': 0.0}, ...]
        """
        res = self._auth_request("/exchange/v1/users/balances")
        if isinstance(res, list):
            return res
        return []

    def get_inr_balance(self) -> float:
        """Helper to get available INR balance."""
        balances = self.get_balances()
        for b in balances:
            if b.get("currency") == "INR":
                return float(b.get("balance", 0.0)) - float(b.get("locked_balance", 0.0))
        return 0.0

    def get_user_info(self) -> Dict[str, Any]:
        """Get user profile details."""
        return self._auth_request("/exchange/v1/users/info")

    def create_order(
        self,
        market: str,
        side: str,
        order_type: str,
        total_quantity: float,
        price_per_unit: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a new spot order on CoinDCX.
        - market: e.g. 'BTCINR'
        - side: 'buy' or 'sell'
        - order_type: 'market_order' or 'limit_order'
        - total_quantity: quantity of base asset
        - price_per_unit: required for limit orders
        """
        body = {
            "side": side.lower(),
            "order_type": order_type.lower(),
            "market": market,
            "total_quantity": total_quantity,
        }
        if price_per_unit is not None and order_type.lower() == "limit_order":
            body["price_per_unit"] = price_per_unit
        if client_order_id:
            body["client_order_id"] = client_order_id

        return self._auth_request("/exchange/v1/orders/create", body)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an active order by ID."""
        return self._auth_request("/exchange/v1/orders/cancel", {"id": order_id})

    def cancel_all_orders(self, market: Optional[str] = None) -> Dict[str, Any]:
        """Cancel all open orders or all open orders for a market."""
        body = {}
        if market:
            body["market"] = market
        return self._auth_request("/exchange/v1/orders/cancel_all", body)

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of an order by ID."""
        return self._auth_request("/exchange/v1/orders/status", {"id": order_id})

    def get_active_orders(self, market: Optional[str] = None, side: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of currently open/active orders."""
        body = {}
        if market:
            body["market"] = market
        if side:
            body["side"] = side
        res = self._auth_request("/exchange/v1/orders/active_orders", body)
        if isinstance(res, list):
            return res
        return []
