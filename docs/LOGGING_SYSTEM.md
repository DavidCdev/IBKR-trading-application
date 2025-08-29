# Centralized Logging System

## Overview

The IB Trading Application now features a centralized, dynamically configurable logging system that provides comprehensive logging capabilities across all modules with real-time configuration changes via the GUI.

## 🎯 Key Features

- **Module Auto-Discovery**: Automatically scans and discovers Python modules
- **Real-Time Configuration**: Change log levels without restarting the application
- **Centralized Management**: Single point of control for all logging
- **GUI Integration**: Control logging verbosity through the settings interface
- **Performance Monitoring**: Built-in performance and trade event logging
- **Log Rotation**: Automatic log file rotation with size limits
- **Master Debug Control**: Complete logging enable/disable with master debug setting

## 🏗️ Architecture

### Core Components

1. **LoggerManager**: Singleton class managing all loggers
2. **LogLevelEnum**: Standardized logging levels
3. **Module Discovery**: Automatic scanning of source files
4. **Configuration Integration**: Seamless integration with ConfigManager

### Logging Levels

| Level | Python Equivalent | Description |
|-------|------------------|-------------|
| TRACE | logging.DEBUG | Detailed debugging information |
| DEBUG | logging.DEBUG | General debugging information |
| INFO | logging.INFO | General information messages |
| WARN | logging.WARNING | Warning messages |
| ERROR | logging.ERROR | Error messages |
| FATAL | logging.CRITICAL | Critical errors |

## 🚀 Usage

### Basic Logger Usage

```python
from utils.logger import get_logger

# Get a logger for your module
logger = get_logger("MODULE_NAME")

# Use standard logging methods
logger.info("Information message")
logger.debug("Debug message")
logger.warning("Warning message")
logger.error("Error message")
```

### Module Naming Convention

- Use UPPERCASE for module names
- Common modules: `MAIN`, `GUI`, `IB_CONNECTION`, `DATA_COLLECTOR`
- Auto-discovered from file paths

### Performance Logging

```python
from utils.logger import log_performance

# Log performance metrics
log_performance("operation_name", duration_seconds, param1="value1")
```

### Trade Event Logging

```python
from utils.logger import log_trade_event

# Log trading events
log_trade_event("BUY", "AAPL", 100, 150.50, order_id="12345")
```

## 🔧 API Reference

### Core Functions

#### `initialize_logger_manager(config)`
Initialize the logging system with configuration.

**Parameters:**
- `config`: AppConfig object containing logging settings

#### `get_logger(module_name)`
Get a logger instance for a specific module.

**Parameters:**
- `module_name`: Name of the module (string)

**Returns:**
- Configured logging.Logger instance

#### `update_log_levels(log_level_dict)`
Update log levels for modules at runtime.

**Parameters:**
- `log_level_dict`: Dictionary mapping module names to log levels

**Example:**
```python
update_log_levels({
    "GUI": "DEBUG",
    "IB_CONNECTION": "TRACE"
})
```

#### `get_available_modules()`
Get list of all discovered modules.

**Returns:**
- List of module names

#### `get_all_log_levels()`
Get current log level for each module.

**Returns:**
- Dictionary mapping module names to current log levels

#### `get_module_log_level(module_name)`
Get current log level for a specific module.

**Parameters:**
- `module_name`: Name of the module

**Returns:**
- Current log level as string

### Master Debug Control Functions

#### `is_logging_enabled()`
Check if logging is currently enabled (master_debug is True).

**Returns:**
- Boolean indicating if logging is enabled

#### `get_master_debug_status()`
Get the current master debug status.

**Returns:**
- Boolean indicating master debug status

#### `force_logging_control(enable)`
Force enable/disable logging (for testing purposes).

**Parameters:**
- `enable`: Boolean to enable (True) or disable (False) logging

### Convenience Functions

#### `log_performance(operation, duration, **kwargs)`
Log performance metrics with context.

#### `log_trade_event(event_type, symbol, quantity, price, **kwargs)`
Log trading events with structured data.

#### `log_connection_event(event_type, host, port, status, **kwargs)`
Log connection events.

#### `log_error_with_context(error, context, **kwargs)`
Log errors with additional context.

## ⚙️ Configuration

### Configuration File (config.json)

```json
{
  "debug": {
    "master_debug": true,
    "modules": {
      "MAIN": "INFO",
      "GUI": "DEBUG",
      "IB_CONNECTION": "TRACE",
      "DATA_COLLECTOR": "INFO",
      "CONFIG_MANAGER": "TRACE",
      "AI_ENGINE": "INFO",
      "TRADING_MANAGER": "INFO"
    }
  }
}
```

### Configuration Options

- **master_debug**: Enable/disable debug logging globally
- **modules**: Per-module log level configuration
- **Log Levels**: TRACE, DEBUG, INFO, WARN, ERROR, FATAL

