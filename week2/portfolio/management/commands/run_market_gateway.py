"""Run the long-lived Zerodha market-data and order-update gateway."""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from portfolio.market_gateway import persist_ticks, reconcile_order_update
from signals.models import Stock


class Command(BaseCommand):
    help = "Stream Kite quotes and order updates into FinPilot"

    def handle(self, *args, **options):
        try:
            # kiteconnect is an OPTIONAL live-trading dependency — CI and the
            # paper-broker default never install it, so pyright cannot resolve
            # the import. pyrefly covers it via `replace-imports-with-any` in
            # pyrefly.toml; the guard below is the real runtime contract.
            from kiteconnect import (  # pyright: ignore[reportMissingImports]
                KiteConnect, KiteTicker,
            )
        except ImportError as exc:
            raise CommandError("kiteconnect is not installed") from exc

        api_key = os.environ.get("KITE_API_KEY")
        access_token = os.environ.get("KITE_ACCESS_TOKEN")
        if not api_key or not access_token:
            raise CommandError(
                "KITE_API_KEY and KITE_ACCESS_TOKEN are required"
            )

        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        tracked = {
            stock.symbol.upper().replace(".NS", ""): stock.pk
            for stock in Stock.objects.all()
        }
        token_to_stock_id = {
            int(row["instrument_token"]): tracked[row["tradingsymbol"]]
            for row in kite.instruments("NSE")
            if row.get("tradingsymbol") in tracked
        }
        if not token_to_stock_id:
            raise CommandError("No tracked FinPilot stocks matched NSE instruments")

        tokens = list(token_to_stock_id)
        ticker = KiteTicker(api_key, access_token)

        def on_connect(ws, response):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Kite connected; subscribing to {len(tokens)} stocks"
                )
            )
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_LTP, tokens)

        def on_ticks(ws, ticks):
            persist_ticks(ticks, token_to_stock_id)

        def on_order_update(ws, update):
            reconcile_order_update(update)

        def on_error(ws, code, reason):
            self.stderr.write(f"Kite stream error {code}: {reason}")

        # kiteconnect's bundled stubs type callback slots as literal None;
        # runtime KiteTicker explicitly expects these function assignments.
        ticker.on_connect = on_connect  # pyright: ignore[reportAttributeAccessIssue]
        ticker.on_ticks = on_ticks  # pyright: ignore[reportAttributeAccessIssue]
        ticker.on_order_update = on_order_update  # pyright: ignore[reportAttributeAccessIssue]
        ticker.on_error = on_error  # pyright: ignore[reportAttributeAccessIssue]
        self.stdout.write("Starting Kite gateway (Ctrl+C to stop)")
        ticker.connect(threaded=False)
