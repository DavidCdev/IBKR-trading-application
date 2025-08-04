
# Documentation: ConfigManager

## 1. Introduction

This document provides a comprehensive overview of the `ConfigManager` class, a Python module responsible for handling all application settings. Its primary role is to load configuration from a `config.json` file, provide a simple interface for other modules to access these settings, and save any changes back to the file.

The `ConfigManager` is designed to be robust. It automatically creates a default configuration file if one doesn't exist, ensuring the application can run smoothly on its first launch. It also intelligently locates the `config.json` file in its own directory, making the application portable and independent of the directory from which it is launched.

## 2. Prompt Context for AI Assistants

Copy and paste the text below into your AI assistant to provide it with a concise but comprehensive context of the `config_manager.py` file.

**File:** `config_manager.py`

**Summary:** This file defines the `ConfigManager` class, which handles loading, accessing, and saving application settings from a `config.json` file. It is a critical component for centralizing application configuration.

**Architecture & Features:**

-   **File-Based:** Manages settings stored in a `config.json` file.
    
-   **Robust Pathing:** Automatically locates `config.json` in the same directory as the script, making it independent of the current working directory.
    
-   **Default Config Generation:** If `config.json` is not found, it creates a default version, preventing errors on first run.
    
-   **Event Bus Integration:** Can be initialized with an event bus. If provided, it will emit a `config_updated` event every time `save_config()` is called, allowing other modules (like the GUI) to react to changes.
    
-   **Standalone Debug Mode:** The file can be run directly (`python config_manager.py`) to test its functionality. The debug mode is non-destructive and will restore the original configuration after testing.
    

**Public API - Methods:**

-   `__init__(config_path=None, event_bus=None)`: Initializes the manager. `config_path` is optional and defaults to `config.json` in the script's directory.
    
-   `load_config()`: Loads settings from the file into memory.
    
-   `get(section, key, default=None)`: Retrieves a specific setting.
    
-   `set(section, key, value)`: Changes a setting in memory.
    
-   `save_config()`: Writes the current settings from memory to the `config.json` file and emits the `config_updated` event.
    
-   `get_available_modules(self) -> list`: Returns a list of all available Python modules discovered in the src directory.
    
-   `get_log_levels(self) -> dict`: Returns the current log level settings for all modules.
    
-   `set_log_level(self, module_name: str, log_level: str)`: Sets the log level for a specific module.
    

## 3. Class Methods Breakdown

### Public API

These methods are the intended interface for interacting with the `ConfigManager` from other parts of your application.

-   `__init__(self, config_path=None, event_bus=None)`
    
    -   **Purpose:** Initializes the `ConfigManager` instance.
        
    -   **Parameters:**
        
        -   `config_path` (str, optional): The full path to the configuration file. If `None`, it defaults to `config.json` in the same directory as `config_manager.py`.
            
        -   `event_bus` (object, optional): An instance of your event bus. If provided, the manager will use it to emit update notifications.
            
    -   **Behavior:** Upon initialization, it immediately calls `self.load_config()` to load settings into memory.
        
-   `load_config(self)`
    
    -   **Purpose:** Reads the JSON file from disk and loads its contents.
        
    -   **Behavior:** If the file specified by `self.config_path` does not exist, it calls `_create_default_config()`. If the file is corrupted or not valid JSON, it prints an error and creates a default configuration to prevent the application from crashing.
        
-   `get(self, section, key, default=None)`
    
    -   **Purpose:** Safely retrieves a configuration value.
        
    -   **Parameters:**
        
        -   `section` (str): The top-level key in the JSON file (e.g., `"connection"`).
            
        -   `key` (str): The key within the section whose value you want to retrieve (e.g., `"host"`).
            
        -   `default` (any, optional): The value to return if the section or key is not found. Defaults to `None`.
            
    -   **Returns:** The requested value or the provided default.
        
