"""
Advanced risk controls for live trading.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .types import TradeOrder, AccountInfo, Position, TradeSide


class RiskLevel(str, Enum):
    """Risk level enumeration"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskLimit:
    """Risk limit configuration"""
    name: str
    max_value: float
    current_value: float = 0.0
    warning_threshold: float = 0.8  # 80% of max triggers warning
    enabled: bool = True
    
    def check_limit(self, additional_value: float = 0.0) -> Tuple[bool, RiskLevel, str]:
        """
        Check if adding additional_value would exceed the limit
        
        Returns:
            (is_within_limit, risk_level, message)
        """
        if not self.enabled:
            return True, RiskLevel.LOW, "Risk control disabled"
        
        total_value = self.current_value + additional_value
        utilization = total_value / self.max_value if self.max_value > 0 else 0
        
        if utilization >= 1.0:
            return False, RiskLevel.CRITICAL, f"{self.name} limit exceeded: {total_value:.2f} >= {self.max_value:.2f}"
        elif utilization >= self.warning_threshold:
            return True, RiskLevel.HIGH, f"{self.name} approaching limit: {utilization:.1%} used"
        elif utilization >= 0.5:
            return True, RiskLevel.MEDIUM, f"{self.name} moderate usage: {utilization:.1%} used"
        else:
            return True, RiskLevel.LOW, f"{self.name} within limits: {utilization:.1%} used"
    
    def update_current(self, value: float):
        """Update current value"""
        self.current_value = value


