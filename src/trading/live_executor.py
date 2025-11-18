"""
Live trading executor that integrates with the existing portfolio management system.
This replaces the BacktestTradeExecutor for real trading.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from ..backtesting.portfolio import Portfolio
from ..backtesting.types import ActionLiteral, Action
from .base_trader import BaseTrader
from .futu_trader import FutuTrader
from .types import TradeConfig, TradeResult, OrderStatus


class LiveTradeExecutor:
    """
    Live trading executor that integrates with existing portfolio management.
    
    This class acts as a bridge between the AI hedge fund's decision-making system
    and real broker APIs, maintaining compatibility with the existing architecture.
    """
    
    def __init__(self, trader: BaseTrader, sync_portfolio: bool = True):
        """
        Initialize live trade executor
        
        Args:
            trader: Trading implementation (e.g., FutuTrader)
            sync_portfolio: Whether to sync portfolio state with broker
        """
        self.trader = trader
        self.sync_portfolio = sync_portfolio
        self.logger = self._setup_logger()
        
        # Trade tracking
        self.execution_history: list[TradeResult] = []
        self.failed_trades: list[dict] = []
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger("LiveTradeExecutor")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    async def connect(self) -> bool:
        """Connect to the trading platform"""
        return await self.trader.connect()
    
    async def disconnect(self) -> bool:
        """Disconnect from the trading platform"""
        return await self.trader.disconnect()
    
    def execute_trade(
        self,
        ticker: str,
        action: ActionLiteral,
        quantity: float,
        current_price: float,
        portfolio: Portfolio,
    ) -> int:
        """
        Execute trade synchronously (compatible with existing interface)
        
        This method maintains compatibility with the existing TradeExecutor interface
        while executing real trades through the broker API.
        
        Args:
            ticker: Stock symbol
            action: Trading action
            quantity: Number of shares
            current_price: Current market price
            portfolio: Portfolio object (for simulation/tracking)
            
        Returns:
            Actually executed quantity
        """
        # Convert to async and run
        return asyncio.run(self.execute_trade_async(
            ticker, action, quantity, current_price, portfolio
        ))
    
    async def execute_trade_async(
        self,
        ticker: str,
        action: ActionLiteral,
        quantity: float,
        current_price: float,
        portfolio: Portfolio,
    ) -> int:
        """
        Execute trade asynchronously
        
        Args:
            ticker: Stock symbol
            action: Trading action
            quantity: Number of shares
            current_price: Current market price
            portfolio: Portfolio object
            
        Returns:
            Actually executed quantity
        """
        if quantity is None or quantity <= 0:
            return 0
        
        if action == "hold":
            return 0
        
        self.total_trades += 1
        
        try:
            # Pre-trade validation and logging
            self.logger.info(
                f"Executing trade: {action.upper()} {quantity} {ticker} @ {current_price:.2f}"
            )
            
            # Execute trade through broker
            executed_qty = await self.trader.execute_trade(
                ticker=ticker,
                action=action,
                quantity=int(quantity),
                current_price=current_price
            )
            
            if executed_qty > 0:
                self.successful_trades += 1
                
                # Update local portfolio to maintain consistency
                self._update_local_portfolio(
                    portfolio, ticker, action, executed_qty, current_price
                )
                
                self.logger.info(
                    f"Trade executed successfully: {executed_qty} shares of {ticker}"
                )
            else:
                self.logger.warning(
                    f"Trade failed or partially failed: {ticker} {action} {quantity}"
                )
                
                # Log failed trade
                self.failed_trades.append({
                    "timestamp": datetime.now(),
                    "ticker": ticker,
                    "action": action,
                    "requested_qty": quantity,
                    "executed_qty": executed_qty,
                    "price": current_price
                })
            
            return executed_qty
            
        except Exception as e:
            self.logger.error(f"Error executing trade {ticker} {action}: {e}")
            
            # Log failed trade
            self.failed_trades.append({
                "timestamp": datetime.now(),
                "ticker": ticker,
                "action": action,
                "requested_qty": quantity,
                "executed_qty": 0,
                "price": current_price,
                "error": str(e)
            })
            
            return 0
    
    def _update_local_portfolio(
        self,
        portfolio: Portfolio,
        ticker: str,
        action: ActionLiteral,
        quantity: int,
        price: float
    ):
        """
        Update local portfolio state to match executed trades
        
        This ensures the local portfolio tracking remains consistent
        with actual broker positions.
        """
        try:
            # Convert action to enum
            action_enum = Action(action) if not isinstance(action, Action) else action
            
            # Apply the same logic as the original TradeExecutor
            if action_enum == Action.BUY:
                portfolio.apply_long_buy(ticker, quantity, price)
            elif action_enum == Action.SELL:
                portfolio.apply_long_sell(ticker, quantity, price)
            elif action_enum == Action.SHORT:
                portfolio.apply_short_open(ticker, quantity, price)
            elif action_enum == Action.COVER:
                portfolio.apply_short_cover(ticker, quantity, price)
                
        except Exception as e:
            self.logger.error(f"Error updating local portfolio: {e}")
    
    async def get_account_summary(self) -> Dict[str, Any]:
        """Get comprehensive account summary"""
        try:
            account_info = await self.trader.get_account_info()
            positions = await self.trader.get_positions()
            trade_summary = self.trader.get_trade_summary()
            
            return {
                "account_info": account_info,
                "positions": positions,
                "trade_summary": trade_summary,
                "execution_stats": {
                    "total_trades": self.total_trades,
                    "successful_trades": self.successful_trades,
                    "failed_trades": len(self.failed_trades),
                    "success_rate": self.successful_trades / max(1, self.total_trades)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account summary: {e}")
            return {}
    
    async def validate_trading_session(self) -> tuple[bool, str]:
        """
        Validate that the trading session is ready
        
        Returns:
            (is_ready, message)
        """
        try:
            if not self.trader.is_connected:
                return False, "Not connected to trading platform"
            
            account_info = await self.trader.get_account_info()
            if not account_info:
                return False, "Unable to get account information"
            
            if account_info["buying_power"] <= 0:
                return False, "No buying power available"
            
            return True, "Trading session is ready"
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def get_execution_report(self) -> Dict[str, Any]:
        """Generate execution report"""
        total_executed_value = 0
        total_commission = 0
        
        for trade in self.execution_history:
            if trade.avg_price and trade.filled_quantity:
                total_executed_value += trade.avg_price * trade.filled_quantity
                total_commission += trade.commission or 0
        
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": len(self.failed_trades),
            "success_rate": self.successful_trades / max(1, self.total_trades),
            "total_executed_value": total_executed_value,
            "total_commission": total_commission,
            "recent_failures": self.failed_trades[-10:] if self.failed_trades else []
        }


def create_live_executor(config: TradeConfig) -> LiveTradeExecutor:
    """
    Factory function to create a live trade executor
    
    Args:
        config: Trading configuration
        
    Returns:
        Configured LiveTradeExecutor
    """
    # Create Futu trader
    futu_trader = FutuTrader(config)
    
    # Create and return live executor
    return LiveTradeExecutor(futu_trader, sync_portfolio=True)