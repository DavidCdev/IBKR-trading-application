#!/usr/bin/env python3
"""
Simple test to verify option contract multiplier of 100 is correctly applied.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.trading_manager import TradingManager

def test_option_multiplier():
    """Test that option contract multiplier of 100 is correctly applied"""
    
    # Mock configuration
    trading_config = {
        'underlying_symbol': 'SPY',
        'max_trade_value': 300.0,  # $300 max trade value
        'trade_delta': 0.05,
        'runner': 1,
        'risk_levels': []
    }
    
    account_config = {'currency': 'USD'}
    
    # Create trading manager
    tm = TradingManager(None, trading_config, account_config)
    
    # Set mock account data
    tm.update_market_data(
        call_option={'Ask': 0.89, 'Bid': 0.87, 'Strike': 500, 'Expiration': '20250117'},
        put_option={'Ask': 1.25, 'Bid': 1.23, 'Strike': 500, 'Expiration': '20250117'},
        underlying_price=500.0,
        account_value=5000.0,
        daily_pnl_percent=0.0
    )
    
    print("=== Option Contract Multiplier Test ===\n")
    
    # Test 1: $0.89 call option with $300 limit
    print("Test 1: $0.89 Call Option with $300 limit")
    print(f"Option Price: $0.89")
    print(f"Cost per Contract: $0.89 × 100 = $89.00")
    print(f"Max Trade Value: $300.00")
    print(f"Expected Max Quantity: floor($300 / $89) = floor(3.37) = 3 contracts")
    print(f"Expected Total Cost: 3 × $89 = $267.00")
    
    capacity = tm.calculate_max_affordable_quantity(0.89)
    print(f"\nActual Results:")
    print(f"Max Quantity: {capacity['max_quantity']} contracts")
    print(f"Total Cost: ${capacity['actual_trade_value']:.2f}")
    print(f"Can Afford: {'Yes' if capacity['can_afford'] else 'No'}")
    print(f"User Message: {capacity['user_friendly_message']}")
    
    # Verify the calculation
    expected_qty = 3
    expected_cost = 3 * 0.89 * 100
    print(f"\nVerification:")
    print(f"Expected Quantity: {expected_qty}, Actual: {capacity['max_quantity']} {'✓' if capacity['max_quantity'] == expected_qty else '✗'}")
    print(f"Expected Cost: ${expected_cost:.2f}, Actual: ${capacity['actual_trade_value']:.2f} {'✓' if abs(capacity['actual_trade_value'] - expected_cost) < 0.01 else '✗'}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    try:
        test_option_multiplier()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
