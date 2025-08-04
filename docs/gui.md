# Documentation: IBTradingGUI

## 1. Introduction

This document provides a comprehensive overview of the `IBTradingGUI` class, a standalone trading interface built with Python's `tkinter` library. The GUI is designed to be completely decoupled from any backend logic, acting as a pure visual layer that can be integrated into any trading application.

Its state is managed through `tkinter` variables (`StringVar`, `DoubleVar`, etc.), and it exposes a set of public methods to receive data updates. This architecture makes it flexible and easy to connect to different data sources and trading engines, particularly through an event-driven model and a centralized configuration manager.

## 2. Prompt Context for AI Assistants

Copy and paste the text below into your AI assistant to provide it with a concise but comprehensive context of the `gui.py` file.

**File:** `gui.py`

**Summary:** This file defines `IBTradingGUI`, a decoupled, standalone user interface for a trading application, built with Python's `tkinter`. It is designed to be a pure view layer, driven entirely by external data and configuration. It can be run directly for testing (using mock data) or integrated into a larger application.

**Architecture:**

-   **Event-Driven:** The GUI listens for events on an event bus. The backend should `emit` events with specific names (e.g., 'underlying_price_update'). The GUI uses `register_event_listeners` to map these event names to its internal `update_*` methods. This is the primary intended method of interaction.
    
-   **Config-Driven:** All settings are loaded from a configuration manager object provided during initialization. The manager must have a `get(section, key, default)` and `set(section, key, value)` interface.
    
-   **Stateful via Tkinter Variables:** UI elements are tied to `tk.StringVar`, `tk.DoubleVar`, etc. Updating these variables updates the UI.
    
-   **Thread-Safety:** The GUI is not thread-safe. All update methods must be called from the main GUI thread, typically using `root.after()` if the backend runs in a separate thread.
    

**Public API - Methods:**

-   `__init__(event_bus, config_manager)`: Initializes the GUI.
    
-   `run()`: Starts the `tkinter` main loop.
    
-   `on_close()`: Handles the window close event.
    
-   `register_event_listeners()`: Connects GUI update methods to the event bus.
    
-   `update_underlying_price(data)`: Updates symbol and price. Requires `{'symbol': str, 'price': float}`.
    
-   `update_forex_rates(data)`: Updates forex display. Requires `{'pair1': str, 'pair2': str}`.
    
-   `update_option_chain(data)`: Updates strike, expiration, and all put/call data. Requires `{'strike': str, 'expiration': str, 'call_data': dict, 'put_data': dict}`. The keys in the nested dicts must match the `self.call_vars` and `self.put_vars` state variables.
    
-   `update_account_metrics(data)`: Updates P&L, account value, etc. Requires a dict where keys match `self.account_metrics_vars`.
    
-   `update_trade_stats(data)`: Updates win rate, total trades, etc. Requires a dict where keys match `self.trade_stats_vars`.
    
-   `update_active_contract(data)`: Updates the currently held position display. Requires a dict where keys match `self.active_contract_vars`.
    
-   `clear_all_data()`: Resets all dynamic data fields to '-'.
    
-   `clear_group(group_name)`: Clears a specific section (e.g., 'option_chain').
    
-   `clear_item(group_name, item_key)`: Clears a single field.
    
-   `on_config_update()`: Public slot to trigger a reload of settings from the config manager.
    
-   `on_error(message)`: Logs an error message.
    

**State Management - Key Tkinter Variables:**

-   `self.status_connection_var`, `self.health_progress_var`, `self.trading_info_var`, `self.forex_rate1_var`, `self.forex_rate2_var`, `self.strike_info_var`, `self.expiration_info_var`.
    
-   `self.call_vars`, `self.put_vars`: Dictionaries of `StringVar`s for option columns.
    
-   `self.account_metrics_vars`, `self.trade_stats_vars`, `self.active_contract_vars`: Dictionaries of `StringVar`s for their respective sections.
    

**Configuration - Key Tkinter Variables (in Preferences Window):**

-   `self.host_var`, `self.port_var`, `self.client_id_var`.
    
-   `self.underlying_var`, `self.trade_delta_var`, `self.runner_var`, `self.max_trade_value_var`.
    
-   `self.pref_risk_table`: The `ttk.Treeview` widget for the editable risk levels.
    

## 3. Configuration Structure

The GUI is driven by a configuration manager object. This object must be passed to the GUI during initialization.

### Expected Interface

The manager object must implement the following methods:

-   `get(section, key, default)`: Retrieves a value from the configuration.
    
-   `set(section, key, value)`: Sets a value in the configuration (in memory).
    
