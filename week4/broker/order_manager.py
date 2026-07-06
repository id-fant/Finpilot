"""Week 4 — order manager.

The bridge between a strategy *signal* and a broker *order*. It does the three
jobs the broker clients deliberately do not:

  1. Sizing    — turn "BUY RELIANCE" into "BUY 14 RELIANCE" from a fixed rupee
                 budget per trade.
  2. Risk gate — reject orders that breach a limit: max rupees per trade, max
                 open positions, a daily order cap, and no naked short selling.
  3. Routing   — hand the approved order to whichever broker it holds
                 (PaperBroker or KiteClient — it cannot tell which).

Signals in; fills, skips or rejections out.

Run:  python order_manager.py     (a short demo against PaperBroker)
"""
from __future__ import annotations

import math
from datetime import date


class RiskRejection(Exception):
    """Raised when an order fails a risk check — caught and logged, not fatal."""


class OrderManager:
    """Sizes and risk-checks signals, then routes them to a broker."""

    def __init__(self, broker, *, max_trade_value: float = 50_000.0,
                 max_positions: int = 10, max_daily_orders: int = 20,
                 allow_short: bool = False):
        self.broker = broker
        self.max_trade_value = max_trade_value
        self.max_positions = max_positions
        self.max_daily_orders = max_daily_orders
        self.allow_short = allow_short
        self._orders_today = 0
        self._order_day = date.today()

    # ── Public API ───────────────────────────────────────────────────────────

    def execute_signal(self, signal: dict, *, budget: float | None = None) -> dict:
        """Take one strategy signal and turn it into a broker order.

        `signal` is {"symbol": "RELIANCE.NS", "action": "BUY"|"SELL"|"HOLD"}.
        `budget` optionally shrinks THIS trade's rupee budget below the
        manager-wide cap — e.g. the LLM analyst gate's "reduce" verdict runs a
        trade at half size. It can only lower the cap, never raise it: the
        risk ceiling stays with the deterministic config, not with any caller.
        Returns the broker's order result, or a SKIPPED / REJECTED record —
        never raises, so a bad signal can't halt the batch.
        """
        self._roll_daily_counter()
        symbol, action = signal["symbol"], signal["action"].upper()

        if action == "HOLD":
            return {"status": "SKIPPED", "symbol": symbol, "reason": "HOLD signal"}

        trade_budget = (min(budget, self.max_trade_value)
                        if budget is not None else self.max_trade_value)

        try:
            self._check_risk(symbol, action)
            ltp = self.broker.get_ltp(symbol)
            quantity = math.floor(trade_budget / ltp)
            if quantity < 1:
                raise RiskRejection(
                    f"{symbol} at {ltp:,.2f} exceeds the per-trade budget "
                    f"of {trade_budget:,.0f}")
            result = self.broker.place_order(symbol, action, quantity)
            if result.get("status") in ("COMPLETE", "SUBMITTED"):
                self._orders_today += 1
            return result
        except RiskRejection as e:
            return {"status": "REJECTED", "symbol": symbol, "reason": str(e)}

    def run(self, signals: list[dict]) -> list[dict]:
        """Process a batch of signals — e.g. a day's output from the engine."""
        return [self.execute_signal(s) for s in signals]

    # ── Internals ────────────────────────────────────────────────────────────

    def _roll_daily_counter(self) -> None:
        """Reset the per-day order count when the date changes."""
        if date.today() != self._order_day:
            self._order_day = date.today()
            self._orders_today = 0

    def _check_risk(self, symbol: str, action: str) -> None:
        """Raise RiskRejection if this order breaches a limit."""
        if self._orders_today >= self.max_daily_orders:
            raise RiskRejection(f"daily order cap reached ({self.max_daily_orders})")

        held = {p["symbol"] for p in self.broker.get_positions()}
        if (action == "BUY" and symbol not in held
                and len(held) >= self.max_positions):
            raise RiskRejection(f"max open positions reached ({self.max_positions})")
        if action == "SELL" and not self.allow_short and symbol not in held:
            raise RiskRejection(f"short selling disabled and {symbol} is not held")


# ── Demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:                                  # works run as a script or as a module
        from paper_trade import PaperBroker  # pyrefly: ignore[missing-import]
    except ImportError:
        from broker.paper_trade import PaperBroker

    broker = PaperBroker(starting_cash=300_000)
    manager = OrderManager(broker, max_trade_value=80_000, max_positions=3)

    # A day's signals — as the week_1/week_2 engine would emit them.
    signals = [
        {"symbol": "RELIANCE.NS", "action": "BUY"},
        {"symbol": "TCS.NS", "action": "BUY"},
        {"symbol": "INFY.NS", "action": "HOLD"},
        {"symbol": "HDFCBANK.NS", "action": "BUY"},
        {"symbol": "WIPRO.NS", "action": "BUY"},   # 4th BUY -> hits max_positions
        {"symbol": "ITC.NS", "action": "SELL"},    # not held -> rejected (no short)
    ]

    print("[ORDER MANAGER] processing the day's signals\n")
    for result in manager.run(signals):
        line = f"  {result['symbol']:14s} -> {result['status']}"
        if result["status"] in ("COMPLETE", "SUBMITTED"):
            line += f"  {result['side']} {result['quantity']}"
        else:
            line += f"  ({result['reason']})"
        print(line)

    print(f"\n  Account: {broker.summary()}")
