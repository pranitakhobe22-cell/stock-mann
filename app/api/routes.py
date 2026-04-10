"""FastAPI REST endpoints."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from pydantic import BaseModel
from datetime import datetime
import numpy as np
import httpx

from app.data.fetcher import fetch_stock_data, fetch_and_store, get_latest_price, get_stored_data
from app.indicators.technical import add_all_indicators
from app.signals.engine import generate_signal, save_signal
from app.scanner.market_scanner import (
    scan_market, find_oversold, find_overbought,
    find_volume_spikes, find_breakouts, get_top_gainers, get_top_losers,
)
from app.backtest.backtester import run_backtest
from app.portfolio.manager import PortfolioManager
from app.alerts.telegram_alert import send_alert_sync
from config.settings import DEFAULT_WATCHLIST

router = APIRouter()
portfolio_mgr = PortfolioManager()


# ─── Auth (Simple — no real security) ───────────────────

class SignupData(BaseModel):
    username: str
    password: str
    name: str
    email: str = ""


class LoginData(BaseModel):
    username: str
    password: str


@router.post("/api/auth/signup")
def signup(data: SignupData):
    """Create account — always accepts. If username exists, just logs them in."""
    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        existing = session.query(UserProfile).filter_by(username=data.username).first()
        if existing:
            # Username taken? No problem — update name/email and log them in
            if data.name:
                existing.name = data.name
            if data.email:
                existing.email = data.email
            existing.password = data.password
            session.commit()
            return {
                "status": "ok",
                "user_id": existing.id,
                "username": existing.username,
                "name": existing.name,
                "avatar_color": existing.avatar_color or "#3B82F6",
            }
        user = UserProfile(
            username=data.username,
            password=data.password,
            name=data.name,
            email=data.email,
            avatar_color="#3B82F6",
            experience="Beginner",
            risk_appetite="Moderate",
            default_capital=1000000,
        )
        session.add(user)
        session.commit()
        return {
            "status": "ok",
            "user_id": user.id,
            "username": user.username,
            "name": user.name,
            "avatar_color": user.avatar_color,
        }
    finally:
        session.close()


@router.post("/api/auth/login")
def login(data: LoginData):
    """Login — always accepts. If user doesn't exist, auto-creates account."""
    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        user = session.query(UserProfile).filter_by(username=data.username).first()
        if not user:
            # User doesn't exist? Auto-create and log in
            user = UserProfile(
                username=data.username,
                password=data.password,
                name=data.username.capitalize(),
                avatar_color="#3B82F6",
                experience="Beginner",
                risk_appetite="Moderate",
                default_capital=1000000,
            )
            session.add(user)
            session.commit()
        return {
            "status": "ok",
            "user_id": user.id,
            "username": user.username,
            "name": user.name or user.username,
            "avatar_color": user.avatar_color or "#3B82F6",
        }
    finally:
        session.close()


# ─── Stock Data ──────────────────────────────────────────

@router.get("/api/stock/{symbol}")
def get_stock(symbol: str, timeframe: str = "1d", limit: int = 200):
    """Fetch stock data (live from Yahoo Finance)."""
    df = fetch_stock_data(symbol, timeframe)
    if df.empty:
        return JSONResponse({"error": "No data found"}, status_code=404)
    df = df.tail(limit).copy()
    df["timestamp"] = df["timestamp"].astype(str)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(df),
        "data": df.to_dict(orient="records"),
    }


@router.post("/api/stock/{symbol}/fetch")
def fetch_and_save(symbol: str, timeframe: str = "1d"):
    """Fetch stock data and save to database."""
    result = fetch_and_store(symbol, timeframe)
    return result


@router.get("/api/stock/{symbol}/price")
def get_price(symbol: str):
    """Get latest price for a symbol."""
    info = get_latest_price(symbol)
    if not info:
        return JSONResponse({"error": "Could not fetch price"}, status_code=404)
    return info


@router.get("/api/search")
async def search_symbols(q: str):
    """Search for symbols using Yahoo Finance autocomplete."""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=8&newsCount=0"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            data = resp.json()
            results = []
            for quote in data.get("quotes", []):
                sym = quote.get("symbol")
                name = quote.get("shortname") or quote.get("longname") or sym
                exch = quote.get("exchDisp") or quote.get("exchange")
                if sym:
                    results.append({"symbol": sym, "name": name, "exchange": exch})
            return {"results": results}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)


# ─── Indicators ──────────────────────────────────────────

@router.get("/api/stock/{symbol}/indicators")
def get_indicators(symbol: str, timeframe: str = "1d"):
    """Get stock data with all technical indicators."""
    df = fetch_stock_data(symbol, timeframe)
    if df.empty:
        return JSONResponse({"error": "No data"}, status_code=404)
    df = add_all_indicators(df)
    # Return last 50 rows to keep response manageable
    records = df.tail(50).replace({np.nan: None}).to_dict(orient="records")
    return {"symbol": symbol, "timeframe": timeframe, "data": records}


