# Trading Manager

A comprehensive trading management system for Interactive Brokers (IBKR) that handles order placement, position management, risk management, and automated trading strategies.

## Overview

The `TradingManager` class provides a complete solution for managing options and stock trading operations with advanced features including:

- **Order Management**: Automated buy/sell order placement with chase logic
- **Risk Management**: Tiered risk levels, PDT buffer protection, and bracket orders
- **Position Tracking**: Real-time position monitoring and management
- **Expiration Management**: Smart expiration date selection and switching
- **Runner Logic**: Partial position selling for profit management
- **Panic Button**: Emergency position flattening
- **Global Hotkey Support**: Instant order execution through keyboard shortcuts

## Features

### Global Hotkey Execution
The system supports instant order execution through global hotkeys:

- **Ctrl-Alt-P**: Instantly place a BUY order for the currently subscribed put option
- **Ctrl-Alt-C**: Instantly place a BUY order for the currently subscribed call option  
- **Ctrl-Alt-X**: Instantly place a SELL order for any open call or put position using "Chase Logic"
- **Ctrl-Alt-F ("Panic Button")**: Instantly flattens all risk for the underlying by:
  1. Placing a Market Order to sell 100% of any open options position
  2. Immediately cancelling all other open orders (including bracket orders) for the underlying
- **macOS Support**: Ctrl is replaced by Command key (e.g., Command-Alt-C)

### Core Trading Features
- **One Active Position Rule**: Ensures only one position is active at a time
- **IBALGO Integration**: All BUY orders use Interactive Brokers' Adaptive Algo with "Normal" urgency setting
- **Chase Logic**: Automatic limit-to-market order conversion after 10 seconds
- **Runner Logic**: Keeps specified contracts when selling profitable positions
- **Smart Expiration Selection**: Programmatically determines correct contract expiration date

### Order Construction Logic
- **Three-Step Quantity Calculation**: Uses the minimum of three calculations:
  1. **GUI Max Trade Value**: Directly from the "Max Trade Value" setting in the GUI
  2. **Tiered Risk Limit**: Based on current "Daily P&L %" and corresponding tier in "Risk Levels" table
  3. **PDT Buffer**: Buffer to stay above PDT minimum equity requirement (Account Value - $2,500 CAD, Account Value - $2,000 USD)
- **Final Calculation**: Lowest of the three results divided by option's ask price determines final contract quantity

### Risk Management
- **Tiered Risk Levels**: Dynamic position sizing based on daily P&L with editable table of risk levels
- **PDT Buffer Protection**: Maintains minimum equity requirements
- **Bracket Orders**: Automatic stop-loss and take-profit orders with One-Cancels-All (OCA) grouping
- **Position Size Calculation**: Three-step calculation (GUI, Tiered Risk, PDT Buffer)

### Expiration Management
- **Smart Expiration Selection**: Automatic selection based on time and availability
- **Fallback Logic**: Robust expiration handling when data is unavailable
- **Manual Switching**: User-controlled expiration changes
- **Available Expirations**: Integration with data collector for real-time expiration availability

## Configuration

### Trading Configuration
```python
trading_config = {
    'underlying_symbol': 'QQQ',           # Underlying asset symbol
    'trade_delta': 0.05,                 # Price delta for chase logic
    'max_trade_value': 475.0,            # Maximum trade value in USD
    'runner': 1,                         # Number of contracts to keep as runner
    'risk_levels': [                     # Tiered risk management
        {
            'loss_threshold': 0.0,       # Daily loss threshold (%)
            'account_trade_limit': 100,  # Maximum trade size (% of account)
            'stop_loss': 20.0,           # Stop loss percentage
            'profit_gain': 50.0          # Take profit percentage
        }
    ]
}
```

### Account Configuration
```python
account_config = {
    'account_id': 'YOUR_ACCOUNT_ID',
    'currency': 'USD'                    # USD or CAD
}
```

## Usage Examples

