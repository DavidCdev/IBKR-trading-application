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
        if not self._config or not self._config.debug:
            return
        
        debug_config = self._config.debug
        modules_config = debug_config.get("modules", {})
        
        # Apply configuration to discovered modules
        for module_name in self._discovered_modules:
            # Get configured level or default to INFO
            configured_level = modules_config.get(module_name, "INFO")
            self._set_module_log_level(module_name, configured_level)
    
    def _set_module_log_level(self, module_name: str, level: str):
        """Set log level for a specific module"""
        try:
            # Convert level to Python logging level
            python_level = LogLevelEnum.get_python_level(level)
            
            # Get or create logger for the module
            logger = logging.getLogger(module_name)
            logger.setLevel(python_level)
            
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
    
    def get_available_modules(self) -> List[str]:
        """Get list of all discovered modules"""
        return sorted(list(self._discovered_modules))
    
    def get_all_log_levels(self) -> Dict[str, str]:
        """Get current log level for each module"""
        return {
            module: info['level'] 
            for module, info in self._module_loggers.items()
        }
    
    def get_module_log_level(self, module_name: str) -> str:
        """Get current log level for a specific module"""
        module_name = module_name.upper()
        if module_name in self._module_loggers:
            return self._module_loggers[module_name]['level']
        return "INFO"  # Default level
    
    def refresh_configuration(self, config: 'AppConfig'):
        """Refresh configuration and reapply to all loggers"""
        self._config = config
        self._apply_config()
        
        logger = logging.getLogger("LOGGER_MANAGER")
        logger.info("Logger configuration refreshed")
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        perf_logger = logging.getLogger("PERFORMANCE")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        perf_logger.info(f"PERF: {operation} took {duration:.3f}s | {context}")
    
    def log_trade_event(self, event_type: str, symbol: str, quantity: int, price: float, **kwargs):
        """Log trading events with structured data"""
        trade_logger = logging.getLogger("TRADING")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        trade_logger.info(f"TRADE: {event_type} | {symbol} | Qty: {quantity} | Price: ${price:.2f} | {context}")
    
    def log_connection_event(self, event_type: str, host: str, port: int, status: str, **kwargs):
        """Log connection events"""
        conn_logger = logging.getLogger("CONNECTION")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        conn_logger.info(f"CONN: {event_type} | {host}:{port} | Status: {status} | {context}")
    
    def log_error_with_context(self, error: Exception, context: str = "", **kwargs):
        """Log errors with additional context"""
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


def get_module_log_level(module_name: str) -> str:
    """Get current log level for a specific module"""
    return _logger_manager.get_module_log_level(module_name)


def refresh_logger_configuration(config: 'AppConfig'):
    """Refresh logger configuration"""
    _logger_manager.refresh_configuration(config)


# Convenience functions for common logging operations
def log_performance(operation: str, duration: float, **kwargs):
    """Log performance metrics"""
    _logger_manager.log_performance(operation, duration, **kwargs)


def log_trade_event(event_type: str, symbol: str, quantity: int, price: float, **kwargs):
    """Log trading events"""
    _logger_manager.log_trade_event(event_type, symbol, quantity, price, **kwargs)


def log_connection_event(event_type: str, host: str, port: int, status: str, **kwargs):
    """Log connection events"""
    _logger_manager.log_connection_event(event_type, host, port, status, **kwargs)


def log_error_with_context(error: Exception, context: str = "", **kwargs):
    """Log errors with context"""
    _logger_manager.log_error_with_context(error, context, **kwargs)
