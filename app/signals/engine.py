"""Signal generation engine — BUY / SELL / HOLD with strength scoring."""

import json
from datetime import datetime

import pandas as pd

from app.indicators.technical import add_all_indicators
from app.data.database import SessionLocal, Signal
from config.settings import RSI_OVERSOLD, RSI_OVERBOUGHT


def _score_indicators(row: pd.Series) -> dict:
    """Score each indicator and return signal details."""
    scores = {}

    # --- RSI ---
    rsi = row.get("rsi")
    if pd.notna(rsi):
        if rsi < RSI_OVERSOLD:
            scores["rsi"] = +2  # Strong buy
        elif rsi < 40:
            scores["rsi"] = +1
        elif rsi > RSI_OVERBOUGHT:
            scores["rsi"] = -2  # Strong sell
        elif rsi > 60:
            scores["rsi"] = -1
        else:
            scores["rsi"] = 0

    # --- EMA crossover ---
    ema12 = row.get("ema_12")
    ema26 = row.get("ema_26")
    if pd.notna(ema12) and pd.notna(ema26):
        diff_pct = (ema12 - ema26) / ema26 * 100
        if diff_pct > 1:
            scores["ema_cross"] = +2
        elif diff_pct > 0:
            scores["ema_cross"] = +1
        elif diff_pct < -1:
            scores["ema_cross"] = -2
        else:
            scores["ema_cross"] = 0

    # --- MACD ---
    macd_hist = row.get("macd_histogram")
    if pd.notna(macd_hist):
        if macd_hist > 0.5:
            scores["macd"] = +2
        elif macd_hist > 0:
            scores["macd"] = +1
        elif macd_hist < -0.5:
            scores["macd"] = -2
        else:
            scores["macd"] = 0

    # --- Bollinger Bands ---
    close = row.get("close")
    bb_lower = row.get("bb_lower")
    bb_upper = row.get("bb_upper")
    if pd.notna(close) and pd.notna(bb_lower) and pd.notna(bb_upper):
        if close <= bb_lower:
            scores["bollinger"] = +2
        elif close >= bb_upper:
            scores["bollinger"] = -2
        else:
            scores["bollinger"] = 0

    # --- Volume spike ---
    vol_ratio = row.get("volume_ratio")
    if pd.notna(vol_ratio):
        if vol_ratio > 2.0:
            scores["volume"] = +1  # Confirms trend
        else:
            scores["volume"] = 0

    # --- Momentum ---
    momentum = row.get("momentum")
    if pd.notna(momentum):
        if momentum > 0.05:
            scores["momentum"] = +1
        elif momentum < -0.05:
            scores["momentum"] = -1
        else:
            scores["momentum"] = 0

    return scores


def generate_signal(df: pd.DataFrame, symbol: str = "", timeframe: str = "1d") -> dict:
    """Generate a trading signal from a DataFrame with indicators."""
    df = add_all_indicators(df)
    if df.empty or len(df) < 30:
        return {"signal": "HOLD", "strength": "Weak", "score": 0, "details": {}}

    latest = df.iloc[-1]
    scores = _score_indicators(latest)

    total = sum(scores.values())
    num_indicators = len(scores) or 1

    # Normalize score to -10..+10 range
    normalized = round((total / num_indicators) * 5, 2)
    normalized = max(-10, min(10, normalized))

    if normalized >= 3:
        signal_type = "BUY"
        strength = "Strong" if normalized >= 6 else "Weak"
    elif normalized <= -3:
        signal_type = "SELL"
        strength = "Strong" if normalized <= -6 else "Weak"
    else:
        signal_type = "HOLD"
        strength = "Neutral"

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": signal_type,
        "strength": strength,
        "score": normalized,
        "details": scores,
        "indicators": {
            "rsi": round(latest.get("rsi", 0), 2) if pd.notna(latest.get("rsi")) else None,
            "ema_12": round(latest.get("ema_12", 0), 2) if pd.notna(latest.get("ema_12")) else None,
            "ema_26": round(latest.get("ema_26", 0), 2) if pd.notna(latest.get("ema_26")) else None,
            "macd": round(latest.get("macd", 0), 4) if pd.notna(latest.get("macd")) else None,
            "macd_histogram": round(latest.get("macd_histogram", 0), 4) if pd.notna(latest.get("macd_histogram")) else None,
            "bb_upper": round(latest.get("bb_upper", 0), 2) if pd.notna(latest.get("bb_upper")) else None,
            "bb_lower": round(latest.get("bb_lower", 0), 2) if pd.notna(latest.get("bb_lower")) else None,
            "volume_ratio": round(latest.get("volume_ratio", 0), 2) if pd.notna(latest.get("volume_ratio")) else None,
            "momentum": round(latest.get("momentum", 0), 4) if pd.notna(latest.get("momentum")) else None,
        },
        "price": round(float(latest["close"]), 2),
        "timestamp": str(latest.get("timestamp", datetime.utcnow())),
    }

    return result


def save_signal(sig: dict):
    """Persist a signal to the database."""
    session = SessionLocal()
    try:
        entry = Signal(
            symbol=sig["symbol"],
            timeframe=sig["timeframe"],
            signal_type=sig["signal"],
            strength=sig["strength"],
            score=sig["score"],
            indicators=json.dumps(sig.get("indicators", {})),
        )
        session.add(entry)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
