# Data Collector

Robust, reconnecting market data pipeline for Interactive Brokers, built around PyQt6 signals. It streams real-time prices, FX rates, options data, account metrics, and trade statistics into your UI while managing connection lifecycle, dynamic option subscriptions, and persistence of key account state.

- Core worker: `utils/data_collector.py::DataCollectorWorker`
- IB integration: `utils/ib_connection.py::IBDataCollector`
- Configuration: `utils/config_manager.py::AppConfig` (persisted to `config.json`)
- Trading logic integration: `utils/trading_manager.py::TradingManager`

---

## Overview

`DataCollectorWorker` runs an async loop in a background thread, connects to TWS/IB Gateway, collects data, and emits structured PyQt6 signals for the UI. It implements:

- Automatic reconnection with capped exponential backoff
- Manual connect/disconnect controls honoring a manual-disconnect flag
- Dynamic option strike and expiration switching driven by the underlying price and time-of-day
- Real-time updates for underlying, FX, options greeks/quotes, active positions PnL, daily PnL, and account metrics
- Periodic full data snapshots (`data_ready`) suitable for UI/state refreshes
- High Water Mark persistence to `config.json`

---

## Key Classes

### `DataCollectorWorker`
Location: `utils/data_collector.py`

Constructed with an `AppConfig`. It owns an `IBDataCollector` and exposes PyQt6 signals to the UI.

Signals (payloads shown as dictionaries):
- `data_ready(dict)`: Aggregated snapshot from `collect_all_data()`
- `connection_status_changed(bool)`: True when connected
- `error_occurred(str)`: Error message
- `price_updated(dict)`: `{ 'symbol': str, 'price': float, 'timestamp': iso8601 }`
- `fx_rate_updated(dict)`: `{ 'symbol': 'USDCAD', 'rate': float, 'timestamp': iso8601 }`
- `connection_success(dict)`: `{ 'status': 'Connecting...|Connected|Reconnecting...', 'message': str }`
- `connection_disconnected(dict)`: `{ 'status': 'Disconnecting...|Disconnected', 'message'?: str }`
- `puts_option_updated(dict)`: Put option quote/greeks update
- `calls_option_updated(dict)`: Call option quote/greeks update
- `daily_pnl_update(dict)`: `{ 'daily_pnl_price': float, 'daily_pnl_percent': float }`
- `account_summary_update(dict)`: `{ 'NetLiquidation': float, 'StartingValue': float, 'HighWaterMark': float }`
- `trading_config_updated(dict)`: `{ 'underlying_symbol': str, 'trading_config': dict }`
- `active_contracts_pnl_refreshed(dict)`: `{ 'symbol': str, 'position_size': int, 'pnl_dollar': float, 'pnl_percent': float }`
- `closed_trades_update(list|dict)`: Stats for closed trades (see `get_trade_statistics`)

Primary methods:
- `start_collection()`: Start the async collection loop (call from background thread)
- `stop_collection()`: Stop the loop
- `connect_to_ib(connection_settings: Optional[dict])`: Manual connect; updates settings and resets reconnect state
- `disconnect_from_ib()`: Manual disconnect; sets manual-disconnect flag to prevent auto-reconnect
- `update_trading_config(trading_config: dict)`: Update trading config, persist to `config.json`, emit `trading_config_updated`
- `cleanup()`: Disconnect and clean associated resources

Lifecycle internals:
- `_collection_loop()`: Periodic collect → emit → sleep cycle. Handles reconnection and HWM persistence
- `_reconnect()`: Capped exponential backoff with jitter. Respects `max_reconnect_attempts`, `reconnect_delay`, `max_reconnect_delay`
- `_sleep_with_cancel(seconds)`: Fine-grained sleep to respond quickly to stop requests

### `IBDataCollector`
Location: `utils/ib_connection.py`

Wraps `ib_async.IB` and owns:
- Real-time streaming for underlying price and USDCAD FX
- Option chain fetching and dynamic subscriptions for selected strike/expiration
- Account metrics (NetLiquidation, PnL, HighWaterMark tracking) and events
- Active positions with PnL calculations
- Today's executions + trade statistics (wins/losses, profit factor)
- Historical data retrieval (used by AI engine)

