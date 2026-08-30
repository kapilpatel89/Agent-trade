import urllib.request
import xml.etree.ElementTree as ET
import time
import re
from typing import Dict, Any, List, Optional
import config

class NewsAndConflictEngine:
    """
    Monitors live geopolitical conflict news, macro economic headlines,
    and crypto news feeds to calculate realistic Threat Level (0-100) and Crypto Sentiment (-100 to +100).
    """

    # Keyword Dictionaries for Risk & Sentiment Scoring
    SEVERE_CRISIS_KEYWORDS = {
        "nuclear strike": 35, "world war": 30, "ww3": 30, "full-scale invasion": 25,
        "martial law declared": 25, "military draft": 20, "emergency defense": 20
    }

    CONFLICT_KEYWORDS = {
        "missile strike": 12, "airstrike": 10, "drone attack": 10, "military clash": 10,
        "escalation": 8, "sanctions": 6, "tensions": 4, "hostilities": 8, "oil crisis": 8,
        "blockade": 8, "conflict": 5
    }

    BEARISH_CRYPTO_KEYWORDS = {
        "sec lawsuit": 10, "hack": 12, "exploit": 10, "ban": 10, "crackdown": 8,
        "insolvency": 15, "fraud": 10, "dump": 8, "crash": 8, "liquidation spike": 8
    }

    BULLISH_CRYPTO_KEYWORDS = {
        "etf approval": 15, "etf inflow": 12, "all-time high": 12, "ath": 10, "breakout": 10,
        "rate cut": 12, "stimulus": 12, "adoption": 8, "institutional inflow": 10, "surge": 8,
        "rally": 8, "partnership": 6
    }

    def __init__(self):
        self.cached_news: List[Dict[str, Any]] = []
        self.last_fetch_time: float = 0
        self.cache_ttl: int = 120  # Cache news for 2 minutes

    def _clean_text(self, text: str) -> str:
        """Strip HTML tags, entities, and excess whitespace."""
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = clean.replace('&quot;', '"').replace('&amp;', '&').replace('&apos;', "'").replace('&#39;', "'")
        return " ".join(clean.split())

    def fetch_rss_feed(self, source_name: str, url: str) -> List[Dict[str, Any]]:
        """Fetch and parse RSS feed articles with timeout and error handling."""
        articles = []
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                content = resp.read()
                root = ET.fromstring(content)

                items = root.findall(".//item")
                for item in items[:10]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_date_elem = item.find("pubDate")
                    desc_elem = item.find("description")

                    title = self._clean_text(title_elem.text if title_elem is not None else "")
                    link = link_elem.text if link_elem is not None else ""
                    pub_date = pub_date_elem.text if pub_date_elem is not None else ""
                    description = self._clean_text(desc_elem.text if desc_elem is not None else "")

                    # Clean publication time display
                    display_time = pub_date[:16] if len(pub_date) >= 16 else time.strftime("%Y-%m-%d %H:%M")

                    if title and len(title) > 8:
                        articles.append({
                            "source": source_name.replace("_", " ").title(),
                            "title": title,
                            "link": link,
                            "pub_date": display_time,
                            "description": description[:180]
                        })
        except Exception as e:
            # Fallback smoothly without crashing
            pass
        return articles

    def fetch_all_news(self, force: bool = False) -> List[Dict[str, Any]]:
        """Fetch real live news from multiple sources and deduplicate."""
        now = time.time()
        if not force and self.cached_news and (now - self.last_fetch_time < self.cache_ttl):
            return self.cached_news

        all_articles = []
        for name, url in config.NEWS_FEEDS.items():
            articles = self.fetch_rss_feed(name, url)
            all_articles.extend(articles)

        # Deduplicate by title similarity
        seen_titles = set()
        unique_articles = []
        for art in all_articles:
            norm_title = art["title"].lower().strip()[:40]
            if norm_title not in seen_titles:
                seen_titles.add(norm_title)
                unique_articles.append(art)

        self.cached_news = unique_articles
        self.last_fetch_time = now
        return unique_articles

    def analyze(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze news for realistic Geopolitical Conflict Threat & Crypto Market Sentiment.
        """
        articles = self.fetch_all_news(force=force_refresh)

        total_threat_score = 0
        total_crypto_bull = 0
        total_crypto_bear = 0
        breaking_alerts = []
        tagged_articles = []

        for art in articles:
            text = f"{art['title']} {art['description']}".lower()

            art_threat = 0
            art_bull = 0
            art_bear = 0
            matched_tags = []

            # Severe Shock check
            for kw, weight in self.SEVERE_CRISIS_KEYWORDS.items():
                if kw in text:
                    art_threat += weight
                    matched_tags.append(f"Crisis: {kw}")

            # Standard Conflict check
            for kw, weight in self.CONFLICT_KEYWORDS.items():
                if kw in text:
                    art_threat += weight
                    matched_tags.append(f"Threat: {kw}")

            # Bullish check
            for kw, weight in self.BULLISH_CRYPTO_KEYWORDS.items():
                if kw in text:
                    art_bull += weight
                    matched_tags.append(f"Bull: {kw}")

            # Bearish check
            for kw, weight in self.BEARISH_CRYPTO_KEYWORDS.items():
                if kw in text:
                    art_bear += weight
                    matched_tags.append(f"Bear: {kw}")

            total_threat_score += min(art_threat, 30)
            total_crypto_bull += art_bull
            total_crypto_bear += art_bear

            # Article Badge
            if art_threat >= 15:
                badge = "CONFLICT_ALERT"
                badge_class = "danger"
                breaking_alerts.append({
                    "title": art["title"],
                    "source": art["source"],
                    "threat_weight": art_threat
                })
            elif art_bull > art_bear + 4:
                badge = "BULLISH"
                badge_class = "success"
            elif art_bear > art_bull + 4:
                badge = "BEARISH"
                badge_class = "warning"
            else:
                badge = "NEUTRAL"
                badge_class = "info"

            art_copy = dict(art)
            art_copy["badge"] = badge
            art_copy["badge_class"] = badge_class
            art_copy["tags"] = matched_tags
            tagged_articles.append(art_copy)

        article_count = max(1, len(articles))

        # Average threat density scaled to 0-100
        # If 3-4 articles out of 30 mention conflict words, threat is ~15-25% (normal)
        # If many articles mention severe crisis, threat jumps to 60-80%+
        avg_threat = (total_threat_score / article_count) * 8.0
        threat_level = int(min(100, max(10, avg_threat)))

        if threat_level < 30:
            threat_status = "LOW_STABILITY"
        elif threat_level < 55:
            threat_status = "ELEVATED_TENSION"
        elif threat_level < 75:
            threat_status = "HIGH_RISK"
        else:
            threat_status = "CRITICAL_CONFLICT_ZONE"

        # Crypto Sentiment (-100 to +100)
        net_sentiment = total_crypto_bull - total_crypto_bear
        sentiment_ratio = (net_sentiment / article_count) * 20.0
        crypto_sentiment = int(max(-100, min(100, sentiment_ratio)))

        if crypto_sentiment >= 35:
            sentiment_label = "STRONG_BULLISH"
        elif crypto_sentiment >= 10:
            sentiment_label = "BULLISH"
        elif crypto_sentiment <= -35:
            sentiment_label = "STRONG_BEARISH"
        elif crypto_sentiment <= -10:
            sentiment_label = "BEARISH"
        else:
            sentiment_label = "NEUTRAL"

        return {
            "threat_level": threat_level,
            "threat_status": threat_status,
            "crypto_sentiment": crypto_sentiment,
            "sentiment_label": sentiment_label,
            "breaking_alerts": breaking_alerts[:5],
            "total_articles_scanned": len(articles),
            "articles": tagged_articles[:20],
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