-   `save()`: Persists the current configuration state (e.g., writes to a file).
    

A valid mock implementation is provided in `gui.py` and shown here for clarity:

```
class MockConfigManager:
    """A simple config manager for demonstration purposes."""
    def __init__(self, initial_config):
        self.config = initial_config
    def get(self, section, key, default=None):
        return self.config.get(section, {}).get(key, default)
    def set(self, section, key, value):
        if section not in self.config: self.config[section] = {}
        self.config[section][key] = value
    def save(self):
        print("Config SAVED to disk (simulated).")

```

### Configuration Schema

The GUI reads and writes settings from the following sections and keys.

#### `connection` Section

**Key**

**Data Type**

**Description**

`host`

`str`

The IP address of the TWS or Gateway.

`port`

`int`

The port number for the TWS or Gateway.

`client_id`

`int`

The unique client ID for the API session.

#### `trading` Section

**Key**

**Data Type**

**Description**

`underlying_symbol`

`str`

The default trading symbol (e.g., "SPY").

`trade_delta`

`float`

A value used for trade calculations (e.g., order price offsets).

`runner`

`int`

The number of contracts to keep as a "runner" when partially closing a position.

`max_trade_value`

`float`

The maximum currency value for a single trade.

`risk_levels`

`list[dict]`

A list of dictionaries defining risk parameters at different loss thresholds.

The `risk_levels` list should contain dictionaries with the following structure:

-   `loss_threshold`: `str` (convertible to `float`)
    
-   `account_trade_limit`: `str` (convertible to `float`)
    
-   `stop_loss`: `str` (convertible to `float`)
    
-   `profit_gain`: `str` (convertible to `float`)
    

### Full Configuration Example

```
{
    "connection": {
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 1
    },
    "trading": {
        "underlying_symbol": "SPY",
        "trade_delta": 0.05,
        "runner": 1,
        "max_trade_value": 500.0,
        "risk_levels": [
            {
                "loss_threshold": "0",
                "account_trade_limit": "30",
                "stop_loss": "20",
                "profit_gain": ""
            }
        ]
    }
}

```

## 4. Event Bus Integration

The most effective way to integrate this GUI is with an event bus. The GUI listens for named events and calls the appropriate update method.

### Example of Correct Usage

To prevent errors, use the exact event names and data structures shown below. The following is a complete, runnable example demonstrating how to update the underlying price.

```
# --- main_app.py ---
# This example shows how a backend component would interact with the GUI.

# Assume MockEventBus and IBTradingGUI are in their own files
# from event_bus import MockEventBus 
# from gui import IBTradingGUI
import threading

# 1. Initialize the Event Bus and GUI
#    In a real app, these would be your actual classes.
event_bus = MockEventBus()
gui = IBTradingGUI(event_bus=event_bus) 

# 2. The backend gets new data and emits an event.
#    This is the key line for updating the price.
price_data = {'symbol': 'SPY', 'price': 505.50}
event_bus.emit("underlying_price_update", price_data)

# 3. Run the GUI (this would typically be in your main thread)
# gui.run() 

```

### GUI Update Methods & Data Formats

Here is a complete list of the public methods designed to receive data from your event bus, with **full, non-truncated examples**.

**Method Name**

**Event Name**

**Purpose**

**Expected Data Payload Example**

`update_underlying_price`

`underlying_price_update`

Updates the main symbol and price display.

`{'symbol': 'SPY', 'price': 501.23}`

`update_forex_rates`

`forex_update`

Updates the currency exchange rates.

`{'pair1': 'USD/CAD: 1.37', 'pair2': 'CAD/USD: 0.73'}`

`update_option_chain`

`option_chain_update`

Updates the entire Puts/Calls section.

`{'strike': '502', 'expiration': '2025-07-18', 'call_data': {'price': '$3.10', 'bid': '$3.09', 'ask': '$3.11', 'delta': '0.55', 'gamma': '0.04', 'theta': '-0.06', 'vega': '0.13', 'oi': '12,345', 'volume': '6,789'}, 'put_data': {'price': '$2.80', 'bid': '$2.79', 'ask': '$2.81', 'delta': '-0.45', 'gamma': '0.04', 'theta': '-0.05', 'vega': '0.13', 'oi': '18,765', 'volume': '4,321'}}`

`update_account_metrics`

`account_metrics_update`

Updates the "Account Metrics" box.

`{'account_value': '$105,123.45', 'starting_value': '$100,000.00', 'high_water_mark': '$106,543.21', 'daily_pnl': '$5,123.45', 'daily_pnl_percent': '5.12%'}`

