#!/usr/bin/env python3
"""
Test script for trading features
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
print(f"Added {current_dir} to Python path")

from utils.config_manager import AppConfig
from utils.trading_manager import TradingManager
from utils.hotkey_manager import HotkeyManager
from utils.smart_logger import get_logger

logger = get_logger("TEST_TRADING")

class MockIB:
    """Mock IB connection for testing"""
    def __init__(self):
        self.connected = True
    
    def isConnected(self):
        return self.connected
    
    def placeOrder(self, contract, order):
        class MockTrade:
            def __init__(self):
                self.order = type('MockOrder', (), {'orderId': 12345})()
                self.orderStatus = type('MockStatus', (), {'status': 'Submitted'})()
        
        logger.info(f"Mock order placed: {order.action} {order.totalQuantity} {contract.symbol}")
        return MockTrade()
    
    def cancelOrder(self, order_id):
        logger.info(f"Mock order cancelled: {order_id}")

async def test_trading_manager():
    """Test the trading manager functionality"""
    logger.info("Testing Trading Manager...")
    
    # Create mock IB connection
    mock_ib = MockIB()
    
    # Create test configuration
    test_config = {
        'underlying_symbol': 'QQQ',
        'trade_delta': 0.05,
        'max_trade_value': 475.0,
        'runner': 1,
        'risk_levels': [
            {
                'loss_threshold': '0',
                'account_trade_limit': '30',
                'stop_loss': '20',
                'profit_gain': ''
            },
            {
                'loss_threshold': '15',
                'account_trade_limit': '10',
                'stop_loss': '15',
                'profit_gain': ''
            }
        ]
    }
    
    account_config = {
        'high_water_mark': 100000
    }
    
    # Initialize trading manager
    trading_manager = TradingManager(mock_ib, test_config, account_config)
    
    # Update with test market data
    trading_manager.update_market_data(
        call_option={
            'Bid': 1.50,
            'Ask': 1.55,
            'Last': 1.52,
            'Strike': 400,
            'Volume': 100,
            'Delta': 0.6,
            'Gamma': 0.02,
            'Theta': -0.05,
            'Vega': 0.1
        },
        put_option={
            'Bid': 1.45,
            'Ask': 1.50,
            'Last': 1.47,
            'Strike': 400,
            'Volume': 80,
            'Delta': -0.4,
            'Gamma': 0.02,
            'Theta': -0.05,
            'Vega': 0.1
        },
        underlying_price=400.50,
        account_value=50000,
        daily_pnl_percent=2.5
    )
    
    # Test order quantity calculation
    quantity = trading_manager._calculate_order_quantity(1.55)
    logger.info(f"Calculated order quantity: {quantity}")
    
    # Test buy order placement
    logger.info("Testing BUY CALL order...")
    success = await trading_manager.place_buy_order("CALL")
    logger.info(f"BUY CALL order result: {success}")
    
    # Test buy put order placement
    logger.info("Testing BUY PUT order...")
    success = await trading_manager.place_buy_order("PUT")
    logger.info(f"BUY PUT order result: {success}")
    
    # Test panic button
    logger.info("Testing panic button...")
    success = await trading_manager.panic_button()
    logger.info(f"Panic button result: {success}")
    
    # Cleanup
    trading_manager.cleanup()
    logger.info("Trading manager test completed")

def test_hotkey_manager():
    """Test the hotkey manager functionality"""
    logger.info("Testing Hotkey Manager...")
    
    # Create mock trading manager
    class MockTradingManager:
        async def place_buy_order(self, option_type):
            logger.info(f"Mock trading manager: BUY {option_type}")
            return True
        
        async def place_sell_order(self, use_chase_logic=True):
            logger.info(f"Mock trading manager: SELL with chase={use_chase_logic}")
            return True
        
        async def panic_button(self):
            logger.info("Mock trading manager: PANIC BUTTON")
            return True
    
    # Initialize hotkey manager
    hotkey_manager = HotkeyManager(MockTradingManager())
    
    # Test hotkey info
    hotkey_info = hotkey_manager.get_hotkey_info()
    logger.info(f"Hotkey configuration: {hotkey_info}")
    
    # Test hotkey execution
    logger.info("Testing hotkey execution...")
    hotkey_manager._execute_buy_call()
    hotkey_manager._execute_buy_put()
    hotkey_manager._execute_sell_position()
    hotkey_manager._execute_panic_button()
    
    # Cleanup
    hotkey_manager.stop()
    logger.info("Hotkey manager test completed")

def main():
    """Main test function"""
    logger.info("Starting trading features test...")
    
    try:
        # Test hotkey manager (synchronous)
        test_hotkey_manager()
        
        # Test trading manager (asynchronous)
        asyncio.run(test_trading_manager())
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
