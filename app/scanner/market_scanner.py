"""Market scanner — scan multiple stocks, rank by signal strength."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.data.fetcher import fetch_stock_data
from app.signals.engine import generate_signal
from config.settings import DEFAULT_WATCHLIST


def scan_stock(symbol: str, timeframe: str = "1d") -> dict | None:
    """Scan a single stock and return its signal."""
    try:
        df = fetch_stock_data(symbol, timeframe)
        if df.empty:
            return None
        sig = generate_signal(df, symbol=symbol, timeframe=timeframe)
        return sig
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def scan_market(
    symbols: list[str] | None = None,
    timeframe: str = "1d",
    max_workers: int = 6,
) -> list[dict]:
    """Scan multiple stocks in parallel and return ranked results."""
    symbols = symbols or DEFAULT_WATCHLIST
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_stock, sym, timeframe): sym for sym in symbols}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result and "error" not in result:
                    results.append(result)
            except Exception:
                pass

    # Rank: strong buys first, then weak buys, hold, weak sells, strong sells
    order = {"BUY": 0, "HOLD": 1, "SELL": 2}
    results.sort(key=lambda r: (order.get(r["signal"], 1), -r["score"]))
    return results


def find_oversold(results: list[dict]) -> list[dict]:
    """Filter stocks with RSI < 30."""
    return [r for r in results if (r.get("indicators", {}).get("rsi") or 100) < 30]


def find_overbought(results: list[dict]) -> list[dict]:
    """Filter stocks with RSI > 70."""
    return [r for r in results if (r.get("indicators", {}).get("rsi") or 0) > 70]


def find_volume_spikes(results: list[dict]) -> list[dict]:
    """Filter stocks with volume ratio > 2x."""
    return [r for r in results if (r.get("indicators", {}).get("volume_ratio") or 0) > 2.0]


def find_breakouts(results: list[dict]) -> list[dict]:
    """Filter stocks breaking above Bollinger upper band."""
    out = []
    for r in results:
        price = r.get("price", 0)
        bb_upper = r.get("indicators", {}).get("bb_upper")
        if bb_upper and price > bb_upper:
            out.append(r)
    return out


def get_top_gainers(results: list[dict], n: int = 5) -> list[dict]:
    """Top N by momentum."""
    sorted_r = sorted(
        [r for r in results if r.get("indicators", {}).get("momentum") is not None],
        key=lambda r: r["indicators"]["momentum"],
        reverse=True,
    )
    return sorted_r[:n]


def get_top_losers(results: list[dict], n: int = 5) -> list[dict]:
    """Bottom N by momentum."""
    sorted_r = sorted(
        [r for r in results if r.get("indicators", {}).get("momentum") is not None],
        key=lambda r: r["indicators"]["momentum"],
    )
    return sorted_r[:n]