`update_trade_stats`

`trade_stats_update`

Updates the "Trade Statistics" box.

`{'win_rate': '75.00%', 'win_count': '15', 'win_sum': '$7,500.00', 'loss_count': '5', 'loss_sum': '$2,500.00', 'total_trades': '20'}`

`update_active_contract`

`active_contract_update`

Updates the "Active Contract" section.

`{'symbol': 'SPY 505C', 'quantity': '5', 'pnl_usd': '$255.50', 'pnl_pct': '20.44%'}`

`on_config_update`

`config_updated`

Tells the GUI to reload settings from the config manager.

`None`

`on_error`

`error`

Logs an error message to the preferences console.

A `str` containing the error message.

## 5. Developer Tips and Best Practices

### How to Add a New Display Field

Let's say you want to add a "Buying Power" field to the "Account Metrics" section. Here are the steps:

1.  **Declare the Variable**: In `_init_tkinter_variables`, add a new `StringVar` to the `self.account_metrics_vars` dictionary. The key you choose will be used by your event bus.
    
    ```
    # In _init_tkinter_variables()
    self.account_metrics_vars = {
        "account_value": tk.StringVar(value="-"),
        "starting_value": tk.StringVar(value="-"),
        # ... other variables ...
        "buying_power": tk.StringVar(value="-") # <-- Add new variable
    }
    
    ```
    
2.  **Add the Widget**: In `_setup_market_display`, find the loop that creates the "Account Metrics" labels and add your new field to the list. The GUI will automatically create and place the labels for you.
    
    ```
    # In _setup_market_display()
    account_metrics_fields = [
        ("Account Value", "account_value"),
        ("Starting Value", "starting_value"),
        # ... other fields ...
        ("Buying Power", "buying_power") # <-- Add new field tuple
    ]
    for i, (label, key) in enumerate(account_metrics_fields):
        # ... existing code that creates the widgets ...
    
    ```
    
3.  **Update from Backend**: Now, your backend can emit an `account_metrics_update` event with the new key, and the GUI will display it automatically.
    
    ```
    # In your backend code
    event_bus.emit("account_metrics_update", {"buying_power": "$200,000.00"})
    
    ```
    

### Best Practices for Modifications

-   **Respect the Decoupling**: Avoid adding any backend logic (API calls, calculations, file I/O) directly into the `gui.py` file. The GUI's only job is to display data.
    
-   **Use the Public API**: When you need to update the UI from your application, use the provided `update_*` methods. This ensures updates are handled consistently.
    
-   **Leverage the Structure**: Before creating a new widget from scratch, see if you can extend an existing section. The layout is built to be easily extensible by adding items to the field lists (like `account_metrics_fields`).
    

### Debugging the UI

-   **Use Standalone Mode**: The easiest way to test visual changes is to run `gui.py` directly. The `if __name__ == "__main__":` block is configured to start the GUI with a `MockConfigManager` and a `MockEventBus` that sends random data.
    
-   **Use `_populate_with_fake_data()`**: This method is called in standalone mode. You can temporarily add your new field to this method to see how it looks with sample data without needing to run your full backend.
    
-   **Check the Console**: The `MockConfigManager` prints messages to the console whenever a setting is changed and saved, which is useful for debugging the preferences window.
    

## 6. Class Methods Breakdown

### Public API

These methods are the intended interface for interacting with the GUI from your application.

-   `__init__(self, event_bus=None, config_manager=None, standalone_mode=False)`: Constructor.
    
-   `run(self)`: Starts the `tkinter` main loop.
    
-   `on_close(self)`: Handles the window close event.
    
-   `register_event_listeners(self)`: Connects the GUI's update methods to the event bus.
    
-   `update_underlying_price(self, data)`: Updates the main symbol and price display.
    
-   `update_forex_rates(self, data)`: Updates the currency exchange rates.
    
-   `update_option_chain(self, data)`: Updates the entire Puts/Calls section.
    
-   `update_account_metrics(self, data)`: Updates the "Account Metrics" box.
    
-   `update_trade_stats(self, data)`: Updates the "Trade Statistics" box.
    
-   `update_active_contract(self, data)`: Updates the "Active Contract" section.
    
-   `on_error(self, error_message)`: Logs an error to the preferences console.
    
-   `on_config_update(self)`: Public slot to trigger a reload of all settings from the config manager.
    
-   `clear_item(self, group_name, item_key)`: Clears a single data field to `-`.
    
-   `clear_group(self, group_name)`: Clears all fields in a UI group to `-`.
    
-   `clear_all_data(self)`: Clears all dynamic data fields on the GUI.
    

