import logging
import logging.handlers
import os
import sys
import inspect
from datetime import datetime
from typing import Dict, Optional, Any, List
from pathlib import Path
from enum import Enum
import json
import threading
from collections import defaultdict

# Import AppConfig type hint only, not the actual class
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .config_manager import AppConfig


class LogLevelEnum(Enum):
    """Standardized logging levels for the application"""
    TRACE = "TRACE"      # Maps to logging.DEBUG with semantic difference
    DEBUG = "DEBUG"      # Maps to logging.DEBUG
    INFO = "INFO"        # Maps to logging.INFO
    WARN = "WARN"        # Maps to logging.WARNING
    ERROR = "ERROR"      # Maps to logging.ERROR
    FATAL = "FATAL"      # Maps to logging.CRITICAL
    
    @classmethod
    def get_python_level(cls, level: str) -> int:
        """Convert enum level to Python logging level"""
        level_mapping = {
            "TRACE": logging.DEBUG,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR,
            "FATAL": logging.CRITICAL
        }
        return level_mapping.get(level.upper(), logging.INFO)
    
    @classmethod
    def get_available_levels(cls) -> List[str]:
        """Get list of available log levels"""
        return [level.value for level in cls]


class LoggerManager:
    """
    Central manager for all application loggers.
    Handles module auto-discovery, configuration management, and runtime updates.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LoggerManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._loggers = {}
            self._module_loggers = {}
            self._config = None
            self._log_dir = Path("logs")
            self._setup_log_directory()
            self._discovered_modules = set()
            self._setup_root_logger()
    
    def _setup_log_directory(self):
        """Create logs directory if it doesn't exist"""
        self._log_dir.mkdir(exist_ok=True)
    
    def _setup_root_logger(self):
        """Setup root logger with handlers"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File handlers with rotation
        self._setup_file_handlers(root_logger, detailed_formatter, simple_formatter)
        
        # Console handler
        self._setup_console_handler(root_logger, simple_formatter)
    
    def _setup_file_handlers(self, root_logger, detailed_formatter, simple_formatter):
        """Setup file handlers with rotation"""
        
        # Main application log with rotation
        main_handler = logging.handlers.RotatingFileHandler(
            self._log_dir / "trading_app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(main_handler)
        
        # Error log
        error_handler = logging.handlers.RotatingFileHandler(
            self._log_dir / "errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
        
        # Debug log (only if master_debug is True)
        if self._config and self._config.debug and self._config.debug.get("master_debug", False):
            debug_handler = logging.handlers.RotatingFileHandler(
                self._log_dir / "debug.log",
                maxBytes=20*1024*1024,  # 20MB
                backupCount=3,
                encoding='utf-8'
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(detailed_formatter)
            root_logger.addHandler(debug_handler)
        
        # Performance log
        perf_handler = logging.handlers.RotatingFileHandler(
            self._log_dir / "performance.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=2,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(simple_formatter)
        root_logger.addHandler(perf_handler)
    
    def _setup_console_handler(self, root_logger, formatter):
        """Setup console handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    def initialize(self, config: 'AppConfig'):
        """
        Initialize the logger manager with configuration
        
        Args:
            config: Application configuration object
        """
        self._config = config
        self._discover_modules()
        self._apply_config()
        
        # Log initialization
        logger = logging.getLogger("LOGGER_MANAGER")
        logger.info("LoggerManager initialized successfully")
        logger.info(f"Discovered {len(self._discovered_modules)} modules")
    
    def _discover_modules(self):
        """Auto-discover Python modules in the source directory"""
        try:
            # Get the project root directory
            project_root = Path(__file__).parent.parent
            
            # Scan for Python files
            for py_file in project_root.rglob("*.py"):
                # Skip __pycache__, .venv, and other non-source directories
                if any(part.startswith('.') or part in ['__pycache__', '.venv', 'venv', 'node_modules'] 
                       for part in py_file.parts):
                    continue
                
                # Convert file path to module name
                relative_path = py_file.relative_to(project_root)
                module_name = str(relative_path).replace('/', '.').replace('\\', '.').replace('.py', '')
                
                # Convert to uppercase for consistency
                module_name = module_name.upper()
                
                if module_name:
                    self._discovered_modules.add(module_name)
            
            # Add common module names that might not be discovered by file scanning
            common_modules = [
                "MAIN", "GUI", "IB_CONNECTION", "DATA_COLLECTOR", 
                "CONFIG_MANAGER", "AI_ENGINE", "TRADING_MANAGER",
                "HOTKEY_MANAGER", "PERFORMANCE_MONITOR", "SETTINGS"
            ]
            
            for module in common_modules:
                self._discovered_modules.add(module)
                
        except Exception as e:
            # Fallback to basic module discovery
            self._discovered_modules = {
                "MAIN", "GUI", "IB_CONNECTION", "DATA_COLLECTOR", 
                "CONFIG_MANAGER", "AI_ENGINE", "TRADING_MANAGER",
                "HOTKEY_MANAGER", "PERFORMANCE_MONITOR", "SETTINGS"
            }
            logging.getLogger("LOGGER_MANAGER").error(f"Error during module discovery: {e}")
    
    def _apply_config(self):
        """Apply configuration to all loggers"""
        try:
            if self._config and self._config.debug:
                # Apply module log levels
                if self._config.debug.get("modules"):
                    self.update_log_levels(self._config.debug["modules"])
                
                # Apply external logger levels
                if self._config.debug.get("external_loggers"):
                    self._refresh_external_logger_config(self._config.debug["external_loggers"])
                    
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error applying config: {e}")
    
    def _set_module_log_level(self, module_name: str, level: str):
        """Set log level for a specific module"""
        try:
            # Check if master debug is enabled - if not, force ERROR level
            if self._config and self._config.debug and not self._config.debug.get("master_debug", False):
                level = "ERROR"
            
            # Convert level to Python logging level
            python_level = LogLevelEnum.get_python_level(level)
            
            # Get or create logger for the module
            logger = logging.getLogger(module_name)
            logger.setLevel(python_level)
            
            # If logging is disabled, prevent propagation and remove handlers
            if self._config and self._config.debug and not self._config.debug.get("master_debug", False):
                logger.propagate = False
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
            
            # Store reference
            self._module_loggers[module_name] = {
                'logger': logger,
                'level': level,
                'python_level': python_level
            }
            
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(
                f"Error setting log level for module {module_name}: {e}"
            )
    
    def set_external_logger_level(self, logger_name: str, level: str):
        """Set log level for external/third-party loggers"""
        try:
            # Convert level to Python logging level
            python_level = LogLevelEnum.get_python_level(level)
            
            # Get the external logger
            external_logger = logging.getLogger(logger_name)
            external_logger.setLevel(python_level)
            
            # Store reference for external loggers
            if not hasattr(self, '_external_loggers'):
                self._external_loggers = {}
            
            self._external_loggers[logger_name] = {
                'logger': external_logger,
                'level': level,
                'python_level': python_level
            }
            
            # Log the change
            logger = logging.getLogger("LOGGER_MANAGER")
            logger.info(f"Set external logger {logger_name} to level: {level}")
            
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(
                f"Error setting log level for external logger {logger_name}: {e}"
            )
    
    def suppress_external_logger(self, logger_name: str, suppress: bool = True):
        """Suppress or enable an external logger"""
        try:
            external_logger = logging.getLogger(logger_name)
            
            if suppress:
                # Suppress the logger by setting to ERROR level and preventing propagation
                external_logger.setLevel(logging.ERROR)
                external_logger.propagate = False
                
                # Remove any existing handlers
                for handler in external_logger.handlers[:]:
                    external_logger.removeHandler(handler)
                
                logger = logging.getLogger("LOGGER_MANAGER")
                logger.info(f"Suppressed external logger: {logger_name}")
            else:
                # Re-enable the logger by allowing propagation and setting to INFO
                external_logger.setLevel(logging.INFO)
                external_logger.propagate = True
                
                logger = logging.getLogger("LOGGER_MANAGER")
                logger.info(f"Re-enabled external logger: {logger_name}")
                
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(
                f"Error {'suppressing' if suppress else 'enabling'} external logger {logger_name}: {e}"
            )
    
    def get_logger(self, module_name: str) -> logging.Logger:
        """
        Get a logger for a specific module
        
        Args:
            module_name: Name of the module requesting the logger
            
        Returns:
            Configured logger instance
        """
        # Normalize module name to uppercase
        module_name = module_name.upper()
        
        # Check if master debug is enabled - if not, return a disabled logger
        if self._config and self._config.debug and not self._config.debug.get("master_debug", False):
            # Return a logger that only shows errors and doesn't propagate
            logger = logging.getLogger(module_name)
            logger.setLevel(logging.ERROR)
            logger.propagate = False
            # Remove any existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            return logger
        
        # Ensure console handler is set up for immediate logging
        self._ensure_console_handler()
        
        # If module not discovered yet, add it
        if module_name not in self._discovered_modules:
            self._discovered_modules.add(module_name)
        
        # Get or create logger
        if module_name not in self._module_loggers:
            self._set_module_log_level(module_name, "INFO")  # Default level
        
        return self._module_loggers[module_name]['logger']
    
    def _ensure_console_handler(self):
        """Ensure console handler is set up for immediate logging"""
        root_logger = logging.getLogger()
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
            # No console handler, add one
            simple_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(simple_formatter)
            root_logger.addHandler(console_handler)
    
    def update_log_levels(self, log_level_dict: Dict[str, str]):
        """
        Update log levels for modules at runtime
        
        Args:
            log_level_dict: Dictionary mapping module names to log levels
        """
        try:
            # Check if master debug is enabled - if not, don't update levels
            if self._config and self._config.debug and not self._config.debug.get("master_debug", False):
                logger = logging.getLogger("LOGGER_MANAGER")
                logger.warning("Cannot update log levels - master debug is disabled")
                return
            
            for module_name, level in log_level_dict.items():
                if level in LogLevelEnum.get_available_levels():
                    self._set_module_log_level(module_name, level)
                    
                    # Log the change
                    logger = logging.getLogger("LOGGER_MANAGER")
                    logger.info(f"Updated log level for {module_name}: {level}")
                else:
                    logging.getLogger("LOGGER_MANAGER").warning(
                        f"Invalid log level '{level}' for module {module_name}"
                    )
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error updating log levels: {e}")
    
    def is_logging_enabled(self) -> bool:
        """Check if logging is currently enabled (master_debug is True)"""
        if not self._config or not self._config.debug:
            return False
        return self._config.debug.get("master_debug", False)
    
    def get_master_debug_status(self) -> bool:
        """Get the current master debug status"""
        return self.is_logging_enabled()
    
    def get_available_modules(self) -> List[str]:
        """Get list of all discovered modules"""
        return sorted(list(self._discovered_modules))
    
    def get_all_log_levels(self) -> Dict[str, str]:
        """Get current log level for each module"""
        try:
            levels = {}
            for module_name, logger_info in self._module_loggers.items():
                levels[module_name] = logger_info['level']
            
            # Include external loggers if any
            if hasattr(self, '_external_loggers'):
                for logger_name, logger_info in self._external_loggers.items():
                    levels[f"EXTERNAL_{logger_name}"] = logger_info['level']
            
            return levels
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error getting all log levels: {e}")
            return {}
    
    def get_external_loggers(self) -> Dict[str, str]:
        """Get current log levels for external loggers"""
        try:
            if hasattr(self, '_external_loggers'):
                return {name: info['level'] for name, info in self._external_loggers.items()}
            return {}
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error getting external loggers: {e}")
            return {}
    
    def get_module_log_level(self, module_name: str) -> str:
        """Get current log level for a specific module"""
        module_name = module_name.upper()
        if module_name in self._module_loggers:
            return self._module_loggers[module_name]['level']
        return "INFO"  # Default level
    
    def refresh_configuration(self, config: 'AppConfig'):
        """Refresh logger configuration from config"""
        try:
            self._config = config
            
            # Check if master debug has changed and apply logging control
            self._apply_master_debug_control()
            
            # Update module log levels
            if config.debug and config.debug.get("modules"):
                self.update_log_levels(config.debug["modules"])
            
            # Update external logger levels if configured
            if config.debug and config.debug.get("external_loggers"):
                self._refresh_external_logger_config(config.debug["external_loggers"])
                
            logger = logging.getLogger("LOGGER_MANAGER")
            logger.info("Logger configuration refreshed")
                
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error refreshing logger configuration: {e}")
    
    def _refresh_external_logger_config(self, external_logger_config: Dict[str, str]):
        """Refresh external logger configuration"""
        try:
            for logger_name, level in external_logger_config.items():
                if level in LogLevelEnum.get_available_levels():
                    self.set_external_logger_level(logger_name, level)
                else:
                    logging.getLogger("LOGGER_MANAGER").warning(
                        f"Invalid log level '{level}' for external logger {logger_name}"
                    )
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error refreshing external logger config: {e}")
    
    def _apply_master_debug_control(self):
        """Apply master debug control to all loggers"""
        try:
            if self._config and self._config.debug:
                master_debug = self._config.debug.get("master_debug", False)
                
                if not master_debug:
                    # Disable all logging except errors
                    root_logger = logging.getLogger()
                    root_logger.setLevel(logging.ERROR)
                    
                    # Disable all module loggers
                    for module_name, logger_info in self._module_loggers.items():
                        logger = logger_info['logger']
                        logger.setLevel(logging.ERROR)
                        logger.propagate = False
                        
                    # Disable all external loggers
                    if hasattr(self, '_external_loggers'):
                        for logger_name, logger_info in self._external_loggers.items():
                            logger = logger_info['logger']
                            logger.setLevel(logging.ERROR)
                            logger.propagate = False
                else:
                    # Re-enable logging based on config
                    self._apply_config()
                    
        except Exception as e:
            logging.getLogger("LOGGER_MANAGER").error(f"Error applying master debug control: {e}")
    
    def force_logging_control(self, enable: bool):
        """Force enable/disable logging (for testing purposes)"""
        if enable:
            # Re-enable all logging
            self._setup_root_logger()
            self._apply_config()
            logging.getLogger("LOGGER_MANAGER").info("Logging force-enabled")
        else:
            # Disable all logging except errors
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                if not isinstance(handler, logging.handlers.RotatingFileHandler) or \
                   not handler.baseFilename.endswith("errors.log"):
                    root_logger.removeHandler(handler)
            
            root_logger.setLevel(logging.ERROR)
            
            # Also disable all module loggers
            for module_info in self._module_loggers.values():
                if 'logger' in module_info:
                    module_info['logger'].setLevel(logging.ERROR)
            
            logging.getLogger("LOGGER_MANAGER").info("Logging force-disabled (errors only)")
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        if not self.is_logging_enabled():
            return
        perf_logger = logging.getLogger("PERFORMANCE")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        perf_logger.info(f"PERF: {operation} took {duration:.3f}s | {context}")
    
    def log_trade_event(self, event_type: str, symbol: str, quantity: int, price: float, **kwargs):
        """Log trading events with structured data"""
        if not self.is_logging_enabled():
            return
        trade_logger = logging.getLogger("TRADING")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        trade_logger.info(f"TRADE: {event_type} | {symbol} | Qty: {quantity} | Price: ${price:.2f} | {context}")
    
    def log_connection_event(self, event_type: str, host: str, port: int, status: str, **kwargs):
        """Log connection events"""
        if not self.is_logging_enabled():
            return
        conn_logger = logging.getLogger("CONNECTION")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        conn_logger.info(f"CONN: {event_type} | {host}:{port} | Status: {status} | {context}")
    
    def log_error_with_context(self, error: Exception, context: str = "", **kwargs):
        """Log errors with additional context"""
        # Always log errors regardless of master_debug setting
        error_logger = logging.getLogger("ERRORS")
        context_data = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        error_logger.error(f"ERROR: {type(error).__name__}: {str(error)} | Context: {context} | {context_data}")


