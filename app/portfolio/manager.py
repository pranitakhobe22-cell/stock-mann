"""Virtual portfolio management."""

from datetime import datetime

from app.data.database import SessionLocal, Portfolio, Trade
from app.data.fetcher import get_latest_price


class PortfolioManager:
    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        from app.data.database import init_db
        init_db()

    def buy(self, symbol: str, quantity: int, price: float | None = None) -> dict:
        """Buy shares of a stock."""
        if price is None:
            info = get_latest_price(symbol)
            if not info:
                return {"error": f"Could not fetch price for {symbol}"}
            price = info["price"]

        total_cost = quantity * price
        session = SessionLocal()
        try:
            holding = session.query(Portfolio).filter_by(symbol=symbol).first()
            if holding:
                new_qty = holding.quantity + quantity
                holding.avg_price = (
                    (holding.avg_price * holding.quantity) + (price * quantity)
                ) / new_qty
                holding.quantity = new_qty
                holding.invested = holding.avg_price * new_qty
            else:
                holding = Portfolio(
                    symbol=symbol,
                    quantity=quantity,
                    avg_price=price,
                    current_price=price,
                    invested=total_cost,
                    current_value=total_cost,
                )
                session.add(holding)

            trade = Trade(
                symbol=symbol,
                trade_type="BUY",
                quantity=quantity,
                price=price,
            )
            session.add(trade)
            session.commit()

            return {
                "action": "BUY",
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "total_cost": round(total_cost, 2),
            }
        finally:
            session.close()

    def sell(self, symbol: str, quantity: int, price: float | None = None) -> dict:
        """Sell shares of a stock."""
        session = SessionLocal()
        try:
            holding = session.query(Portfolio).filter_by(symbol=symbol).first()
            if not holding or holding.quantity < quantity:
                return {"error": f"Insufficient holdings for {symbol}"}

            if price is None:
                info = get_latest_price(symbol)
                if not info:
                    return {"error": f"Could not fetch price for {symbol}"}
                price = info["price"]

            pnl = (price - holding.avg_price) * quantity
            holding.quantity -= quantity
            if holding.quantity == 0:
                session.delete(holding)
            else:
                holding.invested = holding.avg_price * holding.quantity

            trade = Trade(
                symbol=symbol,
                trade_type="SELL",
                quantity=quantity,
                price=price,
                pnl=pnl,
            )
            session.add(trade)
            session.commit()

            return {
                "action": "SELL",
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "pnl": round(pnl, 2),
            }
        finally:
            session.close()

    def get_holdings(self) -> list[dict]:
        """Get all current holdings with live P&L."""
        session = SessionLocal()
        try:
            holdings = session.query(Portfolio).all()
            result = []
            for h in holdings:
                info = get_latest_price(h.symbol)
                current = info["price"] if info else (h.current_price or 0)

                h.current_price = current
                h.current_value = current * h.quantity
                h.pnl = h.current_value - (h.invested or 0)
                h.pnl_pct = (h.pnl / h.invested * 100) if h.invested else 0
                h.updated_at = datetime.utcnow()

                result.append({
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "avg_price": round(h.avg_price, 2),
                    "current_price": round(current, 2),
                    "invested": round(h.invested or 0, 2),
                    "current_value": round(h.current_value, 2),
                    "pnl": round(h.pnl, 2),
                    "pnl_pct": round(h.pnl_pct, 2),
                })
            session.commit()
            return result
        except Exception:
            session.rollback()
            return []
        finally:
            session.close()

    def get_trade_history(self, symbol: str | None = None) -> list[dict]:
        """Get trade log."""
        session = SessionLocal()
        try:
            q = session.query(Trade).filter_by(is_backtest=False)
            if symbol:
                q = q.filter_by(symbol=symbol)
            trades = q.order_by(Trade.timestamp.desc()).all()
            return [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "type": t.trade_type,
                    "quantity": t.quantity,
                    "price": t.price,
                    "pnl": t.pnl,
                    "timestamp": str(t.timestamp),
                }
                for t in trades
            ]
        finally:
            session.close()

    def get_summary(self) -> dict:
        """Portfolio summary."""
        holdings = self.get_holdings()
        total_invested = sum(h["invested"] for h in holdings)
        total_value = sum(h["current_value"] for h in holdings)
        total_pnl = total_value - total_invested
        return {
            "total_invested": round(total_invested, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_invested * 100) if total_invested else 0, 2),
            "num_holdings": len(holdings),
            "holdings": holdings,
        }
