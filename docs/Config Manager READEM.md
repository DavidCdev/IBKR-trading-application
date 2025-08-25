## Config Manager

A small, self-contained configuration layer for the app. It provides sensible defaults, reads/writes a `config.json` file, and exposes a single dataclass `AppConfig` with well‑named sections.

### Where it lives
- Code: `utils/config_manager.py`
- Default file: `config.json` in project root

### What it manages
`AppConfig` groups settings into the following sections (all optional in `config.json`; defaults are applied automatically):

- **connection**: IBKR connectivity and reconnection backoff
  - `host` (str) default `"127.0.0.1"`
  - `port` (int) default `7497`
  - `client_id` (int) default `1`
  - `timeout` (int, seconds) default `30`
  - `readonly` (bool) default `False`
  - `max_reconnect_attempts` (int) default `10`
  - `reconnect_delay` (int, seconds) default `15`
  - `max_reconnect_delay` (int, seconds) default `300`

- **trading**: symbols, risk tiers, and trade sizing
  - `underlying_symbol` (str) default `"QQQ"`
  - `risk_levels` (list of objects)
    - `loss_threshold` (str)
    - `account_trade_limit` (str)
    - `stop_loss` (str)
    - `profit_gain` (str)
  - `max_trade_value` (float) default `475.0`
  - `trade_delta` (float) default `0.05`
  - `runner` (int) default `1`

- **performance**: knobs to balance reliability and speed
  - `memory_allocation_mb` (int) default `4096`
  - `api_timeout_settings` (str) default `"increased"`
  - `market_data_throttling` (bool) default `True`
  - `order_validation` (bool) default `True`
  - `connection_verification` (bool) default `True`

- **debug**: global/module log levels
  - `master_debug` (bool) default `True`
  - `modules` (object str->str) default per-module levels with **auto-discovered modules**

- **ai_prompt**: AI engine prompt and polling behavior
  - `prompt` (str)
  - `context` (str)
  - `gemini_api_key` (str)
  - `polling_interval_minutes` (int) default `10`
  - `enable_auto_polling` (bool) default `True`
  - `enable_price_triggered_polling` (bool) default `True`
  - `max_historical_days` (int) default `30`
  - `cache_duration_minutes` (int) default `15`

- **account**: portfolio/account preferences
  - `high_water_mark` (int) default `1000000`

### Backward-compatible properties
These read from `connection` so existing code continues to work:
- `ib_host` → `connection.host`
- `ib_port` → `connection.port`
- `ib_client_id` → `connection.client_id`
- `data_collection_interval` → constant `60`
- `max_reconnect_attempts` → `connection.max_reconnect_attempts`
- `reconnect_delay` → `connection.reconnect_delay`

### Default config (applied when keys are missing)
```json
{
  "connection": {
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 1,
    "timeout": 30,
    "readonly": false,
    "max_reconnect_attempts": 10,
    "reconnect_delay": 15,
    "max_reconnect_delay": 300
  },
  "trading": {
    "underlying_symbol": "QQQ",
    "risk_levels": [
      {"loss_threshold": "0",  "account_trade_limit": "30", "stop_loss": "20", "profit_gain": ""},
      {"loss_threshold": "15", "account_trade_limit": "10", "stop_loss": "15", "profit_gain": ""},
      {"loss_threshold": "25", "account_trade_limit": "5",  "stop_loss": "5",  "profit_gain": ""}
    ],
    "max_trade_value": 475.0,
    "trade_delta": 0.05,
    "runner": 1
  },
  "performance": {
    "memory_allocation_mb": 4096,
    "api_timeout_settings": "increased",
    "market_data_throttling": true,
    "order_validation": true,
    "connection_verification": true
  },
  "debug": {
    "master_debug": true,
    "modules": {
      "CONFIG_MANAGER": "TRACE",
      "DATA_MONITOR": "INFO",
      "ENHANCED_EVENT_MONITOR": "INFO",
      "ENHANCED_EVENT_MONITOR_GUI": "INFO",
      "ENHANCED_LOGGING": "INFO",
      "EVENT_BUS": "TRACE",
      "EVENT_MONITOR": "INFO",
      "EVENT_MONITOR_GUI": "INFO",
      "GUI": "TRACE",
      "IB_CONNECTION": "TRACE",
      "MAIN": "TRACE",
      "PERFORMANCE_OPTIMIZER": "INFO",
      "SUBSCRIPTION_MANAGER": "TRACE",
      "DATA_COLLECTOR": "INFO",
      "TRADING_MANAGER": "INFO",
      "AI_ENGINE": "INFO"
    }
  },
  "ai_prompt": {
    "prompt": "You are a helpful assistant that can answer questions and help with tasks.",
    "context": "You are a helpful assistant that can answer questions and help with tasks.",
    "gemini_api_key": "",
    "polling_interval_minutes": 10,
    "enable_auto_polling": true,
    "enable_price_triggered_polling": true,
    "max_historical_days": 30,
    "cache_duration_minutes": 15
  },
  "account": {
    "high_water_mark": 1000000
  }
}
```

## Logging System Integration

### Auto-Discovered Modules
The Config Manager now integrates with a centralized logging system that automatically discovers Python modules in the codebase. The `debug.modules` section is dynamically populated with discovered modules, providing individual log level control for each component.

### Log Level Options
Each module can be configured with one of these log levels:
- **TRACE**: Most verbose debugging (equivalent to Python's DEBUG)
- **DEBUG**: General debugging information
- **INFO**: General information messages
- **WARN**: Warning messages
- **ERROR**: Error messages
- **FATAL**: Critical errors

### Real-Time Updates
Log level changes are applied immediately without requiring application restart. The system automatically persists all changes to `config.json`.

### Usage

Load if present, otherwise create with defaults:
```python
from utils.config_manager import AppConfig

config = AppConfig.load_from_file("config.json")
print(config.ib_host, config.ib_port)
```

Modify values and persist to disk:
```python
config.trading["underlying_symbol"] = "SPY"
config.debug["modules"]["MAIN"] = "INFO"
config.save_to_file("config.json")
```

Direct access to sections:
```python
if config.performance["market_data_throttling"]:
    ...
```

### File format
- The file is standard JSON with indentation preserved on save.
- Missing sections/keys are filled with defaults in memory and will be written on the next `save_to_file`.

### Logging and errors
- Uses the centralized logging system via `utils.logger.get_logger("CONFIG_MANAGER")` for messages.
- Load errors: logs a warning and falls back to defaults.
- Save errors: logs an error and leaves the previous file intact.

### Tips
- Keep secrets like `gemini_api_key` safe; consider external secret management if needed.
- You can keep `config.json` under version control with sanitized values, or add it to `.gitignore` for local-only overrides.
- The logging system automatically discovers new modules as they're added to the codebase.
- Use the Settings GUI to easily configure log levels for all discovered modules.

## Related Documentation
- Logging system: `docs/LOGGING_SYSTEM.md`
- Settings GUI: `docs/Setting GUI.md`
- Data collection: `docs/Data Collector README.md`