### Basic Initialization
```python
from utils.trading_manager import TradingManager
from ib_async import IB

# Initialize IB connection
ib = IB()
await ib.connectAsync('127.0.0.1', 7497, clientId=1)

# Create trading manager
trading_manager = TradingManager(ib, trading_config, account_config)

# Set UI notification callback (optional)
trading_manager.ui_notify = your_ui_callback_function
```

### Placing Orders
```python
# Place a BUY order for call options
success = await trading_manager.place_buy_order("CALL")

# Place a BUY order for put options
success = await trading_manager.place_buy_order("PUT")

# Place a SELL order with chase logic
success = await trading_manager.place_sell_order(use_chase_logic=True)

# Place a SELL order without chase logic (market order)
success = await trading_manager.place_sell_order(use_chase_logic=False)

# Emergency panic button
success = await trading_manager.panic_button()
```

### Position Management
```python
# Get current positions
positions = trading_manager.get_active_positions()

# Get open orders
orders = trading_manager.get_open_orders()

# Get bracket orders
bracket_orders = trading_manager.get_bracket_orders()

# Get risk management status
risk_status = trading_manager.get_risk_management_status()

# Get last action message for UI notifications
last_message = trading_manager.get_last_action_message()
```

### Market Data Updates
```python
# Update market data
trading_manager.update_market_data(
    call_option=call_data,
    put_option=put_data,
    underlying_price=underlying_price,
    account_value=account_value,
    daily_pnl_percent=daily_pnl_percent
)

# Update available expirations
trading_manager.update_available_expirations(['20241220', '20241227', '20250103'])
```

### Configuration Updates
```python
# Update trading configuration at runtime
trading_manager.update_trading_config({
    'max_trade_value': 500.0,
    'trade_delta': 0.10,
    'risk_levels': new_risk_levels
})
```

## Key Methods

### Order Placement
- `place_buy_order(option_type)`: Place BUY orders for CALL or PUT options
- `place_sell_order(use_chase_logic)`: Place SELL orders with optional chase logic
- `panic_button()`: Emergency flatten all positions

### Order Algorithm
- **IBALGO Integration**: All BUY orders use Interactive Brokers' Adaptive Algo
- **Urgency Setting**: "Normal" urgency setting for optimal execution
- **Smart Routing**: Automatic order routing through IB's adaptive algorithm
- **Order Types**: Market orders for BUY, Limit/Market for SELL based on chase logic

### Position Management
- `update_position(position_data)`: Update position information
- `clear_position(symbol)`: Clear a specific position
- `get_active_positions()`: Get all active positions
- `get_open_orders()`: Get all open orders
- `get_bracket_orders()`: Get all bracket orders

### Risk Management
- `get_risk_management_status()`: Get current risk level and bracket orders
- `handle_order_fill(order_id, filled_quantity, fill_price)`: Handle order fill events
- `handle_partial_fill(order_id, filled_quantity, remaining_quantity, fill_price)`: Handle partial fills
- `_calculate_tiered_risk_limit()`: Calculate position size based on risk levels
- `_calculate_pdt_buffer()`: Calculate PDT buffer protection

### Expiration Management
- `manual_expiration_switch(target_expiration)`: Manually switch expirations
- `get_expiration_status()`: Get current expiration status
- `update_available_expirations(expirations)`: Update available expiration dates
- `_get_contract_expiration()`: Get smart expiration date
- `_select_smart_expiration(est_now, available_expirations)`: Select best available expiration
- `_get_fallback_expiration(est_now)`: Fallback expiration logic

### Chase Logic Management
- `_start_chase_monitoring()`: Start chase order monitoring
- `_chase_monitor_loop()`: Background monitoring loop
- `_convert_to_market_order(order_id)`: Convert limit order to market order

### Bracket Order Management
- `_place_bracket_orders(parent_order_id, contract, quantity, entry_price, option_type)`: Place stop loss and take profit orders
- `_cancel_bracket_orders(parent_order_id)`: Cancel bracket orders
- `_adjust_bracket_order_quantity(parent_order_id, new_quantity)`: Adjust quantities after partial fills
- `_cancel_remaining_bracket_order(parent_id, order_type)`: Cancel remaining bracket order when one fills

