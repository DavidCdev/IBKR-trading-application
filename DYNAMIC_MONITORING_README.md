# Dynamic Strike Price and Expiration Monitoring

This document describes the dynamic monitoring system implemented in the `IBDataCollector` class that automatically manages option subscriptions based on underlying price changes and time-based expiration switches.

## Features

### 1. Dynamic Strike Price Logic
- **Continuous Monitoring**: The system continuously monitors the underlying symbol's price
- **Automatic Strike Calculation**: Calculates the nearest strike price by rounding to the nearest whole number
  - Example: $522.48 → $522 option strike
  - Example: $522.51 → $523 option strike
- **Smart Resubscription**: When the nearest strike changes, automatically:
  - Unsubscribes from old strike's options
  - Subscribes to new strike's options
  - Maintains active market data subscriptions

### 2. Dynamic Expiration Logic
- **Time-Based Switching**: Monitors system time in EST (Eastern Standard Time)
- **Automatic Expiration Switch**: At 12:00:00 PM EST, automatically switches from 0DTE contracts to 1DTE contracts
- **Expiration Type Detection**: Identifies expiration types (0DTE, 1DTE, 2DTE, etc.)
- **Seamless Transition**: Maintains continuous data flow during expiration switches

## Implementation Details

### Core Components

#### 1. Monitoring Thread
- Runs in a separate daemon thread for non-blocking operation
- Checks for changes every second
- Handles both strike price and expiration monitoring

#### 2. Contract Caching
- Caches option contracts for quick resubscription
- Reduces API calls during dynamic switches
- Maintains contract metadata for efficient updates

#### 3. Smart Subscription Management
- Tracks active market data subscriptions
- Automatically cancels old subscriptions
- Establishes new subscriptions seamlessly

### Key Methods

#### `start_dynamic_monitoring()`
- Starts the continuous monitoring thread
- Automatically called after successful IB connection

#### `stop_dynamic_monitoring()`
- Stops the monitoring thread
- Called during disconnect for cleanup

#### `_switch_option_subscriptions(new_strike=None, new_expiration=None)`
- Core method for switching subscriptions
- Handles both strike and expiration changes
- Manages subscription lifecycle

#### `manual_trigger_update(update_type, value=None)`
- Manual trigger for testing and debugging
- Supports 'strike', 'expiration', and 'status' updates

## Usage

### Automatic Operation
The system operates automatically once connected:

```python
# Create and connect IB collector
ib_collector = IBDataCollector(trading_config=trading_config)
await ib_collector.connect()  # Automatically starts dynamic monitoring

# The system will now automatically:
# 1. Monitor underlying price changes
# 2. Switch strikes when price crosses threshold
# 3. Switch expirations at 12:00 PM EST
```

### Manual Control
For testing and manual control:

```python
# Check monitoring status
ib_collector.log_dynamic_monitoring_status()

# Manually trigger strike update
await ib_collector.manual_trigger_update('strike')

# Manually trigger expiration update
await ib_collector.manual_trigger_update('expiration')

# Get detailed status
status = ib_collector.get_dynamic_monitoring_status()
```

### Configuration
The system uses the existing trading configuration:

```python
trading_config = {
    'underlying_symbol': 'SPY'  # Symbol to monitor
}
```

## Monitoring and Logging

### Status Information
The system provides comprehensive status information:

- Current strike price and previous strike
- Current expiration and expiration type
- Underlying symbol price
- Available expirations
- Cached contracts count
- Active subscriptions count
- Monitor thread status

### Logging
All dynamic changes are logged with detailed information:

```
INFO - Strike price changed from 522 to 523
INFO - Switching from 0DTE (20241220) to 1DTE (20241221) at 12:00 PM EST
INFO - Successfully subscribed to new options for strike 523, expiration 20241221
```

## Testing

Use the provided test script to verify functionality:

```bash
python test_dynamic_monitoring.py
```

The test script will:
1. Connect to IB
2. Start dynamic monitoring
3. Test manual updates
4. Monitor for automatic changes
5. Display status information

## Error Handling

The system includes comprehensive error handling:

- **Connection Failures**: Graceful fallback and retry logic
- **API Errors**: Logging and recovery mechanisms
- **Invalid Data**: Validation and fallback options
- **Thread Safety**: Proper synchronization for async operations

## Performance Considerations

- **Efficient Monitoring**: 1-second check intervals with error backoff
- **Contract Caching**: Reduces API calls during switches
- **Async Operations**: Non-blocking subscription management
- **Resource Cleanup**: Automatic cleanup of old subscriptions

## Dependencies

- `pytz`: Timezone handling for EST calculations
- `threading`: Background monitoring thread
- `asyncio`: Async operation support
- `ib_async`: Interactive Brokers API

## Troubleshooting

### Common Issues

1. **Monitoring Not Starting**
   - Check IB connection status
   - Verify trading configuration
   - Check logs for connection errors

2. **Strikes Not Updating**
   - Verify underlying price is being received
   - Check strike calculation logic
   - Review subscription switching logs

3. **Expiration Not Switching**
   - Verify EST timezone is correct
   - Check available expirations
   - Review 12:00 PM EST logic

### Debug Commands

```python
# Get detailed status
status = ib_collector.get_dynamic_monitoring_status()

# Log current state
ib_collector.log_dynamic_monitoring_status()

# Test manual updates
await ib_collector.manual_trigger_update('status')
```

## Future Enhancements

Potential improvements for future versions:

1. **Configurable Thresholds**: User-defined strike change thresholds
2. **Multiple Symbol Support**: Monitor multiple underlying symbols
3. **Advanced Expiration Logic**: Custom expiration switching rules
4. **Performance Metrics**: Monitoring performance and optimization
5. **Web Interface**: Real-time status dashboard

## Support

For issues or questions regarding the dynamic monitoring system:

1. Check the logs for detailed error information
2. Use the status methods to diagnose issues
3. Review the test script for usage examples
4. Verify IB connection and configuration settings
