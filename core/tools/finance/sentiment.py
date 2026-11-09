"""
Financial News Sentiment Analyzer for MIKE.
Parses free financial RSS news feeds (Yahoo Finance & Google News) without API keys.
Performs sentiment scoring across recent market headlines.
"""

import urllib.parse
from typing import Any, Dict, List
import feedparser

from core.logger import logger

POSITIVE_WORDS = {
    "surge", "rally", "gain", "profit", "bull", "bullish", "jump", "climb", "high",
    "record", "beat", "strong", "outperform", "upgrade", "growth", "boost", "soar",
    "dividend", "upside", "win", "positive", "expand",
}

NEGATIVE_WORDS = {
    "drop", "fall", "loss", "slump", "plunge", "bear", "bearish", "down", "low",
    "miss", "weak", "underperform", "downgrade", "decline", "tumble", "crash",
    "debt", "downside", "negative", "cut", "warning", "probe", "fraud",
}


def fetch_news_sentiment(ticker: str, max_articles: int = 5) -> Dict[str, Any]:
    """
    Fetches latest financial RSS news for ticker and computes polarity score.
    """
    clean_ticker = ticker.split(".")[0]  # e.g. RELIANCE from RELIANCE.NS
    encoded = urllib.parse.quote(f"{clean_ticker} stock")
    rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en"

    logger.info(f"Fetching RSS news sentiment for: {clean_ticker}")

    articles: List[Dict[str, str]] = []
    total_score = 0.0

    try:
        feed = feedparser.parse(rss_url)
        entries = feed.entries[:max_articles]

        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            pub = entry.get("published", "")

            # Score title
            words = set(title.lower().split())
            pos_matches = len(words & POSITIVE_WORDS)
            neg_matches = len(words & NEGATIVE_WORDS)
            art_score = (pos_matches - neg_matches) / max(1, pos_matches + neg_matches) if (pos_matches or neg_matches) else 0.0

            total_score += art_score
            articles.append({
                "title": title,
                "url": link,
                "published": pub,
                "polarity": round(art_score, 2),
            })

    except Exception as e:
        logger.warning(f"Error fetching news feed for {ticker}: {e}")

    avg_score = total_score / len(articles) if articles else 0.0

    if avg_score > 0.15:
        overall_sentiment = "Positive / Bullish"
    elif avg_score < -0.15:
        overall_sentiment = "Negative / Bearish"
    else:
        overall_sentiment = "Neutral / Balanced"

    return {
        "overall_sentiment": overall_sentiment,
        "sentiment_score": round(avg_score, 2),
        "article_count": len(articles),
        "headlines": articles[:3],
    }
