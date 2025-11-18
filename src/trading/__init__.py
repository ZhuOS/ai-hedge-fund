"""
Trading module for real-time execution using various brokers.
"""

from .futu_trader import FutuTrader
from .base_trader import BaseTrader
from .live_executor import create_live_executor
from .types import (
    TradeOrder,
    TradeResult,
    OrderStatus,
    OrderType,
    TradeSide,
    MarketType,
    TradeConfig,
)

__all__ = [
    "FutuTrader",
    "BaseTrader", 
    "TradeOrder",
    "TradeResult",
    "OrderStatus",
    "OrderType",
    "TradeSide",
    "MarketType",
    "TradeConfig",
]