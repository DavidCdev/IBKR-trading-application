# Documentation: Logger

## 1. Introduction

This document provides a comprehensive overview of the `logger.py` module, which implements a centralized logging system for the trading application. The logger provides dynamic log level control, module-specific logging, and integration with the configuration manager to allow runtime adjustment of logging verbosity.

The logging system is designed to be flexible and configurable. It automatically discovers all Python modules in the application, creates individual loggers for each module, and allows fine-grained control over log levels through the configuration system. This enables developers to enable detailed debugging for specific components while keeping other modules at minimal verbosity.

## 2. Prompt Context for AI Assistants

Copy and paste the text below into your AI assistant to provide it with a concise but comprehensive context of the `logger.py` file.

**File:** `logger.py`

**Summary:** This file implements a centralized logging system with dynamic log level control. It provides module-specific loggers that can be configured through the application's configuration manager, allowing runtime adjustment of logging verbosity without restarting the application.

**Architecture & Features:**

-   **Module Discovery:** Automatically discovers all Python modules in the src directory and creates individual loggers for each.
    
-   **Dynamic Configuration:** Log levels can be changed at runtime through the configuration manager, with changes taking effect immediately.
    
-   **Enum-Based Levels:** Uses a custom `LogLevel` enum that maps to Python's standard logging levels for consistency.
    
-   **Global Interface:** Provides a simple `get_logger(module_name)` function that modules can use to get their configured logger.
    
-   **Configuration Integration:** Integrates with the `ConfigManager` to read and write log level settings.
    
-   **Thread-Safe:** All logging operations are thread-safe and can be used from any thread in the application.
    

**Public API - Functions:**

-   `get_logger(module_name)`: Returns a configured logger for the specified module.
    
-   `initialize_logger_manager(config_manager)`: Initializes the global logger manager with configuration.
    
-   `update_log_levels(log_levels)`: Updates log levels for multiple modules at once.
    
-   `get_available_modules()`: Returns a list of all available modules that can be logged.
    
-   `get_all_log_levels()`: Returns the current log levels for all modules as strings.
    

**Public API - Classes:**

-   `LogLevel(Enum)`: Enumeration of available log levels (Trace, Debug, Info, Warn, Error, Fatal).
    
-   `LoggerManager`: Manages all loggers and their configurations.
    

## 3. Architecture & Design

The logging system is built around a central `LoggerManager` class that coordinates all logging operations. The system follows a singleton pattern where a single global instance manages all module loggers.

### Module Discovery

The system automatically discovers all Python modules in the `src` directory by scanning for `.py` files. This ensures that new modules are automatically included in the logging system without manual configuration.

### Log Level Management

The system uses a custom `LogLevel` enum that provides a consistent interface across the application:

- **Trace**: Maps to Python's DEBUG level, for very detailed diagnostic information
- **Debug**: Maps to Python's DEBUG level, for diagnostic information
- **Info**: Maps to Python's INFO level, for general information
- **Warn**: Maps to Python's WARNING level, for warning messages
- **Error**: Maps to Python's ERROR level, for error messages
- **Fatal**: Maps to Python's CRITICAL level, for critical errors

### Configuration Integration

The logger manager integrates with the `ConfigManager` to read log level settings from the configuration file. The configuration structure for logging is:

```json
{
  "debug": {
    "master_debug": false,
    "modules": {
      "GUI": "Info",
      "EVENT_BUS": "Debug",
      "CONFIG_MANAGER": "Info",
      "MAIN": "Info"
    }
  }
}
```

## 4. Public API Reference

### Global Functions

These functions provide the main interface for modules to interact with the logging system.

#### `get_logger(module_name: str) -> logging.Logger`

-   **Description:** Returns a configured logger for the specified module.
    
-   **Parameters:**
    
    -   `module_name` (str): The name of the module (will be converted to uppercase).
        
-   **Returns:** A configured `logging.Logger` instance for the module.
    
-   **Usage:** This is the primary function that modules should use to get their logger.
    
    ```python
    from logger import get_logger
    
    logger = get_logger('GUI')
    logger.info("GUI initialized successfully")
    ```

#### `initialize_logger_manager(config_manager)`

-   **Description:** Initializes the global logger manager with configuration.
    
-   **Parameters:**
    
    -   `config_manager`: The configuration manager instance to read log settings from.
        
-   **Usage:** This should be called once at application startup to configure the logging system.
    
    ```python
    from logger import initialize_logger_manager
    
    initialize_logger_manager(config_manager)
    ```

#### `update_log_levels(log_levels: Dict[str, str])`

-   **Description:** Updates log levels for multiple modules at once.
    
-   **Parameters:**
    
    -   `log_levels` (Dict[str, str]): Dictionary mapping module names to log level strings.
        
-   **Usage:** This is typically called when the configuration is updated.
    
    ```python
    from logger import update_log_levels
    
    new_levels = {
        "GUI": "Debug",
        "EVENT_BUS": "Info"
    }
    update_log_levels(new_levels)
    ```

#### `get_available_modules() -> list`

-   **Description:** Returns a list of all available modules that can be logged.
    
-   **Returns:** List of module names (uppercase).
    
-   **Usage:** Useful for building UI components that allow log level configuration.
    
    ```python
    from logger import get_available_modules
    
    modules = get_available_modules()
    print(f"Available modules: {modules}")
    ```

#### `get_all_log_levels() -> Dict[str, str]`

-   **Description:** Returns the current log levels for all modules as strings.
    
-   **Returns:** Dictionary mapping module names to log level strings.
    
