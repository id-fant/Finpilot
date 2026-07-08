"""Integration tests for portfolio: seed_demo, Order serializer, positions.

These use the test database (pytest-django provides `db` and `transactional_db`
fixtures). They run inside Django so the ORM + management commands are real
— this is the slim integration layer above the pure-function engine tests.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from portfolio.models import Order, Position
from signals.models import Signal, Stock


@pytest.mark.django_db
def test_seed_demo_inserts_expected_rows():
    """seed_demo must populate ALL three tables it claims to populate."""
    call_command("seed_demo")
    # Spec: 5 signals (one per demo stock), 4 orders (one per status mix),
    # 1 open position. If this changes, update both seed_demo AND this test.
    assert Signal.objects.count() >= 5, "demo signals missing"
    assert Order.objects.count() == 4, "demo orders count mismatch"
    assert Position.objects.filter(is_open=True).count() >= 1, (
        "open position missing")


@pytest.mark.django_db
def test_seed_demo_is_idempotent():
    """Running seed_demo twice must NOT duplicate rows.

    The whole point of update_or_create with natural keys is that a re-run
    is a no-op. If this test ever fails, the seed_demo is no longer safe
    for the dashboard demo loop.
    """
    call_command("seed_demo")
    first_signal_count = Signal.objects.count()
    first_order_count = Order.objects.count()
    first_position_count = Position.objects.count()

    call_command("seed_demo")  # second run
    assert Signal.objects.count() == first_signal_count
    assert Order.objects.count() == first_order_count
    assert Position.objects.count() == first_position_count


@pytest.mark.django_db
def test_order_serializer_includes_stock_symbol():
    """The dashboard reads order.symbol, not order.stock_id — serializer must flatten."""
    from portfolio.serializers import OrderSerializer
    call_command("seed_demo")
    order = Order.objects.first()
    assert order is not None
    data = OrderSerializer(order).data
    # The Cardinal frontend expects a bare symbol string, not a nested object.
    assert "symbol" in data, f"OrderSerializer missing 'symbol' key: {data.keys()}"
    assert data["symbol"].endswith(".NS"), (
        f"symbol should be a full NSE ticker, got {data['symbol']!r}")


@pytest.mark.django_db
def test_apply_fill_tracks_position_lifecycle():
    """The Position book must follow fills: open → average up → close with P&L.

    This is the regression test for the gap found during the integrated
    orchestrator run: orders were recorded but Position rows never existed,
    so the dashboard's positions donut stayed empty forever.
    """
    from portfolio.tasks import _apply_fill_to_position
    stock = Stock.objects.create(symbol="TEST.NS", name="Test Co", sector="IT")
    today = date.today()

    # First BUY opens the position.
    _apply_fill_to_position(stock, "BUY", 10, Decimal("100.00"), today)
    pos = Position.objects.get(stock=stock, is_open=True)
    assert pos.quantity == 10
    assert pos.avg_entry_price == Decimal("100.00")

    # Second BUY folds in at the volume-weighted average.
    _apply_fill_to_position(stock, "BUY", 10, Decimal("110.00"), today)
    pos.refresh_from_db()
    assert pos.quantity == 20
    assert pos.avg_entry_price == Decimal("105.00")

    # Full SELL closes it and books realised P&L against the average entry.
    _apply_fill_to_position(stock, "SELL", 20, Decimal("115.00"), today)
    pos.refresh_from_db()
    assert not pos.is_open
    assert pos.exit_price == Decimal("115.00")
    assert pos.pnl == Decimal("200.00")  # (115 - 105) * 20


@pytest.mark.django_db
def test_execute_signal_orders_books_position_on_fill(monkeypatch):
    """A filled BUY must produce BOTH an Order row and an open Position row.

    The broker is the real PaperBroker with only its market-data call stubbed
    (same monkeypatch seam as smoke_test.py), so this exercises the entire
    production path: signal → analyst gate (skipped, no key) → OrderManager →
    fill → Order + Position persistence.
    """
    from broker.paper_trade import PaperBroker
    from portfolio.tasks import execute_signal_orders

    monkeypatch.setattr(PaperBroker, "get_ltp", lambda self, symbol: 100.0)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # gate off → fail-open

    stock = Stock.objects.create(symbol="TEST.NS", name="Test Co", sector="IT")
    Signal.objects.create(stock=stock, date=date.today(), signal_type="BUY",
                          price=Decimal("100.00"), reason="test BUY")

    summary = execute_signal_orders()
    assert summary["placed"] == 1, summary
    assert summary["vetoed"] == 0, summary

    order = Order.objects.get(stock=stock)
    assert order.status == "COMPLETE"
    pos = Position.objects.get(stock=stock, is_open=True)
    assert pos.quantity == order.quantity > 0
    assert pos.avg_entry_price == Decimal("100.00")

    # Idempotency held one layer up: a re-run must not double the book.
    summary2 = execute_signal_orders()
    assert summary2["skipped"] == 1
    assert Position.objects.filter(stock=stock).count() == 1


@pytest.mark.django_db
def test_system_endpoint_reports_full_shape(client):
    """/api/system/ is the control room — every block the dashboard reads
    must be present even on an empty database."""
    resp = client.get("/api/system/")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("broker", "gates", "data", "risk", "actions"):
        assert key in body, f"missing block: {key}"
    assert "analyst" in body["gates"] and "ml" in body["gates"]


@pytest.mark.django_db
def test_actions_denied_outside_debug_without_token(client, settings):
    """The run-now endpoints trigger real work (potentially real orders on
    BROKER=kite) — outside DEBUG they must refuse requests with no token.
    WHY this matters: a 403 here is the only thing between a public deploy
    and anyone on the internet firing trades."""
    settings.DEBUG = False
    settings.ACTIONS_TOKEN = ""  # not configured -> deny, never allow
    assert client.post("/api/signals/refresh/").status_code == 403
    assert client.post("/api/portfolio/execute-orders/").status_code == 403


@pytest.mark.django_db
def test_quant_ml_model_404_when_artifact_missing(client, monkeypatch, tmp_path):
    """CI never trains the model (artifacts are git-ignored) — the endpoint
    must 404 cleanly, not 500."""
    from portfolio.quant_views import MLModelView
    monkeypatch.setattr(MLModelView, "META", tmp_path / "missing.json")
    resp = client.get("/api/quant/ml-model/")
    assert resp.status_code == 404
    assert "error" in resp.json()
