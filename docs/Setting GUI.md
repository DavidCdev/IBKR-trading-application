## Settings GUI

Configure connection, trading, and debug options for the IBKR app. Values are persisted to `config.json` via `utils/config_manager.py::AppConfig` and applied live to the running system.

- Dialog logic: `widgets/settings_form.py::Settings_Form`
- UI file: `ui/settings_gui.py` (Qt Designer generated)
- Launcher: `widgets/ib_trading_app.py` (button `pushButton_settings` → `show_setting_ui`)

---

## Overview

The Settings dialog centralizes application configuration:

- Connection to TWS/IB Gateway (host, port, client ID) with a Connect/Disconnect button and live status.
- Trading parameters including underlying symbol, order sizing helpers, and tiered risk levels.
- Debug controls: master debug and per-module log levels that the app reads at runtime.

All changes are saved to `config.json`. Trading changes are also pushed to the background worker (`DataCollectorWorker`) immediately.

---

## Where things live

- `widgets/settings_form.py` – wires the UI to `AppConfig`, handles validation, connects the button to the worker.
- `ui/settings_gui.py` – Qt Designer generated widgets (line edits, table, checkbox, combos, buttons).
- `utils/config_manager.py` – loads/saves `AppConfig` and sets sensible defaults.
- `utils/data_collector.py::DataCollectorWorker` – receives updates and emits signals back to the UI.
- `widgets/ib_trading_app.py` – owns `Settings_Form`, persists changes, and refreshes the main window.

---

## Fields and behavior

### Connection

- **Host**: `config.connection.host` (default `127.0.0.1`)
- **Port**: `config.connection.port` (default `7497` for TWS; `4001` for Gateway)
- **Client ID**: `config.connection.client_id` (default `1`)
- **Status label**: shows Connected/Disconnected/Connecting… with color (green/red/orange)
- **Connect/Disconnect button**:
  - When Disconnected: attempts to connect using current inputs
  - When Connected: requests a clean disconnect and disables auto-reconnect until you connect again
- **Connection log**: rolling, timestamped entries inside the dialog

Notes:
- Timeouts and retry policy use defaults from `AppConfig.connection` (e.g., `timeout`, `max_reconnect_attempts`, `reconnect_delay`). Not all are exposed in the GUI, but they are honored by the worker.

### Trading

- **Underlying Symbol**: `config.trading.underlying_symbol` (default `QQQ`); echoed on the main window title area.
- **Trade Delta**: `config.trading.trade_delta` (default `0.05`); used by order chase/limit logic.
- **Max Trade Value**: `config.trading.max_trade_value` (default `475.0`); used by sizing helpers.
- **Runner**: `config.trading.runner` (default `1`); contracts kept to run after profit.
- **Risk Levels table** (`config.trading.risk_levels`): tiers used by the trading manager:
  - `loss_threshold` – percent drawdown threshold for a tier
  - `account_trade_limit` – percent of account allowed per trade under this tier
  - `stop_loss` – percent stop for tiered risk
  - `profit_gain` – optional target percent (may be blank)

### Debug

- **Master Debug**: `config.debug.master_debug` (default `True`)
- **Per-module log levels** (`config.debug.modules`):
  - **Auto-Discovered Modules**: The system automatically discovers 47+ Python modules and provides individual log level controls
  - **Common Modules**: `MAIN`, `GUI`, `EVENT_BUS`, `SUBSCRIPTION_MANAGER`, `IB_CONNECTION`, `DATA_COLLECTOR`, `TRADING_MANAGER`, `AI_ENGINE`
  - **Real-Time Updates**: Changes apply immediately without application restart
  - **Combos map friendly names** to standard levels: Trace/Debug/Info/Warning/Error/Critical

#### Logging System Features
- **Module Auto-Discovery**: Automatically scans and discovers Python modules from the codebase
- **Real-Time Configuration**: Change log levels without restarting the application
- **Centralized Management**: Single point of control for all logging across the application
- **Automatic Persistence**: All log level changes are automatically saved to `config.json`

