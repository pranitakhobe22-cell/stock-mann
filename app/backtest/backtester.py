"""Backtesting engine — test strategies on historical data."""

import pandas as pd
from app.indicators.technical import add_all_indicators
from app.signals.engine import _score_indicators
from config.settings import INITIAL_CAPITAL


def run_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    initial_capital: float = INITIAL_CAPITAL,
    buy_threshold: float = 3.0,
    sell_threshold: float = -3.0,
) -> dict:
    """
    Run a backtest on historical data using the signal engine logic.

    Returns trade history, final value, win rate, max drawdown, etc.
    """
    df = add_all_indicators(df)
    if df.empty or len(df) < 30:
        return {"error": "Not enough data for backtesting"}

    capital = initial_capital
    position = 0  # shares held
    entry_price = 0.0
    trades = []
    equity_curve = []
    peak_equity = initial_capital

    for i in range(30, len(df)):
        row = df.iloc[i]
        scores = _score_indicators(row)
        total = sum(scores.values())
        num = len(scores) or 1
        normalized = round((total / num) * 5, 2)
        normalized = max(-10, min(10, normalized))
        price = float(row["close"])
        timestamp = str(row.get("timestamp", ""))

        # Track equity
        equity = capital + (position * price)
        equity_curve.append({"timestamp": timestamp, "equity": equity})
        peak_equity = max(peak_equity, equity)

        # Buy signal
        if normalized >= buy_threshold and position == 0 and price > 0:
            available = capital * 0.95
            shares = int(available / price)
            if shares > 0:
                cost = shares * price
                position = shares
                entry_price = price
                capital -= cost
                trades.append({
                    "type": "BUY",
                    "price": price,
                    "shares": shares,
                    "timestamp": timestamp,
                    "score": normalized,
                })

        # Sell signal
        elif normalized <= sell_threshold and position > 0:
            capital += position * price
            pnl = (price - entry_price) * position
            pnl_pct = ((price - entry_price) / entry_price) * 100
            trades.append({
                "type": "SELL",
                "price": price,
                "shares": position,
                "timestamp": timestamp,
                "score": normalized,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
            position = 0
            entry_price = 0.0

    # Close open position at last price
    final_price = float(df.iloc[-1]["close"])
    if position > 0:
        capital += position * final_price
        pnl = (final_price - entry_price) * position
        trades.append({
            "type": "SELL (forced close)",
            "price": final_price,
            "shares": position,
            "timestamp": str(df.iloc[-1].get("timestamp", "")),
            "pnl": round(pnl, 2),
        })
        position = 0

    final_equity = capital
    total_return = ((final_equity - initial_capital) / initial_capital) * 100

    # Calculate stats
    sell_trades = [t for t in trades if "pnl" in t]
    wins = [t for t in sell_trades if t["pnl"] > 0]
    losses = [t for t in sell_trades if t["pnl"] <= 0]

    win_rate = (len(wins) / len(sell_trades) * 100) if sell_trades else 0
    total_pnl = sum(t["pnl"] for t in sell_trades)
    avg_pnl = total_pnl / len(sell_trades) if sell_trades else 0

    # Max drawdown
    max_drawdown = 0
    peak = initial_capital
    for point in equity_curve:
        eq = point["equity"]
        peak = max(peak, eq)
        dd = ((peak - eq) / peak) * 100
        max_drawdown = max(max_drawdown, dd)

    return {
        "symbol": symbol,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "total_pnl": round(total_pnl, 2),
        "total_trades": len(sell_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "trades": trades,
        "equity_curve": equity_curve,
    }
