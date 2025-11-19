"""
Futu (富途) OpenAPI trading implementation - Clean version.
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import uuid

try:
    import futu as ft
except ImportError:
    ft = None

from .base_trader import BaseTrader
from .types import (
    TradeOrder,
    TradeResult,
    TradeConfig,
    AccountInfo,
    Position,
    OrderStatus,
    TradeSide,
    OrderType,
    MarketType
)


class FutuTrader(BaseTrader):
    """Futu OpenAPI trading implementation"""
    
    def __init__(self, config: TradeConfig):
        super().__init__(config)
        
        if ft is None:
            raise ImportError(
                "futu package is required for FutuTrader. "
                "Install with: pip install futu-api"
            )
        
        self.quote_ctx: Optional[ft.OpenQuoteContext] = None
        self.trade_ctx: Optional[ft.OpenHKTradeContext] = None
        self.logger = self._setup_logger()
        
        # Order tracking
        self.pending_orders: Dict[str, TradeOrder] = {}
        
    def _setup_logger(self):
        """Setup logging for the trader"""
        logger = logging.getLogger("FutuTrader")
        logger.setLevel(getattr(logging, self.config.log_level))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def connect(self) -> bool:
        """Connect to Futu OpenD"""
        try:
            # Initialize quote context for market data
            self.quote_ctx = ft.OpenQuoteContext(
                host=self.config.futu_host,
                port=self.config.futu_port
            )
            
            # Test quote connection by subscribing to a stock first
            ret, data = self.quote_ctx.subscribe(['HK.00700'], [ft.SubType.QUOTE])
            if ret != ft.RET_OK:
                self.logger.warning(f"Could not subscribe to quote data: {data}")
                # Continue anyway, connection might still work for other operations
            
            # Simple connection test - just check if context is working
            self.logger.info("Quote context initialized successfully")
            
            # Initialize trade context for HK market (more accessible)
            if not self.config.dry_run:
                try:
                    self.trade_ctx = ft.OpenHKTradeContext(
                        host=self.config.futu_host,
                        port=self.config.futu_port
                    )
                    self.logger.info("Trade context initialized for HK market")
                except Exception as e:
                    self.logger.warning(f"Could not initialize trade context: {e}")
                    # Continue anyway, as we can still do market data and dry run
            
            self.is_connected = True
            self.logger.info("Successfully connected to Futu OpenD")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to Futu: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Futu OpenD"""
        try:
            if self.quote_ctx:
                self.quote_ctx.close()
                self.quote_ctx = None
            
            if self.trade_ctx:
                self.trade_ctx.close()
                self.trade_ctx = None
            
            self.is_connected = False
            self.logger.info("Disconnected from Futu OpenD")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from Futu: {e}")
            return False
    
    async def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information"""
        if not self.is_connected:
            return None
        
        try:
            if self.config.dry_run:
                # Return mock data for dry run
                return {
                    "account_id": "DEMO_ACCOUNT",
                    "total_assets": 100000.0,
                    "cash": 50000.0,
                    "market_value": 50000.0,
                    "unrealized_pnl": 0.0,
                    "realized_pnl": 0.0,
                    "buying_power": 50000.0
                }
            
            # For real trading, implement actual Futu API calls
            if self.trade_ctx:
                try:
                    # Get account list first
                    ret, acc_list = self.trade_ctx.get_acc_list()
                    if ret != ft.RET_OK:
                        self.logger.error(f"Failed to get account list: {acc_list}")
                        return None
                    
                    # Use the first account if no specific account is configured
                    account_id = self.config.trading_account
                    if not account_id and not acc_list.empty:
                        account_id = acc_list.iloc[0]['acc_id']
                    
                    if not account_id:
                        self.logger.error("No trading account available")
                        return None
                    
                    # Get account info
                    ret, acc_info = self.trade_ctx.accinfo_query(acc_id=account_id)
                    if ret != ft.RET_OK:
                        self.logger.error(f"Failed to get account info: {acc_info}")
                        return None
                    
                    if acc_info.empty:
                        return None
                    
                    info = acc_info.iloc[0]
                    return {
                        "account_id": account_id,
                        "total_assets": float(info.get('total_assets', 0)),
                        "cash": float(info.get('cash', 0)),
                        "market_value": float(info.get('market_val', 0)),
                        "unrealized_pnl": float(info.get('unrealized_pl', 0)),
                        "realized_pnl": float(info.get('realized_pl', 0)),
                        "buying_power": float(info.get('avl_withdrawal_cash', info.get('cash', 0)))
                    }
                    
                except Exception as e:
                    self.logger.error(f"Error calling Futu API for account info: {e}")
                    return None
            
            # Fallback to demo data if trade context not available
            self.logger.warning("Trade context not available, returning demo data")
            return {
                "account_id": "DEMO_ACCOUNT",
                "total_assets": 100000.0,
                "cash": 50000.0,
                "market_value": 50000.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "buying_power": 50000.0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
    
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        if not self.is_connected:
            return []
        
        try:
            if self.config.dry_run:
                # Return empty positions for dry run
                return []
            
            # For real trading, implement actual Futu API calls
            if self.trade_ctx:
                try:
                    # Get account ID
                    account_id = self.config.trading_account
                    if not account_id:
                        ret, acc_list = self.trade_ctx.get_acc_list()
                        if ret == ft.RET_OK and not acc_list.empty:
                            account_id = acc_list.iloc[0]['acc_id']
                        else:
                            return []
                    
                    # Get positions
                    ret, positions = self.trade_ctx.position_list_query(acc_id=account_id)
                    if ret != ft.RET_OK:
                        self.logger.error(f"Failed to get positions: {positions}")
                        return []
                    
                    if positions.empty:
                        return []
                    
                    result = []
                    for _, pos in positions.iterrows():
                        result.append({
                            "symbol": pos.get('code', ''),
                            "quantity": int(pos.get('qty', 0)),
                            "avg_cost": float(pos.get('cost_price', 0)),
                            "market_value": float(pos.get('market_val', 0)),
                            "unrealized_pnl": float(pos.get('unrealized_pl', 0)),
                            "market_price": float(pos.get('cur_price', 0))
                        })
                    
                    return result
                    
                except Exception as e:
                    self.logger.error(f"Error calling Futu API for positions: {e}")
                    return []
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        if not self.is_connected or not self.quote_ctx:
            return None
        
        try:
            # Convert symbol to Futu format
            futu_symbol = self._convert_to_futu_symbol(symbol)
            
            # Subscribe to the symbol first (required for real-time data)
            ret_sub, data_sub = self.quote_ctx.subscribe([futu_symbol], [ft.SubType.QUOTE])
            if ret_sub != ft.RET_OK:
                self.logger.warning(f"Could not subscribe to {futu_symbol}: {data_sub}")
            
            # Get snapshot
            ret, snapshot = self.quote_ctx.get_stock_quote([futu_symbol])
            if ret != ft.RET_OK:
                self.logger.error(f"Failed to get quote for {symbol}: {snapshot}")
                return None
            
            if snapshot.empty:
                return None
            
            return float(snapshot.iloc[0]['last_price'])
            
        except Exception as e:
            self.logger.error(f"Error getting market price for {symbol}: {e}")
            return None
    
    async def submit_order(self, order: TradeOrder) -> TradeResult:
        """Submit a trading order"""
        order_id = str(uuid.uuid4())
        submit_time = datetime.now()
        
        # Validate trade first
        is_valid, error_msg = await self.validate_trade(order)
        if not is_valid:
            return TradeResult(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=0,
                status=OrderStatus.REJECTED,
                submit_time=submit_time,
                error_msg=error_msg
            )
        
        # Handle dry run mode
        if self.config.dry_run:
            return await self._simulate_order(order, order_id, submit_time)
        
        # Execute real trade
        try:
            if self.trade_ctx:
                # Get account ID
                account_id = self.config.trading_account
                if not account_id:
                    ret, acc_list = self.trade_ctx.get_acc_list()
                    if ret == ft.RET_OK and not acc_list.empty:
                        account_id = acc_list.iloc[0]['acc_id']
                    else:
                        return TradeResult(
                            order_id=order_id,
                            symbol=order.symbol,
                            side=order.side,
                            quantity=order.quantity,
                            filled_quantity=0,
                            status=OrderStatus.REJECTED,
                            submit_time=submit_time,
                            error_msg="No trading account available"
                        )
                
                # Convert to Futu format
                futu_symbol = self._convert_to_futu_symbol(order.symbol)
                futu_side = ft.TrdSide.BUY if order.side == TradeSide.BUY else ft.TrdSide.SELL
                futu_order_type = ft.OrderType.MARKET if order.order_type == OrderType.MARKET else ft.OrderType.NORMAL
                
                # Unlock trading if password is provided
                if self.config.trading_pwd:
                    ret, data = self.trade_ctx.unlock_trade(password=self.config.trading_pwd)
                    if ret != ft.RET_OK:
                        self.logger.error(f"Failed to unlock trading: {data}")
                        return TradeResult(
                            order_id=order_id,
                            symbol=order.symbol,
                            side=order.side,
                            quantity=order.quantity,
                            filled_quantity=0,
                            status=OrderStatus.REJECTED,
                            submit_time=submit_time,
                            error_msg="Failed to unlock trading"
                        )
                
                # Submit order
                ret, order_data = self.trade_ctx.place_order(
                    price=order.price if order.price else 0,
                    qty=order.quantity,
                    code=futu_symbol,
                    trd_side=futu_side,
                    order_type=futu_order_type,
                    acc_id=account_id
                )
                
                if ret != ft.RET_OK:
                    return TradeResult(
                        order_id=order_id,
                        symbol=order.symbol,
                        side=order.side,
                        quantity=order.quantity,
                        filled_quantity=0,
                        status=OrderStatus.REJECTED,
                        submit_time=submit_time,
                        error_msg=f"Order submission failed: {order_data}"
                    )
                
                # Get the order ID from Futu
                if not order_data.empty:
                    futu_order_id = order_data.iloc[0]['order_id']
                    
                    # Wait a bit and check order status
                    import asyncio
                    await asyncio.sleep(1)
                    
                    ret, order_status = self.trade_ctx.order_list_query(
                        order_id=futu_order_id,
                        acc_id=account_id
                    )
                    
                    if ret == ft.RET_OK and not order_status.empty:
                        status_info = order_status.iloc[0]
                        filled_qty = int(status_info.get('dealt_qty', 0))
                        avg_price = float(status_info.get('dealt_avg_price', 0))
                        
                        # Map Futu order status to our status
                        futu_status = status_info.get('order_status', '')
                        if futu_status == "FILLED_ALL":
                            status = OrderStatus.FILLED
                        elif futu_status == "FILLED_PART":
                            status = OrderStatus.PARTIALLY_FILLED
                        elif futu_status in ["CANCELLED_ALL", "CANCELLED_PART"]:
                            status = OrderStatus.CANCELLED
                        elif futu_status in ["FAILED", "DISABLED"]:
                            status = OrderStatus.FAILED
                        else:
                            status = OrderStatus.SUBMITTED
                        
                        self.logger.info(f"Order executed: {filled_qty}/{order.quantity} @ ${avg_price:.2f}")
                        
                        return TradeResult(
                            order_id=futu_order_id,
                            symbol=order.symbol,
                            side=order.side,
                            quantity=order.quantity,
                            filled_quantity=filled_qty,
                            avg_price=avg_price if avg_price > 0 else None,
                            status=status,
                            submit_time=submit_time,
                            update_time=datetime.now()
                        )
                
                # If we can't get status, return submitted status
                return TradeResult(
                    order_id=order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    filled_quantity=0,
                    status=OrderStatus.SUBMITTED,
                    submit_time=submit_time
                )
                
            else:
                return TradeResult(
                    order_id=order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    filled_quantity=0,
                    status=OrderStatus.FAILED,
                    submit_time=submit_time,
                    error_msg="Trade context not available"
                )
                
        except Exception as e:
            self.logger.error(f"Error executing real trade: {e}")
            return TradeResult(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=0,
                status=OrderStatus.FAILED,
                submit_time=submit_time,
                error_msg=str(e)
            )
    
    async def _simulate_order(self, order: TradeOrder, order_id: str, submit_time: datetime) -> TradeResult:
        """Simulate order execution in dry run mode"""
        try:
            # Get current market price for simulation
            market_price = await self.get_market_price(order.symbol)
            if not market_price:
                return TradeResult(
                    order_id=order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    filled_quantity=0,
                    status=OrderStatus.FAILED,
                    submit_time=submit_time,
                    error_msg="Unable to get market price for simulation"
                )
            
            # Simulate execution with some slippage
            slippage = 0.001  # 0.1% slippage
            if order.side == TradeSide.BUY:
                fill_price = market_price * (1 + slippage)
            else:
                fill_price = market_price * (1 - slippage)
            
            # Simulate small commission
            commission = max(1.0, order.quantity * fill_price * 0.001)  # 0.1% or $1 minimum
            
            self.logger.info(
                f"[DRY RUN] {order.side.value} {order.quantity} {order.symbol} @ {fill_price:.2f}"
            )
            
            return TradeResult(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=order.quantity,  # Assume full fill in simulation
                avg_price=fill_price,
                status=OrderStatus.FILLED,
                submit_time=submit_time,
                update_time=datetime.now(),
                commission=commission
            )
            
        except Exception as e:
            self.logger.error(f"Error simulating order: {e}")
            return TradeResult(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=0,
                status=OrderStatus.FAILED,
                submit_time=submit_time,
                error_msg=str(e)
            )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        if self.config.dry_run:
            self.logger.info(f"[DRY RUN] Cancel order {order_id}")
            return True
        
        return True
    
    async def get_order_status(self, order_id: str) -> Optional[TradeResult]:
        """Get status of an existing order"""
        if self.config.dry_run:
            # In dry run, orders are immediately filled
            return None
        
        return None
    
    def _convert_to_futu_symbol(self, symbol: str) -> str:
        """Convert symbol to Futu format"""
        # Detect market and format accordingly
        if symbol.isdigit() and len(symbol) == 5:
            # Hong Kong stock (e.g., "00700")
            return f"HK.{symbol}"
        elif symbol.isdigit() and len(symbol) == 6:
            # China A-share (e.g., "000001")
            return f"SH.{symbol}" if symbol[0] in ['6'] else f"SZ.{symbol}"
        else:
            # US stock (e.g., "AAPL")
            return f"US.{symbol}"