import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

class TechnicalAnalysisEngine:
    """
    Computes technical indicators, candlestick pattern detection,
    and multi-timeframe quantitative scoring on CoinDCX candle data.
    """

    @staticmethod
    def candles_to_dataframe(candles: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert list of CoinDCX candle dicts to a clean pandas DataFrame."""
        if not candles or len(candles) < 5:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        # Ensure float types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "time" in df.columns:
            df["time"] = pd.to_numeric(df["time"], errors="coerce")

        df = df.dropna().reset_index(drop=True)
        return df

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI)."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    @staticmethod
    def calculate_ema(series: pd.Series, span: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calculate MACD line, signal line, and histogram."""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    @staticmethod
    def calculate_bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands (Upper, Middle, Lower, Bandwidth, %B)."""
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        bandwidth = (upper - lower) / middle.replace(0, np.nan)
        percent_b = (series - lower) / (upper - lower).replace(0, np.nan)
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth,
            "percent_b": percent_b
        }

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR)."""
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr.fillna(df["close"] * 0.02)

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> List[str]:
        """Detect key bullish, bearish, and indecision candlestick patterns on latest candles."""
        patterns = []
        if len(df) < 3:
            return patterns

        # Latest candle (index -1) and previous (index -2, -3)
        c0 = df.iloc[-1]
        c1 = df.iloc[-2]
        c2 = df.iloc[-3] if len(df) >= 3 else c1

        body0 = abs(c0["close"] - c0["open"])
        upper_shadow0 = c0["high"] - max(c0["open"], c0["close"])
        lower_shadow0 = min(c0["open"], c0["close"]) - c0["low"]
        range0 = c0["high"] - c0["low"] if (c0["high"] - c0["low"]) > 0 else 0.0001

        body1 = abs(c1["close"] - c1["open"])

        # 1. Hammer (Bullish Reversal)
        if lower_shadow0 >= (2 * body0) and upper_shadow0 <= (0.2 * body0) and c0["close"] >= c0["open"]:
            patterns.append("Hammer (Bullish Reversal)")

        # 2. Inverted Hammer / Shooting Star
        if upper_shadow0 >= (2 * body0) and lower_shadow0 <= (0.2 * body0):
            if c0["close"] < c0["open"]:
                patterns.append("Shooting Star (Bearish Reversal)")
            else:
                patterns.append("Inverted Hammer (Bullish Setup)")

        # 3. Bullish Engulfing
        if c1["close"] < c1["open"] and c0["close"] > c0["open"]:
            if c0["close"] >= c1["open"] and c0["open"] <= c1["close"]:
                patterns.append("Bullish Engulfing (Strong Buy)")

        # 4. Bearish Engulfing
        if c1["close"] > c1["open"] and c0["close"] < c0["open"]:
            if c0["open"] >= c1["close"] and c0["close"] <= c1["open"]:
                patterns.append("Bearish Engulfing (Strong Sell)")

        # 5. Doji (Indecision)
        if body0 <= (0.1 * range0):
            patterns.append("Doji (Market Indecision)")

        # 6. Morning Star (Bullish 3-candle pattern)
        if c2["close"] < c2["open"] and abs(c1["close"] - c1["open"]) < body0 * 0.5 and c0["close"] > c0["open"]:
            if c0["close"] > (c2["open"] + c2["close"]) / 2:
                patterns.append("Morning Star (High Probability Bullish)")

        return patterns

    def analyze(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Full technical analysis pipeline on candlestick data.
        Returns indicator values, detected patterns, support/resistance,
        and composite technical score (-100 to +100).
        """
        df = self.candles_to_dataframe(candles)
        if df.empty or len(df) < 20:
            return {
                "status": "insufficient_data",
                "score": 0,
                "signal": "NEUTRAL",
                "reason": "Not enough candles for reliable indicators"
            }

        # Calculate Indicators
        close = df["close"]
        df["rsi"] = self.calculate_rsi(close, period=14)
        df["ema9"] = self.calculate_ema(close, span=9)
        df["ema21"] = self.calculate_ema(close, span=21)
        df["ema50"] = self.calculate_ema(close, span=50)
        df["ema200"] = self.calculate_ema(close, span=min(200, len(df)))

        macd_data = self.calculate_macd(close)
        df["macd"] = macd_data["macd"]
        df["macd_signal"] = macd_data["signal"]
        df["macd_hist"] = macd_data["histogram"]

        bb_data = self.calculate_bollinger_bands(close)
        df["bb_upper"] = bb_data["upper"]
        df["bb_middle"] = bb_data["middle"]
        df["bb_lower"] = bb_data["lower"]
        df["bb_bandwidth"] = bb_data["bandwidth"]

        df["atr"] = self.calculate_atr(df, period=14)
        df["vol_sma"] = df["volume"].rolling(window=20).mean()
        df["vol_surge"] = df["volume"] / df["vol_sma"].replace(0, np.nan)

        # Extract latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = float(latest["close"])
        rsi_val = float(latest["rsi"])
        ema9 = float(latest["ema9"])
        ema21 = float(latest["ema21"])
        ema50 = float(latest["ema50"])
        ema200 = float(latest["ema200"])
        macd_val = float(latest["macd"])
        macd_sig = float(latest["macd_signal"])
        macd_hist = float(latest["macd_hist"])
        prev_macd_hist = float(prev["macd_hist"])
        bb_upper = float(latest["bb_upper"])
        bb_lower = float(latest["bb_lower"])
        bb_mid = float(latest["bb_middle"])
        atr_val = float(latest["atr"])
        vol_surge = float(latest["vol_surge"]) if not math.isnan(latest["vol_surge"]) else 1.0

        # Patterns
        patterns = self.detect_candlestick_patterns(df)

        # Support / Resistance from last 20 candles
        recent_window = df.tail(20)
        resistance = float(recent_window["high"].max())
        support = float(recent_window["low"].min())

        # ==========================================
        # MULTI-FACTOR TECHNICAL SCORING ENGINE (-100 to +100)
        # ==========================================
        score = 0
        signals_breakdown = []

        # 1. RSI Scoring (-30 to +30)
        if rsi_val < 30:
            score += 25
            signals_breakdown.append(f"RSI Oversold ({rsi_val:.1f}) - Bullish Bounce Zone (+25)")
        elif rsi_val < 42:
            score += 10
            signals_breakdown.append(f"RSI Low Zone ({rsi_val:.1f}) - Value Zone (+10)")
        elif rsi_val > 70:
            score -= 25
            signals_breakdown.append(f"RSI Overbought ({rsi_val:.1f}) - Exhaustion Warning (-25)")
        elif rsi_val > 60:
            score += 10
            signals_breakdown.append(f"RSI Bullish Momentum ({rsi_val:.1f}) (+10)")

        # 2. EMA Trend Alignment (-25 to +25)
        if current_price > ema9 > ema21:
            score += 20
            signals_breakdown.append(f"Price above EMA 9/21 - Bullish Trend (+20)")
        elif current_price < ema9 < ema21:
            score -= 20
            signals_breakdown.append(f"Price below EMA 9/21 - Bearish Downward Trend (-20)")

        if current_price > ema50:
            score += 5
        else:
            score -= 5

        # 3. MACD Momentum (-25 to +25)
        if macd_val > macd_sig and macd_hist > 0:
            if macd_hist > prev_macd_hist:
                score += 20
                signals_breakdown.append("MACD Bullish Crossover expanding (+20)")
            else:
                score += 10
                signals_breakdown.append("MACD Positive but decelerating (+10)")
        elif macd_val < macd_sig and macd_hist < 0:
            if macd_hist < prev_macd_hist:
                score -= 20
                signals_breakdown.append("MACD Bearish Crossover expanding (-20)")
            else:
                score -= 10
                signals_breakdown.append("MACD Negative but decelerating (-10)")

        # 4. Bollinger Bands Touch / Squeeze (-15 to +15)
        if current_price <= bb_lower * 1.005:
            score += 15
            signals_breakdown.append("Price near Lower Bollinger Band - Mean Reversion Buy (+15)")
        elif current_price >= bb_upper * 0.995:
            score -= 15
            signals_breakdown.append("Price near Upper Bollinger Band - Overextended Sell (-15)")

        # 5. Volume Surge Multiplier
        if vol_surge > 1.5:
            signals_breakdown.append(f"High Volume Surge ({vol_surge:.1f}x average)")
            # Boost directional score
            if score > 0:
                score += 10
            elif score < 0:
                score -= 10

        # 6. Candlestick Patterns
        for pat in patterns:
            if "Bullish" in pat or "Hammer" in pat or "Buy" in pat:
                score += 15
                signals_breakdown.append(f"Pattern Detected: {pat} (+15)")
            elif "Bearish" in pat or "Shooting Star" in pat or "Sell" in pat:
                score -= 15
                signals_breakdown.append(f"Pattern Detected: {pat} (-15)")

        # Clamp score to [-100, 100]
        score = max(-100, min(100, score))

        # Determine qualitative label
        if score >= 35:
            signal_type = "STRONG_BUY"
        elif score >= 15:
            signal_type = "BUY"
        elif score <= -35:
            signal_type = "STRONG_SELL"
        elif score <= -15:
            signal_type = "SELL"
        else:
            signal_type = "HOLD"

        return {
            "status": "success",
            "score": score,
            "signal": signal_type,
            "current_price": current_price,
            "rsi": round(rsi_val, 2),
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "macd": round(macd_val, 4),
            "macd_signal": round(macd_sig, 4),
            "macd_hist": round(macd_hist, 4),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_middle": round(bb_mid, 2),
            "atr": round(atr_val, 4),
            "volume_surge": round(vol_surge, 2),
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "patterns": patterns,
            "signals_breakdown": signals_breakdown
        }
