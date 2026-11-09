"""
Technical Analysis Engine for MIKE.
Computes SMA/EMA, RSI, MACD, Bollinger Bands, Support/Resistance levels, and Risk Metrics.
Powered by pandas and the ta library.
"""

import math
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
import ta


def compute_technical_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes comprehensive technical indicators from an OHLCV DataFrame.
    """
    if len(df) < 15:
        raise ValueError("Insufficient data points to compute technical indicators (need >= 15 bars).")

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # 1. Moving Averages
    sma_20 = ta.trend.sma_indicator(close, window=min(20, len(df)), fillna=True)
    sma_50 = ta.trend.sma_indicator(close, window=min(50, len(df)), fillna=True)
    ema_20 = ta.trend.ema_indicator(close, window=min(20, len(df)), fillna=True)

    # 2. RSI (Relative Strength Index)
    rsi_series = ta.momentum.rsi(close, window=14, fillna=True)
    current_rsi = float(rsi_series.iloc[-1])

    # 3. MACD (Moving Average Convergence Divergence)
    macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9, fillna=True)
    macd_val = float(macd_obj.macd().iloc[-1])
    macd_signal = float(macd_obj.macd_signal().iloc[-1])
    macd_diff = float(macd_obj.macd_diff().iloc[-1])

    # 4. Bollinger Bands
    bb_obj = ta.volatility.BollingerBands(close, window=min(20, len(df)), window_dev=2, fillna=True)
    bb_upper = float(bb_obj.bollinger_hband().iloc[-1])
    bb_lower = float(bb_obj.bollinger_lband().iloc[-1])
    bb_mid = float(bb_obj.bollinger_mavg().iloc[-1])
    bb_width = float(bb_obj.bollinger_wband().iloc[-1])

    # 5. Support & Resistance Levels (Recent 60 bars pivot analysis)
    recent_window = df.tail(min(60, len(df)))
    support_level = float(recent_window["Low"].min())
    resistance_level = float(recent_window["High"].max())

    current_price = float(close.iloc[-1])
    cur_sma_20 = float(sma_20.iloc[-1])
    cur_sma_50 = float(sma_50.iloc[-1])

    # 6. Trend Signal
    if current_price > cur_sma_20 and macd_diff > 0:
        trend = "Bullish"
        trend_explanation = f"Price is trading above the 20-day SMA ({cur_sma_20:.2f}) with positive MACD momentum."
    elif current_price < cur_sma_20 and macd_diff < 0:
        trend = "Bearish"
        trend_explanation = f"Price is trading below the 20-day SMA ({cur_sma_20:.2f}) with negative MACD pressure."
    else:
        trend = "Neutral / Consolidating"
        trend_explanation = f"Price is consolidating near the 20-day SMA ({cur_sma_20:.2f})."

    # 7. Volatility & Risk Level
    daily_returns = close.pct_change().dropna()
    annual_volatility = float(daily_returns.std() * math.sqrt(252) * 100) if len(daily_returns) > 1 else 15.0

    if annual_volatility > 35.0 or bb_width > 18.0:
        risk_level = "High"
    elif annual_volatility > 20.0:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "current_price": round(current_price, 2),
        "trend": trend,
        "trend_explanation": trend_explanation,
        "risk_level": risk_level,
        "annual_volatility_pct": round(annual_volatility, 2),
        "rsi_14": round(current_rsi, 2),
        "rsi_condition": "Overbought (>70)" if current_rsi > 70 else ("Oversold (<30)" if current_rsi < 30 else "Neutral"),
        "macd": {
            "macd": round(macd_val, 2),
            "signal": round(macd_signal, 2),
            "histogram": round(macd_diff, 2),
            "signal_status": "Bullish Cross" if macd_diff > 0 else "Bearish Cross",
        },
        "bollinger_bands": {
            "upper": round(bb_upper, 2),
            "middle": round(bb_mid, 2),
            "lower": round(bb_lower, 2),
            "bandwidth_pct": round(bb_width, 2),
        },
        "support_level": round(support_level, 2),
        "resistance_level": round(resistance_level, 2),
        "sma_20": round(cur_sma_20, 2),
        "sma_50": round(cur_sma_50, 2),
    }