Important behaviors:
- Underlying price updates → compute nearest strike → resubscribe options if strike changes
- Smart expiration switching around 12:00 PM EST and based on available expirations
- Caches qualified option contracts for fast resubscription
- Emits back into `DataCollectorWorker` via the worker reference (`data_worker`)

Trading integration: `IBDataCollector` initializes a `TradingManager` to compute quantities, apply tiered risk, maintain bracket orders, and support panic-sell flows.

---

## Configuration

Managed by `utils/config_manager.py::AppConfig`. Loaded from and saved to `config.json`.

Connection (`config.connection`):
- `host` (str, default `127.0.0.1`)
- `port` (int, default `7497`)
- `client_id` (int, default `1`)
- `timeout` (int seconds, default `30`)
- `readonly` (bool, default `False`)
- `max_reconnect_attempts` (int, default `10`)
- `reconnect_delay` (int seconds, default `15`)
- `max_reconnect_delay` (int seconds, default `300`)

Trading (`config.trading`):
- `underlying_symbol` (str, default `QQQ`)
- `risk_levels` (list of tiers):
  - `loss_threshold` (percent as string)
  - `account_trade_limit` (percent as string)
  - `stop_loss` (percent as string)
  - `profit_gain` (percent as string or empty)
- `max_trade_value` (float, default `475.0`)
- `trade_delta` (float, default `0.05`) – price delta for chase/limit
- `runner` (int, default `1`) – contracts to keep as runner on profit

Performance (`config.performance`): tuning flags (memory, throttling, validation)

Debug (`config.debug`): logger levels per module with **auto-discovered modules**

AI Prompt (`config.ai_prompt`): only relevant if using `AI_Engine`

Account (`config.account`):
- `high_water_mark` (float, default `1000000`)

Derived convenience properties:
- `AppConfig.ib_host`, `AppConfig.ib_port`, `AppConfig.ib_client_id`
- `AppConfig.data_collection_interval` (seconds, fixed at `60`)
- `AppConfig.max_reconnect_attempts`, `AppConfig.reconnect_delay`

Persistence helpers:
- `AppConfig.load_from_file(path='config.json')`
- `AppConfig.save_to_file(path='config.json')`

---

## Logging System Integration

The Data Collector now uses the centralized logging system for comprehensive logging across all operations:

### Module Logging
- **Module Name**: `DATA_COLLECTOR` (auto-discovered by the logging system)
- **Log Levels**: Configurable via Settings GUI (TRACE, DEBUG, INFO, WARN, ERROR, FATAL)
- **Real-Time Updates**: Log levels can be changed without restarting the application

### Logging Features
- **Connection Events**: Detailed logging of connection attempts, successes, and failures
- **Data Collection**: Logging of data collection cycles and market data updates
- **Error Handling**: Comprehensive error logging with context and stack traces
- **Performance Monitoring**: Built-in performance logging for data collection operations

### Usage Example
```python
from utils.logger import get_logger

logger = get_logger("DATA_COLLECTOR")
logger.info("Starting data collection")
logger.debug(f"Connecting to {host}:{port}")
logger.error(f"Connection failed: {error}")
```

---

## Reconnection & Manual Control

- Automatic reconnection runs when `ib.isConnected()` is False and manual disconnect was not requested.
- Backoff strategy: `reconnect_delay * 2^(attempt-1)`, jittered, capped by `max_reconnect_delay`.
- `connect_to_ib(connection_settings)` updates `host|port|client_id`, persists to `config.json`, resets the manual-disconnect flag, and emits a connecting status.
- `disconnect_from_ib()` sets the manual-disconnect flag, cancels subscriptions via `disconnect()`, and emits disconnect status. While this flag is set, auto-reconnect is skipped.

---

## Data Collected per Cycle

`IBDataCollector.collect_all_data()` populates:
- `fx_ratio`: float (USDCAD)
- `account`: pandas DataFrame-like with keys `NetLiquidation`, `StartingValue`, `HighWaterMark`
- `options`: DataFrame of selected strike/expiration (first chain/expiration by default)
- `active_contract`: DataFrame of active positions for the `underlying_symbol` with PnL detail
- `statistics`: DataFrame with closed-trade statistics (win rate, sums, averages, profit factor)

The worker emits `data_ready(data)` when successful.

---

## Dynamic Options Subscription

