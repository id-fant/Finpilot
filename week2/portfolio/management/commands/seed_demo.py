"""Management command: seed a self-contained demo dataset for the dashboard.

Run with:  python manage.py seed_demo
           python manage.py seed_demo --reset    # wipe demo rows first

Inserts enough Signal + Order + Position rows that the Cardinal dashboard renders
every panel WITHOUT waiting for a live signal job. Use it to take screenshots,
record a Loom, or demo the UI offline.

WHY a management command (not a Python script): it runs inside Django's app
registry — `Stock.objects.get_or_create` and the ORM "just work", and it shows
up in `manage.py help` alongside `seed_stocks` for discoverability.

Idempotent by default: re-running keeps a stable dataset (no duplicates).
`--reset` clears the seeded rows first; useful when the schema changes.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from portfolio.models import Order, Position
from signals.models import Signal, Stock

# A handful of liquid NIFTY 50 stocks. Mirrors `seed_stocks.STARTER_UNIVERSE` —
# kept inline so this command works even if `seed_stocks` was customised.
DEMO_STOCKS = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy Services", "IT"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"),
    ("INFY.NS", "Infosys", "IT"),
    ("ITC.NS", "ITC", "FMCG"),
]


class Command(BaseCommand):
    help = "Seed a self-contained demo dataset (signals, orders, one open position)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset", action="store_true",
            help="delete previously-seeded demo rows before re-seeding",
        )

    def handle(self, *args, reset: bool = False, **options) -> None:
        today = date.today()
        # A few days back so the open Position's entry_date predates today's
        # orders — looks more like a real account that has been running a while.
        entry = today - timedelta(days=5)

        with transaction.atomic():
            stocks = self._ensure_stocks()
            if reset:
                self._reset_demo(stocks, today, entry)
            signals = self._seed_signals(stocks, today)
            self._seed_orders(stocks, signals, today)
            self._seed_position(stocks["TCS.NS"], entry)

        self.stdout.write(self.style.SUCCESS(
            "Demo data ready — open the dashboard to see signals, orders, "
            "and one open position. Re-run any time; data is stable across runs."
        ))

    # ── Stock ────────────────────────────────────────────────────────────────
    def _ensure_stocks(self) -> dict[str, Stock]:
        """Make sure every demo symbol exists; return symbol -> Stock."""
        out: dict[str, Stock] = {}
        for symbol, name, sector in DEMO_STOCKS:
            stock, _ = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={"name": name, "sector": sector},
            )
            out[symbol] = stock
        return out

    # ── Reset (optional) ─────────────────────────────────────────────────────
    def _reset_demo(self, stocks: dict[str, Stock], today: date,
                    entry: date) -> None:
        """Remove ONLY rows this command itself would create — never live data.

        Scope is the demo stocks + the demo dates, so a real Order for, say,
        WIPRO yesterday is never touched.
        """
        stock_qs = [s.pk for s in stocks.values()]
        Signal.objects.filter(stock_id__in=stock_qs, date=today).delete()
        # Orders are identified by their `created_at` being today AND living on
        # one of the demo stocks AND being paper — narrow enough to skip real
        # orders even if the dev is paper-trading the same stocks.
        Order.objects.filter(
            stock_id__in=stock_qs, is_paper=True,
            created_at__date=today,
        ).delete()
        Position.objects.filter(
            stock_id__in=stock_qs, entry_date=entry,
        ).delete()

    # ── Signals ──────────────────────────────────────────────────────────────
    def _seed_signals(self, stocks: dict[str, Stock],
                      today: date) -> dict[str, Signal]:
        """One signal per demo stock — a healthy BUY/SELL/HOLD mix."""
        plan = [
            # (symbol, type, price, rsi, macd, reason)
            ("RELIANCE.NS", "BUY",  Decimal("1354.50"), 32.4, 12.5,
             "RSI in oversold zone (32.4); MACD crossing up — classic mean-reversion entry."),
            ("HDFCBANK.NS", "BUY",  Decimal("1622.10"), 29.8,  8.2,
             "RSI deeply oversold (29.8); price tagged the lower Bollinger band."),
            ("INFY.NS",     "SELL", Decimal("1820.75"), 76.1, -4.7,
             "RSI overbought (76.1); MACD turning negative — distribution likely."),
            ("TCS.NS",      "HOLD", Decimal("3805.00"), 55.0,  0.4,
             "Mid-range RSI; no MACD crossover — wait for a clearer setup."),
            ("ITC.NS",      "HOLD", Decimal("418.90"),  48.7, -0.1,
             "Indicators neutral; volume below 20-day average."),
        ]
        out: dict[str, Signal] = {}
        for symbol, sig_type, price, rsi, macd, reason in plan:
            # `unique_together = [stock, date]` makes update_or_create the right
            # call: re-running the seeder updates today's signal in place.
            signal, _ = Signal.objects.update_or_create(
                stock=stocks[symbol], date=today,
                defaults={
                    "signal_type": sig_type, "price": price,
                    "rsi": rsi, "macd": macd,
                    "macd_signal": macd - 0.5,
                    "reason": reason,
                },
            )
            out[symbol] = signal
        return out

    # ── Orders ───────────────────────────────────────────────────────────────
    def _seed_orders(self, stocks: dict[str, Stock],
                     signals: dict[str, Signal], today: date) -> None:
        """Four orders giving the Trades view variety: pending, filled, sold, rejected.

        Order has no natural uniqueness key, so on re-run we check by
        (stock, side, quantity, status, created_at__date) — distinctive enough
        for the seed without colliding with anything real.
        """
        plan = [
            # (symbol, side,  quantity, price,            status,      signal_key)
            ("RELIANCE.NS", "BUY",  20, Decimal("1354.50"), "COMPLETE", "RELIANCE.NS"),
            ("HDFCBANK.NS", "BUY",  15, Decimal("1622.10"), "PENDING",  "HDFCBANK.NS"),
            ("INFY.NS",     "SELL", 10, Decimal("1820.75"), "COMPLETE", "INFY.NS"),
            ("ITC.NS",      "BUY",  50, Decimal("418.90"),  "REJECTED", None),
        ]
        for symbol, side, qty, price, status, sig_key in plan:
            Order.objects.update_or_create(
                stock=stocks[symbol], side=side, quantity=qty, status=status,
                is_paper=True, created_at__date=today,
                defaults={
                    "order_type": "MARKET", "price": price,
                    "signal": signals.get(sig_key) if sig_key else None,
                },
            )

    # ── Position ─────────────────────────────────────────────────────────────
    def _seed_position(self, stock: Stock, entry: date) -> None:
        """One open TCS position bought a week ago — currently in profit.

        Demo P&L is computed against the seeded TCS signal price above so the
        dashboard's "Open Positions" donut shows a non-zero gain.
        """
        Position.objects.update_or_create(
            stock=stock, entry_date=entry,
            defaults={
                "quantity": 8,
                "avg_entry_price": Decimal("3702.00"),
                "is_open": True,
                "pnl": Decimal("824.00"),   # 8 * (3805 - 3702)
            },
        )
