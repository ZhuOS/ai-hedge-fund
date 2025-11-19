"""
Simplified live trading version of the AI hedge fund main program.

This integrates the AI decision-making system with real trading execution
through the Futu API.
"""

import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style, init

from src.main import run_hedge_fund, parse_hedge_fund_response
from src.trading.types import TradeConfig, MarketType
from src.trading.live_executor import create_live_executor
from src.trading.risk_controls import RiskManager
from src.trading.validator import run_quick_validation
from src.cli.input import parse_cli_inputs
from src.utils.display import print_trading_output

# Load environment variables
load_dotenv()
init(autoreset=True)


async def run_live_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    trading_config: TradeConfig,
    risk_config: dict,
    show_reasoning: bool = False,
    selected_analysts: list[str] = [],
    model_name: str = "gpt-4.1",
    model_provider: str = "OpenAI",
):
    """Run AI hedge fund with live trading execution"""
    
    print(f"{Fore.CYAN}🤖 AI Hedge Fund - Live Trading{Style.RESET_ALL}")
    print("=" * 40)
    
    ## 1. Initialize components
    print("🔌 Connecting...")
    executor = create_live_executor(trading_config)
    connected = await executor.connect()
    
    if not connected:
        print(f"{Fore.RED}❌ Connection failed{Style.RESET_ALL}")
        return None
    
    risk_manager = RiskManager(risk_config)
    print(f"{Fore.GREEN}✅ Connected and ready{Style.RESET_ALL}")
    
    ## 2. AI Analysis
    print("\n🧠 Running AI analysis...")
    try:
        ai_result = run_hedge_fund(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=show_reasoning,
            selected_analysts=selected_analysts,
            model_name=model_name,
            model_provider=model_provider,
        )
        
        if not ai_result or not ai_result.get('decisions'):
            print(f"{Fore.RED}❌ No AI decisions{Style.RESET_ALL}")
            await executor.disconnect()
            return None
            
        decisions = parse_hedge_fund_response(ai_result['decisions'])
        print(f"{Fore.GREEN}✅ Analysis complete{Style.RESET_ALL}")
        
        # Display decisions
        print(f"\n📊 Trading Decisions:")
        if decisions:
            for ticker, decision in decisions.items():
                action = decision.get('action', 'hold').upper()
                quantity = decision.get('quantity', 0)
                confidence = decision.get('confidence', 0)
                
                print(f"   {ticker}: {action} {quantity} shares ({confidence}%)")
                if show_reasoning:
                    print(f"      → {decision.get('reasoning', 'No reasoning')}")
        else:
            print("   No decisions generated")
        
    except Exception as e:
        print(f"{Fore.RED}❌ Analysis failed: {e}{Style.RESET_ALL}")
        await executor.disconnect()
        return None
    
    # Get account info
    account_info = await executor.trader.get_account_info()
    positions = await executor.trader.get_positions() # Get current positions
    
    if account_info:
        print(f"\n💰 Account: ${account_info['cash']:,.2f} cash, ${account_info['total_assets']:,.2f} total")
    
    ## 3. Execute trades
    print(f"\n💼 Executing trades...")
    
    execution_results = {}
    total_executed_value = 0.0
    successful_trades = 0
    
    if not decisions:
        print("   No trades to execute")
    else:
        # Create portfolio object for integration
        from src.backtesting.portfolio import Portfolio
        portfolio_obj = Portfolio(
            tickers=tickers,
            initial_cash=portfolio['cash'],
            margin_requirement=portfolio['margin_requirement']
        )
        
        for ticker, decision in decisions.items():
            action = decision.get('action', 'hold')
            quantity = decision.get('quantity', 0)
            
            if action == 'hold' or quantity <= 0:
                continue
            
            try:
                # Get current market price
                current_price = await executor.trader.get_market_price(ticker)
                if not current_price:
                    print(f"   ❌ {ticker}: No price data")
                    execution_results[ticker] = {'status': 'failed', 'reason': 'No market price'}
                    continue
                
                # Execute trade
                executed_qty = await executor.execute_trade_async(
                    ticker=ticker,
                    action=action,
                    quantity=quantity,
                    current_price=current_price,
                    portfolio=portfolio_obj
                )
                if executed_qty > 0:
                    executed_value = executed_qty * current_price
                    total_executed_value += executed_value
                    successful_trades += 1
                    
                    print(f"   ✅ {ticker}: {action} {executed_qty} @ ${current_price:.2f} (${executed_value:,.2f})")
                    
                    execution_results[ticker] = {
                        'status': 'executed',
                        'quantity': executed_qty,
                        'price': current_price,
                        'value': executed_value
                    }
                else:
                    print(f"   ❌ {ticker}: Execution failed")
                    execution_results[ticker] = {'status': 'failed', 'reason': 'Execution failed'}
                
            except Exception as e:
                print(f"   ❌ {ticker}: Error - {e}")
                execution_results[ticker] = {'status': 'error', 'reason': str(e)}
    
    ## 4. Summary
    total_decisions = len(decisions) if decisions else 0
    print(f"\n📈 Summary:")
    print(f"   Successful trades: {successful_trades}/{total_decisions}")
    print(f"   Total value: ${total_executed_value:,.2f}")
    
    # Risk status
    risk_summary = risk_manager.get_risk_summary()
    emergency_status = "🔴 ACTIVE" if risk_summary['emergency_stop'] else "🟢 INACTIVE"
    print(f"   Emergency stop: {emergency_status}")
    
    # Final account
    try:
        final_account = await executor.get_account_summary()
        if final_account.get('account_info'):
            final_info = final_account['account_info']
            print(f"   Final cash: ${final_info['cash']:,.2f}")
            print(f"   Total assets: ${final_info['total_assets']:,.2f}")
    except:
        pass
    
    # Cleanup
    await executor.disconnect()
    print(f"\n{Fore.GREEN}✅ Session completed{Style.RESET_ALL}")
    
    # Return results
    return {
        'ai_decisions': decisions,
        'execution_results': execution_results,
        'execution_summary': {
            'total_decisions': total_decisions,
            'successful_trades': successful_trades,
            'total_value': total_executed_value
        },
        'risk_summary': risk_summary,
        'final_account': final_account if 'final_account' in locals() else None
    }


