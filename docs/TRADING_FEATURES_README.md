# Trading & Order Management Features

This document describes the comprehensive trading and order management features implemented in the IB Trading Application.

## Overview

The trading system provides global hotkey execution, advanced order algorithms, intelligent position management, and risk controls for options trading through Interactive Brokers.

## Global Hotkey Execution

### Supported Hotkeys

| Action | Windows/Linux | macOS | Description |
|--------|---------------|-------|-------------|
| Buy Call | `Ctrl+Alt+C` | `Cmd+Alt+C` | Instantly place an order to BUY the currently subscribed call option |
| Buy Put | `Ctrl+Alt+P` | `Cmd+Alt+P` | Instantly place an order to BUY the currently subscribed put option |
| Sell Position | `Ctrl+Alt+X` | `Cmd+Alt+X` | Instantly place an order to SELL any open call or put position using "Chase Logic" |
| Panic Button | `Ctrl+Alt+F` | `Cmd+Alt+F` | Instantly flattens all risk for the underlying |

### Hotkey Features

- **Global Hotkeys**: Work even when the application is not in focus
- **Platform Support**: Automatic detection of Windows/Linux vs macOS for correct modifier keys
- **Instant Execution**: Orders are placed immediately upon hotkey activation
- **Error Handling**: Comprehensive error handling with user feedback

## Order Algorithm

### Interactive Brokers Adaptive Algo (IBALGO)

All BUY orders use Interactive Brokers' Adaptive Algo with the "Normal" urgency setting:

```python
order = Order(
    action="BUY",
    totalQuantity=quantity,
    orderType="MKT",
    algoStrategy="Adaptive",
    algoParams=[
        ("adaptivePriority", "Normal")
    ]
)
```

### Order Types

- **BUY Orders**: Market orders for immediate execution
- **SELL Orders**: 
  - Limit orders with chase logic (default)
  - Market orders for panic button and direct execution

## Order Construction Logic

### Contract Expiration Date

The system programmatically determines the correct contract expiration date:

- **Before 12:00 PM EST**: Uses 0DTE (same day) contracts
- **After 12:00 PM EST**: Uses 1DTE (next business day) contracts
- **Weekend Handling**: Automatically skips weekends for next business day
- **Holiday Awareness**: Built-in holiday handling for proper expiration selection

### Order Quantity Calculation

The quantity of contracts to purchase is determined by a three-step calculation, using the **minimum value** of the three:

#### 1. GUI Max Trade Value
- Fetched directly from the "Max Trade Value" setting in the GUI
- Default: $475.00
- Configurable through settings

#### 2. Tiered Risk Limit
- Calculates maximum allowed trade value based on current "Daily P&L %"
- Uses the corresponding tier in the "Risk Levels" table
- Example calculation:
  ```
  If Daily P&L = -20% and Risk Level = 10% of account
  Max Trade Value = Account Value × 0.10
  ```

#### 3. PDT Buffer
- Calculates buffer to stay above PDT minimum equity requirement
- **USD Accounts**: Account Value - $2,000 minimum
- **CAD Accounts**: Account Value - $2,500 minimum
- Uses 80% of available buffer as safety margin

#### Final Calculation
```python
max_trade_value = min(gui_max_value, tiered_max_value, pdt_max_value)
quantity = int(max_trade_value / option_price)
```

## Sell Order "Chase Logic"

### Process Flow

1. **Initial Limit Order**: 
   - Price = (midpoint of bid/ask) - (trade delta)
   - Example: Bid $1.50, Ask $1.55 → Midpoint $1.525 → Limit Price $1.475

2. **Monitoring**: 
   - System monitors the limit order for 10 seconds
   - Tracks fill status and remaining quantity

3. **Automatic Conversion**:
   - If not completely filled within 10 seconds
   - Cancels the original limit order
   - Immediately submits a new Market Order for remaining quantity

### Benefits

- **Price Improvement**: Attempts to get better prices through limit orders
- **Guaranteed Execution**: Falls back to market orders for certainty
- **Time Control**: 10-second window balances price vs. execution speed

## Position Logic

### One Active Position Rule

- **Enforcement**: System prevents placing new orders while a position exists
- **Validation**: Checks active positions before allowing new orders
- **Clearance**: Must close existing position before opening new one

### Runners & Partial Sells

#### Runner Logic
- **Definition**: Number of contracts to keep when exiting profitable trades
- **Configuration**: Set in GUI preferences (default: 1 contract)
- **Application**: Only applies to profitable positions (P&L > 0)

#### Partial Fill Handling
- **Tracking**: System tracks partial fills on exit orders
- **Remaining Quantity**: Chase logic handles remaining unfilled quantity
- **Graceful Degradation**: Continues monitoring until full execution

### Position Management

```python
# Example: Selling 10 contracts with runner = 1
if position.get('pnl_percent', 0) > 0 and self.runner > 0:
    sell_quantity = max(1, quantity - self.runner)  # Sell 9, keep 1
else:
    sell_quantity = quantity  # Sell all
```