## 🔧 Master Debug Control

The logging system includes a master debug control feature that allows you to completely enable or disable all logging (except critical errors) through the `master_debug` setting.

### How It Works

When `master_debug` is set to `false`:
- All logging is immediately stopped
- Only critical error messages are preserved
- All log handlers (except error handlers) are removed
- Module log level changes are ignored
- Performance, trade, and connection event logging is disabled

When `master_debug` is set to `true`:
- All logging is restored to previous levels
- Module-specific log levels are reapplied
- All logging handlers are restored

### Usage

```python
from utils.logger import is_logging_enabled, get_master_debug_status

# Check if logging is currently enabled
if is_logging_enabled():
    logger.info("Logging is active")
else:
    print("Logging is disabled")

# Get the current master debug status
status = get_master_debug_status()
print(f"Master debug is {'enabled' if status else 'disabled'}")
```

### Force Control (Advanced)

For testing or emergency situations, you can force enable/disable logging:

```python
from utils.logger import force_logging_control

# Force disable all logging
force_logging_control(False)

# Force enable all logging
force_logging_control(True)
```

**Note**: Force control bypasses the configuration and should be used sparingly.

## 🖥️ GUI Integration

### Settings Form

The settings form automatically provides:
- Dropdown menus for each module's log level
- Real-time updates when levels are changed
- Automatic configuration saving
- Visual feedback for current settings

### Real-Time Updates

1. User changes log level in GUI
2. LoggerManager immediately applies the change
3. Configuration is saved to disk
4. All future log messages use the new level

## 📁 Log Files

### File Structure

```
logs/
├── trading_app.log      # Main application log
├── errors.log          # Error-only log
├── debug.log           # Debug log (if enabled)
└── performance.log     # Performance metrics
```

### Log Rotation

- **Main Log**: 10MB max, 5 backup files
- **Error Log**: 5MB max, 3 backup files
- **Debug Log**: 20MB max, 3 backup files
- **Performance Log**: 5MB max, 2 backup files

## 🔄 Migration from Smart Logger

### Before (Smart Logger)
```python
from utils.smart_logger import get_logger
logger = get_logger("MODULE_NAME")
```

### After (New Logger)
```python
from utils.logger import get_logger
logger = get_logger("MODULE_NAME")
```

**Note**: The API is identical, so existing code continues to work.

## 🧪 Testing

Run the test script to verify the logging system:

```bash
python test_logger.py
```

This will test:
- Configuration loading
- Module discovery
- Logger creation
- Log level updates
- Performance logging

## 🚨 Troubleshooting

### Common Issues

1. **Module not found**: Ensure module name is in UPPERCASE
2. **Log level not applied**: Check configuration file format
3. **No log output**: Verify master_debug is enabled

### Debug Mode

Enable TRACE level for LOGGER_MANAGER module to see detailed logging system information.

## 📈 Performance Considerations

- **Memory**: Minimal overhead per logger
- **File I/O**: Asynchronous logging with rotation
- **Configuration**: Cached for fast access
- **Updates**: Real-time without performance impact

## 🔮 Future Enhancements

- **Remote Logging**: Send logs to external systems
- **Log Analytics**: Built-in log analysis tools
- **Custom Formatters**: User-defined log formats
- **Log Compression**: Automatic log compression
- **Alerting**: Log-based alerting system

## 📚 Examples

### Complete Module Example

```python
from utils.logger import get_logger

class MyModule:
    def __init__(self):
        self.logger = get_logger("MY_MODULE")
        self.logger.info("MyModule initialized")
    
    def process_data(self, data):
        self.logger.debug(f"Processing data: {len(data)} items")
        try:
            # Process data
            result = self._process(data)
            self.logger.info(f"Data processed successfully: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Failed to process data: {e}")
            raise
```

### Performance Monitoring Example

```python
import time
from utils.logger import log_performance

def expensive_operation():
    start_time = time.time()
    
    # ... perform operation ...
    
    duration = time.time() - start_time
    log_performance("expensive_operation", duration, 
                   input_size=1000, 
                   result_count=500)
```

## ✅ Implementation Status

### Completed Features
- [x] Core logging system architecture
- [x] Module auto-discovery (47+ modules discovered)
- [x] Real-time configuration updates
- [x] GUI integration with settings form
- [x] File rotation and management
- [x] Performance logging functions
- [x] Configuration integration
- [x] Backward compatibility
- [x] Comprehensive testing
- [x] Production deployment

### Current Capabilities
- **Module Discovery**: Automatically discovers 47+ Python modules
- **Real-Time Control**: Change log levels via GUI without restarts
- **Performance Monitoring**: Built-in performance and trade logging
- **File Management**: Automatic log rotation with configurable limits
- **GUI Integration**: Seamless integration with settings interface

This logging system provides a robust foundation for application monitoring, debugging, and operational insight across the entire IB Trading Application.