# ─── Signals ─────────────────────────────────────────────

@router.get("/api/signal/{symbol}")
def get_signal(symbol: str, timeframe: str = "1d"):
    """Generate trading signal for a stock."""
    df = fetch_stock_data(symbol, timeframe)
    if df.empty:
        return JSONResponse({"error": "No data"}, status_code=404)
    sig = generate_signal(df, symbol=symbol, timeframe=timeframe)
    save_signal(sig)
    # Fire alert if BUY/SELL
    if sig["signal"] != "HOLD":
        send_alert_sync(sig)
    return sig


# ─── Scanner ─────────────────────────────────────────────

@router.get("/api/scanner")
def scanner(timeframe: str = "1d"):
    """Scan all watchlist stocks (custom + Nifty 50)."""
    from app.data.database import SessionLocal, UserProfile
    symbols = list(DEFAULT_WATCHLIST)
    session = SessionLocal()
    try:
        profile = session.query(UserProfile).first()
        if profile and profile.watchlist_custom:
            custom = [s.strip() for s in profile.watchlist_custom.split(",") if s.strip()]
            seen = set(symbols)
            for s in custom:
                if s not in seen:
                    symbols.append(s)
                    seen.add(s)
    finally:
        session.close()
    results = scan_market(symbols=symbols, timeframe=timeframe)
    return {
        "timeframe": timeframe,
        "total": len(results),
        "results": results,
        "oversold": find_oversold(results),
        "overbought": find_overbought(results),
        "volume_spikes": find_volume_spikes(results),
        "breakouts": find_breakouts(results),
        "top_gainers": get_top_gainers(results),
        "top_losers": get_top_losers(results),
    }


# ─── Backtesting ─────────────────────────────────────────

@router.get("/api/backtest/{symbol}")
def backtest(
    symbol: str,
    timeframe: str = "1d",
    capital: float = 1_000_000,
    buy_threshold: float = 3.0,
    sell_threshold: float = -3.0,
):
    """Run backtest on a stock."""
    df = fetch_stock_data(symbol, timeframe)
    if df.empty:
        return JSONResponse({"error": "No data"}, status_code=404)
    result = run_backtest(
        df, symbol=symbol,
        initial_capital=capital,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
    )
    return result


# ─── Portfolio ───────────────────────────────────────────

@router.post("/api/portfolio/buy")
def portfolio_buy(symbol: str, quantity: int, price: float | None = None):
    if not symbol or quantity <= 0:
        return JSONResponse({"error": "Invalid symbol or quantity"}, status_code=400)
    if price is not None and price <= 0:
        return JSONResponse({"error": "Price must be positive"}, status_code=400)
    return portfolio_mgr.buy(symbol, quantity, price)


@router.post("/api/portfolio/sell")
def portfolio_sell(symbol: str, quantity: int, price: float | None = None):
    if not symbol or quantity <= 0:
        return JSONResponse({"error": "Invalid symbol or quantity"}, status_code=400)
    if price is not None and price <= 0:
        return JSONResponse({"error": "Price must be positive"}, status_code=400)
    return portfolio_mgr.sell(symbol, quantity, price)


@router.get("/api/portfolio")
def portfolio_holdings():
    return portfolio_mgr.get_summary()


@router.get("/api/portfolio/trades")
def portfolio_trades(symbol: str | None = None):
    return portfolio_mgr.get_trade_history(symbol)


# ─── Watchlist ───────────────────────────────────────────

@router.get("/api/watchlist")
def get_watchlist():
    """Get user's watchlist (custom + default Nifty 50)."""
    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        profile = session.query(UserProfile).first()
        custom = []
        if profile and profile.watchlist_custom:
            custom = [s.strip() for s in profile.watchlist_custom.split(",") if s.strip()]
        # Custom stocks first, then defaults (no duplicates)
        seen = set()
        symbols = []
        for s in custom + DEFAULT_WATCHLIST:
            if s not in seen:
                seen.add(s)
                symbols.append(s)
        return {"symbols": symbols, "custom": custom, "total": len(symbols)}
    finally:
        session.close()


@router.post("/api/watchlist/add")
def add_to_watchlist(symbol: str):
    """Add a stock to user's custom watchlist."""
    symbol = symbol.strip().upper()
    if not symbol:
        return JSONResponse({"error": "Symbol required"}, status_code=400)
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol += ".NS"

    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        profile = session.query(UserProfile).first()
        if not profile:
            profile = UserProfile(username="guest", password="", name="Trader",
                                  avatar_color="#3B82F6", default_capital=1000000)
            session.add(profile)
            session.commit()

        custom = []
        if profile.watchlist_custom:
            custom = [s.strip() for s in profile.watchlist_custom.split(",") if s.strip()]

        if symbol in custom or symbol in DEFAULT_WATCHLIST:
            return {"status": "ok", "message": f"{symbol} already in watchlist"}

        custom.append(symbol)
        profile.watchlist_custom = ",".join(custom)
        session.commit()
        return {"status": "ok", "message": f"{symbol} added", "custom": custom}
    finally:
        session.close()


