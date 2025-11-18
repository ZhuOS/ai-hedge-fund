"""
Base trader interface for implementing different brokers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

from .types import (
    TradeOrder, 
    TradeResult, 
    TradeConfig, 
    AccountInfo, 
    Position,
    ActionLiteral
)


class BaseTrader(ABC):
    """Abstract base class for all trading implementations"""
    
    def __init__(self, config: TradeConfig):
        """Initialize trader with configuration"""
        self.config = config
        self.is_connected = False
        self.trade_history: List[TradeResult] = []
        
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the trading platform"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the trading platform"""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        pass
    
    @abstractmethod
    async def get_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        pass
    
    @abstractmethod
    async def submit_order(self, order: TradeOrder) -> TradeResult:
        """Submit a trading order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Optional[TradeResult]:
        """Get status of an existing order"""
        pass
    
    # Convenience methods that integrate with existing portfolio manager
    async def execute_trade(
        self, 
        ticker: str, 
        action: ActionLiteral, 
        quantity: int, 
        current_price: Optional[float] = None
    ) -> int:
        """
        Execute trade compatible with existing TradeExecutor interface
        
        Args:
            ticker: Stock symbol
            action: Trading action (buy, sell, short, cover, hold)
            quantity: Number of shares
            current_price: Current market price (optional)
            
        Returns:
            Actually executed quantity
        """
        if action == "hold" or quantity <= 0:
            return 0
            
        # Convert action to order
        order = self._convert_action_to_order(ticker, action, quantity, current_price)
        if not order:
            return 0
            
        # Submit order
        result = await self.submit_order(order)
        
        # Log trade
        self.trade_history.append(result)
        
        return result.filled_quantity
    
    def _convert_action_to_order(
        self, 
        ticker: str, 
        action: ActionLiteral, 
        quantity: int, 
        current_price: Optional[float]
    ) -> Optional[TradeOrder]:
        """Convert portfolio manager action to trading order"""
        from .types import TradeSide, OrderType, MarketType
        
        if action == "buy":
            side = TradeSide.BUY
        elif action == "sell":
            side = TradeSide.SELL
        elif action == "short":
            # For short selling, we need to sell shares we don't own
            side = TradeSide.SELL
        elif action == "cover":
            # Covering short position means buying back
            side = TradeSide.BUY
        else:
            return None
            
        # Determine market based on symbol
        market = self._detect_market(ticker)
        
        return TradeOrder(
            symbol=ticker,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,  # Default to market order for simplicity
            market=market,
            price=current_price if current_price else None
        )
    
    def _detect_market(self, symbol: str) -> MarketType:
        """Detect market based on symbol format"""
        if symbol.isdigit() and len(symbol) == 5:
            return MarketType.HK  # Hong Kong stocks (e.g., 00700)
        elif symbol.isdigit() and len(symbol) == 6:
            return MarketType.CN  # China A-shares
        else:
            return MarketType.US  # Default to US market
    
    async def validate_trade(self, order: TradeOrder) -> tuple[bool, str]:
        """
        Validate trade before submission
        
        Returns:
            (is_valid, error_message)
        """
        # Check connection
        if not self.is_connected:
            return False, "Not connected to trading platform"
        
        # Check dry run mode
        if self.config.dry_run:
            return True, "Dry run mode - trade will be simulated"
        
        # Check account info
        account = await self.get_account_info()
        if not account:
            return False, "Unable to get account information"
        
        # Check buying power for buy orders
        if order.side.value == "BUY":
            estimated_cost = order.quantity * (order.price or await self.get_market_price(order.symbol) or 0)
            if estimated_cost > account["buying_power"]:
                return False, f"Insufficient buying power. Required: {estimated_cost}, Available: {account['buying_power']}"
        
        # Check position for sell orders
        if order.side.value == "SELL":
            positions = await self.get_positions()
            position = next((p for p in positions if p["symbol"] == order.symbol), None)
            if not position or position["quantity"] < order.quantity:
                if not self.config.enable_short_selling:
                    return False, f"Insufficient shares to sell. Required: {order.quantity}, Available: {position['quantity'] if position else 0}"
        
        # Check risk limits
        estimated_value = order.quantity * (order.price or await self.get_market_price(order.symbol) or 0)
        if estimated_value > self.config.max_order_value:
            return False, f"Order value exceeds limit. Value: {estimated_value}, Limit: {self.config.max_order_value}"
        
        return True, "Trade validation passed"
    
    def get_trade_summary(self) -> Dict:
        """Get summary of trading activity"""
        if not self.trade_history:
            return {"total_trades": 0, "successful_trades": 0, "failed_trades": 0}
        
        successful = len([t for t in self.trade_history if t.status.value in ["FILLED", "PARTIALLY_FILLED"]])
        failed = len([t for t in self.trade_history if t.status.value in ["REJECTED", "FAILED", "CANCELLED"]])
        
        return {
            "total_trades": len(self.trade_history),
            "successful_trades": successful,
            "failed_trades": failed,
            "success_rate": successful / len(self.trade_history) if self.trade_history else 0
        }