class RiskManager:
    """
    Comprehensive risk management system for live trading.
    
    Features:
    - Position size limits
    - Portfolio concentration limits
    - Maximum daily loss limits
    - Trading frequency controls
    - Drawdown protection
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize risk manager with configuration"""
        self.config = config or {}
        self.logger = self._setup_logger()
        
        # Risk limits
        self.limits = {
            "max_position_size": self.config.get("max_position_size", 100000),  # $100k per position
            "max_portfolio_value": self.config.get("max_portfolio_value", 1000000),  # $1M total
            "max_daily_loss": self.config.get("max_daily_loss", 10000),  # $10k per day
            "max_position_concentration": self.config.get("max_position_concentration", 0.2),  # 20%
            "max_trades_per_day": self.config.get("max_trades_per_day", 100),
            "min_cash_reserve": self.config.get("min_cash_reserve", 10000),  # $10k cash buffer
        }
        
        # State tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.trade_history: List[Dict] = []
        self.last_reset = datetime.now().date()
        
        # Risk events
        self.risk_events: List[Dict] = []
        self.circuit_breaker_active = False
        
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger("RiskManager")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def validate_order(
        self,
        order: TradeOrder,
        account_info: AccountInfo,
        positions: List[Position]
    ) -> Tuple[bool, str, RiskLevel]:
        """
        Validate if an order passes all risk checks
        
        Args:
            order: The order to validate
            account_info: Current account information
            positions: Current positions
            
        Returns:
            (is_valid, reason, risk_level)
        """
        # Reset daily counters if new day
        self._check_daily_reset()
        
        # Circuit breaker check
        if self.circuit_breaker_active:
            return False, "Circuit breaker active - trading halted", RiskLevel.CRITICAL
        
        # Run all risk checks
        checks = [
            self._check_position_size(order, account_info),
            self._check_cash_reserve(order, account_info),
            self._check_daily_loss(account_info),
            self._check_trading_frequency(),
            self._check_position_concentration(order, account_info, positions),
        ]
        
        # Find highest risk level and any failed checks
        max_risk_level = RiskLevel.LOW
        failed_checks = []
        
        for is_valid, risk_level, message in checks:
            if not is_valid:
                failed_checks.append(message)
                self._log_risk_event(order, message, risk_level)
            
            # Track highest risk level
            if risk_level == RiskLevel.CRITICAL:
                max_risk_level = RiskLevel.CRITICAL
            elif risk_level == RiskLevel.HIGH and max_risk_level != RiskLevel.CRITICAL:
                max_risk_level = RiskLevel.HIGH
            elif risk_level == RiskLevel.MEDIUM and max_risk_level == RiskLevel.LOW:
                max_risk_level = RiskLevel.MEDIUM
        
        # If any checks failed, reject the order
        if failed_checks:
            reason = "; ".join(failed_checks)
            self.logger.warning(f"Order validation failed: {reason}")
            return False, reason, max_risk_level
        
        # Log successful validation with risk level
        if max_risk_level != RiskLevel.LOW:
            self.logger.info(f"Order validated with {max_risk_level.value} risk level")
        
        return True, "All risk checks passed", max_risk_level
    
    def _check_position_size(
        self,
        order: TradeOrder,
        account_info: AccountInfo
    ) -> Tuple[bool, RiskLevel, str]:
        """Check if position size is within limits"""
        if order.price:
            position_value = order.quantity * order.price
        else:
            # Estimate using buying power as rough price indicator
            position_value = order.quantity * 100  # Assume $100/share if no price
        
        max_size = self.limits["max_position_size"]
        
        if position_value > max_size:
            return False, RiskLevel.CRITICAL, f"Position size ${position_value:.2f} exceeds limit ${max_size:.2f}"
        elif position_value > max_size * 0.8:
            return True, RiskLevel.HIGH, f"Position size approaching limit"
        else:
            return True, RiskLevel.LOW, "Position size OK"
    
    def _check_cash_reserve(
        self,
        order: TradeOrder,
        account_info: AccountInfo
    ) -> Tuple[bool, RiskLevel, str]:
        """Check if sufficient cash reserve will remain"""
        if order.side == TradeSide.SELL:
            return True, RiskLevel.LOW, "Sell order - increases cash"
        
        required_cash = order.quantity * (order.price or 0)
        remaining_cash = account_info.cash - required_cash
        min_reserve = self.limits["min_cash_reserve"]
        
        if remaining_cash < min_reserve:
            return False, RiskLevel.CRITICAL, f"Insufficient cash reserve: ${remaining_cash:.2f} < ${min_reserve:.2f}"
        elif remaining_cash < min_reserve * 1.5:
            return True, RiskLevel.MEDIUM, "Cash reserve low"
        else:
            return True, RiskLevel.LOW, "Cash reserve OK"
    
    def _check_daily_loss(
        self,
        account_info: AccountInfo
    ) -> Tuple[bool, RiskLevel, str]:
        """Check if daily loss limit would be exceeded"""
        max_loss = self.limits["max_daily_loss"]
        
        if self.daily_pnl < -max_loss:
            self.circuit_breaker_active = True
            return False, RiskLevel.CRITICAL, f"Daily loss limit exceeded: ${abs(self.daily_pnl):.2f}"
        elif self.daily_pnl < -max_loss * 0.8:
            return True, RiskLevel.HIGH, f"Approaching daily loss limit"
        else:
            return True, RiskLevel.LOW, "Daily P&L within limits"
    
    def _check_trading_frequency(self) -> Tuple[bool, RiskLevel, str]:
        """Check if trading frequency is within limits"""
        max_trades = self.limits["max_trades_per_day"]
        
        if self.daily_trades >= max_trades:
            return False, RiskLevel.CRITICAL, f"Daily trade limit reached: {self.daily_trades}"
        elif self.daily_trades >= max_trades * 0.9:
            return True, RiskLevel.MEDIUM, "Approaching daily trade limit"
        else:
            return True, RiskLevel.LOW, "Trading frequency OK"
    
    def _check_position_concentration(
        self,
        order: TradeOrder,
        account_info: AccountInfo,
        positions: List[Position]
    ) -> Tuple[bool, RiskLevel, str]:
        """Check if position would create excessive concentration"""
        portfolio_value = account_info.net_liquidation
        
        if portfolio_value <= 0:
            return True, RiskLevel.LOW, "No portfolio value to check"
        
        try:
            # Find current position for this symbol
            current_position = next(
                (p for p in positions if p['symbol'] == order.symbol),
                {'quantity': 0, 'market_value': 0.0}
            )
            
            # Calculate new position size
            if order.side == TradeSide.BUY:
                new_quantity = current_position['quantity'] + order.quantity
            else:
                new_quantity = current_position['quantity'] - order.quantity
            
            # Estimate new position value
            estimated_price = order.price or (current_position['market_value'] / max(current_position['quantity'], 1))
            new_position_value = abs(new_quantity * estimated_price)
            
            # Check concentration
            concentration = new_position_value / portfolio_value if portfolio_value > 0 else 0
            
            limit = self.limits['max_position_concentration']
            
            if concentration > limit:
                return False, RiskLevel.HIGH, f"Position concentration {concentration:.1%} exceeds limit {limit:.1%}"
            elif concentration > limit * 0.8:
                return True, RiskLevel.MEDIUM, f"Position concentration approaching limit"
            else:
                return True, RiskLevel.LOW, "Position concentration OK"
                
        except Exception as e:
            self.logger.error(f"Error checking position concentration: {e}")
            return True, RiskLevel.LOW, "Concentration check skipped due to error"
    
    def _check_daily_reset(self):
        """Reset daily counters if new day"""
        today = datetime.now().date()
        
        if today > self.last_reset:
            self.logger.info(f"Resetting daily counters (Previous day P&L: ${self.daily_pnl:.2f}, Trades: {self.daily_trades})")
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.circuit_breaker_active = False
            self.last_reset = today
    
    def record_trade(self, order: TradeOrder, executed_qty: int, execution_price: float):
        """Record executed trade for tracking"""
        self.daily_trades += 1
        
        trade_record = {
            "timestamp": datetime.now(),
            "symbol": order.symbol,
            "side": order.side,
            "quantity": executed_qty,
            "price": execution_price,
        }
        
        self.trade_history.append(trade_record)
    
    def update_pnl(self, pnl_change: float):
        """Update daily P&L tracking"""
        self.daily_pnl += pnl_change
        
        if self.daily_pnl < -self.limits["max_daily_loss"]:
            self.circuit_breaker_active = True
            self.logger.critical(f"Circuit breaker activated! Daily loss: ${abs(self.daily_pnl):.2f}")
    
    def _log_risk_event(self, order: TradeOrder, message: str, risk_level: RiskLevel):
        """Log a risk event"""
        event = {
            "timestamp": datetime.now(),
            "order": order,
            "message": message,
            "risk_level": risk_level,
        }
        
        self.risk_events.append(event)
        
        if risk_level == RiskLevel.CRITICAL:
            self.logger.critical(f"RISK EVENT: {message}")
        elif risk_level == RiskLevel.HIGH:
            self.logger.warning(f"RISK WARNING: {message}")
    
    def get_risk_summary(self) -> Dict:
        """Get comprehensive risk summary"""
        # Calculate total volume from trade history
        total_volume = 0.0
        for trade in self.trade_history:
            if 'quantity' in trade and 'price' in trade:
                total_volume += trade['quantity'] * trade['price']
        
        return {
            "circuit_breaker_active": self.circuit_breaker_active,
            "emergency_stop": self.circuit_breaker_active,  # Same as circuit breaker
            "circuit_breakers": [  # List of active circuit breakers
                {
                    "type": "daily_loss",
                    "active": self.circuit_breaker_active,
                    "threshold": self.limits["max_daily_loss"],
                    "current_value": abs(self.daily_pnl) if self.daily_pnl < 0 else 0
                }
            ] if self.circuit_breaker_active else [],
            "current_session": {
                "trades_count": self.daily_trades,
                "total_volume": total_volume,
                "pnl": self.daily_pnl,
                "start_time": self.last_reset.isoformat()
            },
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "limits": self.limits,
            "recent_risk_events": self.risk_events[-10:],
            "last_reset": self.last_reset.isoformat(),
        }
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker (use with caution)"""
        self.logger.warning("Circuit breaker manually reset")
        self.circuit_breaker_active = False
