"""Integration tests for portfolio: seed_demo, Order serializer, positions.

These use the test database (pytest-django provides `db` and `transactional_db`
fixtures). They run inside Django so the ORM + management commands are real
— this is the slim integration layer above the pure-function engine tests.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from portfolio.models import (
    ActionReceipt,
    JournalEntry,
    MarketQuote,
    Order,
    Position,
)
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
def test_expected_value_gate_skips_negative_edge(monkeypatch, settings):
    from portfolio.tasks import execute_signal_orders

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings.ML_GATE = "off"
    settings.EV_GATE = "auto"
    stock = Stock.objects.create(symbol="NOEDGE.NS", name="No Edge")
    Signal.objects.create(
        stock=stock,
        date=date.today(),
        signal_type="BUY",
        price=Decimal("100.00"),
        reason="test",
        ml_prob=0.20,
    )

    summary = execute_signal_orders()
    assert summary["ev_skipped"] == 1
    assert not Order.objects.filter(stock=stock).exists()
    assert JournalEntry.objects.filter(
        symbol=stock.symbol, decision="EV_SKIP"
    ).exists()


@pytest.mark.django_db
def test_volatility_target_reduces_order_size(monkeypatch, settings):
    from broker.paper_trade import PaperBroker
    from portfolio.tasks import execute_signal_orders

    monkeypatch.setattr(PaperBroker, "get_ltp", lambda self, symbol: 100.0)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings.ML_GATE = "off"
    settings.EV_GATE = "off"
    settings.BROKER_MAX_TRADE_VALUE = 50_000
    settings.VOL_TARGET = 0.15
    stock = Stock.objects.create(symbol="HIGHVOL.NS", name="High Vol")
    Signal.objects.create(
        stock=stock,
        date=date.today(),
        signal_type="BUY",
        price=Decimal("100.00"),
        reason="test",
        annualized_vol=0.30,
    )

    summary = execute_signal_orders()
    assert summary["placed"] == 1
    assert Order.objects.get(stock=stock).quantity == 250


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
def test_projection_includes_stock_price_surface(client, monkeypatch):
    from portfolio import views

    monkeypatch.setattr(
        views,
        "_load_backtest_stats",
        lambda: {
            "SURFACE.NS": {
                "annual_return_pct": 12.0,
                "annual_sharpe": 0.8,
            }
        },
    )
    stock = Stock.objects.create(symbol="SURFACE.NS", name="Surface")
    Signal.objects.create(
        stock=stock,
        date=date.today(),
        signal_type="HOLD",
        price=Decimal("123.45"),
    )

    response = client.get(
        "/api/portfolio/projection/?symbol=SURFACE.NS&horizon_days=5&n_sims=100"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "gaussian"
    assert {item["id"] for item in body["available_methods"]} == {
        "gaussian", "gbm", "student_t", "mean_reversion",
    }
    assert body["price_scale"] == "market"
    assert body["starting_price"] == 123.45
    assert set(body["price_percentiles"]) == {
        "p05", "p25", "p50", "p75", "p95",
    }
    assert body["price_percentiles"]["p50"][0] == 123.45


@pytest.mark.parametrize(
    "method",
    ["gaussian", "gbm", "student_t", "mean_reversion"],
)
@pytest.mark.django_db
def test_projection_methods_return_ordered_finite_bands(
        client, monkeypatch, method):
    from portfolio import views

    monkeypatch.setattr(
        views,
        "_load_backtest_stats",
        lambda: {
            "MODEL.NS": {
                "annual_return_pct": 14.0,
                "annual_sharpe": 0.9,
            }
        },
    )

    response = client.get(
        f"/api/portfolio/projection/?symbol=MODEL.NS&method={method}"
        "&horizon_days=12&n_sims=250"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method"] == method
    assert body["method_label"]
    assert body["method_description"]
    assert len(body["days"]) == 13

    bands = body["percentiles"]
    for day in range(len(body["days"])):
        values = [bands[key][day] for key in ("p05", "p25", "p50", "p75", "p95")]
        assert all(math.isfinite(value) and value > 0 for value in values)
        assert values == sorted(values)


@pytest.mark.django_db
def test_projection_rejects_unknown_method(client, monkeypatch):
    from portfolio import views

    monkeypatch.setattr(
        views,
        "_load_backtest_stats",
        lambda: {
            "MODEL.NS": {
                "annual_return_pct": 14.0,
                "annual_sharpe": 0.9,
            }
        },
    )
    response = client.get(
        "/api/portfolio/projection/?symbol=MODEL.NS&method=crystal_ball"
    )
    assert response.status_code == 400
    assert set(response.json()["available_methods"]) == {
        "gaussian", "gbm", "student_t", "mean_reversion",
    }


@pytest.mark.django_db
def test_dashboard_snapshot_is_complete_and_sets_csrf_cookie(client):
    call_command("seed_demo")
    resp = client.get("/api/dashboard/snapshot/")
    assert resp.status_code == 200
    body = resp.json()
    assert set(("signals", "positions", "orders", "journal", "system")) <= set(body)
    assert body["signals"]
    assert "csrftoken" in resp.cookies


@pytest.mark.django_db
def test_compiled_frontend_index_is_served(client, settings, tmp_path):
    settings.FRONTEND_DIST = tmp_path
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>FinPilot compiled</title>", encoding="utf-8",
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"FinPilot compiled" in b"".join(resp.streaming_content)


@pytest.mark.django_db
def test_action_idempotency_key_prevents_second_launch(
        client, monkeypatch, settings):
    from portfolio import runner

    settings.DEBUG = True
    launches = []
    monkeypatch.setattr(
        runner, "launch",
        lambda name, fn: launches.append(name) or "started",
    )
    headers = {"HTTP_IDEMPOTENCY_KEY": "browser-retry-123"}
    first = client.post("/api/signals/refresh/", **headers)
    second = client.post("/api/signals/refresh/", **headers)

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert launches == ["refresh-signals"]
    assert ActionReceipt.objects.count() == 1


@pytest.mark.django_db
def test_market_ticks_persist_latest_quote():
    from portfolio.market_gateway import persist_ticks

    stock = Stock.objects.create(symbol="LIVE.NS", name="Live", sector="Test")
    assert persist_ticks(
        [{"instrument_token": 123, "last_price": 456.75}],
        {123: stock.pk},
    ) == 1
    quote = MarketQuote.objects.get(stock=stock)
    assert quote.instrument_token == 123
    assert quote.last_price == Decimal("456.75")


@pytest.mark.django_db
def test_broker_fill_update_is_exactly_once():
    from portfolio.market_gateway import reconcile_order_update

    stock = Stock.objects.create(symbol="FILL.NS", name="Fill", sector="Test")
    order = Order.objects.create(
        stock=stock, order_type="MARKET", side="BUY", quantity=5,
        price=Decimal("100"), status="PENDING", is_paper=False,
        broker_order_id="KITE-123",
    )
    update = {
        "order_id": "KITE-123", "status": "COMPLETE",
        "filled_quantity": 5, "average_price": 101.25,
    }
    assert reconcile_order_update(update)
    assert reconcile_order_update(update)
    order.refresh_from_db()
    assert order.status == "COMPLETE" and order.fill_applied
    position = Position.objects.get(stock=stock, is_open=True)
    assert position.quantity == 5
    assert position.avg_entry_price == Decimal("101.25")


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
def test_portfolio_risk_empty_book(client):
    """No open positions -> a calm 200 with open_positions=0, never an error."""
    resp = client.get("/api/portfolio/risk/")
    assert resp.status_code == 200
    assert resp.json()["open_positions"] == 0


@pytest.mark.django_db
def test_portfolio_risk_historical_simulation_invariants(client, monkeypatch):
    """The VaR math must satisfy its defining invariants on synthetic data:
    CVaR >= VaR > 0, per-position contributions sum to CVaR (component CVaR
    is linear by construction), and the book value matches qty x last close.
    No network — the price panel is monkeypatched."""
    import numpy as np
    import pandas as pd
    from portfolio import quant_views

    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=250)

    def frame(seed):
        r = np.random.default_rng(seed).normal(0.0004, 0.015, 250)
        close = 100 * np.exp(np.cumsum(r))
        return pd.DataFrame({"Close": close}, index=idx)

    panel = {"AAA.NS": frame(1), "BBB.NS": frame(2)}
    monkeypatch.setattr(quant_views, "_tracked_panel", lambda: panel)

    for sym in panel:
        stock = Stock.objects.create(symbol=sym, name=sym, sector="Test")
        Position.objects.create(stock=stock, quantity=10,
                                avg_entry_price=Decimal("100.00"),
                                entry_date=date.today())

    resp = client.get("/api/portfolio/risk/")
    assert resp.status_code == 200
    d = resp.json()

    assert d["open_positions"] == 2
    expected_book = sum(10 * float(panel[s]["Close"].iloc[-1]) for s in panel)
    assert abs(d["book_value_rs"] - expected_book) < 0.05

    # Defining property of expected shortfall: tail average >= tail cutoff.
    assert d["cvar95_rs"] >= d["var95_rs"] > 0
    assert d["var99_rs"] >= d["var95_rs"]
    assert d["worst_day_rs"] >= d["cvar95_rs"]

    # Component CVaR must sum (to rounding) to the portfolio CVaR.
    total_contrib = sum(c["cvar_contrib_rs"] for c in d["contributions"])
    assert abs(total_contrib - d["cvar95_rs"]) < 0.05, (
        f"contributions {total_contrib} != CVaR {d['cvar95_rs']}")
    assert not d["thin_history"] and d["days_used"] > 200


@pytest.mark.django_db
def test_quant_ml_model_404_when_artifact_missing(client, monkeypatch, tmp_path):
    """CI never trains the model (artifacts are git-ignored) — the endpoint
    must 404 cleanly, not 500."""
    from portfolio.quant_views import MLModelView
    monkeypatch.setattr(MLModelView, "META", tmp_path / "missing.json")
    resp = client.get("/api/quant/ml-model/")
    assert resp.status_code == 404
    assert "error" in resp.json()
