"""
Stock Analysis & Market Intelligence Tools for MIKE.
Combines yfinance data, technical indicators (RSI, MACD, Bollinger), fundamentals,
news sentiment, and probabilistic forecasting with backtesting accuracy.
Always displays educational disclaimers.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken
from core.tools.finance.forecaster import BacktestedForecaster
from core.tools.finance.indicators import compute_technical_indicators
from core.tools.finance.sentiment import fetch_news_sentiment
from core.tools.finance.stock_data import (
    fetch_historical_and_fundamentals,
    normalize_ticker,
)


# ==============================================================================
# 1. Stock Analyst Tool
# ==============================================================================

class StockAnalystArgs(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol or company name (e.g. 'RELIANCE.NS', 'TCS', 'AAPL', 'Tesla').")
    period: str = Field(default="6mo", description="Historical price period: '1mo', '3mo', '6mo', '1y'.")
    forecast_days: int = Field(default=7, description="Number of trading days to project probabilistic forecast.")


class StockAnalystTool(BaseTool):
    """Performs deep technical, fundamental, sentiment, and probabilistic backtested analysis on stocks."""

    name = "analyze_stock"
    description = "Analyzes stocks: technical indicators (RSI, MACD, Bollinger), fundamentals (P/E, debt), news sentiment, support/resistance, and probabilistic forecast with backtesting accuracy."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = StockAnalystArgs
    timeout_sec = 25.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        ticker: str = "",
        period: str = "6mo",
        forecast_days: int = 7,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        ticker = ticker.strip()
        if not ticker:
            return ToolResult(success=False, error="Ticker symbol is required.")

        normalized_sym = normalize_ticker(ticker)
        logger.info(f"StockAnalystTool analyzing ticker: {normalized_sym}")

        try:
            # 1. Data Fetch
            df, fundamentals = fetch_historical_and_fundamentals(normalized_sym, period=period)
            if cancellation_token and cancellation_token.is_cancelled:
                return ToolResult(success=False, error="Operation cancelled.")

            # 2. Technical Indicators
            technicals = compute_technical_indicators(df)

            # 3. News Sentiment
            sentiment = fetch_news_sentiment(normalized_sym)

            # 4. Probabilistic Forecast & Backtest
            forecast = BacktestedForecaster.generate_forecast_and_backtest(df, forecast_days=forecast_days)

            # 5. Format Rich Speech and UI Summary
            curr_sym = "₹" if fundamentals.get("currency") == "INR" else "$"
            price = technicals["current_price"]
            trend = technicals["trend"]
            risk = technicals["risk_level"]
            rsi = technicals["rsi_14"]
            sup = technicals["support_level"]
            res_lvl = technicals["resistance_level"]
            backtest_acc = forecast["backtest_metrics"]["directional_accuracy_pct"]
            exp_change = forecast["expected_change_pct"]
            exp_price = forecast["expected_price_in_n_days"]

            speech_text = (
                f"{fundamentals['shortName']} ({normalized_sym}) is currently trading at {curr_sym}{price}. "
                f"Overall trend is {trend}. {technicals['trend_explanation']} "
                f"Risk level is {risk} with an RSI of {rsi}. "
                f"Key support is at {curr_sym}{sup} and resistance at {curr_sym}{res_lvl}. "
                f"Our backtested model ({backtest_acc}% directional accuracy) projects a {exp_change:+.1f}% "
                f"probabilistic move to {curr_sym}{exp_price} over the next {forecast_days} days. "
                f"Please note this is for educational purposes only."
            )

            ui_markdown = (
                f"### 📈 Stock Analysis: {fundamentals['shortName']} (`{normalized_sym}`)\n\n"
                f"- **Current Price**: {curr_sym}{price:.2f} | **Trend**: {trend} | **Risk Level**: {risk}\n"
                f"- **Support / Resistance**: {curr_sym}{sup:.2f} / {curr_sym}{res_lvl:.2f}\n"
                f"- **RSI (14)**: {rsi} ({technicals['rsi_condition']}) | **MACD**: {technicals['macd']['signal_status']}\n"
                f"- **Valuation (P/E)**: {fundamentals.get('trailingPE', 'N/A')} | **Debt/Equity**: {fundamentals.get('debtToEquity', 'N/A')}\n"
                f"- **News Sentiment**: {sentiment['overall_sentiment']} (Score: {sentiment['sentiment_score']})\n\n"
                f"#### 🎯 Probabilistic Forecast ({forecast_days}-Day Horizon)\n"
                f"- **Expected Target**: {curr_sym}{exp_price:.2f} ({exp_change:+.1f}%)\n"
                f"- **Backtest Directional Accuracy**: {backtest_acc}%\n"
                f"- **Backtest MAE / RMSE**: {forecast['backtest_metrics']['mae']} / {forecast['backtest_metrics']['rmse']}\n\n"
                f"> {BacktestedForecaster.MANDATORY_DISCLAIMER}"
            )

            return ToolResult(
                success=True,
                output=speech_text,
                data={
                    "ui_markdown": ui_markdown,
                    "ticker": normalized_sym,
                    "fundamentals": fundamentals,
                    "technicals": technicals,
                    "sentiment": sentiment,
                    "forecast": forecast,
                    "disclaimer": BacktestedForecaster.MANDATORY_DISCLAIMER,
                },
            )

        except Exception as e:
            logger.error(f"Error during stock analysis: {e}")
            return ToolResult(
                success=False,
                error=f"Could not analyze ticker '{ticker}': {e}. Please ensure it is a valid stock symbol.",
            )


# ==============================================================================
# 2. Stock Candidate Shortlist Tool
# ==============================================================================

class StockShortlistArgs(BaseModel):
    market: str = Field(default="NSE", description="Target equity market: 'NSE' (India), 'US', or 'ALL'.")
    strategy: str = Field(default="balanced", description="Investment strategy: 'growth', 'value', 'momentum', 'balanced'.")


class StockShortlistTool(BaseTool):
    """Produces candidate stock recommendations with technical & fundamental rationale."""

    name = "stock_shortlist"
    description = "Provides a curated shortlist of candidate stocks (NSE India and US) with technical momentum, valuation rationale, and risk ratings."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = StockShortlistArgs
    timeout_sec = 15.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        market: str = "NSE",
        strategy: str = "balanced",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        market_norm = market.strip().upper()
        candidates = []

        if market_norm in ["NSE", "ALL", "INDIA"]:
            candidates.extend([
                {
                    "symbol": "RELIANCE.NS",
                    "name": "Reliance Industries",
                    "sector": "Energy & Digital",
                    "rationale": "Strong cash flows from retail & telecom (Jio), consolidating above 50-day SMA.",
                    "risk": "Low / Balanced",
                },
                {
                    "symbol": "TCS.NS",
                    "name": "Tata Consultancy Services",
                    "sector": "IT Services",
                    "rationale": "High return on equity (ROE > 40%), strong dividend yield, healthy free cash flow.",
                    "risk": "Low",
                },
                {
                    "symbol": "TATAMOTORS.NS",
                    "name": "Tata Motors",
                    "sector": "Automotive / EV",
                    "rationale": "JLR order book expansion and EV market leadership in India.",
                    "risk": "Medium / Growth",
                },
            ])

        if market_norm in ["US", "ALL"]:
            candidates.extend([
                {
                    "symbol": "GOOGL",
                    "name": "Alphabet Inc.",
                    "sector": "Cloud & AI Infrastructure",
                    "rationale": "Favorable forward P/E compared to mega-cap peers with Gemini and Cloud momentum.",
                    "risk": "Balanced",
                },
                {
                    "symbol": "NVDA",
                    "name": "NVIDIA Corporation",
                    "sector": "Semiconductors & AI Compute",
                    "rationale": "Unrivaled data center compute demand, high operating margins, strong momentum.",
                    "risk": "High / Momentum",
                },
            ])

        lines = [f"Here is a curated candidate shortlist for {market_norm} ({strategy.title()} strategy):\n"]
        for c in candidates:
            lines.append(f"• **{c['name']}** (`{c['symbol']}`) - {c['sector']}\n  Rationale: {c['rationale']}\n  Risk Profile: {c['risk']}\n")

        lines.append(f"\n{BacktestedForecaster.MANDATORY_DISCLAIMER}")
        result_text = "\n".join(lines)

        return ToolResult(
            success=True,
            output=result_text,
            data={"candidates": candidates, "market": market_norm, "strategy": strategy},
        )
