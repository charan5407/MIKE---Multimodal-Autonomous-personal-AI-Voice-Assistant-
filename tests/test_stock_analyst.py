"""
Unit Tests for Phase 11: Stock Analyst Module with Backtesting.
Tests ticker normalization (Indian NSE/BSE & US), technical indicators (RSI, MACD, Bollinger),
news sentiment, probabilistic forecasting with backtest metrics, and educational disclaimers.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from core.brain.intent_router import IntentRouter
from core.tools.cancellation import root_cancellation_token
from core.tools.finance.forecaster import BacktestedForecaster
from core.tools.finance.indicators import compute_technical_indicators
from core.tools.finance.sentiment import fetch_news_sentiment
from core.tools.finance.stock_data import normalize_ticker
from core.tools.finance.stock_tool import StockAnalystTool, StockShortlistTool


# ==============================================================================
# Helper to create synthetic OHLCV DataFrame
# ==============================================================================

def create_sample_ohlcv(days: int = 50, start_price: float = 2500.0) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range(end="2026-11-08", periods=days, freq="D")
    prices = [start_price]
    for _ in range(days - 1):
        change = np.random.normal(loc=0.001, scale=0.015)
        prices.append(prices[-1] * (1 + change))

    prices = np.array(prices)
    df = pd.DataFrame(
        {
            "Open": prices * 0.995,
            "High": prices * 1.015,
            "Low": prices * 0.985,
            "Close": prices,
            "Volume": np.random.randint(100000, 2000000, size=days),
        },
        index=dates,
    )
    return df


# ==============================================================================
# 1. Ticker Normalization Tests
# ==============================================================================

def test_ticker_normalization():
    """Verifies Indian NSE/BSE and US ticker aliases map accurately."""
    assert normalize_ticker("Reliance") == "RELIANCE.NS"
    assert normalize_ticker("tcs") == "TCS.NS"
    assert normalize_ticker("infosys") == "INFY.NS"
    assert normalize_ticker("tata motors") == "TATAMOTORS.NS"
    assert normalize_ticker("nifty") == "^NSEI"
    assert normalize_ticker("apple") == "AAPL"
    assert normalize_ticker("TSLA") == "TSLA"
    assert normalize_ticker("RELIANCE.NS") == "RELIANCE.NS"


# ==============================================================================
# 2. Technical Indicators Tests
# ==============================================================================

def test_compute_technical_indicators():
    """Verifies calculation of SMA, RSI, MACD, Bollinger Bands, and Support/Resistance."""
    df = create_sample_ohlcv(days=45, start_price=2800.0)
    technicals = compute_technical_indicators(df)

    assert "current_price" in technicals
    assert "trend" in technicals
    assert technicals["trend"] in ["Bullish", "Bearish", "Neutral / Consolidating"]
    assert "risk_level" in technicals
    assert technicals["risk_level"] in ["Low", "Medium", "High"]

    # RSI
    assert 0.0 <= technicals["rsi_14"] <= 100.0
    # MACD
    assert "macd" in technicals["macd"]
    assert "signal" in technicals["macd"]
    # Bollinger Bands
    assert technicals["bollinger_bands"]["upper"] >= technicals["bollinger_bands"]["lower"]
    # Support & Resistance
    assert technicals["support_level"] <= technicals["current_price"] <= technicals["resistance_level"] * 1.05


# ==============================================================================
# 3. News Sentiment Tests
# ==============================================================================

def test_news_sentiment_scoring():
    """Verifies RSS news parsing and polarity categorization."""
    mock_feed = MagicMock()
    mock_feed.entries = [
        {"title": "Reliance surges to record high as profits beat estimates", "link": "http://news1", "published": "Nov 8"},
        {"title": "TCS posts strong quarterly revenue growth and dividend hike", "link": "http://news2", "published": "Nov 8"},
    ]

    with patch("feedparser.parse", return_value=mock_feed):
        res = fetch_news_sentiment("RELIANCE.NS")

        assert res["article_count"] == 2
        assert res["sentiment_score"] > 0
        assert "Positive" in res["overall_sentiment"]
        assert len(res["headlines"]) == 2


# ==============================================================================
# 4. Probabilistic Forecaster & Backtesting Tests
# ==============================================================================

def test_backtested_forecaster():
    """Verifies train/test backtest metrics, confidence intervals, and mandatory disclaimer."""
    df = create_sample_ohlcv(days=60, start_price=1000.0)
    forecast = BacktestedForecaster.generate_forecast_and_backtest(df, forecast_days=7, backtest_window=15)

    assert forecast["forecast_days"] == 7
    assert len(forecast["trajectory"]) == 7

    # Check backtest metrics
    bm = forecast["backtest_metrics"]
    assert "directional_accuracy_pct" in bm
    assert bm["directional_accuracy_pct"] >= 50.0
    assert "mae" in bm
    assert "rmse" in bm

    # Check trajectory confidence bounds
    first_step = forecast["trajectory"][0]
    assert first_step["lower_bound_80"] < first_step["predicted_close"] < first_step["upper_bound_80"]

    # Check mandatory regulatory disclaimer
    assert "educational purposes only" in forecast["disclaimer"].lower()
    assert "does not constitute financial" in forecast["disclaimer"].lower()


# ==============================================================================
# 5. Stock Analyst Agent Tool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_stock_analyst_tool():
    """Verifies StockAnalystTool produces complete voice summary and markdown card."""
    tool = StockAnalystTool()
    sample_df = create_sample_ohlcv(days=50, start_price=2900.0)
    sample_fundamentals = {
        "symbol": "RELIANCE.NS",
        "shortName": "Reliance Industries",
        "currency": "INR",
        "trailingPE": 28.5,
        "debtToEquity": 38.2,
    }

    with patch("core.tools.finance.stock_tool.fetch_historical_and_fundamentals", return_value=(sample_df, sample_fundamentals)), \
         patch("core.tools.finance.stock_tool.fetch_news_sentiment", return_value={"overall_sentiment": "Positive / Bullish", "sentiment_score": 0.45}):

        res = await tool.execute(root_cancellation_token, ticker="Reliance", period="6mo")

        assert res.success is True
        assert "Reliance Industries" in res.output
        assert "₹" in res.output
        assert "educational purposes only" in res.output.lower()

        # UI Markdown verification
        ui_md = res.data["ui_markdown"]
        assert "Stock Analysis: Reliance Industries" in ui_md
        assert "Backtest Directional Accuracy" in ui_md
        assert "DISCLAIMER" in ui_md


@pytest.mark.asyncio
async def test_stock_shortlist_tool():
    """Verifies StockShortlistTool returns candidate stocks with rationale and disclaimers."""
    tool = StockShortlistTool()

    res = await tool.execute(root_cancellation_token, market="NSE")
    assert res.success is True
    assert "Reliance Industries" in res.output
    assert "Tata Motors" in res.output
    assert "educational purposes only" in res.output.lower()
    assert len(res.data["candidates"]) >= 3


# ==============================================================================
# 6. Intent Router Fast Path Tests
# ==============================================================================

def test_intent_router_finance_fast_paths():
    """Verifies instant matching for stock queries and recommendations."""
    router = IntentRouter()

    match = router.match("Mike, analyze stock Reliance")
    assert match is not None
    assert match.tool_name == "analyze_stock"
    assert match.parameters["ticker"] == "Reliance"

    match = router.match("analyze Apple stock")
    assert match is not None
    assert match.tool_name == "analyze_stock"
    assert match.parameters["ticker"] == "Apple"

    match = router.match("stock shortlist")
    assert match is not None
    assert match.tool_name == "stock_shortlist"

    match = router.match("Mike, candidate stocks")
    assert match is not None
    assert match.tool_name == "stock_shortlist"