-   **Usage:** Useful for saving current log levels to configuration.
    
    ```python
    from logger import get_all_log_levels
    
    current_levels = get_all_log_levels()
    print(f"Current log levels: {current_levels}")
    ```

### Classes

#### `LogLevel(Enum)`

-   **Description:** Enumeration of available log levels.
    
-   **Values:**
    
    -   `TRACE`: Very detailed diagnostic information
    -   `DEBUG`: Diagnostic information
    -   `INFO`: General information
    -   `WARN`: Warning messages
    -   `ERROR`: Error messages
    -   `FATAL`: Critical errors
    
-   **Usage:** Used when setting log levels programmatically.
    
    ```python
    from logger import LogLevel
    
    logger_manager.update_log_level("GUI", LogLevel.DEBUG)
    ```

#### `LoggerManager`

-   **Description:** Manages all loggers and their configurations.
    
-   **Methods:**
    
    -   `__init__(config_manager=None)`: Initializes the logger manager.
    -   `get_logger(module_name: str) -> logging.Logger`: Gets a logger for a module.
    -   `update_log_level(module_name: str, log_level: LogLevel)`: Updates log level for a module.
    -   `update_all_log_levels(log_levels: Dict[str, str])`: Updates log levels for multiple modules.
    -   `get_available_modules() -> list`: Gets list of all available modules.
    -   `get_module_log_level(module_name: str) -> LogLevel`: Gets current log level for a module.
    -   `get_all_log_levels() -> Dict[str, LogLevel]`: Gets all current log levels.

## 5. Configuration Integration

The logger system integrates seamlessly with the `ConfigManager` to provide persistent log level settings.

### Configuration Structure

The logger expects the following structure in the configuration file:

```json
{
  "debug": {
    "master_debug": false,
    "modules": {
      "GUI": "Info",
      "EVENT_BUS": "Debug",
      "CONFIG_MANAGER": "Info",
      "MAIN": "Info",
      "IB_CONNECTION": "Warn",
      "ACCOUNT_MANAGER": "Info"
    }
  }
}
```

### Automatic Module Discovery

When the logger manager is initialized, it automatically discovers all Python modules in the `src` directory and creates loggers for them. If a module exists in the codebase but not in the configuration, it will be added with a default log level of "Info".

### Runtime Configuration Updates

The logger system supports runtime updates to log levels. When the configuration is updated through the GUI or programmatically, the logger manager can be notified to update all log levels:

```python
# Example: Updating log levels from configuration changes
def on_config_update():
    new_levels = config_manager.get('debug', 'modules', {})
    update_log_levels(new_levels)
```

## 6. Usage Examples

### Basic Usage in a Module

```python
# In any module (e.g., gui.py)
from logger import get_logger

logger = get_logger('GUI')

class IBTradingGUI:
    def __init__(self):
        logger.info("Initializing GUI...")
        # ... initialization code ...
        logger.debug("GUI initialization complete")
    
    def update_price(self, price):
        logger.debug(f"Updating price to {price}")
        # ... update logic ...
        logger.info(f"Price updated successfully to {price}")
```

### Application Startup

```python
# In main.py
from logger import get_logger, initialize_logger_manager
from config_manager import ConfigManager

logger = get_logger('MAIN')

def main():
    # Initialize configuration
    config_manager = ConfigManager()
    
    # Initialize logger with configuration
    initialize_logger_manager(config_manager)
    
    logger.info("Application starting...")
    # ... rest of application startup ...
```

### Dynamic Log Level Changes

```python
# Example: Changing log levels at runtime
from logger import update_log_levels

def enable_debug_mode():
    debug_levels = {
        "GUI": "Debug",
        "EVENT_BUS": "Debug",
        "CONFIG_MANAGER": "Debug"
    }
    update_log_levels(debug_levels)
    print("Debug mode enabled for all modules")
```

## 7. Best Practices

### Module Naming

- Use uppercase module names when calling `get_logger()`
- The logger will automatically convert module names to uppercase
- Use descriptive module names that match your file structure

### Log Level Selection

- **Trace/Debug**: Use for detailed diagnostic information during development
- **Info**: Use for general application flow and important state changes
- **Warn**: Use for potentially problematic situations that don't stop execution
- **Error**: Use for errors that prevent normal operation but don't crash the app
- **Fatal**: Use for critical errors that may cause application crashes

### Performance Considerations

- Logging calls are relatively expensive, so avoid logging in tight loops
- Use appropriate log levels to control verbosity in production
- Consider using `logger.isEnabledFor()` checks for expensive log operations

### Thread Safety

- All logging operations are thread-safe
- Multiple threads can safely call logging functions simultaneously
- The logger manager handles thread safety internally

## 8. Integration with Other Components

### GUI Integration

The GUI can display and modify log levels through the preferences window. The logger provides the necessary functions to:

- Get available modules: `get_available_modules()`
- Get current log levels: `get_all_log_levels()`
- Update log levels: `update_log_levels()`

### Config Manager Integration

The config manager automatically discovers new modules and adds them to the configuration with default log levels. This ensures that all modules are properly configured for logging.

### Event Bus Integration

The logger can emit events when log levels are changed, allowing other components to react to logging configuration updates.

## 9. Debugging and Troubleshooting

### Common Issues

1. **Module not found**: Ensure the module file exists in the `src` directory
2. **Log levels not updating**: Check that `initialize_logger_manager()` was called with the config manager
3. **Too much logging**: Use the GUI to adjust log levels or modify the configuration file

### Debug Mode

The logger system includes built-in debugging capabilities. When `master_debug` is enabled in the configuration, additional debug information is logged about logger operations.

### Log File Output

The logger can be configured to output to files in addition to console output. This is useful for production environments where console access may be limited. 