import logging
import os
import glob
from enum import Enum
from typing import Dict, Optional

class LogLevel(Enum):
    """Enumeration of available log levels."""
    TRACE = "Trace"
    DEBUG = "Debug"
    INFO = "Info"
    WARN = "Warn"
    ERROR = "Error"
    FATAL = "Fatal"

class LoggerManager:
    """
    Manages logging for all modules in the application.
    Provides dynamic log level control based on configuration.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the logger manager.
        
        Args:
            config_manager: Configuration manager instance to read log settings
        """
        self.config_manager = config_manager
        self.loggers: Dict[str, logging.Logger] = {}
        self.log_levels: Dict[str, LogLevel] = {}
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Initialize loggers for all modules
        self._initialize_module_loggers()
    
    def _discover_python_modules(self) -> list:
        """
        Dynamically discover all Python modules in the src directory.
        
        Returns:
            List of module names (without .py extension)
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        python_files = glob.glob(os.path.join(script_dir, "*.py"))
        
        modules = []
        for file_path in python_files:
            filename = os.path.basename(file_path)
            if filename != "__init__.py" and filename != "logger.py":
                module_name = os.path.splitext(filename)[0]
                modules.append(module_name.upper())
        
        return modules
    
    def _initialize_module_loggers(self):
        """Initialize loggers for all discovered modules."""
        if not self.config_manager:
            return
            
        # Get debug modules from config
        debug_modules = self.config_manager.get('debug', 'modules', {})
        
        # Discover all Python modules
        discovered_modules = self._discover_python_modules()
        
        # Initialize loggers for each module
        for module_name in discovered_modules:
            logger = logging.getLogger(module_name)
            
            # Get log level from config, default to INFO
            log_level_str = debug_modules.get(module_name, "Info")
            log_level = self._get_log_level_from_string(log_level_str)
            
            logger.setLevel(self._get_python_log_level(log_level))
            self.loggers[module_name] = logger
            self.log_levels[module_name] = log_level
    
    def _get_log_level_from_string(self, level_str: str) -> LogLevel:
        """Convert string log level to LogLevel enum."""
        try:
            return LogLevel(level_str)
        except ValueError:
            return LogLevel.INFO
    
    def _get_python_log_level(self, log_level: LogLevel) -> int:
        """Convert LogLevel enum to Python logging level."""
        level_map = {
            LogLevel.TRACE: logging.DEBUG,  # Trace maps to DEBUG
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARN: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.FATAL: logging.CRITICAL
        }
        return level_map.get(log_level, logging.INFO)
    
    def get_logger(self, module_name: str) -> logging.Logger:
        """
        Get a logger for a specific module.
        
        Args:
            module_name: Name of the module (will be converted to uppercase)
            
        Returns:
            Configured logger instance
        """
        module_name = module_name.upper()
        if module_name not in self.loggers:
            # Create new logger if not exists
            logger = logging.getLogger(module_name)
            logger.setLevel(logging.INFO)
            self.loggers[module_name] = logger
            self.log_levels[module_name] = LogLevel.INFO
        
        return self.loggers[module_name]
    
    def update_log_level(self, module_name: str, log_level: LogLevel):
        """
        Update the log level for a specific module.
        
        Args:
            module_name: Name of the module
            log_level: New log level
        """
        module_name = module_name.upper()
        if module_name in self.loggers:
            self.loggers[module_name].setLevel(self._get_python_log_level(log_level))
            self.log_levels[module_name] = log_level
    
    def update_all_log_levels(self, log_levels: Dict[str, str]):
        """
        Update log levels for multiple modules.
        
        Args:
            log_levels: Dictionary mapping module names to log level strings
        """
        for module_name, level_str in log_levels.items():
            log_level = self._get_log_level_from_string(level_str)
            self.update_log_level(module_name, log_level)
    
    def get_available_modules(self) -> list:
        """Get list of all available modules."""
        return list(self.loggers.keys())
    
    def get_module_log_level(self, module_name: str) -> LogLevel:
        """Get current log level for a module."""
        module_name = module_name.upper()
        return self.log_levels.get(module_name, LogLevel.INFO)
    
    def get_all_log_levels(self) -> Dict[str, LogLevel]:
        """Get all current log levels."""
        return self.log_levels.copy()

# Global logger manager instance
_logger_manager: Optional[LoggerManager] = None

def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a module. This is the main interface for modules to get their logger.
    
    Args:
        module_name: Name of the module (usually __name__)
        
    Returns:
        Configured logger instance
    """
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = LoggerManager()
    
    return _logger_manager.get_logger(module_name)

def initialize_logger_manager(config_manager):
    """Initialize the global logger manager with configuration."""
    global _logger_manager
    _logger_manager = LoggerManager(config_manager)

def update_log_levels(log_levels: Dict[str, str]):
    """Update log levels for multiple modules."""
    global _logger_manager
    if _logger_manager:
        _logger_manager.update_all_log_levels(log_levels)

def get_available_modules() -> list:
    """Get list of all available modules."""
    global _logger_manager
    if _logger_manager:
        return _logger_manager.get_available_modules()
    return []

def get_all_log_levels() -> Dict[str, str]:
    """Get all current log levels as strings."""
    global _logger_manager
    if _logger_manager:
        levels = _logger_manager.get_all_log_levels()
        return {module: level.value for module, level in levels.items()}
    return {} 