# Global instance
_logger_manager = LoggerManager()


def initialize_logger_manager(config: 'AppConfig'):
    """
    Initialize the logging system with configuration
    
    Args:
        config: Application configuration object
    """
    _logger_manager.initialize(config)


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module
    
    Args:
        module_name: Name of the module requesting the logger
        
    Returns:
        Configured logger instance
    """
    return _logger_manager.get_logger(module_name)


def update_log_levels(log_level_dict: Dict[str, str]):
    """
    Update log levels for modules at runtime
    
    Args:
        log_level_dict: Dictionary mapping module names to log levels
    """
    _logger_manager.update_log_levels(log_level_dict)


def get_available_modules() -> List[str]:
    """Get list of all available modules"""
    return _logger_manager.get_available_modules()


def get_all_log_levels() -> Dict[str, str]:
    """Get current log level for each module"""
    return _logger_manager.get_all_log_levels()


def get_external_loggers() -> Dict[str, str]:
    """Get current log levels for external loggers"""
    return _logger_manager.get_external_loggers()


def get_module_log_level(module_name: str) -> str:
    """Get current log level for a specific module"""
    return _logger_manager.get_module_log_level(module_name)


def refresh_logger_configuration(config: 'AppConfig'):
    """Refresh logger configuration"""
    _logger_manager.refresh_configuration(config)


def is_logging_enabled() -> bool:
    """Check if logging is currently enabled (master_debug is True)"""
    return _logger_manager.is_logging_enabled()


def force_logging_control(enable: bool):
    """Force enable/disable logging (for testing purposes)"""
    _logger_manager.force_logging_control(enable)


def get_master_debug_status() -> bool:
    """Get the current master debug status"""
    return _logger_manager.get_master_debug_status()


def set_external_logger_level(logger_name: str, level: str):
    """Set log level for external/third-party loggers"""
    _logger_manager.set_external_logger_level(logger_name, level)


def suppress_external_logger(logger_name: str, suppress: bool = True):
    """Suppress or enable an external logger"""
    _logger_manager.suppress_external_logger(logger_name, suppress)


# Convenience functions for common logging operations
def log_performance(operation: str, duration: float, **kwargs):
    """Log performance metrics"""
    if not is_logging_enabled():
        return
    _logger_manager.log_performance(operation, duration, **kwargs)


def log_trade_event(event_type: str, symbol: str, quantity: int, price: float, **kwargs):
    """Log trading events"""
    if not is_logging_enabled():
        return
    _logger_manager.log_trade_event(event_type, symbol, quantity, price, **kwargs)


def log_connection_event(event_type: str, host: str, port: int, status: str, **kwargs):
    """Log connection events"""
    if not is_logging_enabled():
        return
    _logger_manager.log_connection_event(event_type, host, port, status, **kwargs)


def log_error_with_context(error: Exception, context: str = "", **kwargs):
    """Log errors with context"""
    # Always log errors regardless of master_debug setting
    _logger_manager.log_error_with_context(error, context, **kwargs)
