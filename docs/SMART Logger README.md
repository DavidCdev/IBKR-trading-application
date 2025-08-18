## SMART Logger

Centralized, structured logging for the IB Trading Application. Provides rotating log files, per-module levels, contextual event logging (trades, connections, errors), and performance metrics with minimal setup.

### Key features
- **Centralized configuration**: Reads `debug` settings from `config.json` if present; sensible defaults otherwise.
- **Rotating log files**: Prevents unbounded growth via size-based rotation and backups.
- **Per-module log levels**: Control verbosity by logical module name.
- **Structured event helpers**: Purpose-built helpers for performance, trade, connection, and error logs.
- **Console + file outputs**: Human-readable console output and detailed file logs.
- **Singleton**: Auto-initializes once on first import.

### Log destinations
Logs are written to the `logs/` directory in the project root (e.g., `D:\IBKR\logs` on Windows). Files and rotation:

- `trading_app.log`: General application logs (INFO+), rotates at ~10 MB, keeps 5 backups
- `errors.log`: Error logs (ERROR+), rotates at ~5 MB, keeps 3 backups
- `debug.log`: Verbose logs (DEBUG), only if `master_debug` is true, rotates at ~20 MB, keeps 3 backups
- `performance.log`: Performance metrics (INFO), rotates at ~5 MB, keeps 2 backups

Console output prints at INFO level with a simple format.

### Configuration (optional)
If `config.json` exists in the project root, `SmartLogger` will read the `debug` key for configuration. When absent or invalid, built-in defaults are used.

Example `config.json`:
```json
{
  "debug": {
    "master_debug": true,
    "modules": {
      "MAIN": "INFO",
      "IB_CONNECTION": "DEBUG",
      "DATA_COLLECTOR": "INFO",
      "CONFIG_MANAGER": "INFO",
      "GUI": "INFO",
      "AI_ENGINE": "WARNING"
    }
  }
}
```

Notes:
- **master_debug**: When true, enables `debug.log` and writes DEBUG-level details.
- **modules**: Per-module levels apply to loggers retrieved via `get_logger(module_name)`. Named helper loggers (e.g., performance, trading) inherit the root level by default.

### Usage
Import once anywhere early in your app (it auto-initializes). Then either get a module-specific logger or use the convenience helpers for structured events.

```python
from utils.smart_logger import (
    get_logger,
    log_performance,
    log_trade_event,
    log_connection_event,
    log_error_with_context,
)

# Per-module logger with level controlled by config.json -> debug.modules["IB_CONNECTION"]
logger = get_logger("IB_CONNECTION")
logger.info("Connecting to IB Gateway…")

# Performance metrics
elapsed_seconds = 0.274
log_performance("historical_data_fetch", elapsed_seconds, symbol="AAPL", bars=5000)

# Trade events
log_trade_event(
    event_type="ORDER_PLACED",
    symbol="AAPL",
    quantity=100,
    price=189.12,
    orderId=1234,
    strategy="Breakout",
)

# Connection events
log_connection_event(
    event_type="CONNECT",
    host="127.0.0.1",
    port=7497,
    status="SUCCESS",
    clientId=7,
)

# Error with context
try:
    1 / 0
except Exception as exc:
    log_error_with_context(exc, context="placing order", symbol="AAPL", qty=100)
```

### API surface
- `get_logger(module_name: str) -> logging.Logger`: Returns a module-specific logger with level pulled from config.
- `log_performance(operation: str, duration: float, **kwargs)`: Logs `PERF: …` lines to `performance.log` and other enabled handlers.
- `log_trade_event(event_type: str, symbol: str, quantity: int, price: float, **kwargs)`: Logs `TRADE: …` entries.
- `log_connection_event(event_type: str, host: str, port: int, status: str, **kwargs)`: Logs `CONN: …` entries.
- `log_error_with_context(error: Exception, context: str = "", **kwargs)`: Logs `ERROR: …` entries with extra context.
- `smart_logger.cleanup_old_logs(days_to_keep: int = 30)`: Removes aged rotated files in `logs/`.

### Formats
- File format (detailed): `%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s`
- Console/performance format (simple): `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

Examples emitted messages:
```text
2025-01-01 12:00:00,000 - IB_CONNECTION - INFO - connect:123 - Connecting to IB Gateway…
2025-01-01 12:00:00,300 - PERFORMANCE - INFO - PERF: historical_data_fetch took 0.300s | symbol=AAPL | bars=5000
2025-01-01 12:00:01,000 - TRADING - INFO - TRADE: ORDER_PLACED | AAPL | Qty: 100 | Price: $189.12 | orderId=1234 | strategy=Breakout
2025-01-01 12:00:01,050 - CONNECTION - INFO - CONN: CONNECT | 127.0.0.1:7497 | Status: SUCCESS | clientId=7
2025-01-01 12:00:01,100 - ERRORS - ERROR - ERROR: ZeroDivisionError: division by zero | Context: placing order | symbol=AAPL | qty=100
```

### Best practices
- Use `get_logger("YOUR_MODULE_NAME")` at the top of each module; reference the same name consistently in `config.json`.
- Prefer the structured helpers for performance, trade, connection, and error contexts to keep logs uniform and searchable.
- Keep `master_debug` enabled during development; disable it in production to reduce I/O.

### Maintenance
Optionally prune old rotated logs during startup or on a schedule:

```python
from utils.smart_logger import smart_logger

smart_logger.cleanup_old_logs(days_to_keep=30)
```

### Troubleshooting
- No files appear: Ensure the process has write permission to the project root; `logs/` is created automatically.
- `config.json` ignored: Verify it is valid JSON and the `debug` key is present at the top level.
- Too chatty or too quiet: Adjust per-module levels in `config.json` or toggle `master_debug`.

### Implementation notes
- Defined in `utils/smart_logger.py` as a singleton `SmartLogger` with root logger setup on import.
- Handlers: multiple `RotatingFileHandler` instances plus one console `StreamHandler` to `stdout`.
- Root logger level is DEBUG; individual handlers and module loggers gate effective output.

#