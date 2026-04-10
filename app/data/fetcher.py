"""Real-time and historical stock data fetching via Yahoo Finance — with caching."""

import time
import threading
import yfinance as yf
import pandas as pd
from datetime import datetime

from app.data.database import SessionLocal, StockPrice
from config.settings import TIMEFRAMES

# ═══ IN-MEMORY CACHES ═══
# Stock data cache: key="SYMBOL:TIMEFRAME" -> (timestamp, DataFrame)
_data_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_data_lock = threading.Lock()
DATA_CACHE_TTL = 60  # seconds

# Price cache: key="SYMBOL" -> (timestamp, dict)
_price_cache: dict[str, tuple[float, dict]] = {}
_price_lock = threading.Lock()
PRICE_CACHE_TTL = 30  # seconds


def _get_cached(cache, lock, key, ttl):
    """Thread-safe cache lookup. Returns cached value or None."""
    with lock:
        if key in cache:
            ts, value = cache[key]
            if time.time() - ts < ttl:
                return value
            del cache[key]
    return None


def _set_cached(cache, lock, key, value):
    """Thread-safe cache store."""
    with lock:
        cache[key] = (time.time(), value)


def fetch_stock_data(symbol: str, timeframe: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data — cached for 60s to avoid redundant Yahoo calls."""
    cache_key = f"{symbol}:{timeframe}"

    # Check cache first
    cached = _get_cached(_data_cache, _data_lock, cache_key, DATA_CACHE_TTL)
    if cached is not None:
        return cached.copy()

    # Cache miss — fetch using Ticker.history (thread-safe, per-ticker session)
    tf = TIMEFRAMES.get(timeframe, TIMEFRAMES["1d"])
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=tf["period"], interval=tf["interval"])
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    # Normalize column names
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ("date", "datetime"):
            col_map[c] = "timestamp"
        elif cl == "open":
            col_map[c] = "open"
        elif cl == "high":
            col_map[c] = "high"
        elif cl == "low":
            col_map[c] = "low"
        elif cl == "close":
            col_map[c] = "close"
        elif cl == "volume":
            col_map[c] = "volume"
    df = df.rename(columns=col_map)

    needed = ["timestamp", "open", "high", "low", "close", "volume"]
    for col in needed:
        if col not in df.columns:
            return pd.DataFrame()

    df = df[needed]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.dropna(subset=["close"])

    # Store in cache
    _set_cached(_data_cache, _data_lock, cache_key, df)
    return df.copy()


def save_to_db(symbol: str, timeframe: str, df: pd.DataFrame) -> int:
    """Save fetched data to SQLite, skipping duplicates. Returns rows inserted."""
    if df.empty:
        return 0

    session = SessionLocal()
    inserted = 0
    try:
        for _, row in df.iterrows():
            exists = (
                session.query(StockPrice)
                .filter_by(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=row["timestamp"].to_pydatetime(),
                )
                .first()
            )
            if not exists:
                entry = StockPrice(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=row["timestamp"].to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                )
                session.add(entry)
                inserted += 1
        session.commit()
    finally:
        session.close()
    return inserted


def fetch_and_store(symbol: str, timeframe: str = "1d") -> dict:
    """Fetch data and save to DB. Returns summary."""
    df = fetch_stock_data(symbol, timeframe)
    rows = save_to_db(symbol, timeframe, df)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_rows": len(df),
        "new_rows": rows,
    }


def get_stored_data(symbol: str, timeframe: str = "1d", limit: int = 500) -> pd.DataFrame:
    """Load stored data from DB as a DataFrame."""
    session = SessionLocal()
    try:
        rows = (
            session.query(StockPrice)
            .filter_by(symbol=symbol, timeframe=timeframe)
            .order_by(StockPrice.timestamp.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return pd.DataFrame()
        data = [
            {
                "timestamp": r.timestamp,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
        df = pd.DataFrame(data).sort_values("timestamp").reset_index(drop=True)
        return df
    finally:
        session.close()


def get_latest_price(symbol: str) -> dict | None:
    """Get the most recent price — cached for 30s."""
    # Check cache first
    cached = _get_cached(_price_cache, _price_lock, symbol, PRICE_CACHE_TTL)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        result = {
            "symbol": symbol,
            "price": info.last_price,
            "previous_close": info.previous_close,
            "change_pct": round(
                ((info.last_price - info.previous_close) / info.previous_close) * 100, 2
            ),
        }
        _set_cached(_price_cache, _price_lock, symbol, result)
        return result
    except Exception:
        return None


def clear_cache():
    """Clear all caches — called by scheduler after fresh fetch."""
    with _data_lock:
        _data_cache.clear()
    with _price_lock:
        _price_cache.clear()