-   `set(self, section, key, value)`
    
    -   **Purpose:** Updates a configuration value in memory. **This does not save the file.**
        
    -   **Behavior:** Changes are held in memory until `save_config()` is called. This is useful for making multiple changes before writing to disk once.
        
-   `save_config(self)`
    
    -   **Purpose:** Persists all in-memory settings to the `config.json` file.
        
    -   **Behavior:** It writes the current state of `self.config` to the file with human-readable indentation. If an `event_bus` was provided during initialization, it will emit a `"config_updated"` event after a successful save.
        
-   `get_available_modules(self) -> list`
    
    -   **Purpose:** Returns a list of all available Python modules discovered in the src directory.
        
    -   **Returns:** List of module names in uppercase (e.g., ["GUI", "EVENT_BUS", "CONFIG_MANAGER"]).
        
    -   **Behavior:** Dynamically scans the src directory for .py files and returns their names as module identifiers. This is useful for building UI components that need to know which modules can be configured.
        
-   `get_log_levels(self) -> dict`
    
    -   **Purpose:** Returns the current log level settings for all modules.
        
    -   **Returns:** Dictionary mapping module names to their current log level strings.
        
    -   **Behavior:** Returns the current state of log level configuration from the 'debug' section of the config.
        
-   `set_log_level(self, module_name: str, log_level: str)`
    
    -   **Purpose:** Sets the log level for a specific module.
        
    -   **Parameters:**
        
        -   `module_name` (str): The name of the module (will be converted to uppercase).
            
        -   `log_level` (str): The new log level (e.g., "Debug", "Info", "Warn").
            
    -   **Behavior:** Updates the log level for the specified module in the configuration. The change is made in memory and should be persisted by calling `save_config()`.

### Private Methods

These methods are used internally and should not be called from outside the class.

-   `_create_default_config(self)`
    
    -   **Purpose:** Generates a default configuration dictionary and immediately saves it to a new `config.json` file.
        
    -   **Behavior:** This is the fallback mechanism that ensures the application always has a valid configuration to work with.
        
-   `_discover_python_modules(self) -> list`
    
    -   **Purpose:** Dynamically discovers all Python modules in the src directory.
        
    -   **Returns:** List of module names (without .py extension) in uppercase.
        
    -   **Behavior:** Scans the src directory for .py files and returns their names as module identifiers.
        
-   `_update_config_with_new_modules(self)`
    
    -   **Purpose:** Updates the configuration with any new modules that have been added since the config was created.
        
    -   **Behavior:** Compares discovered modules with those in the config, adds new ones with default log levels, and removes non-existent ones. This ensures the configuration stays synchronized with the actual codebase.
        
-   `_discover_python_modules(self) -> list`
    
    -   **Purpose:** Dynamically discovers all Python modules in the src directory.
        
    -   **Returns:** List of module names (without .py extension) in uppercase.
        
    -   **Behavior:** Scans the src directory for .py files and returns their names as module identifiers. Excludes `__init__.py` and `logger.py` from the discovery process.


## 4. Standalone Debug Mode

The `config_manager.py` file can be executed directly from the command line to test its core functionality.

**Command:** `python config_manager.py`

When run, the script will perform the following actions to verify its behavior without permanently altering your settings:

1.  **Initialize:** It creates an instance of `ConfigManager`, which automatically loads `config.json` or creates it if missing.
    
2.  **Read:** It reads and prints the current `underlying_symbol`.
    
3.  **Modify & Save:** It changes the symbol to a different value (e.g., "SPY" -> "QQQ") and calls `save_config()` to write this temporary change to the file.
    
4.  **Verify:** It creates a _new_ `ConfigManager` instance to reload the file from disk and confirms that the new value was written correctly.
    
5.  **Restore:** It immediately sets the symbol back to its original value and saves the file again, ensuring the test is non-destructive.
    

This standalone mode is invaluable for quickly testing the file I/O and data access logic without needing to run the full application.