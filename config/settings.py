"""Central configuration for Stock Mann."""

import os
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, ".env"))

# --- Database ---
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "stock_mann.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# --- Stock Symbols (NSE) ---
# --- Full Nifty 50 Watchlist ---
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
    "WIPRO.NS", "SUNPHARMA.NS", "TITAN.NS", "BAJFINANCE.NS", "NESTLEIND.NS",
    "ULTRACEMCO.NS", "NTPC.NS", "POWERGRID.NS", "TECHM.NS", "ADANIENT.NS",
    "BAJAJFINSV.NS", "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "INDUSINDBK.NS",
    "COALINDIA.NS", "HDFCLIFE.NS", "SBILIFE.NS", "GRASIM.NS", "BPCL.NS",
    "DRREDDY.NS", "DIVISLAB.NS", "CIPLA.NS", "APOLLOHOSP.NS", "EICHERMOT.NS",
    "TATACONSUM.NS", "BRITANNIA.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "M&M.NS",
    "HINDALCO.NS", "ADANIPORTS.NS", "SHRIRAMFIN.NS", "BEL.NS", "TRENT.NS",
]

DEFAULT_WATCHLIST = NIFTY_50

# --- Timeframes ---
TIMEFRAMES = {
    "1m": {"period": "7d", "interval": "1m"},
    "5m": {"period": "60d", "interval": "5m"},
    "15m": {"period": "60d", "interval": "15m"},
    "1h": {"period": "730d", "interval": "1h"},
    "1d": {"period": "2y", "interval": "1d"},
}

# --- Indicator Defaults ---
RSI_PERIOD = 14
EMA_SHORT = 12
EMA_LONG = 26
SMA_PERIOD = 20
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# --- Signal Thresholds ---
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_SPIKE_MULTIPLIER = 2.0

# --- Telegram Alerts ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")  # Set your bot token via ENV var
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")      # Set your chat ID via ENV var

# --- Scheduler ---
FETCH_INTERVAL_MINUTES = 5
SCAN_INTERVAL_MINUTES = 15

# --- Portfolio ---
INITIAL_CAPITAL = 1_000_000  # 10 Lakh INR

# --- API ---
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT") or 8000)
