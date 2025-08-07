import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    """Application configuration"""
    # Connection settings
    connection: Dict[str, Any] = None
    # Trading settings
    trading: Dict[str, Any] = None
    # Performance settings
    performance: Dict[str, Any] = None
    # Debug settings
    debug: Dict[str, Any] = None
    # AI prompt settings
    ai_prompt: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values if not provided"""
        if self.connection is None:
            self.connection = {
                "host": "127.0.0.1",
                "port": 7497,
                "client_id": 1,
                "timeout": 30,
                "readonly": False,
                "max_reconnect_attempts": 10,
                "reconnect_delay": 15,
                "max_reconnect_delay": 300
            }
        
        if self.trading is None:
            self.trading = {
                "underlying_symbol": "QQQ",
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
                "max_trade_value": 475.0,
                "trade_delta": 0.05,
                "runner": 1
            }
        
        if self.performance is None:
            self.performance = {
                "memory_allocation_mb": 4096,
                "api_timeout_settings": "increased",
                "market_data_throttling": True,
                "order_validation": True,
                "connection_verification": True
            }
        
        if self.debug is None:
            self.debug = {
                "master_debug": True,
                "modules": {
                    "CONFIG_MANAGER": "Trace",
                    "DATA_MONITOR": "Info",
                    "ENHANCED_EVENT_MONITOR": "Info",
                    "ENHANCED_EVENT_MONITOR_GUI": "Info",
                    "ENHANCED_LOGGING": "Info",
                    "EVENT_BUS": "Trace",
                    "EVENT_MONITOR": "Info",
                    "EVENT_MONITOR_GUI": "Info",
                    "GUI": "Trace",
                    "IB_CONNECTION": "Trace",
                    "MAIN": "Trace",
                    "PERFORMANCE_OPTIMIZER": "Info",
                    "SUBSCRIPTION_MANAGER": "Trace"
                }
            }
        if self.ai_prompt is None:
            self.ai_prompt = {
                "prompt": "You are a helpful assistant that can answer questions and help with tasks.",
                "context": "You are a helpful assistant that can answer questions and help with tasks."
            }

    # Properties for backward compatibility
    @property
    def ib_host(self) -> str:
        return self.connection.get("host", "127.0.0.1")
    
    @property
    def ib_port(self) -> int:
        return self.connection.get("port", 7497)
    
    @property
    def ib_client_id(self) -> int:
        return self.connection.get("client_id", 1)
    
    @property
    def data_collection_interval(self) -> int:
        return 60  # Keep this constant for now
    
    @property
    def max_reconnect_attempts(self) -> int:
        return self.connection.get("max_reconnect_attempts", 10)
    
    @property
    def reconnect_delay(self) -> int:
        return self.connection.get("reconnect_delay", 15)
    
    @classmethod
    def load_from_file(cls, config_path: str = 'config.json') -> 'AppConfig':
        """Load configuration from JSON file"""
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                return cls(
                    connection=config_data.get('connection'),
                    trading=config_data.get('trading'), 
                    performance=config_data.get('performance'),
                    debug=config_data.get('debug'),
                    ai_prompt=config_data.get('ai_prompt')
                )
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return cls()
    
    def save_to_file(self, config_path: str = 'config.json'):
        """Save configuration to JSON file"""
        try:
            config_dict = {
                "connection": self.connection,
                "trading": self.trading,
                "performance": self.performance,
                "debug": self.debug,
                "ai_prompt": self.ai_prompt
            }
            with open(config_path, 'w') as f:
                json.dump(config_dict, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