@router.post("/api/watchlist/remove")
def remove_from_watchlist(symbol: str):
    """Remove a stock from user's custom watchlist."""
    symbol = symbol.strip().upper()
    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        profile = session.query(UserProfile).first()
        if not profile or not profile.watchlist_custom:
            return {"status": "ok", "message": "Nothing to remove"}

        custom = [s.strip() for s in profile.watchlist_custom.split(",") if s.strip()]
        if symbol in custom:
            custom.remove(symbol)
            profile.watchlist_custom = ",".join(custom) if custom else ""
            session.commit()
            return {"status": "ok", "message": f"{symbol} removed", "custom": custom}
        return {"status": "ok", "message": f"{symbol} not in custom watchlist"}
    finally:
        session.close()


# ─── User Profile ───────────────────────────────────────

@router.post("/api/telegram/test")
async def test_telegram():
    """Send a test message to verify Telegram setup."""
    from app.alerts.telegram_alert import send_telegram_message, _get_telegram_credentials
    credentials = _get_telegram_credentials()
    if not credentials:
        return JSONResponse(
            {"error": "No Telegram configured. Set Bot Token and Chat ID in your profile settings."},
            status_code=400,
        )
    msg = "✅ <b>StockMann Telegram Test</b>\n\nYour Telegram alerts are working! You will receive BUY/SELL signals automatically."
    success = 0
    for cred in credentials:
        ok = await send_telegram_message(msg, token=cred["token"], chat_id=cred["chat_id"])
        if ok:
            success += 1
    if success > 0:
        return {"status": "ok", "message": f"Test message sent to {success} user(s)"}
    return JSONResponse({"error": "Failed to send. Check your Bot Token and Chat ID."}, status_code=400)


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar_color: str | None = None
    bio: str | None = None
    experience: str | None = None
    risk_appetite: str | None = None
    preferred_sectors: str | None = None
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    default_capital: float | None = None
    watchlist_custom: str | None = None
    theme: str | None = None


@router.get("/api/profile")
def get_profile(username: str = ""):
    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        if username:
            profile = session.query(UserProfile).filter_by(username=username).first()
        else:
            profile = session.query(UserProfile).first()
        if not profile:
            # Auto-create a default guest profile so terminal works without login
            profile = UserProfile(
                username="guest",
                password="",
                name="Trader",
                avatar_color="#3B82F6",
                experience="Beginner",
                risk_appetite="Moderate",
                default_capital=1000000,
            )
            session.add(profile)
            session.commit()
        return {
            "id": profile.id,
            "username": profile.username,
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone,
            "avatar_color": profile.avatar_color,
            "bio": profile.bio,
            "experience": profile.experience,
            "risk_appetite": profile.risk_appetite,
            "preferred_sectors": profile.preferred_sectors,
            "telegram_token": profile.telegram_token,
            "telegram_chat_id": profile.telegram_chat_id,
            "default_capital": profile.default_capital,
            "watchlist_custom": profile.watchlist_custom,
            "theme": profile.theme,
            "created_at": str(profile.created_at),
            "updated_at": str(profile.updated_at),
        }
    finally:
        session.close()


@router.put("/api/profile")
def update_profile(data: ProfileUpdate, username: str = ""):
    from app.data.database import SessionLocal, UserProfile
    session = SessionLocal()
    try:
        if username:
            profile = session.query(UserProfile).filter_by(username=username).first()
        else:
            profile = session.query(UserProfile).first()
        if not profile:
            # Auto-create guest profile
            profile = UserProfile(username="guest", password="", name="Trader",
                                  avatar_color="#3B82F6", default_capital=1000000)
            session.add(profile)
            session.commit()
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(profile, key, value)
        profile.updated_at = datetime.utcnow()
        session.commit()
        return {"status": "ok", "message": "Profile updated"}
    finally:
        session.close()


@router.get("/api/profile/stats")
def get_profile_stats():
    """Get user activity stats for the profile page."""
    from app.data.database import SessionLocal, Trade, Signal, AlertLog
    session = SessionLocal()
    try:
        total_trades = session.query(Trade).filter_by(is_backtest=False).count()
        buy_trades = session.query(Trade).filter_by(trade_type="BUY", is_backtest=False).count()
        sell_trades = session.query(Trade).filter_by(trade_type="SELL", is_backtest=False).count()
        total_signals = session.query(Signal).count()
        total_alerts = session.query(AlertLog).count()

        # Recent signals
        recent_signals = (
            session.query(Signal)
            .order_by(Signal.timestamp.desc())
            .limit(10)
            .all()
        )
        signals_list = [
            {
                "symbol": s.symbol,
                "signal": s.signal_type,
                "strength": s.strength,
                "score": s.score,
                "timestamp": str(s.timestamp),
            }
            for s in recent_signals
        ]

        return {
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_signals": total_signals,
            "total_alerts": total_alerts,
            "recent_signals": signals_list,
        }
    finally:
        session.close()
