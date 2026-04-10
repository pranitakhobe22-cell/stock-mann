"""Telegram alert system with per-user tokens and smart deduplication."""

import threading
import asyncio
from datetime import datetime, timedelta

import httpx

from app.data.database import SessionLocal, AlertLog, UserProfile
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# In-memory cache to avoid repeated alerts — thread-safe with lock
_recent_alerts: dict[str, datetime] = {}
_alert_lock = threading.Lock()
ALERT_COOLDOWN = timedelta(minutes=30)
MAX_CACHE_SIZE = 500


def _get_telegram_credentials() -> list[dict]:
    """
    Get all Telegram credentials — per-user tokens from DB + global fallback.
    Returns list of {token, chat_id} dicts for each configured user.
    """
    credentials = []

    # 1. Check all user profiles for personal tokens
    session = SessionLocal()
    try:
        users = session.query(UserProfile).all()
        for user in users:
            if user.telegram_token and user.telegram_chat_id:
                credentials.append({
                    "token": user.telegram_token.strip(),
                    "chat_id": user.telegram_chat_id.strip(),
                    "user": user.name or user.username or "User",
                })
    except Exception:
        pass
    finally:
        session.close()

    # 2. Fallback to global .env token if no user tokens found
    if not credentials and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        credentials.append({
            "token": TELEGRAM_BOT_TOKEN,
            "chat_id": TELEGRAM_CHAT_ID,
            "user": "Global",
        })

    return credentials


async def send_telegram_message(message: str, token: str = "", chat_id: str = "") -> bool:
    """Send a message via Telegram Bot API to a specific user."""
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            return resp.status_code == 200
    except Exception:
        return False


async def send_to_all_users(message: str):
    """Send a message to ALL users who have Telegram configured."""
    credentials = _get_telegram_credentials()
    for cred in credentials:
        await send_telegram_message(message, token=cred["token"], chat_id=cred["chat_id"])


def _should_send(symbol: str, alert_type: str) -> bool:
    """Check cooldown to avoid repeated alerts. Thread-safe."""
    key = f"{symbol}:{alert_type}"
    now = datetime.utcnow()
    with _alert_lock:
        if key in _recent_alerts:
            if now - _recent_alerts[key] < ALERT_COOLDOWN:
                return False
        # Evict stale entries to prevent memory leak
        if len(_recent_alerts) > MAX_CACHE_SIZE:
            stale = [k for k, v in _recent_alerts.items() if now - v > ALERT_COOLDOWN]
            for k in stale:
                del _recent_alerts[k]
        _recent_alerts[key] = now
        return True


def _log_alert(symbol: str, alert_type: str, message: str):
    """Save alert to database."""
    session = SessionLocal()
    try:
        session.add(AlertLog(symbol=symbol, alert_type=alert_type, message=message))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


async def send_signal_alert(signal: dict):
    """Send a BUY/SELL signal alert to all configured Telegram users."""
    symbol = signal.get("symbol", "?")
    sig_type = signal.get("signal", "HOLD")
    if sig_type == "HOLD":
        return

    if not _should_send(symbol, f"signal_{sig_type}"):
        return

    strength = signal.get("strength", "")
    price = signal.get("price", 0)
    score = signal.get("score", 0)
    indicators = signal.get("indicators", {})

    icon = "🟢" if sig_type == "BUY" else "🔴"
    arrow = "▲" if sig_type == "BUY" else "▼"

    msg = (
        f"{icon} <b>STOCKMANN {sig_type} SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Stock:</b>    {symbol.replace('.NS', '')} (NSE)\n"
        f"<b>Signal:</b>   {arrow} {sig_type} ({strength})\n"
        f"<b>Score:</b>    {score} / 10\n"
        f"<b>Price:</b>    ₹{price:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>RSI:</b>      {indicators.get('rsi', 'N/A')}\n"
        f"<b>MACD:</b>     {indicators.get('macd_histogram', 'N/A')}\n"
        f"<b>Momentum:</b> {indicators.get('momentum', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {signal.get('timestamp', '')}\n"
        f"📊 Open terminal: localhost:8000/terminal"
    )

    await send_to_all_users(msg)
    _log_alert(symbol, f"signal_{sig_type}", msg)


async def send_price_alert(symbol: str, current_price: float, threshold: float, direction: str):
    """Send alert when price crosses a threshold."""
    if not _should_send(symbol, f"price_{direction}"):
        return

    icon = "⬆️" if direction == "above" else "⬇️"
    msg = (
        f"{icon} <b>PRICE ALERT — {symbol.replace('.NS', '')}</b>\n"
        f"Price crossed {direction} ₹{threshold:,.2f}\n"
        f"Current: ₹{current_price:,.2f}"
    )
    await send_to_all_users(msg)
    _log_alert(symbol, f"price_{direction}", msg)


async def send_trend_alert(symbol: str, trend: str, details: str = ""):
    """Send alert on trend change."""
    if not _should_send(symbol, f"trend_{trend}"):
        return

    msg = (
        f"📈 <b>TREND CHANGE — {symbol.replace('.NS', '')}</b>\n"
        f"New Trend: {trend}\n"
        f"{details}"
    )
    await send_to_all_users(msg)
    _log_alert(symbol, f"trend_{trend}", msg)


def _run_in_thread(coro):
    """Run a coroutine in a separate thread with its own event loop."""
    def target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        except Exception:
            pass
        finally:
            loop.close()
    t = threading.Thread(target=target, daemon=True)
    t.start()


def send_alert_sync(signal: dict):
    """Synchronous wrapper for signal alerts — safe from any context."""
    _run_in_thread(send_signal_alert(signal))
