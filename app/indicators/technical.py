"""Technical indicator calculations."""

import pandas as pd
import numpy as np
from config.settings import (
    RSI_PERIOD, EMA_SHORT, EMA_LONG, SMA_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BOLLINGER_PERIOD, BOLLINGER_STD,
)


def calculate_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100)  # All gains, no losses = RSI 100
    return rsi


def calculate_ema(df: pd.DataFrame, period: int = EMA_SHORT) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return df["close"].ewm(span=period, adjust=False).mean()


def calculate_sma(df: pd.DataFrame, period: int = SMA_PERIOD) -> pd.Series:
    """Calculate Simple Moving Average."""
    return df["close"].rolling(window=period).mean()


def calculate_macd(df: pd.DataFrame) -> dict:
    """Calculate MACD line, signal line, and histogram."""
    ema_fast = df["close"].ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = df["close"].ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calculate_bollinger_bands(df: pd.DataFrame) -> dict:
    """Calculate Bollinger Bands."""
    sma = df["close"].rolling(window=BOLLINGER_PERIOD).mean()
    std = df["close"].rolling(window=BOLLINGER_PERIOD).std()
    return {
        "upper": sma + (BOLLINGER_STD * std),
        "middle": sma,
        "lower": sma - (BOLLINGER_STD * std),
    }


def calculate_volume_metrics(df: pd.DataFrame) -> dict:
    """Calculate volume-based metrics."""
    avg_volume = df["volume"].rolling(window=20).mean()
    volume_ratio = df["volume"] / avg_volume
    return {"avg_volume": avg_volume, "volume_ratio": volume_ratio}


def calculate_volatility(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate rolling volatility (std of returns)."""
    returns = df["close"].pct_change()
    return returns.rolling(window=period).std() * np.sqrt(252)


def calculate_momentum(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """Calculate price momentum."""
    return df["close"] / df["close"].shift(period) - 1


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators to a DataFrame."""
    if df.empty or len(df) < 30:
        return df

    df = df.copy()
    df["rsi"] = calculate_rsi(df)
    df["ema_12"] = calculate_ema(df, EMA_SHORT)
    df["ema_26"] = calculate_ema(df, EMA_LONG)
    df["sma_20"] = calculate_sma(df)

    macd = calculate_macd(df)
    df["macd"] = macd["macd"]
    df["macd_signal"] = macd["signal"]
    df["macd_histogram"] = macd["histogram"]

    bb = calculate_bollinger_bands(df)
    df["bb_upper"] = bb["upper"]
    df["bb_middle"] = bb["middle"]
    df["bb_lower"] = bb["lower"]

    vol = calculate_volume_metrics(df)
    df["avg_volume"] = vol["avg_volume"]
    df["volume_ratio"] = vol["volume_ratio"]

    df["volatility"] = calculate_volatility(df)
    df["momentum"] = calculate_momentum(df)

    return df