## Risk Management

### Tiered Risk Levels

The system implements configurable risk levels based on daily P&L:

| Daily P&L | Account Trade Limit | Stop Loss | Description |
|-----------|-------------------|-----------|-------------|
| 0% | 30% | 20% | Normal trading conditions |
| 15% | 10% | 15% | Reduced position sizing |
| 25% | 5% | 5% | Minimal position sizing |

### PDT Protection

- **Automatic Calculation**: Monitors account value vs. PDT minimums
- **Safety Buffer**: Uses 80% of available buffer
- **Currency Support**: Handles both USD and CAD accounts

## Technical Implementation

### Core Components

1. **TradingManager** (`utils/trading_manager.py`)
   - Handles all order placement and position management
   - Implements quantity calculations and risk controls
   - Manages chase logic and order monitoring

2. **HotkeyManager** (`utils/hotkey_manager.py`)
   - Global hotkey registration and detection
   - Platform-specific key handling
   - Signal-based execution

3. **Integration** (`widgets/ib_trading_app.py`)
   - Main application integration
   - Market data updates
   - Position tracking

### Market Data Integration

The trading manager receives real-time updates for:

- **Option Prices**: Call and put option bid/ask/last prices
- **Underlying Price**: Current underlying symbol price
- **Account Data**: Account value and daily P&L
- **Position Data**: Active positions and P&L calculations

### Error Handling

- **Connection Issues**: Graceful handling of IB connection problems
- **Order Failures**: Comprehensive error logging and user feedback
- **Data Validation**: Input validation for all trading parameters
- **Recovery**: Automatic retry mechanisms for failed operations

## Configuration

### Trading Settings

```json
{
  "trading": {
    "underlying_symbol": "QQQ",
    "trade_delta": 0.05,
    "max_trade_value": 475.0,
    "runner": 1,
    "risk_levels": [
      {
        "loss_threshold": "0",
        "account_trade_limit": "30",
        "stop_loss": "20",
        "profit_gain": ""
      }
    ]
  }
}
```

### Key Parameters

- **underlying_symbol**: The underlying asset (QQQ, SPY, etc.)
- **trade_delta**: Price adjustment for sell orders ($0.05)
- **max_trade_value**: Maximum dollar amount per trade
- **runner**: Number of contracts to keep on profitable exits
- **risk_levels**: Tiered risk management configuration

## Testing

### Test Script

Run the test script to verify functionality:

```bash
python test_trading_features.py
```

### Test Coverage

- Order quantity calculations
- Hotkey detection and execution
- Position management
- Risk level calculations
- Chase logic simulation

## Safety Features

### Pre-Trade Validation

- **Connection Check**: Verifies IB connection before placing orders
- **Data Validation**: Ensures all required market data is available
- **Position Check**: Validates one active position rule
- **Risk Validation**: Confirms order size within risk limits

### Post-Trade Monitoring

- **Order Status**: Tracks order submission and execution
- **Position Updates**: Monitors position changes
- **Error Recovery**: Handles partial fills and failed orders
- **Logging**: Comprehensive audit trail of all trading activity

## Usage Examples

### Basic Trading Workflow

1. **Setup**: Configure trading parameters in settings
2. **Monitor**: Watch real-time market data
3. **Execute**: Use hotkeys for instant order placement
4. **Manage**: Monitor positions and use chase logic for exits

### Hotkey Usage

```
Ctrl+Alt+C  → Buy call option
Ctrl+Alt+P  → Buy put option  
Ctrl+Alt+X  → Sell position with chase logic
Ctrl+Alt+F  → Panic button (flatten all risk)
```

### Advanced Features

- **Automatic Expiration**: System selects correct contract expiration
- **Intelligent Sizing**: Risk-based position sizing
- **Smart Exits**: Runner logic for profitable trades
- **Risk Controls**: Multi-tiered risk management

## Troubleshooting

### Common Issues

1. **Hotkeys Not Working**
   - Check if application has focus
   - Verify platform-specific modifier keys
   - Check system permissions for global hotkeys

2. **Orders Not Placing**
   - Verify IB connection status
   - Check account permissions
   - Ensure sufficient buying power

3. **Chase Logic Issues**
   - Monitor order status in logs
   - Check market data availability
   - Verify trade delta settings

### Logging

All trading activity is logged with detailed information:

- Order placement and execution
- Position changes and P&L updates
- Risk calculations and validations
- Error conditions and recovery actions

## Future Enhancements

### Planned Features

- **Bracket Orders**: Automatic stop-loss and take-profit orders
- **Advanced Algos**: Additional IB algorithm support
- **Position Scaling**: Dynamic position sizing based on volatility
- **Risk Analytics**: Enhanced risk reporting and analysis
- **Mobile Support**: Remote trading capabilities

### Integration Opportunities

- **External Signals**: API for external trading signals
- **Backtesting**: Historical strategy testing
- **Portfolio Management**: Multi-strategy support
- **Reporting**: Enhanced trade and performance reporting
