"""FinPilot week 4 — broker integration.

`PaperBroker` (simulated money) and `KiteClient` (live Zerodha) expose the same
interface — get_ltp / place_order / get_positions. `OrderManager` sizes and
risk-checks strategy signals, then routes the orders to whichever broker it was
given, without knowing or caring which.
"""
from .kite_client import KiteClient
from .order_manager import OrderManager, RiskRejection
from .paper_trade import PaperBroker

__all__ = ["KiteClient", "OrderManager", "RiskRejection", "PaperBroker"]
