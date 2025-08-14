import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Any
import json
from pathlib import Path


class SmartLogger:
    """
    Smart logging system for IB Trading Application
    
    Features:
    - Centralized configuration
    - Log rotation with size limits
    - Different log levels per module
    - Structured logging with context
    - Performance monitoring
    - Error tracking and alerting
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SmartLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._loggers = {}
            self._config = {}
            self._log_dir = Path("logs")
            self._setup_log_directory()
            self._load_config()
            self._setup_root_logger()
    
    def _setup_log_directory(self):
        """Create logs directory if it doesn't exist"""
        self._log_dir.mkdir(exist_ok=True)
    
    def _load_config(self):
        """Load logging configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                self._config = config.get('debug', {})
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Default configuration if config.json is not available
            self._config = {
                "master_debug": True,
                "modules": {
                    "MAIN": "INFO",
                    "IB_CONNECTION": "INFO",
                    "DATA_COLLECTOR": "INFO",
                    "CONFIG_MANAGER": "INFO",
                    "GUI": "INFO",
                    "AI_ENGINE": "INFO"
                }
            }
    
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
        if self._config.get("master_debug", False):
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
    
    def get_logger(self, module_name: str) -> logging.Logger:
        """
        Get a logger for a specific module with appropriate level
        
        Args:
            module_name: Name of the module requesting the logger
            
        Returns:
            Configured logger instance
        """
        if module_name in self._loggers:
            return self._loggers[module_name]
        
        logger = logging.getLogger(module_name)
        
        # Set log level based on configuration
        module_level = self._config.get("modules", {}).get(module_name, "INFO")
        logger.setLevel(getattr(logging, module_level.upper(), logging.INFO))
        
        # Store logger for reuse
        self._loggers[module_name] = logger
        
        return logger
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """
        Log performance metrics
        
        Args:
            operation: Name of the operation
            duration: Duration in seconds
            **kwargs: Additional context data
        """
        perf_logger = logging.getLogger("PERFORMANCE")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        perf_logger.info(f"PERF: {operation} took {duration:.3f}s | {context}")
    
    def log_trade_event(self, event_type: str, symbol: str, quantity: int, price: float, **kwargs):
        """
        Log trading events with structured data
        
        Args:
            event_type: Type of trade event (BUY, SELL, ORDER_PLACED, etc.)
            symbol: Trading symbol
            quantity: Number of shares/contracts
            price: Price per unit
            **kwargs: Additional trade data
        """
        trade_logger = logging.getLogger("TRADING")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        trade_logger.info(f"TRADE: {event_type} | {symbol} | Qty: {quantity} | Price: ${price:.2f} | {context}")
    
    def log_connection_event(self, event_type: str, host: str, port: int, status: str, **kwargs):
        """
        Log connection events
        
        Args:
            event_type: Type of connection event
            host: Connection host
            port: Connection port
            status: Connection status
            **kwargs: Additional connection data
        """
        conn_logger = logging.getLogger("CONNECTION")
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        conn_logger.info(f"CONN: {event_type} | {host}:{port} | Status: {status} | {context}")
    
    def log_error_with_context(self, error: Exception, context: str = "", **kwargs):
        """
        Log errors with additional context
        
        Args:
            error: Exception that occurred
            context: Additional context string
            **kwargs: Additional context data
        """
        error_logger = logging.getLogger("ERRORS")
        context_data = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        error_logger.error(f"ERROR: {type(error).__name__}: {str(error)} | Context: {context} | {context_data}")
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """
        Clean up old log files
        
        Args:
            days_to_keep: Number of days to keep log files
        """
        try:
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            
            for log_file in self._log_dir.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    logging.getLogger("MAINTENANCE").info(f"Cleaned up old log file: {log_file}")
        except Exception as e:
            logging.getLogger("MAINTENANCE").error(f"Error cleaning up old logs: {e}")


# Global instance
smart_logger = SmartLogger()


def get_logger(module_name: str) -> logging.Logger:
    """
    Convenience function to get a logger for a module
    
    Args:
        module_name: Name of the module requesting the logger
        
    Returns:
        Configured logger instance
    """
    return smart_logger.get_logger(module_name)


def log_performance(operation: str, duration: float, **kwargs):
    """Convenience function to log performance metrics"""
    smart_logger.log_performance(operation, duration, **kwargs)


def log_trade_event(event_type: str, symbol: str, quantity: int, price: float, **kwargs):
    """Convenience function to log trading events"""
    smart_logger.log_trade_event(event_type, symbol, quantity, price, **kwargs)


def log_connection_event(event_type: str, host: str, port: int, status: str, **kwargs):
    """Convenience function to log connection events"""
    smart_logger.log_connection_event(event_type, host, port, status, **kwargs)


def log_error_with_context(error: Exception, context: str = "", **kwargs):
    """Convenience function to log errors with context"""
    smart_logger.log_error_with_context(error, context, **kwargs)
