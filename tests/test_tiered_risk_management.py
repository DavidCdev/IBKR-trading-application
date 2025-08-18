import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.trading_manager import TradingManager
from utils.smart_logger import get_logger

logger = get_logger("TEST_TIERED_RISK")


def test_tiered_risk_management():
    """Test the tiered risk management functionality"""
    logger.info("Testing Tiered Risk Management...")
    
    # Mock IB connection
    class MockIB:
        def placeOrder(self, contract, order):
            class MockTrade:
                class MockOrder:
                    def __init__(self, order_id):
                        self.orderId = order_id
                
                def __init__(self, order_id):
                    self.order = self.MockOrder(order_id)
                    self.orderStatus = type('MockStatus', (), {'status': 'Submitted'})()
            
            return MockTrade(12345)  # Mock order ID
        
        def cancelOrder(self, order_id):
            logger.info(f"Mock IB: Cancelled order {order_id}")
    
    # Test configuration
    trading_config = {
        'underlying_symbol': 'SPY',
        'trade_delta': 0.05,
        'max_trade_value': 475.0,
        'runner': 1,
        'risk_levels': [
            {
                'loss_threshold': '0',
                'account_trade_limit': '30',
                'stop_loss': '20',
                'profit_gain': '50'
            },
            {
                'loss_threshold': '15',
                'account_trade_limit': '10',
                'stop_loss': '15',
                'profit_gain': '30'
            },
            {
                'loss_threshold': '25',
                'account_trade_limit': '5',
                'stop_loss': '5',
                'profit_gain': '10'
            }
        ]
    }
    
    account_config = {
        'currency': 'USD',
        'account_value': 10000.0
    }
    
    # Initialize trading manager
    ib = MockIB()
    trading_manager = TradingManager(ib, trading_config, account_config)
    
    # Test 1: Risk level selection based on daily P&L
    logger.info("Test 1: Risk level selection")
    
    # Test with 0% daily P&L (should use first risk level)
    trading_manager.update_market_data(daily_pnl_percent=0.0, account_value=10000.0)
    risk_level = trading_manager._get_current_risk_level()
    logger.info(f"Risk level for 0% P&L: {risk_level}")
    assert risk_level['stop_loss'] == '20', "Should use first risk level"
    
    # Test with 20% daily loss (should use second risk level)
    trading_manager.update_market_data(daily_pnl_percent=-20.0, account_value=10000.0)
    risk_level = trading_manager._get_current_risk_level()
    logger.info(f"Risk level for -20% P&L: {risk_level}")
    assert risk_level['stop_loss'] == '15', "Should use second risk level"
    
    # Test 2: Stop loss and take profit calculations
    logger.info("Test 2: Price calculations")
    
    entry_price = 2.50
    stop_loss_price = trading_manager._calculate_stop_loss_price(entry_price, 20.0, "CALL")
    take_profit_price = trading_manager._calculate_take_profit_price(entry_price, 50.0, "CALL")
    
    logger.info(f"Entry: ${entry_price:.2f}, Stop Loss: ${stop_loss_price:.2f}, Take Profit: ${take_profit_price:.2f}")
    
    expected_stop_loss = entry_price * 0.8  # 20% loss
    expected_take_profit = entry_price * 1.5  # 50% gain
    
    assert abs(stop_loss_price - expected_stop_loss) < 0.01, "Stop loss calculation incorrect"
    assert abs(take_profit_price - expected_take_profit) < 0.01, "Take profit calculation incorrect"
    
    # Test 3: Bracket order creation
    logger.info("Test 3: Bracket order creation")
    
    # Mock option data
    call_option_data = {
        "Ask": 2.50,
        "Bid": 2.45,
        "Strike": 450.0
    }
    
    trading_manager.update_market_data(call_option=call_option_data)
    
    # Test bracket order placement
    result = asyncio.run(trading_manager._place_bracket_orders(
        parent_order_id=12345,
        contract=None,  # Mock contract
        quantity=10,
        entry_price=2.50,
        option_type="CALL"
    ))
    
    logger.info(f"Bracket order placement result: {result}")
    
    # Test 4: Risk management status
    logger.info("Test 4: Risk management status")
    
    status = trading_manager.get_risk_management_status()
    logger.info(f"Risk management status: {status}")
    
    assert 'current_risk_level' in status, "Status should include current risk level"
    assert 'active_bracket_orders' in status, "Status should include bracket order count"
    
    # Test 5: Order fill handling
    logger.info("Test 5: Order fill handling")
    
    # Simulate a buy order fill
    trading_manager.handle_order_fill(order_id=12345, filled_quantity=10, fill_price=2.50)
    
    # Check position tracking
    positions = trading_manager.get_active_positions()
    logger.info(f"Active positions after fill: {positions}")
    
    # Test 6: Partial fill handling
    logger.info("Test 6: Partial fill handling")
    
    trading_manager.handle_partial_fill(order_id=12345, filled_quantity=5, remaining_quantity=5, fill_price=2.50)
    
    logger.info("Tiered risk management tests completed successfully!")


def test_bracket_order_cancellation():
    """Test bracket order cancellation functionality"""
    logger.info("Testing Bracket Order Cancellation...")
    
    # Mock IB connection
    class MockIB:
        def cancelOrder(self, order_id):
            logger.info(f"Mock IB: Cancelled order {order_id}")
    
    # Test configuration
    trading_config = {
        'underlying_symbol': 'SPY',
        'risk_levels': [
            {
                'loss_threshold': '0',
                'stop_loss': '20',
                'profit_gain': '50'
            }
        ]
    }
    
    account_config = {}
    
    # Initialize trading manager
    ib = MockIB()
    trading_manager = TradingManager(ib, trading_config, account_config)
    
    # Simulate bracket orders
    trading_manager._bracket_orders[12345] = {
        'stop_loss_id': 67890,
        'take_profit_id': 67891,
        'contract': None,
        'quantity': 10,
        'entry_price': 2.50,
        'option_type': 'CALL'
    }
    
    # Test stop loss fill (should cancel take profit)
    logger.info("Testing stop loss fill")
    trading_manager.handle_order_fill(order_id=67890, filled_quantity=10, fill_price=2.00)
    
    # Test take profit fill (should cancel stop loss)
    logger.info("Testing take profit fill")
    trading_manager._bracket_orders[12346] = {
        'stop_loss_id': 67892,
        'take_profit_id': 67893,
        'contract': None,
        'quantity': 10,
        'entry_price': 2.50,
        'option_type': 'CALL'
    }
    
    trading_manager.handle_order_fill(order_id=67893, filled_quantity=10, fill_price=3.75)
    
    logger.info("Bracket order cancellation tests completed!")


def main():
    """Main test function"""
    try:
        logger.info("Starting Tiered Risk Management Tests")
        
        test_tiered_risk_management()
        test_bracket_order_cancellation()
        
        logger.info("All tiered risk management tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Tiered risk management tests failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = main()
    if success:
        print("✅ Tiered Risk Management Tests PASSED")
    else:
        print("❌ Tiered Risk Management Tests FAILED")
