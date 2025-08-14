#!/usr/bin/env python3
"""
Simple test script for trading features
"""

import sys
import os

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
print(f"Added {current_dir} to Python path")

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        from utils.smart_logger import get_logger
        print("✓ smart_logger imported")
    except Exception as e:
        print(f"✗ smart_logger import failed: {e}")
        return False
    
    try:
        from utils.config_manager import AppConfig
        print("✓ config_manager imported")
    except Exception as e:
        print(f"✗ config_manager import failed: {e}")
        return False
    
    try:
        from utils.trading_manager import TradingManager
        print("✓ trading_manager imported")
    except Exception as e:
        print(f"✗ trading_manager import failed: {e}")
        return False
    
    try:
        from utils.hotkey_manager import HotkeyManager
        print("✓ hotkey_manager imported")
    except Exception as e:
        print(f"✗ hotkey_manager import failed: {e}")
        return False
    
    return True

def test_config():
    """Test configuration loading"""
    print("\nTesting configuration...")
    
    try:
        config = AppConfig()
        print("✓ Default configuration created")
        
        # Test trading config
        trading_config = config.trading
        print(f"✓ Trading config loaded: {trading_config.get('underlying_symbol', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_trading_manager_basic():
    """Test basic trading manager functionality"""
    print("\nTesting Trading Manager (basic)...")
    
    try:
        # Create mock IB connection
        class MockIB:
            def __init__(self):
                self.connected = True
            
            def isConnected(self):
                return self.connected
        
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
                }
            ]
        }
        
        account_config = {
            'high_water_mark': 100000
        }
        
        # Initialize trading manager
        trading_manager = TradingManager(mock_ib, test_config, account_config)
        print("✓ Trading Manager initialized")
        
        # Test market data update
        trading_manager.update_market_data(
            underlying_price=400.50,
            account_value=50000,
            daily_pnl_percent=2.5
        )
        print("✓ Market data updated")
        
        # Test quantity calculation
        quantity = trading_manager._calculate_order_quantity(1.55)
        print(f"✓ Order quantity calculated: {quantity}")
        
        return True
    except Exception as e:
        print(f"✗ Trading Manager test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def test_hotkey_manager_basic():
    """Test basic hotkey manager functionality"""
    print("\nTesting Hotkey Manager (basic)...")
    
    try:
        # Create mock trading manager
        class MockTradingManager:
            def __init__(self):
                self.calls = 0
                self.puts = 0
                self.sells = 0
                self.panics = 0
            
            async def place_buy_order(self, option_type):
                if option_type == "CALL":
                    self.calls += 1
                elif option_type == "PUT":
                    self.puts += 1
                return True
            
            async def place_sell_order(self, use_chase_logic=True):
                self.sells += 1
                return True
            
            async def panic_button(self):
                self.panics += 1
                return True
        
        mock_trading = MockTradingManager()
        
        # Initialize hotkey manager
        hotkey_manager = HotkeyManager(mock_trading)
        print("✓ Hotkey Manager initialized")
        
        # Test hotkey info
        hotkey_info = hotkey_manager.get_hotkey_info()
        print(f"✓ Hotkey configuration: {hotkey_info}")
        
        return True
    except Exception as e:
        print(f"✗ Hotkey Manager test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Main test function"""
    print("Starting simple trading features test...\n")
    
    tests = [
        test_imports,
        test_config,
        test_trading_manager_basic,
        test_hotkey_manager_basic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Trading features are ready to use.")
    else:
        print("❌ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