### Private Methods

These methods are used internally for setup and are not meant to be called from outside the class.

-   `_init_tkinter_variables()`: Initializes all `tk.StringVar` objects.
    
-   `_setup_market_display()`: Constructs the main layout of the window.
    
-   `_setup_status_bar()`: Constructs the bottom status bar.
    
-   `_update_clock()`: The recurring method that updates the clock every second.
    
-   `_check_data_freshness()`: The recurring method that updates the health indicator.
    
-   `_show_preferences_popup()`: Creates and displays the modal preferences window.
    
-   `_load_preferences_from_config()`: Loads all settings from the config manager into the GUI's variables.
    
-   `_save_preferences(...)`: Saves all settings from the preferences window back to the config manager.
    
-   `_edit_risk_table_cell(...)`: The event handler for making the risk table editable.
    
-   `_create_option_column(...)`: A helper factory for building the Puts/Calls columns.
    
-   `_record_update()`: Helper to record the timestamp of a data update.
    
-   `_format_max_trade_value(...)`: Helper to format a currency value in an entry widget.
    
-   `_populate_with_fake_data()`: Helper to fill the UI with sample data for standalone mode.
    
-   `_start_config_polling()`: Starts periodic synchronization with the config manager.
    
-   `_sync_with_config()`: Synchronizes the GUI with the config manager and checks for file changes.
    
-   `force_config_refresh()`: Forces a complete refresh of all configuration data from the config manager.

## Configuration Synchronization

The GUI automatically synchronizes with the configuration manager to ensure settings remain up-to-date:

### Automatic Config Polling

The GUI implements a background polling mechanism that checks for configuration file changes every 5 seconds. When changes are detected, the GUI automatically refreshes its settings without requiring a restart.

**Features:**
- **File Change Detection**: Monitors the config.json file for modifications
- **Automatic Refresh**: Reloads settings when changes are detected
- **Non-Intrusive**: Runs in the background without affecting UI responsiveness
- **Error Handling**: Gracefully handles configuration errors without crashing

### Manual Configuration Refresh

The GUI provides a `force_config_refresh()` method that can be called to manually trigger a complete configuration reload. This is useful when external changes are made to the configuration that the polling mechanism might miss.

### Configuration Integration Points

The GUI integrates with the configuration system at several points:
- **Startup**: Loads initial settings during initialization
- **Preferences Window**: Reads and writes settings through the config manager
- **Runtime Updates**: Responds to `config_updated` events from the event bus
- **Background Polling**: Periodically checks for file changes

## Color Coding Features

The GUI includes intelligent color coding for various financial metrics to provide quick visual feedback:

### Price Movement Color Coding

#### Underlying Price, Call Prices, and Put Prices
- **Green**: When the current price is higher than the previous tick
- **Red**: When the current price is lower than the previous tick  
- **Black**: When the current price equals the previous tick or on first update

### Account Metrics Color Coding

#### Account Value
- **Green**: When account value is higher than the starting value
- **Red**: When account value is lower than the starting value  
- **Black**: When account value equals the starting value or when data is unavailable

#### Daily P&L (Profit & Loss)
- **Green**: When daily P&L is positive
- **Red**: When daily P&L is negative
- **Black**: When daily P&L is zero or when data is unavailable

### Active Contract Color Coding

#### P&L Fields
- **Green**: When P&L is positive
- **Red**: When P&L is negative
- **Black**: When P&L is zero or when data is unavailable

### Trade Statistics Color Coding

#### Win/Loss Sums
- **Green**: Total wins sum (always green)
- **Red**: Total losses sum (always red)

## Implementation Details

The color coding is implemented in the following methods:

- `update_underlying_price()`: Handles underlying price movement color coding
- `update_option_chain()`: Handles call and put price movement color coding
- `update_account_metrics()`: Handles account value and daily P&L color coding
- `update_active_contract()`: Handles active contract P&L color coding
- `clear_group()` and `clear_item()`: Reset colors when data is cleared

The system automatically handles:
- Currency formatting ($, %, commas)
- Invalid or missing data (shows black color)
- Real-time updates when new data arrives
- Proper color reset when data is cleared
- Price movement tracking (compares current vs previous tick)

## Usage

The color coding works automatically when data is updated through the event system:

```python
# Example: Update account metrics with color coding
event_bus.emit("account_metrics_update", {
    "account_value": "$110,000.00",
    "starting_value": "$100,000.00", 
    "daily_pnl": "$5,000.00",
    "daily_pnl_percent": "5.00%"
})
```

The GUI will automatically apply green color to account value (higher than starting) and daily P&L (positive).