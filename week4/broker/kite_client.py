"""Week 4 — Zerodha Kite Connect client (the LIVE broker).

A thin wrapper over Zerodha's Kite Connect REST API (the `kiteconnect` SDK).
Orders placed here hit the real exchange with real money — FinPilot defaults to
`PaperBroker`, and you opt into this class explicitly.

It mirrors `PaperBroker`'s interface (get_ltp / place_order / get_positions) so
`OrderManager` works with either, unchanged.

Login flow (Kite re-authenticates once per trading day):
  1. KiteConnect(api_key).login_url()  -> user logs in via a browser.
  2. Zerodha redirects back with a short-lived `request_token`.
  3. generate_access_token(...) exchanges it for an `access_token`, valid
     until the next morning. Cache that token (e.g. in the environment).

Credentials come from environment variables — NEVER hard-code them:
  KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN
"""
from __future__ import annotations

import os
from typing import Any

# kiteconnect is optional. `Any`-typed so the use sites below are not flagged
# on `KiteConnect = None` after ImportError — see week3/llm/__init__.py for the
# same pattern. The runtime `_HAS_KITE` guard is the real safety check.
KiteConnect: Any
try:
    from kiteconnect import KiteConnect  # pyrefly: ignore[missing-import]
    _HAS_KITE = True
except ImportError:  # SDK optional — PaperBroker needs nothing extra
    KiteConnect = None
    _HAS_KITE = False


def _to_kite_symbol(symbol: str) -> str:
    """FinPilot uses 'RELIANCE.NS'; Kite wants the bare tradingsymbol 'RELIANCE'."""
    return symbol.upper().replace(".NS", "")


class KiteClient:
    """Live Zerodha broker. Same interface as PaperBroker — they're swappable."""

    EXCHANGE = "NSE"
    PRODUCT = "CNC"  # CNC = delivery (settled holdings); MIS = intraday

    def __init__(self, api_key: str, access_token: str):
        if not _HAS_KITE:
            raise ImportError(
                "kiteconnect is not installed. Run `pip install kiteconnect`, "
                "or use PaperBroker for a zero-dependency simulation.")
        # pyrefly: ignore[not-callable] -- guarded by _HAS_KITE above
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)

    @classmethod
    def from_env(cls) -> "KiteClient":
        """Build from KITE_API_KEY / KITE_ACCESS_TOKEN environment variables."""
        api_key = os.environ.get("KITE_API_KEY")
        access_token = os.environ.get("KITE_ACCESS_TOKEN")
        if not api_key or not access_token:
            raise RuntimeError(
                "KITE_API_KEY and KITE_ACCESS_TOKEN must be set in the "
                "environment. See .env.example; never commit real keys.")
        return cls(api_key, access_token)

    @staticmethod
    def generate_access_token(api_key: str, api_secret: str,
                              request_token: str) -> str:
        """Login step 3 — swap a `request_token` (valid ~minutes) for an
        `access_token` (valid until the next morning). Run once per day."""
        if not _HAS_KITE:
            raise ImportError("kiteconnect is not installed.")
        # pyrefly: ignore[not-callable] -- guarded by _HAS_KITE above
        kite = KiteConnect(api_key=api_key)
        session = kite.generate_session(request_token, api_secret=api_secret)
        # pyrefly: ignore[bad-index] -- kiteconnect stubs mistype session as bytes; it is a dict
        return session["access_token"]

    # ── Market data ──────────────────────────────────────────────────────────

    def get_ltp(self, symbol: str) -> float:
        """Last traded price for one symbol."""
        key = f"{self.EXCHANGE}:{_to_kite_symbol(symbol)}"
        # pyrefly: ignore[bad-index] -- kiteconnect stubs mistype ltp() return as bytes; it is dict[str, dict]
        return float(self.kite.ltp(key)[key]["last_price"])

    # ── Orders ───────────────────────────────────────────────────────────────

    def place_order(self, symbol: str, side: str, quantity: int,
                    order_type: str = "MARKET") -> dict:
        """Place a market order on the live exchange.

        Returns immediately with the broker order id — exchange orders are
        asynchronous, so the fill status is fetched later via the order book.
        """
        order_id = self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR,
            exchange=self.EXCHANGE,
            tradingsymbol=_to_kite_symbol(symbol),
            transaction_type=(self.kite.TRANSACTION_TYPE_BUY if side.upper() == "BUY"
                              else self.kite.TRANSACTION_TYPE_SELL),
            quantity=quantity,
            product=self.PRODUCT,
            order_type=self.kite.ORDER_TYPE_MARKET,
        )
        return {"status": "SUBMITTED", "order_id": order_id, "symbol": symbol,
                "side": side.upper(), "quantity": quantity}

    # ── Reporting ────────────────────────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        """Today's net intraday + carry-forward positions."""
        # pyrefly: ignore[missing-attribute] -- stubs mistype positions() return as bytes; it is dict
        net: Any = self.kite.positions().get("net", [])
        return [{
            "symbol": f"{p['tradingsymbol']}.NS",
            "quantity": p["quantity"],
            "avg_price": p["average_price"],
            "ltp": p["last_price"],
            "unrealised_pnl": p["unrealised"],
        } for p in net]

    def get_holdings(self) -> list[dict]:
        """Settled, delivery holdings in the demat account."""
        holdings: Any = self.kite.holdings()  # stubs mistype as int; it is list[dict]
        return [{
            "symbol": f"{h['tradingsymbol']}.NS",
            "quantity": h["quantity"],
            "avg_price": h["average_price"],
            "ltp": h["last_price"],
            "pnl": h["pnl"],
        } for h in holdings]
