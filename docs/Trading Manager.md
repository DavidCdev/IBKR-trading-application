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

### Order Construction Logic
- **Smart Expiration Selection**: Programmatically determines correct contract expiration date, handling weekends and holidays
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
    'currency': 'USD'
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
```

### Placing Orders
```python
# Place a BUY order for call options
success = await trading_manager.place_buy_order("CALL")

# Place a SELL order with chase logic
success = await trading_manager.place_sell_order(use_chase_logic=True)

# Emergency panic button
success = await trading_manager.panic_button()
```

### Position Management
```python
# Get current positions
positions = trading_manager.get_active_positions()

# Get open orders
orders = trading_manager.get_open_orders()

# Get risk management status
risk_status = trading_manager.get_risk_management_status()
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

### Position Management
- `update_position(position_data)`: Update position information
- `clear_position(symbol)`: Clear a specific position
- `get_active_positions()`: Get all active positions
- `get_open_orders()`: Get all open orders

### Risk Management
- `get_risk_management_status()`: Get current risk level and bracket orders
- `handle_order_fill(order_id, filled_quantity, fill_price)`: Handle order fill events
- `handle_partial_fill(order_id, filled_quantity, remaining_quantity, fill_price)`: Handle partial fills

### Expiration Management
- `manual_expiration_switch(target_expiration)`: Manually switch expirations
- `get_expiration_status()`: Get current expiration status
- `update_available_expirations(expirations)`: Update available expiration dates

## Risk Management Features

### Tiered Risk Levels
The system automatically adjusts position sizes based on daily P&L:

1. **Loss Thresholds**: Different risk levels based on daily loss percentage
2. **Account Trade Limits**: Maximum trade size as percentage of account value
3. **Dynamic Adjustment**: Real-time position sizing based on current risk level

### Editable Risk Levels Table
- **Configurable Tiers**: Implement an editable table of "Risk Levels"
- **Stop Loss & Profit Gain**: Each tier has optional "Stop Loss %" and "Profit Gain %" values
- **Primary Order Integration**: When a primary order is filled, the system places exit orders accordingly:
  - **OCA Group**: One-Cancels-All group if both stop loss and profit gain are provided
  - **Single Order**: Single order if only one is provided
  - **No Order**: No exit orders if both are blank

### PDT Buffer Protection
- Maintains minimum equity requirements ($2,000 USD / $2,500 CAD)
- Uses 80% of available buffer as safety margin
- Prevents PDT rule violations

### Bracket Orders
- **Stop Loss Orders**: Automatic stop-loss placement based on risk level
- **Take Profit Orders**: Automatic take-profit placement for profit management
- **Order Management**: Automatic cancellation of remaining bracket orders when one fills

## Chase Logic

The chase logic provides intelligent order management:

1. **Initial Limit Order**: Places limit order at midpoint - trade_delta
2. **Automatic Conversion**: Converts to market order after 10 seconds if not filled
3. **Quantity Tracking**: Manages remaining quantity through partial fills
4. **Thread Safety**: Background monitoring with proper thread management

### Sell Order "Chase Logic" Details
When a sell order is placed via Ctrl-Alt-X:
- **Initial Submission**: Limit Order at price of (midpoint of bid/ask) - (trade delta)
- **Monitoring**: System monitors the limit order for 10 seconds
- **Automatic Conversion**: If not completely filled within 10 seconds, automatically cancels the original limit order and immediately submits a new Market Order for the remaining quantity
- **Partial Fill Handling**: Gracefully handles partial fills on exit orders

## Position Logic

### One Active Position Rule
- **Enforcement**: System enforces a "one active position" rule
- **Validation**: Prevents new orders when an active position exists
- **Management**: Ensures clean position tracking and risk management

### Runners & Partial Sells
- **Runner Definition**: Handles "runners" as defined in GUI preferences
- **Profitable Exit**: When exiting a profitable trade, sells position minus the runner quantity
- **Partial Fill Handling**: Gracefully handles partial fills on exit orders
- **Position Updates**: Automatically updates position size after partial sales

## Runner Logic

For profitable positions, the runner logic:

1. **Partial Selling**: Sells most contracts while keeping specified number
2. **Position Tracking**: Updates position size after partial sales
3. **Bracket Adjustment**: Adjusts bracket orders for remaining quantity
4. **Profit Management**: Allows for continued profit potential

## Error Handling

The system includes comprehensive error handling:

- **Exception Logging**: All errors are logged with detailed information
- **Graceful Degradation**: Fallback mechanisms for critical operations
- **Thread Safety**: Proper locking mechanisms for concurrent operations
- **Resource Cleanup**: Automatic cleanup of threads and resources

## Threading and Concurrency

- **Background Monitoring**: Chase logic runs in background thread
- **Thread Safety**: Proper locking for position and order tracking
- **Resource Management**: Automatic thread cleanup on shutdown
- **Event-Driven**: Uses events for thread coordination

## Integration

### IBKR Connection
- Requires active IBKR TWS or Gateway connection
- Supports both paper and live trading
- Handles connection state management

### Data Collector Integration
- Integrates with market data collectors
- Supports real-time price updates
- Manages expiration date availability

## Best Practices

1. **Always check return values** from order placement methods
2. **Monitor risk management status** regularly
3. **Use panic button** for emergency situations
4. **Update market data** frequently for accurate calculations
5. **Handle order fill events** properly for position tracking
6. **Clean up resources** when shutting down

## Troubleshooting

### Common Issues
- **Order Rejection**: Check account permissions and margin requirements
- **Expiration Issues**: Verify available expirations and market hours
- **Connection Problems**: Ensure TWS/Gateway is running and connected
- **Position Tracking**: Verify order fill event handling

### Debug Information
- All operations are logged with detailed information
- Use `get_risk_management_status()` for system health checks
- Monitor bracket order status for risk management issues

## Dependencies

- `ib_async`: Interactive Brokers API
- `asyncio`: Asynchronous programming support
- `pytz`: Timezone handling
- `threading`: Thread management
- `datetime`: Date and time operations

