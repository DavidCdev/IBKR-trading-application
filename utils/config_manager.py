import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any
from .logger import get_logger

logger = get_logger("CONFIG_MANAGER")

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
    # Account settings
    account: Dict[str, Any] = None
    
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
                        "profit_gain": "30"
                    },
                    {
                        "loss_threshold": "15",
                        "account_trade_limit": "10",
                        "stop_loss": "15",
                        "profit_gain": "25"
                    },
                    {
                        "loss_threshold": "25",
                        "account_trade_limit": "5",
                        "stop_loss": "5",
                        "profit_gain": "20"
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
                    "CONFIG_MANAGER": "TRACE",
                    "DATA_COLLECTOR": "INFO",
                    "GUI": "DEBUG",
                    "IB_CONNECTION": "TRACE",
                    "MAIN": "INFO",
                    "AI_ENGINE": "INFO"
                },
                "external_loggers": {
                    "ib_async.wrapper": "WARN",
                    "ib_async": "WARN",
                    "urllib3.connectionpool": "WARN",
                    "requests.packages.urllib3.connectionpool": "WARN"
                }
            }
        if self.ai_prompt is None:
            self.ai_prompt = {
                "prompt": "Analyze the current market conditions and provide trading insights for options trading. Focus on support/resistance levels, volatility patterns, and potential price movements.\n\n\nI'll provide additional Context for you:\n\n<@&1221916358267109397>\n## 0DTE Day-Trading Strategy for **2025-08-04 09:31:05.891611**\n\n### **I. Context Recap & Data-Driven Observations**\n\n#### **A. Macro Backdrop**\n- **No high-impact economic releases today.** Major macro events (ISM, S&P Global PMIs) are scheduled for **tomorrow (2025-08-05)** at 09:45 and 10:00 ET.\n- **Expect lower realized volatility** this session, with potential for volatility expansion into the close as traders reposition for tomorrow's data.\n\n#### **B. Volatility & Positioning Metrics**\n- **IV Ratio:** **0.2250** (very low)  \n  \u2192 Implied volatility is suppressed, options are cheap relative to realized vol.\n- **GEX Ratio:** **0.5663** (moderate)  \n  \u2192 Gamma exposure is positive but not excessive; market makers are likely dampening moves, but not fully pinning price.\n- **OI Ratio:** **0.5373** (moderate)  \n  \u2192 Open interest is not extreme; liquidity is healthy but not crowded.\n\n- **Fragility Score:** **1.67**  \n  \u2192 Market is somewhat fragile; susceptible to sharp moves if key levels break.\n\n#### **C. Skew & GEX Structure (626.09 Underlying Reference)**\n\n- **Top GEX (Put) Walls:**  \n  - **627P:** 18,302 GEX (distance +0.69)  \n  - **625P:** 9,984 GEX (+1.31)  \n  - **624P:** 5,133 GEX (+2.31)  \n  - **Flip Candidate:** **628.0** (Gamma shift: -18,617)\n\n- **Top GEX (Call) Walls:**  \n  - **635C:** 3,182 GEX (+8.69)  \n  - **637C:** 1,981 GEX (+10.69)\n\n- **Pin Risk:**  \n  - Strikes 625P, 626P, 627P, and 628P are all in the immediate vicinity and flagged for pin risk.\n\n---\n\n### **II. Quantitative 0DTE Trading Plan**\n\n#### **A. Opening Thesis (09:31 ET)**\n- **IV is cheap:** Favor long premium structures, especially if expecting a move.\n- **Pin risk is high (625-628):** Market likely to gravitate toward these strikes unless a catalyst emerges.\n- **Fragility > 1.5:** If price escapes the pin zone, expect a sharp move.\n- **Gamma flip at 628:** A move above 628 could trigger dealer hedging, amplifying upside.\n\n---\n\n#### **B. Key Levels for Today**\n- **Support:** 624P, 625P, 626P, 627P (GEX put walls, pin risk)\n- **Resistance:** 628 (gamma flip), 635C (call wall)\n- **Immediate range:** **624\u2013628**  \n  - If price stays in this band, expect mean reversion and chop.\n  - A break above 628 or below 624 could trigger a fast move.\n\n---\n\n#### **C. Trade Setups**\n\n##### **1. Mean Reversion/Pinned Market Play (Base Case)**\n- **When to Enter:**  \n  - Price trades between **625\u2013627** for >10 minutes, no directional impulse.\n- **Strategy:**  \n  - **Sell straddle or iron butterfly** at 626 (ATM), targeting premium decay as price pins.\n  - **Hedge:** Buy cheap OTM strangle (e.g., 624P/628C) as tail risk hedge, given fragility score >1.5.\n- **Profit Target:** 60\u201380% of max profit or close by 15:30 ET.\n- **Stop:** If price closes 5-min candle above 628 or below 624.\n\n##### **2. Gamma Flip Momentum Play (Breakout)**\n- **When to Enter:**  \n  - Price breaks and holds above **628** (gamma flip) on strong volume.\n- **Strategy:**  \n  - **Buy 629C or 630C** (0DTE, cheap IV, positive gamma).\n  - **Optional:** Sell 635C to create a call vertical, targeting the call wall.\n- **Profit Target:** 50\u2013100% gain or trailing stop.\n- **Stop:** If price reverts and closes back below 628.\n\n##### **3. Breakdown Play**\n- **When to Enter:**  \n  - Price breaks and holds below **624** (GEX wall) on strong volume.\n- **Strategy:**  \n  - **Buy 623P or 622P** (0DTE, cheap IV).\n  - **Optional:** Sell 620P for a put vertical, targeting next GEX wall.\n- **Profit Target:** 50\u2013100% gain or trailing stop.\n- **Stop:** If price reverts and closes back above 624.\n\n##### **4. Volatility Expansion Play (Late Session)**\n- **When to Enter:**  \n  - After 14:00 ET, if price remains pinned and IV is still low.\n- **Strategy:**  \n  - **Buy straddle at ATM (626)** for a potential late-day move as traders hedge for tomorrow's macro events.\n- **Profit Target:** 20\u201340% gain (due to rapid decay).\n- **Stop:** If no move by 15:30 ET, close for salvage value.\n\n---\n\n### **III. Risk Management & Execution**\n\n- **Position Sizing:**  \n  - Use small size for directional breakouts (1\u20132% of portfolio per play).\n  - Size up slightly for mean reversion trades, but always hedge tail risk.\n- **Monitor:**  \n  - **Volume:** Confirm breakouts with above-average volume.\n  - **Order Book:** Watch for large orders at 625\u2013628 (potential pinning).\n  - **IV:** If IV spikes, consider taking profit on long premium trades.\n\n---\n\n### **IV. Summary Table**\n\n| Scenario         | Trigger                      | Trade Structure           | Targets         | Stop/Exit         |\n|------------------|-----------------------------|---------------------------|-----------------|-------------------|\n| Pin/Chop         | 625\u2013627, no move            | Sell 626 straddle/IB, buy OTM strangle | 60\u201380% max profit | Break 628/624     |\n| Gamma Flip Up    | >628, strong volume         | Buy 629C/630C, sell 635C  | 50\u2013100%         | <628              |\n| Breakdown Down   | <624, strong volume         | Buy 623P/622P, sell 620P  | 50\u2013100%         | >624              |\n| Late Vol Play    | 14:00+, still pinned, low IV| Buy 626 straddle          | 20\u201340%          | 15:30 ET          |\n\n---\n\n## **Key Quantitative Takeaways**\n- **IV Ratio (0.2250):** Options are cheap, favor long premium if expecting a move.\n- **GEX Ratio (0.5663):** Market is moderately pinned; expect chop unless a breakout.\n- **Fragility Score (1.67):** If breakout occurs, expect it to be sharp.\n- **Gamma Flip (628):** Key inflection\u2014watch for momentum if breached.\n- **Pin Risk (625\u2013628):** High likelihood of price gravitating here unless a catalyst emerges.\n\n---\n\n**Stay nimble, respect the pin, and be ready to flip directional if the gamma flip at 628 is breached.**\n\nWeekly and Daily levels:\nWeekly:\n612.04\u2013612.81    ESH25 ATH\n611.59    ES1 ATH\n609.26\u2013608.17    \n605.49\u2013606.29    *\n603.21\u2013603.81    \n602.49    6/8 ETH H\n601.25\u2013601.65    6/8 RTH H\n599.97\u2013600.57    *\n598.03\u2013598.25    Fri 6/13 H\n594.98\u2013595.38    LAAF test\n593.84    3W RTH top\n591.63\u2013591.88    6/13 LOD / SPX 3W top\n590.42\u2013590.72    \n587.84\u2013588.34    6/8 ETH L\n586.65    \n583.87\u2013580.50    *\n577.43\u2013574.55    \n573.31     3W balance low\n572.17\u2013572.76    \n570.93 Fri 5/23 PM L\n568.65\u2013569.39    Bull gap fill / 7D retest\n\n\nDaily:\n596.37-596.37\n592.92\n597.42\n599.53\n602.02\n603.55",
                "context": "You are a helpful assistant that can answer questions and help with tasks.",
                "gemini_api_key": "",
                "polling_interval_minutes": 10,
                "enable_auto_polling": True,
                "enable_price_triggered_polling": True,
                "max_historical_days": 30,
                "cache_duration_minutes": 15
            }
        if self.account is None:
            self.account = {
                "high_water_mark": 1000000
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
                    ai_prompt=config_data.get('ai_prompt'),
                    account=config_data.get('account')
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
                "ai_prompt": self.ai_prompt,
                "account": self.account
            }
            with open(config_path, 'w') as f:
                json.dump(config_dict, f, indent=4)
            
            # Notify logger manager of configuration changes
            self._notify_logger_manager()
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
    
    def _notify_logger_manager(self):
        """Notify the logger manager of configuration changes"""
        try:
            # Use a delayed import to avoid circular dependencies
            import importlib
            logger_module = importlib.import_module('.logger', package='utils')
            logger_module.refresh_logger_configuration(self)
            logger.info("Logger configuration updated after config save")
        except ImportError:
            logger.warning("Logger module not available for configuration update")
        except Exception as e:
            logger.error(f"Error updating logger configuration: {e}")
