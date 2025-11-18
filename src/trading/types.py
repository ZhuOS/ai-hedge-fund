"""
Trading types and enums for the trading module.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Optional, Literal, TypedDict
from enum import Enum
from pydantic import BaseModel, Field


class TradeSide(str, Enum):
    """Trading side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class MarketType(str, Enum):
    """Market type enumeration"""
    HK = "HK"  # Hong Kong
    US = "US"  # US Market
    CN = "CN"  # China A-Share


class TradeOrder(BaseModel):
    """Trading order model"""
    symbol: str = Field(..., description="Stock symbol (e.g., 'AAPL', '00700')")
    side: TradeSide = Field(..., description="Buy or Sell")
    quantity: int = Field(..., gt=0, description="Number of shares")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    price: Optional[float] = Field(default=None, description="Limit price (required for LIMIT orders)")
    stop_price: Optional[float] = Field(default=None, description="Stop price (for STOP orders)")
    market: MarketType = Field(default=MarketType.HK, description="Target market")
    time_in_force: str = Field(default="DAY", description="Time in force")
    
    class Config:
        use_enum_values = True


class TradeResult(BaseModel):
    """Trading result model"""
    order_id: str = Field(..., description="Unique order identifier")
    symbol: str = Field(..., description="Stock symbol")
    side: TradeSide = Field(..., description="Buy or Sell")
    quantity: int = Field(..., description="Requested quantity")
    filled_quantity: int = Field(default=0, description="Actually filled quantity")
    avg_price: Optional[float] = Field(default=None, description="Average filled price")
    status: OrderStatus = Field(..., description="Order status")
    submit_time: datetime = Field(..., description="Order submission time")
    update_time: Optional[datetime] = Field(default=None, description="Last update time")
    error_msg: Optional[str] = Field(default=None, description="Error message if failed")
    commission: Optional[float] = Field(default=0.0, description="Trading commission")
    
    class Config:
        use_enum_values = True


class TradeConfig(BaseModel):
    """Trading configuration"""
    # Futu API configuration
    futu_host: str = Field(default="127.0.0.1", description="Futu OpenD host")
    futu_port: int = Field(default=11111, description="Futu OpenD port")
    
    # Account configuration
    trading_account: Optional[str] = Field(default=None, description="Trading account ID")
    trading_pwd: Optional[str] = Field(default=None, description="Trading password")
    
    # Risk controls
    max_position_size: float = Field(default=10000.0, description="Maximum position size per stock")
    max_daily_trades: int = Field(default=100, description="Maximum trades per day")
    max_order_value: float = Field(default=50000.0, description="Maximum single order value")
    
    # Trading settings
    dry_run: bool = Field(default=True, description="Dry run mode (paper trading)")
    enable_short_selling: bool = Field(default=False, description="Enable short selling")
    default_market: MarketType = Field(default=MarketType.HK, description="Default market")
    
    # Logging
    log_trades: bool = Field(default=True, description="Log all trades")
    log_level: str = Field(default="INFO", description="Logging level")


class AccountInfo(TypedDict):
    """Account information"""
    account_id: str
    total_assets: float
    cash: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    buying_power: float


class Position(TypedDict):
    """Position information"""
    symbol: str
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    market_price: float


# Type aliases for backward compatibility
ActionLiteral = Literal["buy", "sell", "short", "cover", "hold"]