## Risk Management Features

### Tiered Risk Levels
The system automatically adjusts position sizes based on daily P&L:

1. **Loss Thresholds**: Different risk levels based on daily loss percentage
2. **Account Trade Limits**: Maximum trade size as percentage of account value
3. **Dynamic Adjustment**: Real-time position sizing based on current risk level
4. **Stop Loss & Profit Gain**: Each tier has optional "Stop Loss %" and "Profit Gain %" values

### Editable Risk Levels Table
- **Configurable Tiers**: Implement an editable table of "Risk Levels"
- **Primary Order Integration**: When a primary order is filled, the system places exit orders accordingly:
  - **OCA Group**: One-Cancels-All group if both stop loss and profit gain are provided
  - **Single Order**: Single order if only one is provided
  - **No Order**: No exit orders if both are blank

### PDT Buffer Protection
- Maintains minimum equity requirements ($2,000 USD / $2,500 CAD)
- Uses 80% of available buffer as safety margin
- Prevents PDT rule violations
- Currency-aware calculations (USD/CAD)

### Bracket Orders
- **Stop Loss Orders**: Automatic stop-loss placement based on risk level
- **Take Profit Orders**: Automatic take-profit placement for profit management
- **Order Management**: Automatic cancellation of remaining bracket orders when one fills
- **OCA Grouping**: One-Cancels-All functionality for risk management
- **Partial Fill Handling**: Automatic adjustment of quantities after partial fills

## Chase Logic

The chase logic provides intelligent order management:

1. **Initial Limit Order**: Places limit order at midpoint - trade_delta
2. **Automatic Conversion**: Converts to market order after 10 seconds if not filled
3. **Quantity Tracking**: Manages remaining quantity through partial fills
4. **Thread Safety**: Background monitoring with proper thread management
5. **Order Cancellation**: Automatically cancels original limit order before market conversion

### Sell Order "Chase Logic" Details
When a sell order is placed via Ctrl-Alt-X:
- **Initial Submission**: Limit Order at price of (midpoint of bid/ask) - (trade delta)
- **Monitoring**: System monitors the limit order for 10 seconds
- **Automatic Conversion**: If not completely filled within 10 seconds, automatically cancels the original limit order and immediately submits a new Market Order for the remaining quantity
- **Partial Fill Handling**: Gracefully handles partial fills on exit orders
- **Background Threading**: Chase monitoring runs in background thread for non-blocking operation

## Position Logic

### One Active Position Rule
- **Enforcement**: System enforces a "one active position" rule
- **Validation**: Prevents new orders when an active position exists
- **Management**: Ensures clean position tracking and risk management
- **Symbol Filtering**: Positions are filtered by current underlying symbol

### Runners & Partial Sells
- **Runner Definition**: Handles "runners" as defined in GUI preferences
- **Profitable Exit**: When exiting a profitable trade, sells position minus the runner quantity
- **Partial Fill Handling**: Gracefully handles partial fills on exit orders
- **Position Updates**: Automatically updates position size after partial sales
- **Bracket Adjustment**: Adjusts bracket orders for remaining quantity

### Position Tracking
- **Real-time Updates**: Position information updated through `update_position()`
- **Contract Validation**: Automatic contract recreation if position contract is invalid
- **Symbol Matching**: Intelligent matching of positions to current underlying symbol
- **Size Management**: Automatic position size updates after partial fills

## Expiration Management

### Smart Expiration Selection
- **Time-based Logic**: Before 12:00 PM EST prefers 0DTE, after prefers 1DTE
- **Weekend Handling**: Automatically skips weekends for next business day
- **Available Expirations**: Integrates with data collector for real-time availability
- **Fallback Strategy**: Multiple fallback strategies if preferred expirations unavailable

### Expiration Strategies
1. **Exact Target Date**: Find exact target expiration date
2. **Nearest Available**: Find nearest available expiration to target
3. **First Available**: Use first available expiration as final fallback

