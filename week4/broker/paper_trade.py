"""Week 4 — paper-trading broker.

A paper broker fills orders against *simulated* money: no real capital, no real
exchange. It is FinPilot's safe default — you run the whole
signal -> order -> fill pipeline and watch the P&L, with nothing at risk.

The design choice that matters: `PaperBroker` exposes the SAME methods as
`KiteClient` (get_ltp / place_order / get_positions). `OrderManager` talks to
whichever it is handed and cannot tell them apart — ports and adapters. You go
from paper to live by swapping one object, not by rewriting the pipeline.

Run:  python paper_trade.py     (a short self-contained demo)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import yfinance as yf


@dataclass
class Trade:
    """One filled paper trade — the audit trail."""
    timestamp: str
    symbol: str
    side: str
    quantity: int
    price: float
    cost: float


class PaperBroker:
    """Simulated broker. Interface mirrors KiteClient so they're swappable."""

    def __init__(self, starting_cash: float = 1_000_000.0, cost_pct: float = 0.0006):
        # cost_pct rolls brokerage + taxes + slippage into one per-trade haircut
        # (~0.06% is a realistic round-figure for Zerodha-style delivery costs).
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.cost_pct = cost_pct
        self.positions: dict[str, dict] = {}  # symbol -> {quantity, avg_price}
        self.trades: list[Trade] = []
        self.realised_pnl = 0.0

    # ── Market data ──────────────────────────────────────────────────────────

    def get_ltp(self, symbol: str) -> float:
        """Last traded price. yfinance stands in for a real market-data feed."""
        df = yf.Ticker(symbol).history(period="1d")
        if df.empty:
            raise RuntimeError(f"No price available for {symbol}")
        return round(float(df["Close"].iloc[-1]), 2)

    # ── Orders ───────────────────────────────────────────────────────────────

    def place_order(self, symbol: str, side: str, quantity: int,
                    order_type: str = "MARKET") -> dict:
        """Fill a market order immediately at the current price.

        BUY is rejected if cash is short; SELL is rejected if you don't hold
        enough — a real exchange rejects these too, so the simulation should.
        """
        side = side.upper()
        if quantity <= 0:
            raise ValueError("quantity must be a positive integer")

        price = self.get_ltp(symbol)
        cost = price * quantity * self.cost_pct

        if side == "BUY":
            cash_needed = price * quantity + cost
            if cash_needed > self.cash:
                return self._rejected(symbol, side, quantity, "insufficient cash")
            self.cash -= cash_needed
            self._add_position(symbol, quantity, price)
        elif side == "SELL":
            held = self.positions.get(symbol, {}).get("quantity", 0)
            if quantity > held:
                return self._rejected(symbol, side, quantity, f"only {held} held")
            self.cash += price * quantity - cost
            self._reduce_position(symbol, quantity, price)
        else:
            raise ValueError("side must be 'BUY' or 'SELL'")

        self.trades.append(Trade(
            datetime.now().isoformat(timespec="seconds"),
            symbol, side, quantity, price, round(cost, 2)))
        return {"status": "COMPLETE", "order_id": f"PAPER-{len(self.trades):04d}",
                "symbol": symbol, "side": side, "quantity": quantity,
                "price": price, "cost": round(cost, 2)}

    @staticmethod
    def _rejected(symbol: str, side: str, quantity: int, reason: str) -> dict:
        return {"status": "REJECTED", "symbol": symbol, "side": side,
                "quantity": quantity, "reason": reason}

    def _add_position(self, symbol: str, quantity: int, price: float) -> None:
        """Add shares, updating the volume-weighted average cost."""
        pos = self.positions.setdefault(symbol, {"quantity": 0, "avg_price": 0.0})
        invested = pos["avg_price"] * pos["quantity"] + price * quantity
        pos["quantity"] += quantity
        pos["avg_price"] = invested / pos["quantity"]

    def _reduce_position(self, symbol: str, quantity: int, price: float) -> None:
        """Remove shares, booking realised P&L against the average cost."""
        pos = self.positions[symbol]
        self.realised_pnl += (price - pos["avg_price"]) * quantity
        pos["quantity"] -= quantity
        if pos["quantity"] == 0:
            del self.positions[symbol]

    # ── Reporting ────────────────────────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        """Open positions, each marked to the current market price."""
        out = []
        for symbol, pos in self.positions.items():
            ltp = self.get_ltp(symbol)
            out.append({
                "symbol": symbol,
                "quantity": pos["quantity"],
                "avg_price": round(pos["avg_price"], 2),
                "ltp": ltp,
                "unrealised_pnl": round((ltp - pos["avg_price"]) * pos["quantity"], 2),
            })
        return out

    def portfolio_value(self) -> float:
        """Cash plus the marked-to-market value of every holding."""
        holdings = sum(self.get_ltp(s) * p["quantity"]
                       for s, p in self.positions.items())
        return round(self.cash + holdings, 2)

    def summary(self) -> dict:
        """One-line snapshot of the simulated account."""
        value = self.portfolio_value()
        return {
            "cash": round(self.cash, 2),
            "open_positions": len(self.positions),
            "portfolio_value": value,
            "realised_pnl": round(self.realised_pnl, 2),
            "total_return_%": round((value / self.starting_cash - 1) * 100, 2),
            "trades": len(self.trades),
        }


# ── Demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    broker = PaperBroker(starting_cash=500_000)
    print("[PAPER] starting cash: 5,00,000\n")

    for symbol, side, qty in [("RELIANCE.NS", "BUY", 10),
                              ("TCS.NS", "BUY", 5),
                              ("RELIANCE.NS", "SELL", 4)]:
        result = broker.place_order(symbol, side, qty)
        print(f"  {side:4s} {qty:3d} {symbol:14s} -> {result['status']}"
              + (f" @ {result['price']}" if result["status"] == "COMPLETE"
                 else f" ({result['reason']})"))

    print("\n  Positions:")
    for pos in broker.get_positions():
        print(f"    {pos['symbol']:14s} qty={pos['quantity']:3d} "
              f"avg={pos['avg_price']:>10,.2f} ltp={pos['ltp']:>10,.2f} "
              f"uPnL={pos['unrealised_pnl']:>+10,.2f}")

    print(f"\n  Account: {broker.summary()}")
