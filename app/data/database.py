"""SQLite database setup and models."""

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Boolean, Text,
    create_engine, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(5), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_stock_time"),
    )


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(5), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    signal_type = Column(String(10))  # BUY / SELL / HOLD
    strength = Column(String(10))     # Strong / Weak
    score = Column(Float)
    indicators = Column(Text)         # JSON string of indicator values


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    trade_type = Column(String(4))   # BUY / SELL
    quantity = Column(Integer)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    pnl = Column(Float, default=0.0)
    is_backtest = Column(Boolean, default=False)


class Portfolio(Base):
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    quantity = Column(Integer, default=0)
    avg_price = Column(Float, default=0.0)
    current_price = Column(Float, default=0.0)
    invested = Column(Float, default=0.0)
    current_value = Column(Float, default=0.0)
    pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    alert_type = Column(String(30))
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    name = Column(String(100), default="Trader")
    email = Column(String(150), default="")
    phone = Column(String(20), default="")
    avatar_color = Column(String(10), default="#3B82F6")
    bio = Column(Text, default="")
    experience = Column(String(30), default="Beginner")
    risk_appetite = Column(String(20), default="Moderate")
    preferred_sectors = Column(Text, default="")
    telegram_token = Column(String(100), default="")
    telegram_chat_id = Column(String(50), default="")
    default_capital = Column(Float, default=1000000)
    watchlist_custom = Column(Text, default="")
    theme = Column(String(10), default="dark")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