- Nearest strike is computed from current underlying price (rounded).
- If price movement changes the nearest strike, the collector unsubscribes old options and subscribes to new contracts at the new strike.
- Around 12:00 PM EST (and using smart checks), the system may switch expirations (0DTE → 1DTE) if beneficial. Available expirations are discovered via the chain response and cached.

---

## High Water Mark (HWM) Persistence

- `HighWaterMark` is treated as a currency value (not a percent).
- When `NetLiquidation` exceeds the current HWM, the collector updates `config.account.high_water_mark`.
- The worker detects changes and persists to `config.json` during the collection loop.

---

## Usage

Minimal PyQt integration sketch:

```python
from PyQt6.QtCore import QThread
from utils.config_manager import AppConfig
from utils.data_collector import DataCollectorWorker

config = AppConfig.load_from_file('config.json')
worker = DataCollectorWorker(config)

thread = QThread()
worker.moveToThread(thread)

# Connect signals
worker.connection_status_changed.connect(lambda ok: print('Connected' if ok else 'Disconnected'))
worker.data_ready.connect(lambda data: print('Snapshot received'))
worker.error_occurred.connect(print)
worker.price_updated.connect(lambda p: print('Price', p))
worker.fx_rate_updated.connect(lambda r: print('FX', r))
worker.calls_option_updated.connect(lambda d: print('CALLS', d))
worker.puts_option_updated.connect(lambda d: print('PUTS', d))
worker.daily_pnl_update.connect(lambda d: print('Daily PnL', d))
worker.account_summary_update.connect(lambda d: print('Acct', d))

# Thread lifecycle
thread.started.connect(worker.start_collection)
thread.start()

# ... later
# worker.connect_to_ib({'host': '127.0.0.1', 'port': 7497, 'client_id': 1})
# worker.update_trading_config({'underlying_symbol': 'SPY'})
# worker.disconnect_from_ib()
# worker.stop_collection(); worker.cleanup(); thread.quit(); thread.wait()
```

Notes:
- `start_collection()` runs an `asyncio` loop; call it after moving to a `QThread`.
- Use `connect_to_ib()` for manual connect attempts; it's safe to call while the loop manages the actual connection.
- Call `cleanup()` before application shutdown to cancel subscriptions and stop monitoring threads.

---

## Emitted Payload Examples

- `price_updated`:
```json
{ "symbol": "SPY", "price": 512.34, "timestamp": "2025-01-01T14:30:00.000Z" }
```

- `fx_rate_updated`:
```json
{ "symbol": "USDCAD", "rate": 1.3572, "timestamp": "2025-01-01T14:30:05.000Z" }
```

- `account_summary_update`:
```json
{ "NetLiquidation": 105432.10, "StartingValue": 104900.00, "HighWaterMark": 105432.10 }
```

- `calls_option_updated`/`puts_option_updated` (subset):
```json
{ "Bid": 1.23, "Ask": 1.28, "Last": 1.26, "Volume": 1520, "Delta": 0.41, "Gamma": 0.07, "Theta": -0.02, "Vega": 0.11, "Implied_Volatility": 24.5 }
```

---

## Dependencies

- Python 3.10+
- PyQt6
- `ib_async`
- pandas
- pytz
- (Optional) `google-generativeai` if using `utils/ai_engine.py`

Ensure your TWS/IB Gateway is running and API is enabled on `host:port` with the configured `client_id`.

---

## Troubleshooting

- Connection times out: confirm TWS/Gateway is running, API enabled, correct `host/port`, and that the client ID is not conflicting
- Auto-reconnect not happening: verify `disconnect_from_ib()` wasn't called (manual-disconnect flag set). Use `reset_manual_disconnect_flag()` or `connect_to_ib()`
- No option data: ensure an underlying symbol is configured and that the account has proper market data subscriptions
- No FX data: IB may require specific FX permissions/subscriptions
- HWM not persisting: check write permissions to `config.json`
- UI freezes: ensure data collection runs in a separate `QThread` and heavy work stays off the GUI thread
- Logging issues: verify the logging system is properly initialized and `DATA_COLLECTOR` module is configured in the debug settings

---

## Related Modules

- `utils/trading_manager.py`: Receives market/account data to place/manage orders, apply risk tiers, chase logic, and bracket orders
- `utils/ai_engine.py`: Uses historical data and current price for AI-driven analysis (optional)
- `utils/logger.py`: Centralized logging system for comprehensive application logging

---

## License

Proprietary – internal use unless specified otherwise.
