# IB Connection Documentation

## Overview

The IB Connection module provides a comprehensive interface for connecting to Interactive Brokers (IB) TWS or IB Gateway, managing real-time market data, and handling trading operations. The module is built around the `IBDataCollector` class which offers robust error handling, dynamic strike price and expiration monitoring, and efficient resource management.

## Key Features

- **Real-time Market Data**: Live streaming of underlying prices, option chains, and FX rates
- **Dynamic Strike Monitoring**: Automatic adjustment of option strikes based on underlying price changes
- **Smart Expiration Switching**: Intelligent expiration management with 0DTE/1DTE switching
- **Position Management**: Real-time P&L calculation and position tracking
- **Account Monitoring**: Account metrics, daily P&L, and high water mark tracking
- **Trade Statistics**: Comprehensive trade analysis and performance metrics
- **Error Handling**: Robust error handling with logging and recovery mechanisms
- **Resource Management**: Proper cleanup of subscriptions and connections

## Architecture

### Core Components

1. **IBDataCollector**: Main class handling all IB interactions
2. **TradingManager**: Manages trading operations and strategies
3. **Performance Monitoring**: Built-in performance tracking
4. **Smart Logger**: Comprehensive logging system

### Connection Management

The module supports both TWS and IB Gateway connections with configurable parameters:

```python
# Basic connection
collector = IBDataCollector(
    host='127.0.0.1',
    port=7497,  # 7497 for TWS, 4001 for IB Gateway
    clientId=1,
    timeout=30
)
```

## Class Reference

### IBDataCollector

The main class for IB data collection and management.

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | '127.0.0.1' | IB host address |
| `port` | int | 7497 | IB port (7497=TWS, 4001=Gateway) |
| `clientId` | int | 1 | Client ID for connection |
| `timeout` | int | 30 | Connection timeout in seconds |
| `trading_config` | dict | None | Trading configuration |
| `account_config` | dict | None | Account configuration |

#### Key Methods

##### Connection Management

```python
async def connect() -> bool
```
Establishes connection to IB with timeout and retry logic.

```python
def disconnect()
```
Safely disconnects from IB and cleans up resources.

##### Market Data

```python
async def get_underlying_symbol_price(symbol: str) -> Optional[float]
```
Gets real-time price for underlying symbol with automatic strike calculation.

```python
async def get_fx_ratio()
```
Gets current USD/CAD exchange rate.

```python
async def get_option_chain() -> pd.DataFrame
```
Retrieves option chain data for current strike and expiration.

##### Position Management

```python
async def get_active_positions(underlying_symbol) -> pd.DataFrame
```
Gets current positions with real-time P&L calculation.

```python
async def calculate_pnl_detailed(pos, underlying_symbol_price)
```
Calculates detailed P&L for a position.

##### Account Management

```python
async def get_account_metrics() -> pd.DataFrame
```
Retrieves account metrics including net liquidation, high water mark.

```python
async def get_trade_statistics() -> pd.DataFrame
```
Gets comprehensive trade statistics and performance metrics.

##### Data Collection

```python
async def collect_all_data() -> Optional[Dict[str, Any]]
```
Collects all market data, positions, and account information.

## Dynamic Monitoring

### Strike Price Monitoring

The system automatically monitors underlying price changes and adjusts option strikes:

```python
def _calculate_nearest_strike(self, price: float) -> int
```
Calculates nearest strike price by rounding to whole number.

```python
def _should_update_strike(self, new_strike: int) -> bool
```
Determines if strike price needs updating.

### Expiration Management

Smart expiration switching based on time and market conditions:

```python
def _should_switch_expiration_smart() -> bool
```
Determines if expiration should be switched based on:
- Current time (12:00 PM EST switch from 0DTE to 1DTE)
- Expiration validity
- Better expiration availability

```python
def _get_best_available_expiration(self, target_date: date = None) -> Optional[str]
```
Finds optimal expiration based on target date and availability.

### Monitoring Control

```python
def start_dynamic_monitoring()
```
Starts continuous monitoring thread.

```python
def stop_dynamic_monitoring()
```
Stops monitoring and cleans up resources.

```python
def get_dynamic_monitoring_status() -> Dict[str, Any]
```
Returns current monitoring status.

## Real-time Data Streaming

### Price Updates

The system provides real-time price updates through callback mechanisms:

```python
def _on_underlying_price_update(self, ticker, symbol=None)
```
Handles real-time underlying price updates with automatic strike adjustment.

