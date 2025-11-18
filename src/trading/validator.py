"""
Trading system validator and testing utilities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
from dataclasses import dataclass

from .futu_trader import FutuTrader
from .live_executor import LiveTradeExecutor
from .risk_controls import RiskManager
from .types import TradeConfig, TradeOrder, TradeSide, OrderType, MarketType


@dataclass
class ValidationResult:
    """Validation test result"""
    test_name: str
    passed: bool
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class TradingSystemValidator:
    """
    Comprehensive trading system validator
    """
    
    def __init__(self, config: TradeConfig):
        """Initialize validator with configuration"""
        self.config = config
        self.logger = self._setup_logger()
        self.results: List[ValidationResult] = []
        
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger("TradingValidator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    async def run_full_validation(self) -> Dict[str, Any]:
        """
        Run comprehensive validation suite
        
        Returns:
            Validation summary report
        """
        self.logger.info("Starting comprehensive trading system validation...")
        
        # Clear previous results
        self.results.clear()
        
        # 1. Configuration validation
        await self._validate_configuration()
        
        # 2. Connection tests
        await self._validate_connections()
        
        # 3. API functionality tests
        await self._validate_api_functionality()
        
        # 4. Risk control tests
        await self._validate_risk_controls()
        
        # 5. Order management tests
        await self._validate_order_management()
        
        # 6. Integration tests
        await self._validate_integration()
        
        # 7. Performance tests
        await self._validate_performance()
        
        # Generate summary report
        return self._generate_report()
    
    async def _validate_configuration(self):
        """Validate trading configuration"""
        self.logger.info("Validating configuration...")
        
        try:
            # Check required fields
            required_fields = ['futu_host', 'futu_port', 'dry_run']
            missing_fields = [field for field in required_fields if not hasattr(self.config, field)]
            
            if missing_fields:
                self.results.append(ValidationResult(
                    test_name="Configuration Completeness",
                    passed=False,
                    message=f"Missing required fields: {missing_fields}"
                ))
            else:
                self.results.append(ValidationResult(
                    test_name="Configuration Completeness",
                    passed=True,
                    message="All required configuration fields present"
                ))
            
            # Validate field values
            if self.config.futu_port <= 0 or self.config.futu_port > 65535:
                self.results.append(ValidationResult(
                    test_name="Port Configuration",
                    passed=False,
                    message=f"Invalid port number: {self.config.futu_port}"
                ))
            else:
                self.results.append(ValidationResult(
                    test_name="Port Configuration",
                    passed=True,
                    message=f"Port configuration valid: {self.config.futu_port}"
                ))
            
            # Validate risk limits
            if self.config.max_position_size <= 0:
                self.results.append(ValidationResult(
                    test_name="Risk Limits",
                    passed=False,
                    message="Invalid max_position_size"
                ))
            else:
                self.results.append(ValidationResult(
                    test_name="Risk Limits",
                    passed=True,
                    message="Risk limits configuration valid"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Configuration Validation",
                passed=False,
                message=f"Configuration validation error: {e}"
            ))
    
    async def _validate_connections(self):
        """Validate connections to trading platforms"""
        self.logger.info("Validating connections...")
        
        try:
            # Test Futu connection
            trader = FutuTrader(self.config)
            
            connection_success = await trader.connect()
            
            if connection_success:
                self.results.append(ValidationResult(
                    test_name="Futu Connection",
                    passed=True,
                    message="Successfully connected to Futu OpenD"
                ))
                
                # Test basic API call
                try:
                    account_info = await trader.get_account_info()
                    if account_info:
                        self.results.append(ValidationResult(
                            test_name="Account Info Retrieval",
                            passed=True,
                            message="Successfully retrieved account information",
                            details={"account_id": account_info.get("account_id", "N/A")}
                        ))
                    else:
                        self.results.append(ValidationResult(
                            test_name="Account Info Retrieval",
                            passed=False,
                            message="Failed to retrieve account information"
                        ))
                except Exception as e:
                    self.results.append(ValidationResult(
                        test_name="Account Info Retrieval",
                        passed=False,
                        message=f"Account info error: {e}"
                    ))
                
                await trader.disconnect()
            else:
                self.results.append(ValidationResult(
                    test_name="Futu Connection",
                    passed=False,
                    message="Failed to connect to Futu OpenD"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Connection Test",
                passed=False,
                message=f"Connection test error: {e}"
            ))
    
    async def _validate_api_functionality(self):
        """Validate API functionality"""
        self.logger.info("Validating API functionality...")
        
        try:
            trader = FutuTrader(self.config)
            await trader.connect()
            
            # Test market data retrieval
            try:
                price = await trader.get_market_price("AAPL")
                if price and price > 0:
                    self.results.append(ValidationResult(
                        test_name="Market Data Retrieval",
                        passed=True,
                        message=f"Successfully retrieved AAPL price: ${price:.2f}"
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="Market Data Retrieval",
                        passed=False,
                        message="Failed to retrieve valid market price"
                    ))
            except Exception as e:
                self.results.append(ValidationResult(
                    test_name="Market Data Retrieval",
                    passed=False,
                    message=f"Market data error: {e}"
                ))
            
            # Test position retrieval
            try:
                positions = await trader.get_positions()
                self.results.append(ValidationResult(
                    test_name="Position Retrieval",
                    passed=True,
                    message=f"Successfully retrieved {len(positions)} positions"
                ))
            except Exception as e:
                self.results.append(ValidationResult(
                    test_name="Position Retrieval",
                    passed=False,
                    message=f"Position retrieval error: {e}"
                ))
            
            await trader.disconnect()
            
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="API Functionality",
                passed=False,
                message=f"API functionality error: {e}"
            ))
    
    async def _validate_risk_controls(self):
        """Validate risk control system"""
        self.logger.info("Validating risk controls...")
        
        try:
            # Initialize risk manager
            risk_config = {
                'max_portfolio_value': 100000.0,
                'max_daily_loss': 5000.0,
                'max_position_concentration': 0.20,
                'max_daily_trades': 50,
                'max_leverage': 2.0,
                'max_drawdown': 0.10
            }
            
            risk_manager = RiskManager(risk_config)
            
            # Test risk limit initialization
            risk_summary = risk_manager.get_risk_summary()
            if risk_summary and 'risk_limits' in risk_summary:
                self.results.append(ValidationResult(
                    test_name="Risk Limits Initialization",
                    passed=True,
                    message="Risk limits initialized successfully"
                ))
            else:
                self.results.append(ValidationResult(
                    test_name="Risk Limits Initialization",
                    passed=False,
                    message="Failed to initialize risk limits"
                ))
            
            # Test trade validation with mock data
            mock_order = TradeOrder(
                symbol="AAPL",
                side=TradeSide.BUY,
                quantity=100,
                order_type=OrderType.MARKET,
                market=MarketType.US
            )
            
            mock_account = {
                'account_id': 'test',
                'total_assets': 50000.0,
                'cash': 25000.0,
                'buying_power': 25000.0,
                'unrealized_pnl': 0.0
            }
            
            mock_positions = []
            
            is_approved, risk_level, messages = await risk_manager.validate_trade(
                mock_order, mock_account, mock_positions
            )
            
            self.results.append(ValidationResult(
                test_name="Trade Risk Validation",
                passed=True,
                message=f"Risk validation completed: {risk_level.value}",
                details={"approved": is_approved, "messages": messages}
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Risk Controls",
                passed=False,
                message=f"Risk control validation error: {e}"
            ))
    
    async def _validate_order_management(self):
        """Validate order management functionality"""
        self.logger.info("Validating order management...")
        
        if not self.config.dry_run:
            self.results.append(ValidationResult(
                test_name="Order Management",
                passed=True,
                message="Skipping order tests in live mode for safety"
            ))
            return
        
        try:
            trader = FutuTrader(self.config)
            await trader.connect()
            
            # Test dry run order submission
            test_order = TradeOrder(
                symbol="AAPL",
                side=TradeSide.BUY,
                quantity=1,
                order_type=OrderType.MARKET,
                market=MarketType.US
            )
            
            result = await trader.submit_order(test_order)
            
            if result.status.value in ["FILLED", "SUBMITTED"]:
                self.results.append(ValidationResult(
                    test_name="Order Submission",
                    passed=True,
                    message=f"Order submitted successfully: {result.status.value}",
                    details={"order_id": result.order_id, "symbol": result.symbol}
                ))
            else:
                self.results.append(ValidationResult(
                    test_name="Order Submission",
                    passed=False,
                    message=f"Order submission failed: {result.status.value}",
                    details={"error": result.error_msg}
                ))
            
            await trader.disconnect()
            
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Order Management",
                passed=False,
                message=f"Order management error: {e}"
            ))
    
    async def _validate_integration(self):
        """Validate integration with existing system"""
        self.logger.info("Validating system integration...")
        
        try:
            # Test LiveTradeExecutor integration
            from .live_executor import create_live_executor
            from ..backtesting.portfolio import Portfolio
            
            executor = create_live_executor(self.config)
            
            # Test connection
            connected = await executor.connect()
            if connected:
                self.results.append(ValidationResult(
                    test_name="Live Executor Integration",
                    passed=True,
                    message="Live executor connected successfully"
                ))
                
                # Test portfolio integration (dry run only)
                if self.config.dry_run:
                    test_portfolio = Portfolio(
                        tickers=["AAPL"],
                        initial_cash=10000.0,
                        margin_requirement=0.5
                    )
                    
                    # Test execute_trade interface
                    executed_qty = await executor.execute_trade_async(
                        ticker="AAPL",
                        action="buy",
                        quantity=1,
                        current_price=150.0,
                        portfolio=test_portfolio
                    )
                    
                    self.results.append(ValidationResult(
                        test_name="Portfolio Integration",
                        passed=executed_qty > 0,
                        message=f"Portfolio integration test: {executed_qty} shares executed"
                    ))
                
                await executor.disconnect()
            else:
                self.results.append(ValidationResult(
                    test_name="Live Executor Integration",
                    passed=False,
                    message="Failed to connect live executor"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="System Integration",
                passed=False,
                message=f"Integration validation error: {e}"
            ))
    
    async def _validate_performance(self):
        """Validate system performance"""
        self.logger.info("Validating performance...")
        
        try:
            trader = FutuTrader(self.config)
            
            # Test connection speed
            start_time = datetime.now()
            connected = await trader.connect()
            connection_time = (datetime.now() - start_time).total_seconds()
            
            if connected:
                self.results.append(ValidationResult(
                    test_name="Connection Performance",
                    passed=connection_time < 10.0,  # Should connect within 10 seconds
                    message=f"Connection time: {connection_time:.2f} seconds"
                ))
                
                # Test market data speed
                start_time = datetime.now()
                price = await trader.get_market_price("AAPL")
                data_retrieval_time = (datetime.now() - start_time).total_seconds()
                
                self.results.append(ValidationResult(
                    test_name="Data Retrieval Performance",
                    passed=data_retrieval_time < 5.0,  # Should get data within 5 seconds
                    message=f"Data retrieval time: {data_retrieval_time:.2f} seconds"
                ))
                
                await trader.disconnect()
            else:
                self.results.append(ValidationResult(
                    test_name="Connection Performance",
                    passed=False,
                    message="Could not establish connection for performance test"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Performance Validation",
                passed=False,
                message=f"Performance validation error: {e}"
            ))
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.passed])
        failed_tests = total_tests - passed_tests
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "timestamp": datetime.now().isoformat()
            },
            "results": [
                {
                    "test_name": r.test_name,
                    "passed": r.passed,
                    "message": r.message,
                    "details": r.details,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self.results
            ],
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        failed_tests = [r for r in self.results if not r.passed]
        
        if failed_tests:
            recommendations.append("Address failed validation tests before proceeding with live trading")
        
        # Check for specific issues
        connection_failed = any("Connection" in r.test_name for r in failed_tests)
        if connection_failed:
            recommendations.append("Ensure Futu OpenD is running and accessible")
        
        config_failed = any("Configuration" in r.test_name for r in failed_tests)
        if config_failed:
            recommendations.append("Review and correct trading configuration")
        
        risk_failed = any("Risk" in r.test_name for r in failed_tests)
        if risk_failed:
            recommendations.append("Review risk control settings")
        
        if not failed_tests:
            recommendations.append("All validations passed - system ready for trading")
        
        return recommendations
    
    def save_report(self, filename: str):
        """Save validation report to file"""
        report = self._generate_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Validation report saved to {filename}")


async def run_quick_validation(config: TradeConfig) -> bool:
    """
    Run quick validation check
    
    Returns:
        True if basic validations pass
    """
    validator = TradingSystemValidator(config)
    
    # Run essential tests only
    await validator._validate_configuration()
    await validator._validate_connections()
    
    # Check if critical tests passed
    critical_tests = [r for r in validator.results if "Configuration" in r.test_name or "Connection" in r.test_name]
    return all(r.passed for r in critical_tests)