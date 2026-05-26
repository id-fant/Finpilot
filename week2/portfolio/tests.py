"""Integration tests for portfolio: seed_demo + Order serializer.

These use the test database (pytest-django provides `db` and `transactional_db`
fixtures). They run inside Django so the ORM + management commands are real
— this is the slim integration layer above the pure-function engine tests.
"""
from __future__ import annotations

import pytest
from django.core.management import call_command

from portfolio.models import Order, Position
from signals.models import Signal


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