### Manual Control
- **Manual Switching**: User can manually trigger expiration changes
- **Status Monitoring**: Real-time expiration status monitoring
- **Integration**: Seamless integration with IB connection and data collector

## Error Handling

The system includes comprehensive error handling:

- **Exception Logging**: All errors are logged with detailed information
- **Graceful Degradation**: Fallback mechanisms for critical operations
- **Thread Safety**: Proper locking mechanisms for concurrent operations
- **Resource Cleanup**: Automatic cleanup of threads and resources
- **UI Notifications**: Optional UI notification callbacks for user feedback

## Threading and Concurrency

- **Background Monitoring**: Chase logic runs in background thread
- **Thread Safety**: Proper locking for position, order, and bracket tracking
- **Resource Management**: Automatic thread cleanup on shutdown
- **Event-Driven**: Uses events for thread coordination
- **Daemon Threads**: Chase monitoring runs as daemon thread

### Locking Mechanisms
- `_position_lock`: Protects position data access
- `_order_lock`: Protects order data access
- `_bracket_lock`: Protects bracket order data access
- `_config_lock`: Protects configuration updates

## Integration

### IBKR Connection
- Requires active IBKR TWS or Gateway connection
- Supports both paper and live trading
- Handles connection state management
- Integrates with IB's native order types and algorithms

### Data Collector Integration
- Integrates with market data collectors
- Supports real-time price updates
- Manages expiration date availability
- Provides market data for calculations

### UI Integration
- Optional UI notification callbacks
- Real-time action message updates
- Status monitoring for user interface
- Configuration update support

## Best Practices

1. **Always check return values** from order placement methods
2. **Monitor risk management status** regularly
3. **Use panic button** for emergency situations
4. **Update market data** frequently for accurate calculations
5. **Handle order fill events** properly for position tracking
6. **Clean up resources** when shutting down
7. **Set UI notification callback** for user feedback
8. **Update available expirations** when data changes
9. **Monitor bracket order status** for risk management
10. **Use proper error handling** for all operations

## Troubleshooting

### Common Issues
- **Order Rejection**: Check account permissions and margin requirements
- **Expiration Issues**: Verify available expirations and market hours
- **Connection Problems**: Ensure TWS/Gateway is running and connected
- **Position Tracking**: Verify order fill event handling
- **Chase Logic**: Check background thread status and order monitoring
- **Bracket Orders**: Verify risk level configuration and order placement

### Debug Information
- All operations are logged with detailed information
- Use `get_risk_management_status()` for system health checks
- Monitor bracket order status for risk management issues
- Check chase order monitoring thread status
- Verify expiration selection logic and available dates

### System Health Checks
```python
# Check risk management status
risk_status = trading_manager.get_risk_management_status()

# Check active positions
positions = trading_manager.get_active_positions()

# Check open orders
orders = trading_manager.get_open_orders()

# Check bracket orders
brackets = trading_manager.get_bracket_orders()

# Get last action message
last_message = trading_manager.get_last_action_message()
```

## Dependencies

- `ib_async`: Interactive Brokers API
- `asyncio`: Asynchronous programming support
- `pytz`: Timezone handling
- `threading`: Thread management
- `datetime`: Date and time operations
- `time`: Time-based operations for chase logic

## Performance Considerations

- **Background Processing**: Chase logic runs in background thread
- **Efficient Locking**: Minimal lock contention for concurrent operations
- **Memory Management**: Automatic cleanup of completed orders and positions
- **Async Operations**: Non-blocking order placement and management
- **Resource Pooling**: Efficient reuse of contract and order objects

## Future Enhancements

- **Advanced Order Types**: Support for more complex order types
- **Risk Analytics**: Enhanced risk analysis and reporting
- **Multi-Asset Support**: Support for multiple underlying assets
- **Advanced Algorithms**: More sophisticated order execution algorithms
- **Real-time Monitoring**: Enhanced real-time position and risk monitoring

