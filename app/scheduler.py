"""Automation scheduler — periodic data fetching & signal updates."""

from apscheduler.schedulers.background import BackgroundScheduler

from app.data.fetcher import fetch_and_store
from app.signals.engine import generate_signal, save_signal
from app.data.fetcher import fetch_stock_data
from app.alerts.telegram_alert import send_alert_sync
from config.settings import (
    DEFAULT_WATCHLIST, FETCH_INTERVAL_MINUTES, SCAN_INTERVAL_MINUTES,
)

scheduler = BackgroundScheduler()


def scheduled_fetch():
    """Fetch latest data for all watchlist stocks."""
    print("[Scheduler] Fetching data for watchlist...")
    for symbol in DEFAULT_WATCHLIST:
        try:
            result = fetch_and_store(symbol, "1d")
            if result["new_rows"] > 0:
                print(f"  {symbol}: {result['new_rows']} new rows")
        except Exception as e:
            print(f"  {symbol}: ERROR — {e}")


def scheduled_scan():
    """Generate signals for all watchlist stocks."""
    print("[Scheduler] Scanning for signals...")
    for symbol in DEFAULT_WATCHLIST:
        try:
            df = fetch_stock_data(symbol, "1d")
            if df.empty:
                continue
            sig = generate_signal(df, symbol=symbol, timeframe="1d")
            save_signal(sig)
            if sig["signal"] != "HOLD":
                print(f"  {symbol}: {sig['signal']} ({sig['strength']}) score={sig['score']}")
                send_alert_sync(sig)
        except Exception as e:
            print(f"  {symbol}: ERROR — {e}")


def start_scheduler():
    """Start the background scheduler."""
    scheduler.add_job(
        scheduled_fetch,
        "interval",
        minutes=FETCH_INTERVAL_MINUTES,
        id="fetch_job",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_scan,
        "interval",
        minutes=SCAN_INTERVAL_MINUTES,
        id="scan_job",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[Scheduler] Started — fetch every {FETCH_INTERVAL_MINUTES}m, scan every {SCAN_INTERVAL_MINUTES}m")


def stop_scheduler():
    """Stop the scheduler."""
    scheduler.shutdown(wait=False)
