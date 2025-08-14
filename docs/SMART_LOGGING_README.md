# Smart Logging System for IB Trading Application

## Overview

The Smart Logging System is a comprehensive logging solution designed specifically for the IB Trading Application. It replaces the basic logging configuration with a sophisticated, configurable, and performance-oriented logging system.

## Features

### 🎯 **Centralized Configuration**
- Loads logging settings from `config.json`
- Different log levels per module
- Master debug switch for global debug control

### 📁 **Organized Log Files**
- **`logs/trading_app.log`** - Main application log (10MB rotation, 5 backups)
- **`logs/errors.log`** - Error-only log (5MB rotation, 3 backups)
- **`logs/debug.log`** - Debug log (20MB rotation, 3 backups, only when debug enabled)
- **`logs/performance.log`** - Performance metrics (5MB rotation, 2 backups)

### ⚡ **Performance Monitoring**
- Automatic function execution time tracking
- Configurable thresholds for performance alerts
- Support for both sync and async functions
- Manual performance monitoring capabilities

### 📊 **Structured Logging**
- Trading events with standardized format
- Connection events with detailed context
- Error logging with rich context information
- Performance metrics with operation details

### 🔄 **Log Rotation**
- Automatic log file rotation based on size
- Configurable backup retention
- UTF-8 encoding support

## Quick Start

### 1. Basic Usage

```python
from utils.smart_logger import get_logger

# Get a logger for your module
logger = get_logger("YOUR_MODULE_NAME")

# Use standard logging methods
logger.info("Application started")
logger.warning("Connection timeout")
logger.error("Failed to process trade")
logger.debug("Debug information")
```

### 2. Performance Monitoring

```python
from utils.performance_monitor import monitor_function, monitor_async_function

# Monitor function execution time
@monitor_function("operation_name", threshold_ms=100)
def your_function():
    # Your code here
    pass

# Monitor async function execution time
@monitor_async_function("async_operation", threshold_ms=50)
async def your_async_function():
    # Your async code here
    pass

# Manual performance monitoring
from utils.performance_monitor import start_monitor, stop_monitor

monitor_id = start_monitor("manual_operation")
# ... do work ...
duration = stop_monitor(monitor_id, context_data="additional info")
```

### 3. Structured Logging

```python
from utils.smart_logger import (
    log_trade_event,
    log_connection_event,
    log_error_with_context
)

# Log trading events
log_trade_event(
    event_type="ORDER_PLACED",
    symbol="SPY",
    quantity=100,
    price=450.25,
    order_type="LIMIT",
    side="BUY"
)

# Log connection events
log_connection_event(
    event_type="CONNECT_SUCCESS",
    host="127.0.0.1",
    port=7497,
    status="Connected",
    connection_time_ms=1250
)

# Log errors with context
try:
    # Your code
    pass
except Exception as e:
    log_error_with_context(
        error=e,
        context="Processing market data",
        symbol="SPY",
        timestamp="2024-01-01T10:00:00"
    )
```

## Configuration

### config.json Structure

```json
{
    "debug": {
        "master_debug": true,
        "modules": {
            "MAIN": "INFO",
            "IB_CONNECTION": "DEBUG",
            "DATA_COLLECTOR": "INFO",
            "CONFIG_MANAGER": "INFO",
            "GUI": "INFO",
            "AI_ENGINE": "INFO"
        }
    }
}
```

### Log Levels
- **TRACE** - Most detailed logging (equivalent to DEBUG)
- **DEBUG** - Detailed debugging information
- **INFO** - General application flow
- **WARNING** - Something to be aware of
- **ERROR** - Something went wrong
- **CRITICAL** - Critical errors

## Migration Guide

### From Old Logging System

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
```

**After:**
```python
from utils.smart_logger import get_logger
logger = get_logger("MODULE_NAME")
logger.info("Message")
```

### Performance Monitoring Integration

**Before:**
```python
import time
start_time = time.time()
# ... your code ...
duration = time.time() - start_time
logger.info(f"Operation took {duration:.3f}s")
```

**After:**
```python
from utils.performance_monitor import monitor_function

@monitor_function("operation_name")
def your_function():
    # ... your code ...
    pass
```

## Advanced Features

### Custom Log Formatters

The system uses different formatters for different log types:

- **Detailed Formatter**: `%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s`
- **Simple Formatter**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

### Log File Management

```python
from utils.smart_logger import smart_logger

# Clean up old log files (older than 30 days)
smart_logger.cleanup_old_logs(days_to_keep=30)
```

### Performance Thresholds

Set performance thresholds to only log slow operations:

```python
@monitor_function("slow_operation", threshold_ms=1000)  # Only log if > 1 second
def slow_function():
    # This will only be logged if it takes more than 1 second
    pass
```

## Best Practices

### 1. Module Naming
Use consistent, descriptive module names:
- `MAIN` - Main application
- `IB_CONNECTION` - Interactive Brokers connection
- `DATA_COLLECTOR` - Data collection operations
- `GUI` - User interface components
- `TRADING` - Trading operations
- `PERFORMANCE` - Performance monitoring

### 2. Error Logging
Always include context when logging errors:

```python
try:
    # Your code
    pass
except Exception as e:
    log_error_with_context(
        error=e,
        context="What operation was being performed",
        additional_data="relevant context"
    )
```

### 3. Performance Monitoring
Use performance monitoring for:
- Database operations
- API calls
- File I/O operations
- Complex calculations
- Network operations

### 4. Log Levels
- **DEBUG**: Detailed information for debugging
- **INFO**: General application flow
- **WARNING**: Potential issues
- **ERROR**: Actual errors that need attention

## Example Usage

See `examples/smart_logging_example.py` for comprehensive examples of all features.

## Troubleshooting

### Common Issues

1. **Log files not created**
   - Check if the `logs` directory exists
   - Ensure write permissions

2. **Performance monitoring not working**
   - Verify decorator syntax
   - Check if threshold is set correctly

3. **Configuration not loading**
   - Ensure `config.json` exists and is valid JSON
   - Check file permissions

### Debug Mode

Enable debug mode in `config.json`:

```json
{
    "debug": {
        "master_debug": true,
        "modules": {
            "YOUR_MODULE": "DEBUG"
        }
    }
}
```

## Performance Impact

The smart logging system is designed to be lightweight:
- Minimal overhead for standard logging
- Performance monitoring adds ~1-2ms per monitored function
- Log rotation is handled asynchronously
- Configurable thresholds prevent log spam

## Future Enhancements

- Log aggregation and analysis tools
- Real-time log monitoring dashboard
- Integration with external logging services
- Advanced filtering and search capabilities
- Log compression and archival