def main():
    """Main entry point for live trading"""
    
    print(f"{Fore.CYAN}🚀 AI Hedge Fund - Live Trading{Style.RESET_ALL}")
    print("=" * 45)
    
    # Parse command line inputs
    inputs = parse_cli_inputs(
        description="Run AI hedge fund with live trading",
        require_tickers=True,
        default_months_back=None,
        include_graph_flag=False,
        include_reasoning_flag=True,
    )
    
    # Check for live trading environment variable
    import os
    enable_live_trading = os.getenv('ENABLE_LIVE_TRADING', 'false').lower() == 'true'
    
    # Trading configuration
    trading_config = TradeConfig(
        futu_host=os.getenv('FUTU_HOST', '127.0.0.1'),
        futu_port=int(os.getenv('FUTU_PORT', '11111')),
        trading_account=os.getenv('FUTU_ACCOUNT_ID'),
        trading_pwd=os.getenv('FUTU_TRADING_PWD'),
        dry_run=not enable_live_trading,  # Use environment variable to control
        max_position_size=float(os.getenv('MAX_POSITION_SIZE', '5000.0')),
        max_daily_trades=int(os.getenv('MAX_DAILY_TRADES', '10')),
        max_order_value=float(os.getenv('MAX_ORDER_VALUE', '10000.0')),
        enable_short_selling=os.getenv('ENABLE_SHORT_SELLING', 'false').lower() == 'true',
        log_trades=True,  # Always log for audit trail
        log_level=os.getenv('LOG_LEVEL', 'INFO')
    )
    
    # Display trading mode
    if trading_config.dry_run:
        print(f"\n{Fore.GREEN}📝 DRY RUN MODE - No real trades will be executed{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}⚠️  LIVE TRADING MODE ENABLED{Style.RESET_ALL}")
        print(f"{Fore.RED}💰 REAL MONEY WILL BE AT RISK{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Account: {trading_config.trading_account or 'Default'}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Max Position Size: ${trading_config.max_position_size:,.2f}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Max Order Value: ${trading_config.max_order_value:,.2f}{Style.RESET_ALL}")
        
        confirmation = input(f"\n{Fore.YELLOW}Type 'CONFIRM LIVE TRADING' to proceed with real money: {Style.RESET_ALL}")
        if confirmation != 'CONFIRM LIVE TRADING':
            print(f"{Fore.GREEN}✅ Cancelled for safety{Style.RESET_ALL}")
            return
    
    # Risk management configuration
    risk_config = {
        'max_portfolio_value': 50000.0, # Maximum portfolio value
        'max_daily_loss': 2000.0, # Maximum daily loss
        'max_position_concentration': 0.15, # Maximum position concentration
        'max_sector_concentration': 0.25,
        'max_daily_trades': 20, 
        'max_leverage': 1.5,
        'max_drawdown': 0.10,
    }
    
    # Construct portfolio
    portfolio = {
        'cash': inputs.initial_cash,
        'margin_requirement': inputs.margin_requirement,
        'margin_used': 0.0,
        'positions': {
            ticker: {
                'long': 0,
                'short': 0,
                'long_cost_basis': 0.0,
                'short_cost_basis': 0.0,
                'short_margin_used': 0.0,
            }
            for ticker in inputs.tickers
        },
        'realized_gains': {
            ticker: {'long': 0.0, 'short': 0.0}
            for ticker in inputs.tickers
        }
    }
    
    # Run live hedge fund
    try:
        result = asyncio.run(run_live_hedge_fund(
            tickers=inputs.tickers,
            start_date=inputs.start_date,
            end_date=inputs.end_date,
            portfolio=portfolio,
            trading_config=trading_config,
            risk_config=risk_config,
            show_reasoning=inputs.show_reasoning,
            selected_analysts=inputs.selected_analysts,
            model_name=inputs.model_name,
            model_provider=inputs.model_provider,
        ))
        
        if result:
            print(f"\n{Fore.GREEN}🎉 Trading session completed!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}⚠️  Session ended without results{Style.RESET_ALL}")
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠️  Interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Session failed: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()