---

## Persistence and live updates

- Pressing Save in the main app triggers `_save_setting_form()` in `widgets/ib_trading_app.py` which:
  1. Reads all fields from the dialog
  2. Updates `self.config` (an `AppConfig`)
  3. Calls `self.config.save_to_file()` → writes `config.json`
  4. Invokes `DataCollectorWorker.update_trading_config(...)` so the running worker uses the new values immediately

- The Connect/Disconnect button in the dialog calls:
  - `DataCollectorWorker.connect_to_ib(connection_settings)` on connect, which updates `AppConfig.connection`, persists, and lets the background loop establish the session
  - `DataCollectorWorker.disconnect_from_ib()` on disconnect, which cleanly stops subscriptions and emits status signals

- The main window and the dialog both listen to worker signals and update status labels and logs accordingly.

- **Log Level Changes**: All log level modifications are applied immediately and persisted to disk automatically.

---

## Signal flow (simplified)

- Dialog → Worker
  - Connect: `connect_to_ib({host,port,client_id})`
  - Disconnect: `disconnect_from_ib()`
  - Trading changed: `update_trading_config(trading_config)`

- Worker → Main window/Settings dialog
  - `connection_success({ status, message })`
  - `connection_disconnected({ status })`
  - `connection_status_changed(bool)`
  - `trading_config_updated({ underlying_symbol, trading_config })`

---

## Using the Settings dialog

1. Open the main app window and click Settings.
2. Adjust Connection fields as needed. Click Connect to initiate a session; the status label and log will update.
3. Set Trading fields. Edit Risk Levels rows as needed (values are strings; blanks are allowed for `profit_gain`).
4. Toggle Debug options if desired.
5. **Configure Logging**: Use the per-module log level dropdowns to control logging verbosity for each component.
6. Click Save in the main window context (wired to `_save_setting_form()`), or close the dialog after connecting; configuration persists to `config.json`.

Tip: Changing the underlying symbol immediately refreshes labels in the main UI and clears symbol-dependent fields until new data arrives.

**Log Level Control**: Each discovered module has its own log level dropdown. Changes apply immediately and are saved automatically. Use this to control debugging verbosity for specific components without affecting others.

---

## Troubleshooting

- **Connect button stays on "Connecting…"**: Verify TWS/IB Gateway is running, API is enabled, and the port/client ID match your TWS/Gateway configuration.
- **Disconnect takes a while**: The dialog disables the button and polls for completion; it will re-enable once the underlying API reports `isConnected() == False`.
- **No option or price data**: Ensure `underlying_symbol` is set and your IB account has the necessary market data subscriptions.
- **Settings not saved**: Check write permissions for `config.json` in the project root.
- **UI file missing errors**: Ensure `ui/settings_gui.py` exists; regenerate from `.ui` if needed.
- **Auto-reconnect after manual disconnect**: Manual disconnect sets a flag to skip auto-reconnect. Click Connect again to clear that flag and resume.
- **Log levels not applying**: Ensure the logging system is properly initialized. Check that `master_debug` is enabled and the module exists in the discovered modules list.

---

## Defaults reference (from `AppConfig`)

- Connection: `{ host: "127.0.0.1", port: 7497, client_id: 1, timeout: 30, max_reconnect_attempts: 10, reconnect_delay: 15, max_reconnect_delay: 300 }`
- Trading: `{ underlying_symbol: "QQQ", max_trade_value: 475.0, trade_delta: 0.05, runner: 1, risk_levels: [ ... ] }`
- Debug: `master_debug: True`, with per-module levels (see `utils/config_manager.py`)

---

## Related

- IB connection internals: `docs/IB connection.md`
- Data collection and signals: `docs/Data Collector README.md`
- Hotkeys and trading shortcuts: `docs/HotKey Manager README.md`
- Logging system: `docs/LOGGING_SYSTEM.md`