```python
def _on_update_calloption(self, option_ticker)
```
Processes real-time call option data.

```python
def _on_update_putoption(self, option_ticker)
```
Processes real-time put option data.

### FX Rate Updates

```python
def _on_fx_ratio_update(self, ticker)
```
Handles USD/CAD exchange rate updates.

## Error Handling

### Connection Errors

- Automatic retry logic for connection failures
- Timeout handling with configurable limits
- Graceful degradation on connection loss

### Data Errors

- Fallback mechanisms for missing market data
- Validation of contract qualification
- Error logging with context

### Resource Cleanup

- Automatic subscription cleanup on disconnect
- Memory leak prevention
- Thread-safe operations

## Performance Monitoring

The module includes built-in performance monitoring:

```python
@monitor_async_function("IB_CONNECTION.connect", threshold_ms=5000)
async def connect(self) -> bool
```

```python
@monitor_function("IB_CONNECTION.disconnect")
def disconnect(self)
```

## Usage Examples

### Basic Setup

```python
from utils.ib_connection import IBDataCollector

# Initialize collector
collector = IBDataCollector(
    host='127.0.0.1',
    port=7497,
    clientId=1,
    trading_config={'underlying_symbol': 'SPY'},
    account_config={'high_water_mark': 100000}
)

# Connect to IB
await collector.connect()

# Collect all data
data = await collector.collect_all_data()
```

### Real-time Monitoring

```python
# Start dynamic monitoring
collector.start_dynamic_monitoring()

# Get monitoring status
status = collector.get_dynamic_monitoring_status()
print(f"Monitoring active: {status['monitoring_active']}")
print(f"Current strike: {status['current_strike']}")
print(f"Current expiration: {status['current_expiration']}")

# Manual expiration switch
collector.manual_expiration_switch("20241220")
```

### Position Tracking

```python
# Get active positions
positions = await collector.get_active_positions('SPY')

# Get account metrics
account_data = await collector.get_account_metrics()

# Get trade statistics
stats = await collector.get_trade_statistics()
```

### Historical Data

```python
# Get historical price data
historical_data = await collector.get_historical_data(
    symbol='SPY',
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)
```

## Configuration

### Trading Configuration

```python
trading_config = {
    'underlying_symbol': 'SPY',
    'option_strike': 500,
    'expiration': '20241220',
    'position_size': 100,
    'max_loss': 1000
}
```

### Account Configuration

```python
account_config = {
    'high_water_mark': 100000,
    'max_drawdown': 0.05,
    'risk_per_trade': 0.02
}
```

## Event Handling

The module supports various events for UI integration:

- `connection_success`: Connection established
- `connection_disconnected`: Connection lost
- `price_updated`: Underlying price change
- `fx_rate_updated`: FX rate change
- `calls_option_updated`: Call option data
- `puts_option_updated`: Put option data
- `account_summary_update`: Account metrics
- `daily_pnl_update`: Daily P&L
- `active_contracts_pnl_refreshed`: Position P&L
- `closed_trades_update`: Trade statistics

## Best Practices

1. **Connection Management**
   - Always use `disconnect()` to clean up resources
   - Handle connection errors gracefully
   - Use appropriate timeouts

2. **Data Handling**
   - Validate data before processing
   - Use error handling for missing data
   - Cache contracts for performance

3. **Monitoring**
   - Start dynamic monitoring after connection
   - Monitor system status regularly
   - Handle expiration switches appropriately

4. **Performance**
   - Limit active subscriptions
   - Use appropriate sleep intervals
   - Monitor memory usage

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Verify TWS/Gateway is running
   - Check port and client ID settings
   - Ensure API connections are enabled

2. **Missing Data**
   - Verify market data subscriptions
   - Check contract qualification
   - Validate symbol and expiration

3. **Performance Issues**
   - Monitor subscription count
   - Check for memory leaks
   - Verify thread safety

### Debug Information

```python
# Get detailed status
collector.log_dynamic_monitoring_status()

# Get expiration status
exp_status = collector.get_expiration_status()

# Check monitoring status
monitor_status = collector.get_dynamic_monitoring_status()
```

## Dependencies

- `ib_async`: IB API wrapper
- `pandas`: Data manipulation
- `pytz`: Timezone handling
- `asyncio`: Asynchronous operations
- `threading`: Background monitoring

## Version Compatibility

- Python 3.8+
- IB API 9.76+
- TWS/Gateway 9.76+

## License

This module is part of the IBKR trading system and follows the project's licensing terms.