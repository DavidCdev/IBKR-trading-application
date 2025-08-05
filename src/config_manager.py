import json
import os
import glob
from logger import get_available_modules, LogLevel, get_logger
from event_bus import EventPriority

logger = get_logger('CONFIG_MANAGER')

class ConfigManager:
    """
    Manages loading, accessing, and saving application settings from a JSON file.
    It locates the config file relative to its own script location, making it
    robust to being run from different working directories.
    """
    def __init__(self, config_path=None, event_bus=None):
        """
        Initializes the ConfigManager.

        Args:
            config_path (str, optional): The path to the JSON configuration file. 
                                         If None, defaults to 'config.json' in the same
                                         directory as this script.
            event_bus: An optional event bus instance to notify other components of changes.
        """
        logger.debug("Initializing ConfigManager")
        if config_path is None:
            # Get the absolute path to the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Join it with the default config file name to create a robust path
            self.config_path = os.path.join(script_dir, 'config.json')
            logger.debug(f"Using default config path: {self.config_path}")
        else:
            self.config_path = config_path
            logger.debug(f"Using custom config path: {self.config_path}")
            
        self.event_bus = event_bus
        if event_bus:
            logger.debug("Event bus provided for config notifications")
        else:
            logger.debug("No event bus provided")
            
        self.config = {}
        self._access_count = 0
        self._save_count = 0
        self.load_config()
        logger.info("ConfigManager initialized successfully")

    def _discover_python_modules(self) -> list:
        """
        Dynamically discover all Python modules in the src directory.
        
        Returns:
            List of module names (without .py extension)
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        python_files = glob.glob(os.path.join(script_dir, "*.py"))
        logger.debug(f"Found {len(python_files)} Python files in {script_dir}")
        
        modules = []
        for file_path in python_files:
            filename = os.path.basename(file_path)
            if filename != "__init__.py" and filename != "logger.py":
                module_name = os.path.splitext(filename)[0]
                modules.append(module_name.upper())
                logger.debug(f"Discovered module: {module_name.upper()}")
        
        logger.info(f"Discovered {len(modules)} modules: {modules}")
        return modules

    def _create_default_config(self):
        """
        Creates a default configuration structure if the config file is missing.
        This ensures the application can run successfully on the first launch.
        """
        logger.warning(f"Configuration file not found. Creating default '{self.config_path}'.")
        
        # Discover available modules
        discovered_modules = self._discover_python_modules()
        
        # Create default log levels for each module
        default_modules = {}
        for module in discovered_modules:
            default_modules[module] = "Info"  # Default to Info level
            logger.debug(f"Setting default log level 'Info' for module '{module}'")
        
        default_config = {
            "connection": {
                "host": "127.0.0.1",
                "port": 7497,
                "client_id": 1
            },
            "trading": {
                "underlying_symbol": "SPY",
                "risk_levels": [
                    {
                        "loss_threshold": "0",
                        "account_trade_limit": "30",
                        "stop_loss": "20",
                        "profit_gain": ""
                    },
                    {
                        "loss_threshold": "15",
                        "account_trade_limit": "10",
                        "stop_loss": "15",
                        "profit_gain": ""
                    },
                    {
                        "loss_threshold": "25",
                        "account_trade_limit": "5",
                        "stop_loss": "5",
                        "profit_gain": ""
                    }
                ],
                "max_trade_value": 500.0,
                "trade_delta": 0.05,
                "runner": 1
            },
            "debug": {
                "master_debug": False,
                "modules": default_modules
            }
        }
        self.config = default_config
        logger.debug("Default configuration created")
        self.save_config()

    def load_config(self):
        """
        Loads the configuration from the JSON file. If the file doesn't exist
        or is invalid, it creates a default configuration.
        """
        logger.debug(f"Loading configuration from '{self.config_path}'")
        
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file does not exist: {self.config_path}")
            self._create_default_config()
            return

        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            logger.debug(f"Successfully loaded config file ({len(self.config)} sections)")
                
            # Update config with any new modules that weren't in the original config
            self._update_config_with_new_modules()
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading config file '{self.config_path}': {e}. Loading default config.")
            self._create_default_config()

    def _update_config_with_new_modules(self):
        """
        Updates the config with any new modules that have been added since the config was created.
        This ensures the GUI will show all available modules.
        """
        logger.debug("Checking for new modules in config")
        discovered_modules = self._discover_python_modules()
        current_modules = self.config.get('debug', {}).get('modules', {})
        
        # Add any new modules that aren't in the config
        updated = False
        new_modules = []
        for module in discovered_modules:
            if module not in current_modules:
                current_modules[module] = "Info"  # Default to Info level
                new_modules.append(module)
                updated = True
                logger.debug(f"Added new module '{module}' with default log level 'Info'")
        
        # Remove any modules that no longer exist
        modules_to_remove = []
        for module in current_modules:
            if module not in discovered_modules:
                modules_to_remove.append(module)
        
        for module in modules_to_remove:
            del current_modules[module]
            updated = True
            logger.debug(f"Removed non-existent module '{module}' from config")
        
        if updated:
            logger.info(f"Updated config with new modules: {new_modules}")
            if modules_to_remove:
                logger.info(f"Removed modules: {modules_to_remove}")
            self.save_config()
        else:
            logger.debug("No module updates needed")

    def get(self, section, key, default=None):
        """
        Retrieves a configuration value safely.

        Args:
            section (str): The top-level section (e.g., 'trading').
            key (str): The key within the section.
            default: The value to return if the key is not found.

        Returns:
            The configuration value or the default.
        """
        self._access_count += 1
        logger.debug(f"Getting config value: [{section}][{key}] (access #{self._access_count})")
        
        value = self.config.get(section, {}).get(key, default)
        logger.debug(f"Config value [{section}][{key}] = {value}")
        return value

    def set(self, section, key, value):
        """
        Sets a configuration value in memory. Does not save to disk.
        Call save_config() to persist changes.

        Args:
            section (str): The top-level section.
            key (str): The key within the section.
            value: The new value to set.
        """
        logger.debug(f"Setting config value: [{section}][{key}] = {value}")
        
        if section not in self.config:
            self.config[section] = {}
            logger.debug(f"Created new config section '{section}'")
            
        old_value = self.config[section].get(key)
        self.config[section][key] = value
        
        if old_value != value:
            logger.debug(f"Value changed from '{old_value}' to '{value}'")
        else:
            logger.debug("Value unchanged")

    def save_config(self):
        """
        Saves the current configuration to the JSON file.
        """
        try:
            self._save_count += 1
            logger.debug(f"Saving configuration (save #{self._save_count})")
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to '{self.config_path}'.")
            
            # If an event bus is configured, emit an event to notify other
            # parts of the application that the configuration has changed.
            if self.event_bus:
                logger.debug("Emitting config_updated event")
                self.event_bus.emit("config_updated", {}, priority=EventPriority.LOW)
            else:
                logger.debug("No event bus available for config update notification")

        except IOError as e:
            logger.error(f"Error saving config file '{self.config_path}': {e}")

    def get_available_modules(self) -> list:
        """
        Get list of all available Python modules in the src directory.
        
        Returns:
            List of module names (uppercase)
        """
        logger.debug("Getting available modules")
        modules = self._discover_python_modules()
        logger.debug(f"Available modules: {modules}")
        return modules

    def get_log_levels(self) -> dict:
        """
        Get current log levels for all modules.
        
        Returns:
            Dictionary mapping module names to log level strings
        """
        log_levels = self.config.get('debug', {}).get('modules', {})
        logger.debug(f"Current log levels: {log_levels}")
        return log_levels

    def set_log_level(self, module_name: str, log_level: str):
        """
        Set log level for a specific module.
        
        Args:
            module_name: Name of the module
            log_level: Log level string (Trace, Debug, Info, Warn, Error, Fatal)
        """
        module_name = module_name.upper()
        logger.debug(f"Setting log level for '{module_name}' to '{log_level}'")
        
        modules = self.config.get('debug', {}).get('modules', {})
        old_level = modules.get(module_name)
        modules[module_name] = log_level
        self.config.setdefault('debug', {})['modules'] = modules
        
        if old_level != log_level:
            logger.info(f"Log level for '{module_name}' changed from '{old_level}' to '{log_level}'")
        else:
            logger.debug(f"Log level for '{module_name}' unchanged: '{log_level}'")

# This block allows the script to be run directly for testing purposes.
if __name__ == '__main__':
    print("--- Running ConfigManager in Standalone Debug Mode ---")
    
    # 1. Initialize the manager. It will automatically load or create config.json
    #    in the same directory as this script.
    config_mgr = ConfigManager()
    
    print(f"\nConfiguration loaded from: {config_mgr.config_path}")
    
    # 2. Display available modules
    print("\n--- Available Modules ---")
    modules = config_mgr.get_available_modules()
    print(f"Discovered modules: {modules}")
    
    # 3. Display current log levels
    print("\n--- Current Log Levels ---")
    log_levels = config_mgr.get_log_levels()
    for module, level in log_levels.items():
        print(f"{module}: {level}")
    
    # 4. Display a value from the loaded config
    print("\n--- Reading Initial Value ---")
    original_symbol = config_mgr.get('trading', 'underlying_symbol', 'N/A')
    print(f"Original underlying symbol: {original_symbol}")
    
    # 5. Change a value temporarily and save it
    print("\n--- Setting and Saving New Value ---")
    new_symbol = "QQQ" if original_symbol == "SPY" else "SPY"
    config_mgr.set('trading', 'underlying_symbol', new_symbol)
    config_mgr.save_config()
    print(f"Set underlying symbol to: {new_symbol}")
    
    # 6. Create a new instance to prove the change was persisted
    print("\n--- Verifying Persisted Change ---")
    new_config_mgr = ConfigManager()
    reloaded_symbol = new_config_mgr.get('trading', 'underlying_symbol')
    print(f"Reloaded underlying symbol: {reloaded_symbol}")
    
    if reloaded_symbol == new_symbol:
        print("\nVerification successful! The change was saved and reloaded.")
    else:
        print("\nVerification failed!")

    # 7. Restore the original value to leave the file unchanged
    print("\n--- Restoring Original Value ---")
    new_config_mgr.set('trading', 'underlying_symbol', original_symbol)
    new_config_mgr.save_config()
    print(f"Restored original symbol: {original_symbol}")
        
    print("\n--- Debug Mode Finished ---")
