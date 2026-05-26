"""Week 2 smoke test — proves the daily signal pipeline works end to end.

WHY this exists: the build spec says "verify before claiming success". This
script exercises the whole path — fetch OHLCV -> compute indicators ->
generate signal -> write to the database — in one process, with no Redis and
no Celery worker (it calls the task function directly, synchronously).

Two modes:
    python smoke_test.py            # live run — fetches real data via yfinance
    python smoke_test.py --offline  # synthetic price data, no network needed

WHY --offline: yfinance is unofficial and flaky — it gets rate-limited, and on
some networks a TLS-intercepting proxy blocks it entirely. --offline swaps in a
deterministic synthetic price series so the strategy + DB-write + idempotency
logic can still be verified when the network is not cooperating.

Prerequisites:
    pip install -r requirements.txt
    python manage.py migrate

Run:
    python smoke_test.py
"""
import os
import sys

import django

# WHY django.setup() before importing models: Django must load its settings and
# populate the app registry before any model class can be imported or used.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finpilot.settings")
django.setup()

from django.db.utils import OperationalError       # noqa: E402
from signals.models import Signal, Stock          # noqa: E402  (must follow setup)
from signals.tasks import generate_daily_signals  # noqa: E402

SEED = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy Services", "IT"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"),
]


def _install_synthetic_data() -> None:
    """Monkeypatch the task's `fetch_ohlcv` with a synthetic price series.

    Used by --offline mode. The series is a deterministic uptrend plus noise,
    so the run is repeatable. This isolates the test from the network: it
    exercises everything EXCEPT the live yfinance call.
    """
    import numpy as np
    import pandas as pd

    import signals.tasks  # the module whose fetch_ohlcv name we rebind

    idx = pd.date_range("2024-01-01", periods=160, freq="B")
    rng = np.random.RandomState(7)
    # pandas-stubs has no overload that takes (ndarray[float64], index=DatetimeIndex)
    # cleanly — this is a stub limitation, not a real type bug.
    close = pd.Series(  # pyrefly: ignore[no-matching-overload]
        np.linspace(100, 140, 160) + rng.randn(160) * 4, index=idx)
    df = pd.DataFrame({
        "Open": close, "High": close * 1.01, "Low": close * 0.99,
        "Close": close, "Volume": 1_000_000.0,
    }, index=idx)
    df.index.name = "Date"

    signals.tasks.fetch_ohlcv = lambda symbol, period="1y", retries=3: df


def main() -> None:
    """Seed a few stocks, run the task, and assert that signals were written."""
    offline = "--offline" in sys.argv
    if offline:
        print("[MODE] --offline: synthetic price data, no network call")
        _install_synthetic_data()
    else:
        print("[MODE] live: fetching real data via yfinance")

    # WHY this guard: if the DB has not been migrated, the very first query
    # raises a 40-line OperationalError traceback. Catch it and tell the user
    # the one command they need, instead.
    try:
        already_seeded = Stock.objects.exists()
    except OperationalError:
        sys.exit("[ERROR] Database tables not found. Run this first:\n"
                 "          python manage.py migrate")

    if not already_seeded:
        for symbol, name, sector in SEED:
            Stock.objects.create(symbol=symbol, name=name, sector=sector)
        print(f"[SEED] created {len(SEED)} stocks")

    print("[RUN] generate_daily_signals() - synchronous, no broker needed")
    summary = generate_daily_signals()
    print(f"[RESULT] {summary}")

    print("\n[SIGNALS] most recent rows in the database:")
    for signal in Signal.objects.select_related("stock").order_by("-date")[:10]:
        print(f"  {signal.stock.symbol:14s} {signal.date}  "
              f"{signal.signal_type:4s}  price={signal.price}  rsi={signal.rsi}")

    # WHY assert: a smoke test must FAIL LOUDLY if the pipeline is broken,
    # rather than print a happy message regardless.
    assert summary["written"] > 0, (
        "no signals written. In live mode this usually means yfinance could "
        "not fetch data (rate limit / offline / TLS proxy). Retry later, or "
        "run `python smoke_test.py --offline` to verify the logic without a "
        "network call."
    )
    print("\n[OK] Smoke test passed - the signal pipeline works end to end.")


if __name__ == "__main__":
    main()
