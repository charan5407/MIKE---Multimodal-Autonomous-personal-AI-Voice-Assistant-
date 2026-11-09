"""
Financial Market Data Retrieval for MIKE.
Fetches quotes, OHLCV historical prices, and fundamentals using yfinance.
Supports Indian tickers (NSE/BSE, e.g. RELIANCE.NS, TCS.NS) and US tickers.
"""

import re
from typing import Any, Dict, Optional, Tuple
import pandas as pd
import yfinance as yf

from core.logger import logger

# Common ticker aliases for quick voice & text normalization
TICKER_MAP = {
    # Indian NSE
    "reliance": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "infosys": "INFY.NS",
    "infy": "INFY.NS",
    "hdfc": "HDFCBANK.NS",
    "hdfc bank": "HDFCBANK.NS",
    "hdfcbank": "HDFCBANK.NS",
    "tata motors": "TATAMOTORS.NS",
    "tatamotors": "TATAMOTORS.NS",
    "wipro": "WIPRO.NS",
    "sbi": "SBIN.NS",
    "sbin": "SBIN.NS",
    "state bank of india": "SBIN.NS",
    "icici": "ICICIBANK.NS",
    "icicibank": "ICICIBANK.NS",
    "itc": "ITC.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "airtel": "BHARTIARTL.NS",
    "nifty": "^NSEI",
    "nifty 50": "^NSEI",
    "sensex": "^BSESN",
    # US Equities
    "apple": "AAPL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "microsoft": "MSFT",
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "amazon": "AMZN",
    "meta": "META",
}


def normalize_ticker(query: str) -> str:
    """Normalizes raw input or company name into valid Yahoo Finance ticker symbol."""
    clean = query.strip().lower()
    # Check alias map
    if clean in TICKER_MAP:
        return TICKER_MAP[clean]

    # If it ends with .ns or .bo or has uppercase symbol format
    raw_upper = query.strip().upper()
    if raw_upper.endswith(".NS") or raw_upper.endswith(".BO") or "^" in raw_upper:
        return raw_upper

    # If it looks like an Indian ticker without extension, check if user specified Indian
    return raw_upper


def fetch_historical_and_fundamentals(
    ticker_symbol: str,
    period: str = "6mo",
    interval: str = "1d",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Fetches historical OHLCV DataFrame and key fundamental ratios.
    """
    ticker = normalize_ticker(ticker_symbol)
    logger.info(f"Fetching financial data for ticker: {ticker} (period: {period})")

    yf_obj = yf.Ticker(ticker)
    df = yf_obj.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No price history found for ticker '{ticker}'. Please verify the symbol.")

    fundamentals = {}
    try:
        info = yf_obj.info or {}
        fundamentals = {
            "symbol": ticker,
            "shortName": info.get("shortName") or info.get("longName") or ticker,
            "currency": info.get("currency", "INR" if ticker.endswith(".NS") else "USD"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice") or float(df["Close"].iloc[-1]),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "debtToEquity": info.get("debtToEquity"),
            "returnOnEquity": info.get("returnOnEquity"),
            "dividendYield": info.get("dividendYield"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
    except Exception as e:
        logger.debug(f"Fundamentals lookup notice for {ticker}: {e}")
        fundamentals = {
            "symbol": ticker,
            "shortName": ticker,
            "currency": "INR" if ticker.endswith(".NS") else "USD",
            "currentPrice": float(df["Close"].iloc[-1]),
        }

    return df, fundamentals
