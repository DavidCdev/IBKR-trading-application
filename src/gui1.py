import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
import threading
import time
import random
import os
from logger import LogLevel, get_logger
from event_bus import EventPriority

logger = get_logger('GUI')

class IBTradingGUI:
    """
    A pure tkinter graphical user interface for a trading application.
    
    This version contains only the visual components. All backend logic,
    data processing, and event handling have been removed. Placeholders and
    comments indicate where to connect backend functionality.
    """

    def __init__(self, event_bus=None, config_manager=None, standalone_mode=False):
        logger.info("Initializing IBTradingGUI...")
        # --- Root Window Setup ---
        self.root = tk.Tk()
        self.root.title("IB Trading GUI")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        logger.debug("Root window created")

        # --- Core Components ---
        self.event_bus = event_bus
        self.last_update_time = None
        self._update_count = 0
        self._error_count = 0
        
        # --- Price Movement Tracking ---
        self.previous_prices = {
            'underlying': 0.0,
            'call_price': 0.0,
            'put_price': 0.0
        }
        
        # If no config manager is provided, use the mock one for standalone operation.
        if config_manager is None:
            logger.warning("No config manager provided, using mock config")
            mock_config_data = {
                "connection": {"host": "127.0.0.1", "port": 7497, "client_id": 1},
                "trading": {
                    "underlying_symbol": "SPY", 
                    "risk_levels": [
                        {"loss_threshold": "0", "account_trade_limit": "30", "stop_loss": "20", "profit_gain": ""},
                        {"loss_threshold": "15", "account_trade_limit": "10", "stop_loss": "15", "profit_gain": ""},
                        {"loss_threshold": "25", "account_trade_limit": "5", "stop_loss": "5", "profit_gain": ""}
                    ],
                    "max_trade_value": 500.0,
                    "trade_delta": 0.05,
                    "runner": 1
                },
                "application": {
                    "log_level": True
                },
                "debug": {
                    "master_debug": False,
                    "modules": {
                        "IB_CONNECTION": False,
                        "ACCOUNT_MANAGER": False,
                        "ORDER_EXECUTION": False,
                        "GUI": False,
                        "PERFORMANCE_MONITOR": False,
                        "SELF_HEALING": False,
                        "EVENT_BUS": False,
                        "CONFIG_MANAGER": False
                    }
                }
            }
            self.config_manager = MockConfigManager(mock_config_data)
            standalone_mode = True 
            logger.info("Running in standalone mode with mock config.")
        else:
            self.config_manager = config_manager
            logger.debug("Using provided config manager")

        if self.event_bus:
            logger.debug("Event bus provided, registering listeners")
            self.register_event_listeners()
        else:
            logger.warning("No event bus provided")

        # --- Initialize Tkinter Variables ---
        logger.debug("Initializing Tkinter variables")
        self._init_tkinter_variables()

        # --- Main Frame ---
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        logger.debug("Main frame created")

        # --- Status Bar ---
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        self._setup_status_bar()
        logger.debug("Status bar created")

        # --- Build the Main Display ---
        logger.debug("Setting up market display")
        self._setup_market_display()
        
        # --- Styling (Optional) ---
        try:
            self.style = ttk.Style()
            self.style.theme_use('default')
            self.style.configure("Green.Horizontal.TProgressbar", background='green')
            self.style.configure("Yellow.Horizontal.TProgressbar", background='yellow')
            self.style.configure("Red.Horizontal.TProgressbar", background='red')
            self.style.configure("Header.TLabel", font=("", 11, "bold"))
            logger.debug("Custom styles applied successfully")
        except Exception as e:
            logger.warning(f"Could not apply custom styles: {e}")
            pass
            
        # --- Final Setup ---
        logger.debug("Loading preferences from config")
        self._load_preferences_from_config() # Load initial config
        if standalone_mode:
            logger.debug("Populating with fake data for standalone mode")
            self._populate_with_fake_data()
            # Force GUI update to ensure data is displayed
            self.root.update()
        
        self._update_clock()
        self._check_data_freshness()
        
        # Start periodic config and connection state polling
        logger.debug("Starting config polling")
        self._start_config_polling()
        logger.info("GUI initialization complete.")

    def _init_tkinter_variables(self):
        """Initializes all tk.StringVar, etc., for the widgets, defaulting to '-'."""
        # Status Bar
        self.status_connection_var = tk.StringVar(value="Disconnected")
        self.health_progress_var = tk.DoubleVar(value=0)
        self.current_time_var = tk.StringVar(value="-")

        # Trading Information
        self.trading_info_var = tk.StringVar(value="-")
        self.forex_rate1_var = tk.StringVar(value="-")
        self.forex_rate2_var = tk.StringVar(value="-")

        # Option Information
        self.strike_info_var = tk.StringVar(value="-")
        self.expiration_info_var = tk.StringVar(value="-")
        self.call_vars = { "price": tk.StringVar(value="-"), "bid": tk.StringVar(value="-"), "ask": tk.StringVar(value="-"), "delta": tk.StringVar(value="-"), "gamma": tk.StringVar(value="-"), "theta": tk.StringVar(value="-"), "vega": tk.StringVar(value="-"), "oi": tk.StringVar(value="-"), "volume": tk.StringVar(value="-") }
        self.put_vars = { "price": tk.StringVar(value="-"), "bid": tk.StringVar(value="-"), "ask": tk.StringVar(value="-"), "delta": tk.StringVar(value="-"), "gamma": tk.StringVar(value="-"), "theta": tk.StringVar(value="-"), "vega": tk.StringVar(value="-"), "oi": tk.StringVar(value="-"), "volume": tk.StringVar(value="-") }

        # Bottom Row
        self.account_metrics_vars = { "account_value": tk.StringVar(value="-"), "starting_value": tk.StringVar(value="-"), "high_water_mark": tk.StringVar(value="-"), "daily_pnl": tk.StringVar(value="-"), "daily_pnl_percent": tk.StringVar(value="-") }
        self.trade_stats_vars = { "win_rate": tk.StringVar(value="-"), "win_count": tk.StringVar(value="-"), "win_sum": tk.StringVar(value="-"), "loss_count": tk.StringVar(value="-"), "loss_sum": tk.StringVar(value="-"), "total_trades": tk.StringVar(value="-") }
        self.active_contract_vars = { "symbol": tk.StringVar(value="-"), "quantity": tk.StringVar(value="-"), "pnl_usd": tk.StringVar(value="-"), "pnl_pct": tk.StringVar(value="-") }
        
        self.variable_groups = {
            'trading_info': {'trading_info': self.trading_info_var, 'forex1': self.forex_rate1_var, 'forex2': self.forex_rate2_var},
            'option_chain': {**self.call_vars, **self.put_vars, 'strike': self.strike_info_var, 'expiration': self.expiration_info_var},
            'account_metrics': self.account_metrics_vars,
            'trade_stats': self.trade_stats_vars,
            'active_contract': self.active_contract_vars
        }

        # Preferences Popup
        self.host_var = tk.StringVar()
        self.port_var = tk.IntVar()
        self.client_id_var = tk.IntVar()
        self.underlying_var = tk.StringVar()
        self.trade_delta_var = tk.DoubleVar()
        self.runner_var = tk.IntVar()
        self.max_trade_value_var = tk.DoubleVar()
        self.master_debug_var = tk.BooleanVar()
        self.debug_modules_vars = {}  # Will store StringVar for each module's log level
        self.conn_button_var = tk.StringVar(value="Connect")
        self.conn_status_var = tk.StringVar(value="Disconnected")

    def run(self):
        logger.info("Starting Tkinter main event loop.")
        try:
            # Ensure we're in the main thread for Tkinter
            if threading.current_thread() is not threading.main_thread():
                logger.warning("GUI is running in a non-main thread. This may cause Tkinter issues.")
            
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error in main event loop: {e}")
        finally:
            logger.info("Main event loop ended.")

    def on_close(self):
        """Handle application close with proper cleanup."""
        try:
            # Clean up event monitor if it exists
            if hasattr(self, 'event_monitor_window') and self.event_monitor_window:
                try:
                    self.event_monitor_window.on_close()
                    logger.info("Event monitor cleaned up")
                except Exception as e:
                    logger.warning(f"Error cleaning up event monitor: {e}")
            
            # Clean up event bus wrapper if it exists
            if hasattr(self, 'event_bus_wrapper') and self.event_bus_wrapper:
                try:
                    self.event_bus_wrapper.cleanup()
                    logger.info("Event bus wrapper cleaned up")
                except Exception as e:
                    logger.warning(f"Error cleaning up event bus wrapper: {e}")
            
            # Stop the event bus
            if hasattr(self, 'event_bus') and self.event_bus:
                try:
                    self.event_bus.stop()
                    logger.info("Event bus stopped")
                except Exception as e:
                    logger.warning(f"Error stopping event bus: {e}")
            
            # Force garbage collection
            import gc
            collected = gc.collect()
            if collected > 0:
                logger.info(f"Garbage collection collected {collected} objects")
            
            logger.info("Application cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during application cleanup: {e}")
        
        # Destroy the main window
        self.root.destroy()

    # --- Event Handlers / Public Data Update API ---

    def register_event_listeners(self):
        """Register all event listeners for the GUI."""
        logger.debug("Registering GUI event listeners")
        
        # Connection events
        self.event_bus.on("ib.connected", self.on_ib_connected)
        self.event_bus.on("ib.disconnected", self.on_ib_disconnected)
        self.event_bus.on("ib.error", self.on_ib_error)
        self.event_bus.on("ib.connection_error", self.on_ib_connection_error)
        self.event_bus.on("ib.order_error", self.on_ib_order_error)
        self.event_bus.on("ib.market_data_error", self.on_ib_market_data_error)
        
        # Circuit breaker and recovery events
        self.event_bus.on("ib.circuit_breaker_activated", self.on_ib_circuit_breaker_activated)
        self.event_bus.on("ib.order_circuit_breaker_activated", self.on_ib_order_circuit_breaker_activated)
        self.event_bus.on("ib.market_data_backoff_activated", self.on_ib_market_data_backoff_activated)
        
        # Market data events
        self.event_bus.on("market_data.tick_update", self.on_market_data_tick)
        self.event_bus.on("market_data.subscribed", self.on_market_data_subscribed)
        self.event_bus.on("market_data.unsubscribed", self.on_market_data_unsubscribed)
        self.event_bus.on("market_data.error", self.on_market_data_error)
        
        # Order events
        self.event_bus.on("order.status_update", self.on_order_status_update)
        self.event_bus.on("order.fill", self.on_order_fill)
        self.event_bus.on("order.commission_report", self.on_order_commission_report)
        self.event_bus.on("order.rejected", self.on_order_rejected)
        self.event_bus.on("order.chased", self.on_order_chased)
        
        # Account events
        self.event_bus.on("account.summary_update", self.on_account_summary_update)
        self.event_bus.on("account.pnl_update", self.on_account_pnl_update)
        self.event_bus.on("account.transactions_update", self.on_account_transactions_update)
        self.event_bus.on("account.summary_error", self.on_account_summary_error)
        self.event_bus.on("account.pnl_error", self.on_account_pnl_error)
        self.event_bus.on("account.transactions_error", self.on_account_transactions_error)
        
        # Position and order events
        self.event_bus.on("positions_update", self.on_positions_update)
        self.event_bus.on("open_orders_update", self.on_open_orders_update)
        self.event_bus.on("active_contract_status_update", self.on_active_contract_status_update)
        
        # Trade status events
        self.event_bus.on("trade_status_update", self.on_trade_status_update)
        
        # Options events
        self.event_bus.on("option_chain_update", self.on_options_chain_update)
        self.event_bus.on("options.chain_error", self.on_options_chain_error)
        self.event_bus.on("options.selection_update", self.on_options_selection_update)
        
        # Trading information events (filtered for underlying symbol)
        self.event_bus.on("underlying_price_update", self.update_underlying_price)
        self.event_bus.on("forex_update", self.update_forex_rates)
        
        # Account metrics events
        self.event_bus.on("account_metrics_update", self.update_account_metrics)
        self.event_bus.on("trade_stats_update", self.update_trade_stats)
        self.event_bus.on("active_contract_update", self.update_active_contract)
        
        logger.info("GUI event listeners registered successfully")
    
    def _record_update(self):
        """Records the timestamp of the latest data update and resets the health bar."""
        self.last_update_time = time.time()
        self._update_count += 1
        self.health_progress_var.set(0) # Reset progress bar on new update
        logger.debug(f"Data update recorded (update #{self._update_count})")
    
    def update_underlying_price(self, data):
        """Thread-safe update of underlying price display with filtering for configured symbol."""
        def _update():
            try:
                symbol = data.get('symbol', '')
                price = data.get('price', 0)
                
                # Only update if this is the configured underlying symbol
                configured_symbol = self.config_manager.get('trading', 'underlying_symbol', 'SPY')
                if symbol != configured_symbol:
                    logger.debug(f"Ignoring price update for {symbol}, configured symbol is {configured_symbol}")
                    return
                
                if price > 0:
                    # Update the trading information display
                    self.trading_info_var.set(f"{symbol}: ${price:.2f}")
                    
                    # Track price movement
                    previous_price = self.previous_prices.get('underlying', 0)
                    if previous_price > 0:
                        change = price - previous_price
                        change_percent = (change / previous_price) * 100
                        
                        # Add color coding for price movement
                        if change > 0:
                            self.trading_info_var.set(f"{symbol}: ${price:.2f} (+${change:.2f}, +{change_percent:.2f}%)")
                        elif change < 0:
                            self.trading_info_var.set(f"{symbol}: ${price:.2f} (${change:.2f}, {change_percent:.2f}%)")
                    
                    self.previous_prices['underlying'] = price
                    self._record_update()
                    logger.debug(f"Updated underlying price: {symbol} ${price:.2f}")
                
            except Exception as e:
                logger.error(f"Error updating underlying price: {e}")
        
        # Schedule update on main thread
        if hasattr(self, 'root') and self.root:
            try:
                self.root.after(0, _update)
            except Exception as e:
                # Fallback: execute directly if main loop is not running
                logger.debug(f"Main loop not running, executing update directly: {e}")
                _update()
        else:
            logger.warning("GUI root not available for update")
    
    def update_forex_rates(self, data):
        """Thread-safe update of forex rates display on the right side of trading information."""
        def _update():
            try:
                from_currency = data.get('from_currency', 'USD')
                to_currency = data.get('to_currency', 'CAD')
                rate = data.get('rate', 0)
                reciprocal_rate = data.get('reciprocal_rate', 0)
                
                if rate > 0:
                    # Update forex rate displays
                    self.forex_rate1_var.set(f"{from_currency}/{to_currency}: {rate:.4f}")
                    self.forex_rate2_var.set(f"{to_currency}/{from_currency}: {reciprocal_rate:.4f}")
                    
                    self._record_update()
                    logger.debug(f"Updated forex rates: {from_currency}/{to_currency} = {rate:.4f}")
                
            except Exception as e:
                logger.error(f"Error updating forex rates: {e}")
        
        # Schedule update on main thread
        if hasattr(self, 'root') and self.root:
            try:
                self.root.after(0, _update)
            except Exception as e:
                # Fallback: execute directly if main loop is not running
                logger.debug(f"Main loop not running, executing update directly: {e}")
                _update()
        else:
            logger.warning("GUI root not available for update")
    
    def on_options_selection_update(self, data):
        """Handle options selection updates from subscription manager."""
        try:
            expiration = data.get('expiration', '')
            strike = data.get('strike', 0)
            underlying_symbol = data.get('underlying_symbol', 'SPY')
            
            # Update the strike and expiration display
            if strike > 0 and expiration:
                self.strike_info_var.set(f"${strike:.2f}")
                self.expiration_info_var.set(expiration)
                
                logger.debug(f"Updated options selection: {underlying_symbol} {expiration} ${strike:.2f}")
            
        except Exception as e:
            logger.error(f"Error handling options selection update: {e}")
    
    def on_options_chain_update(self, data):
        """Handle options chain updates from subscription manager."""
        logger.debug(f"GUI RECEIVED: options.chain_update - Data: {data}")
        try:
            options = data.get('options', [])
            underlying_symbol = data.get('underlying_symbol', 'SPY')
            
            # Filter for the configured underlying symbol
            configured_symbol = self.config_manager.get('trading', 'underlying_symbol', 'SPY')
            if underlying_symbol != configured_symbol:
                logger.debug(f"Ignoring options chain for {underlying_symbol}, configured symbol is {configured_symbol}")
                return
            
            if options:
                # Find the current strike and expiration being tracked
                current_strike = None
                current_expiration = None
                
                # Look for the currently subscribed options
                for option in options:
                    if option.get('subscribed', False):
                        current_strike = option.get('strike')
                        current_expiration = option.get('expiration')
                        break
                
                if current_strike and current_expiration:
                    # Find call and put data for current strike/expiration
                    call_data = {}
                    put_data = {}
                    
                    for option in options:
                        if (option.get('strike') == current_strike and 
                            option.get('expiration') == current_expiration):
                            
                            if option.get('right') == 'C':
                                call_data = {
                                    'price': f"${option.get('last', 0):.2f}" if option.get('last') else "-",
                                    'bid': f"${option.get('bid', 0):.2f}" if option.get('bid') else "-",
                                    'ask': f"${option.get('ask', 0):.2f}" if option.get('ask') else "-",
                                    'volume': f"{option.get('volume', 0):,}" if option.get('volume') else "-",
                                    'open_interest': f"{option.get('openInterest', 0):,}" if option.get('openInterest') else "-",
                                    'delta': f"{option.get('delta', 0):.3f}" if option.get('delta') else "-",
                                    'gamma': f"{option.get('gamma', 0):.4f}" if option.get('gamma') else "-",
                                    'theta': f"{option.get('theta', 0):.3f}" if option.get('theta') else "-",
                                    'vega': f"{option.get('vega', 0):.2f}" if option.get('vega') else "-"
                                }
                            elif option.get('right') == 'P':
                                put_data = {
                                    'price': f"${option.get('last', 0):.2f}" if option.get('last') else "-",
                                    'bid': f"${option.get('bid', 0):.2f}" if option.get('bid') else "-",
                                    'ask': f"${option.get('ask', 0):.2f}" if option.get('ask') else "-",
                                    'volume': f"{option.get('volume', 0):,}" if option.get('volume') else "-",
                                    'open_interest': f"{option.get('openInterest', 0):,}" if option.get('openInterest') else "-",
                                    'delta': f"{option.get('delta', 0):.3f}" if option.get('delta') else "-",
                                    'gamma': f"{option.get('gamma', 0):.4f}" if option.get('gamma') else "-",
                                    'theta': f"{option.get('theta', 0):.3f}" if option.get('theta') else "-",
                                    'vega': f"{option.get('vega', 0):.2f}" if option.get('vega') else "-"
                                }
                    
                    # Update the option chain display
                    option_chain_data = {
                        'strike': current_strike,
                        'expiration': current_expiration,
                        'call_data': call_data,
                        'put_data': put_data
                    }
                    
                    self.update_option_chain(option_chain_data)
                    logger.debug(f"Updated option chain: strike=${current_strike}, expiration={current_expiration}")
            
        except Exception as e:
            logger.error(f"Error handling options chain update: {e}")

    def update_account_metrics(self, data):
        """Updates the Account Metrics display with color coding."""
        logger.debug(f"Updating account metrics: {data}")
        self._record_update()
        for key, var in self.account_metrics_vars.items():
            var.set(data.get(key, "-"))
        
        # Color coding logic for account metrics
        default_color = 'black'  # Use black for neutral/default color
        
        # Account Value color coding (green when higher than starting value, red when lower)
        account_value_str = self.account_metrics_vars['account_value'].get().replace('$', '').replace(',', '')
        starting_value_str = self.account_metrics_vars['starting_value'].get().replace('$', '').replace(',', '')
        
        try:
            account_val = float(account_value_str)
            starting_val = float(starting_value_str)
            if account_val > starting_val:
                account_color = 'green'
            elif account_val < starting_val:
                account_color = 'red'
            else:
                account_color = default_color
            logger.debug(f"Account value: ${account_val:,.2f}, starting: ${starting_val:,.2f}, color: {account_color}")
        except (ValueError, TypeError):
            # This handles cases where the value is '-' or invalid
            logger.debug(f"Could not parse account values: '{account_value_str}', '{starting_value_str}'")
            account_color = default_color
        
        # Daily P&L color coding (green when positive, red when negative)
        daily_pnl_str = self.account_metrics_vars['daily_pnl'].get().replace('$', '').replace(',', '')
        daily_pnl_pct_str = self.account_metrics_vars['daily_pnl_percent'].get().replace('%', '').replace(',', '')
        
        try:
            daily_pnl_val = float(daily_pnl_str)
            if daily_pnl_val > 0:
                pnl_color = 'green'
            elif daily_pnl_val < 0:
                pnl_color = 'red'
            else:
                pnl_color = default_color
            logger.debug(f"Daily P&L: ${daily_pnl_val:,.2f}, color: {pnl_color}")
        except (ValueError, TypeError):
            # This handles cases where the value is '-' or invalid
            logger.debug(f"Could not parse daily P&L value: '{daily_pnl_str}'")
            pnl_color = default_color
        
        # Apply colors to the labels
        if hasattr(self, 'account_metrics_labels'):
            if 'account_value' in self.account_metrics_labels:
                self.account_metrics_labels['account_value'].config(foreground=account_color)
            if 'daily_pnl' in self.account_metrics_labels:
                self.account_metrics_labels['daily_pnl'].config(foreground=pnl_color)
            if 'daily_pnl_percent' in self.account_metrics_labels:
                self.account_metrics_labels['daily_pnl_percent'].config(foreground=pnl_color)
        
        logger.debug("Account metrics updated with color coding")

    def update_trade_stats(self, data):
        """Updates the Trade Statistics display."""
        logger.debug(f"Updating trade stats: {data}")
        self._record_update()
        for key, var in self.trade_stats_vars.items():
            var.set(data.get(key, "-"))
        logger.debug("Trade stats updated")

    def update_active_contract(self, data):
        """Updates the Active Contract display and color-codes P/L."""
        logger.debug(f"Updating active contract: {data}")
        self._record_update()
        for key, var in self.active_contract_vars.items():
            var.set(data.get(key, "-"))

        # Color coding logic for P/L
        pnl_usd_str = self.active_contract_vars['pnl_usd'].get().replace('$', '').replace(',', '')
        default_color = 'black' # Use black for neutral/default color
        color = default_color
        try:
            pnl_val = float(pnl_usd_str)
            if pnl_val > 0:
                color = 'green'
            elif pnl_val < 0:
                color = 'red'
            logger.debug(f"Active contract PnL: ${pnl_val:,.2f}, color: {color}")
        except (ValueError, TypeError):
            # This handles cases where the value is '-' or invalid
            logger.debug(f"Could not parse PnL value: '{pnl_usd_str}'")
            pass 

        if hasattr(self, 'active_contract_labels'):
            for label in self.active_contract_labels.values():
                label.config(foreground=color)
        
        logger.debug("Active contract updated")

    def on_error(self, error_message):
        self._error_count += 1
        logger.error(f"GUI error #{self._error_count}: {error_message}")
        if hasattr(self, 'conn_log') and self.conn_log:
            timestamp = datetime.now().strftime("%I:%M:%S %p")
            log_message = f"[{timestamp}] Error: {error_message}\n"
            self.conn_log.config(state=tk.NORMAL)
            self.conn_log.insert(tk.END, log_message)
            self.conn_log.see(tk.END)
            self.conn_log.config(state=tk.DISABLED)
            logger.debug("Error logged to connection log")
        else:
            logger.error(f"Error: {error_message}")

    def on_config_update(self, data=None):
        logger.info("Configuration updated externally. Reloading settings.")
        self.force_config_refresh()

    # --- Public Data Clearing API ---

    def clear_item(self, group_name, item_key):
        """Clears a single data item in the GUI."""
        logger.debug(f"Clearing item '{item_key}' in group '{group_name}'")
        if group_name in self.variable_groups and item_key in self.variable_groups[group_name]:
            self.variable_groups[group_name][item_key].set("-")
            # Special handling for clearing colors
            if group_name == 'active_contract' and item_key in ['pnl_usd', 'pnl_pct']:
                self.update_active_contract({}) # Recalculate colors
            elif group_name == 'account_metrics' and item_key in ['account_value', 'daily_pnl', 'daily_pnl_percent']:
                self.update_account_metrics({}) # Recalculate colors
            logger.debug(f"Item '{item_key}' in group '{group_name}' cleared")
        else:
            logger.warning(f"Warning: Item '{item_key}' in group '{group_name}' not found.")

    def clear_group(self, group_name):
        """Clears all data items in a specified group."""
        logger.debug(f"Clearing group '{group_name}'")
        if group_name in self.variable_groups:
            for key in self.variable_groups[group_name]:
                self.variable_groups[group_name][key].set("-")
            # Special handling for clearing colors
            if group_name == 'active_contract':
                self.update_active_contract({}) # Recalculate colors
            elif group_name == 'account_metrics':
                self.update_account_metrics({}) # Recalculate colors
            logger.debug(f"Group '{group_name}' cleared")
        else:
            logger.warning(f"Warning: Group '{group_name}' not found.")

    def clear_all_data(self):
        """Clears all dynamic data fields in the GUI."""
        logger.info("Clearing all data fields")
        for group_name in self.variable_groups:
            self.clear_group(group_name)
        logger.debug("All data fields cleared")

    # --- Widget Setup and Internal Methods ---

    def _update_clock(self):
        """Updates the time in the status bar every second."""
        now = datetime.now().strftime("%I:%M:%S %p")
        self.current_time_var.set(now)
        self.root.after(1000, self._update_clock)

    def _check_data_freshness(self):
        """Periodically checks the time since the last update and updates the health indicator."""
        logger.debug("Checking data freshness")
        color = "gray"
        progress = 0
        style = "Green.Horizontal.TProgressbar"

        if self.last_update_time:
            time_since_update = time.time() - self.last_update_time
            
            if time_since_update < 5:  # Fresh data
                color = "green"
                progress = 100
                style = "Green.Horizontal.TProgressbar"
            elif time_since_update < 15:  # Stale data
                color = "yellow"
                progress = 50
                style = "Yellow.Horizontal.TProgressbar"
            else:  # Very stale data
                color = "red"
                progress = 25
                style = "Red.Horizontal.TProgressbar"
                
            logger.debug(f"Data freshness: {time_since_update:.1f}s ago, color: {color}")

        self.health_progress_var.set(progress)
        
        # Schedule next check
        self.root.after(1000, self._check_data_freshness)

    def _setup_status_bar(self):
        """Sets up the status bar at the bottom of the window."""
        preferences_btn = ttk.Button(self.status_bar, text="⚙", command=self._show_preferences_popup, width=3)
        preferences_btn.pack(side=tk.LEFT, padx=(5, 5))
        
        # Event Monitor button
        event_monitor_btn = ttk.Button(self.status_bar, text="📊", command=self._show_event_monitor, width=3)
        event_monitor_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(self.status_bar, text="Connection:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Label(self.status_bar, textvariable=self.status_connection_var).pack(side=tk.LEFT, padx=(0, 10))
        
        self.health_canvas = tk.Canvas(self.status_bar, width=20, height=20, highlightthickness=0)
        self.health_indicator_oval = self.health_canvas.create_oval(4, 4, 16, 16, fill="gray", outline="gray")
        self.health_canvas.pack(side=tk.LEFT, padx=(5,5))
        
        self.health_bar = ttk.Progressbar(self.status_bar, orient="horizontal", length=50, mode="determinate", variable=self.health_progress_var, maximum=3)
        self.health_bar.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(self.status_bar, textvariable=self.current_time_var).pack(side=tk.RIGHT, padx=(0, 5))

    def _setup_market_display(self):
        """Sets up the main market data and statistics display."""
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        trading_label = ttk.Label(top_frame, text="Trading Information", font=("", 10, "bold"))
        trading_frame = ttk.LabelFrame(top_frame, labelwidget=trading_label, padding=10)
        trading_frame.pack(fill=tk.X)
        info_frame = ttk.Frame(trading_frame)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        self.underlying_price_label = ttk.Label(info_frame, textvariable=self.trading_info_var, font=("", 12, "bold"))
        self.underlying_price_label.pack(side=tk.LEFT)
        forex_frame = ttk.Frame(info_frame)
        forex_frame.pack(side=tk.RIGHT)
        ttk.Label(forex_frame, textvariable=self.forex_rate1_var).pack(anchor='e')
        ttk.Label(forex_frame, textvariable=self.forex_rate2_var).pack(anchor='e')

        option_label = ttk.Label(top_frame, text="Option Information", font=("", 10, "bold"))
        option_info_frame = ttk.LabelFrame(top_frame, labelwidget=option_label, padding=10)
        option_info_frame.pack(fill=tk.X, expand=True, pady=10)
        strike_exp_frame = ttk.Frame(option_info_frame)
        strike_exp_frame.pack(fill=tk.X, pady=(5, 10), padx=10)
        ttk.Label(strike_exp_frame, text="Strike:", font=("", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(strike_exp_frame, textvariable=self.strike_info_var, font=("", 10)).pack(side=tk.LEFT, padx=(5, 20))
        ttk.Label(strike_exp_frame, text="Expiration:", font=("", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(strike_exp_frame, textvariable=self.expiration_info_var, font=("", 10)).pack(side=tk.LEFT, padx=5)
        columns_frame = ttk.Frame(option_info_frame)
        columns_frame.pack(fill=tk.X, expand=True)
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(1, weight=0)
        columns_frame.columnconfigure(2, weight=1)
        put_frame = self._create_option_column(columns_frame, "Puts", self.put_vars)
        put_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5))
        separator = ttk.Separator(columns_frame, orient='vertical')
        separator.grid(row=0, column=1, sticky='ns', padx=10)
        call_frame = self._create_option_column(columns_frame, "Calls", self.call_vars)
        call_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 10))

        ac_label = ttk.Label(self.main_frame, text="Active Contract", font=("", 10, "bold"))
        active_contract_frame = ttk.LabelFrame(self.main_frame, labelwidget=ac_label, padding=10)
        active_contract_frame.pack(fill=tk.X, padx=5, pady=(0, 10))
        ac_inner_frame = ttk.Frame(active_contract_frame)
        ac_inner_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.active_contract_labels = {}
        active_contract_fields = [ ("Symbol:", "symbol"), ("Quantity:", "quantity"), ("P/L ($):", "pnl_usd"), ("P/L (%):", "pnl_pct") ]
        for i, (label, key) in enumerate(active_contract_fields):
            ttk.Label(ac_inner_frame, text=label).grid(row=0, column=i*2, sticky=tk.W, padx=(0, 5))
            value_label = ttk.Label(ac_inner_frame, textvariable=self.active_contract_vars[key])
            value_label.grid(row=0, column=i*2 + 1, sticky=tk.W, padx=(0, 20))
            if key in ['pnl_usd', 'pnl_pct']:
                self.active_contract_labels[key] = value_label

        bottom_row_frame = ttk.Frame(self.main_frame)
        bottom_row_frame.pack(fill=tk.X, padx=5, pady=10)
        am_label = ttk.Label(bottom_row_frame, text="Account Metrics", font=("", 10, "bold"))
        account_metrics_frame = ttk.LabelFrame(bottom_row_frame, labelwidget=am_label, padding=10)
        account_metrics_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.account_metrics_labels = {}
        account_metrics_fields = [ ("Account Value", "account_value"), ("Starting Value", "starting_value"), ("High Water Mark", "high_water_mark"), ("Daily P&L", "daily_pnl"), ("Daily P&L %", "daily_pnl_percent") ]
        for i, (label, key) in enumerate(account_metrics_fields):
            ttk.Label(account_metrics_frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            value_label = ttk.Label(account_metrics_frame, textvariable=self.account_metrics_vars[key])
            value_label.grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)
            # Store labels for fields that need color coding
            if key in ['account_value', 'daily_pnl', 'daily_pnl_percent']:
                self.account_metrics_labels[key] = value_label

        ts_label = ttk.Label(bottom_row_frame, text="Trade Statistics", font=("", 10, "bold"))
        trade_stats_frame = ttk.LabelFrame(bottom_row_frame, labelwidget=ts_label, padding=10)
        trade_stats_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.trade_stats_labels = {}
        trade_stats_fields = [ ("Win Rate", "win_rate"), ("Total Wins (count)", "win_count"), ("Total Wins (sum)", "win_sum"), ("Total Losses (count)", "loss_count"), ("Total Losses (sum)", "loss_sum"), ("Total Trades", "total_trades") ]
        for i, (label, key) in enumerate(trade_stats_fields):
            ttk.Label(trade_stats_frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            value_label = ttk.Label(trade_stats_frame, textvariable=self.trade_stats_vars[key])
            value_label.grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)
            self.trade_stats_labels[key] = value_label
        self.trade_stats_labels['win_sum'].config(foreground="green")
        self.trade_stats_labels['loss_sum'].config(foreground="red")

    def _create_option_column(self, parent, title, variables):
        """Helper function to create one column (Call or Put) of option data."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)
        header = ttk.Label(frame, text=title, style="Header.TLabel")
        header.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        price_label = ttk.Label(frame, textvariable=variables["price"], font=("", 14, "bold"))
        price_label.grid(row=1, column=0, columnspan=2, pady=(0, 5))
        
        # Store price label for color coding
        if title == "Calls":
            self.call_price_label = price_label
        elif title == "Puts":
            self.put_price_label = price_label
        
        fields = [ ("Bid:", "bid"), ("Ask:", "ask"), ("Delta:", "delta"), ("Gamma:", "gamma"), ("Theta:", "theta"), ("Vega:", "vega"), ("Open Int:", "oi"), ("Volume:", "volume") ]
        for i, (label_text, key) in enumerate(fields):
            row_num = i + 2
            ttk.Label(frame, text=label_text).grid(row=row_num, column=0, sticky="w", padx=5, pady=1)
            ttk.Label(frame, textvariable=variables[key]).grid(row=row_num, column=1, sticky="e", padx=5, pady=1)
        return frame

    def _show_event_monitor(self):
        """Shows the enhanced event monitor window."""
        logger.debug("Showing enhanced event monitor")
        try:
            # Clean up existing event monitor if it exists
            if hasattr(self, 'event_monitor_window') and self.event_monitor_window:
                try:
                    self.event_monitor_window.on_close()
                except Exception as e:
                    logger.warning(f"Error cleaning up existing event monitor: {e}")
            
            from enhanced_event_monitor_gui import create_enhanced_event_monitor
            self.event_monitor_window = create_enhanced_event_monitor(self.event_bus, self.root)
            
            # Ensure the window is visible and brought to front
            self.event_monitor_window.window.deiconify()
            self.event_monitor_window.window.lift()
            self.event_monitor_window.window.focus_force()
            
            logger.info("Enhanced event monitor window opened")
        except Exception as e:
            logger.error(f"Failed to open enhanced event monitor: {e}")
            messagebox.showerror("Error", f"Failed to open enhanced event monitor: {e}")

    def _show_preferences_popup(self):
        """Shows the modal preferences popup window."""
        popup = tk.Toplevel(self.root)
        popup.title("Preferences")
        popup.transient(self.root)
        popup.grab_set()
        
        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        conn_frame = ttk.Frame(notebook)
        trading_frame = ttk.Frame(notebook)
        debug_frame = ttk.Frame(notebook)
        
        notebook.add(conn_frame, text="Connection")
        notebook.add(trading_frame, text="Trading")
        notebook.add(debug_frame, text="Debug")
        
        self._setup_connection_preferences(conn_frame)
        self._setup_trading_preferences(trading_frame)
        self._setup_debug_preferences(debug_frame)
        
        # Force refresh from config manager when preferences opens
        logger.info("Preferences opened - refreshing from config manager...")
        self._load_preferences_from_config()
        
        # Load risk levels table after all widgets are created
        if hasattr(self, 'pref_risk_table'):
            self._load_risk_levels_to_preferences()
        
        # Sync connection status after all widgets are created and loaded
        self.conn_status_var.set(self.status_connection_var.get())
        if "Connected" in self.status_connection_var.get():
            self.conn_button_var.set("Disconnect")
        else:
            self.conn_button_var.set("Connect")

        button_frame = ttk.Frame(popup)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10), side=tk.BOTTOM)
        save_btn = ttk.Button(button_frame, text="Save", command=lambda: self._save_preferences(popup))
        save_btn.pack(side=tk.RIGHT, padx=(5, 0))
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=popup.destroy)
        cancel_btn.pack(side=tk.RIGHT)

    def _setup_connection_preferences(self, frame):
        """Sets up the Connection tab in the preferences popup."""
        main_frame = ttk.Frame(frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        conn_settings_frame = ttk.LabelFrame(main_frame, text="Connection Settings")
        conn_settings_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(conn_settings_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(conn_settings_frame, textvariable=self.host_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(conn_settings_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(conn_settings_frame, textvariable=self.port_var, width=6).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        ttk.Label(conn_settings_frame, text="Client ID:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(conn_settings_frame, textvariable=self.client_id_var, width=3).grid(row=0, column=5, sticky=tk.W, padx=5, pady=5)
        controls_frame = ttk.LabelFrame(main_frame, text="Connection Controls")
        controls_frame.pack(fill=tk.X, padx=5, pady=5, expand=False)
        ttk.Button(controls_frame, textvariable=self.conn_button_var, command=self._toggle_connection).pack(side=tk.LEFT, padx=5, pady=10)
        status_frame = ttk.LabelFrame(controls_frame, text="Status")
        status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20, pady=5)
        ttk.Label(status_frame, text="Connection:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_frame, textvariable=self.conn_status_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        log_frame = ttk.LabelFrame(main_frame, text="Connection Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.conn_log = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
        self.conn_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.on_error("Application started.")

    def _setup_trading_preferences(self, frame):
        """Sets up the Trading tab in the preferences popup."""
        main_frame = ttk.Frame(frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        settings_group = ttk.LabelFrame(main_frame, text="Trading Settings")
        settings_group.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(settings_group, text="Underlying Symbol:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(settings_group, textvariable=self.underlying_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(settings_group, text="Trade Delta:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(settings_group, textvariable=self.trade_delta_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        risk_group = ttk.LabelFrame(main_frame, text="Risk Tolerance")
        risk_group.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(risk_group, text="Max Trade Value:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        max_trade_entry = ttk.Entry(risk_group, textvariable=self.max_trade_value_var, width=10)
        max_trade_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        max_trade_entry.bind("<FocusOut>", self._format_max_trade_value)
        max_trade_entry.bind("<Return>", self._format_max_trade_value)
        ttk.Label(risk_group, text="Runner:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(risk_group, textvariable=self.runner_var, width=5).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        table_frame = ttk.LabelFrame(main_frame, text="Risk Levels")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        columns = ("Loss Threshold (%)", "Account Trade Limit (%)", "Stop Loss (%)", "Profit Gain (%)")
        self.pref_risk_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=5)
        for col in columns:
            self.pref_risk_table.heading(col, text=col)
            self.pref_risk_table.column(col, width=120, anchor=tk.CENTER)
        self.pref_risk_table.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.pref_risk_table.bind('<Double-1>', self._edit_risk_table_cell)
        btn_frame = ttk.Frame(table_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Add Row", command=self._add_pref_risk_row).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Selected Row", command=self._remove_pref_risk_row).pack(side=tk.LEFT, padx=5)

    def _setup_debug_preferences(self, frame):
        """Sets up the Debug tab in the preferences popup."""
        main_frame = ttk.Frame(frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Debug Settings
        debug_settings_frame = ttk.LabelFrame(main_frame, text="Debug Settings")
        debug_settings_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(debug_settings_frame, text="Master Debug (Enable All Debug Modules)", 
                       variable=self.master_debug_var).pack(anchor=tk.W, padx=5, pady=5)

        # Debug Modules
        modules_frame = ttk.LabelFrame(main_frame, text="Module Log Levels")
        modules_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Get dynamic module list from config manager
        module_names = []
        if self.config_manager:
            module_names = self.config_manager.get_available_modules()
        log_levels = [level.value for level in LogLevel]

        for i, module_name in enumerate(module_names):
            row = i // 2
            col = i % 2
            if module_name not in self.debug_modules_vars:
                self.debug_modules_vars[module_name] = tk.StringVar()
            # Combobox for log level selection
            frame = ttk.Frame(modules_frame)
            frame.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            ttk.Label(frame, text=module_name.replace('_', ' ').title()+":").pack(side=tk.LEFT)
            cb = ttk.Combobox(frame, textvariable=self.debug_modules_vars[module_name], values=log_levels, width=8, state="readonly")
            cb.pack(side=tk.LEFT)

    def _toggle_connection(self):
        """Connect/disconnect from the IB trading service."""
        if self.conn_button_var.get() == "Connect":
            # Emit connect event to IB connection
            if self.event_bus:
                self.event_bus.emit("ib.connect", {})
                self.conn_button_var.set("Disconnect")
                self.conn_status_var.set("Connecting...")
                self.status_connection_var.set("Connecting...")
                self.on_error("Connecting to IB...")
            else:
                self.on_error("No event bus available for connection.")
        else:
            # Emit disconnect event to IB connection
            if self.event_bus:
                self.event_bus.emit("ib.disconnect", {})
                self.conn_button_var.set("Connect")
                self.conn_status_var.set("Disconnecting...")
                self.status_connection_var.set("Disconnecting...")
                self.on_error("Disconnecting from IB...")
            else:
                self.on_error("No event bus available for disconnection.")

    def _load_preferences_from_config(self):
        logger.info("Loading preferences from config manager.")
        if not self.config_manager:
            logger.error("No config manager available.")
            return
        
        # Connection Settings
        self.host_var.set(self.config_manager.get('connection', 'host', '127.0.0.1'))
        self.port_var.set(self.config_manager.get('connection', 'port', 7497))
        self.client_id_var.set(self.config_manager.get('connection', 'client_id', 1))

        # Trading Settings
        self.underlying_var.set(self.config_manager.get('trading', 'underlying_symbol', 'SPY'))
        self.trade_delta_var.set(self.config_manager.get('trading', 'trade_delta', 0.05))
        self.runner_var.set(self.config_manager.get('trading', 'runner', 1))
        self.max_trade_value_var.set(self.config_manager.get('trading', 'max_trade_value', 500.0))
        
        # Debug Settings
        self.master_debug_var.set(self.config_manager.get('debug', 'master_debug', False))
        
        # Initialize debug modules variables
        debug_modules = self.config_manager.get_log_levels()
        module_names = self.config_manager.get_available_modules() if self.config_manager else []
        
        for module_name in module_names:
            if module_name not in self.debug_modules_vars:
                self.debug_modules_vars[module_name] = tk.StringVar()
            self.debug_modules_vars[module_name].set(debug_modules.get(module_name, "Info"))
        
        logger.debug(f"Loaded preferences for {len(module_names)} modules")

    def _save_preferences(self, popup):
        logger.info("Saving preferences to config manager.")
        if not self.config_manager:
            messagebox.showerror("Error", "Configuration manager not available.")
            logger.error("Configuration manager not available when saving preferences.")
            return

        try:
            # Connection Settings
            self.config_manager.set('connection', 'host', self.host_var.get())
            self.config_manager.set('connection', 'port', self.port_var.get())
            self.config_manager.set('connection', 'client_id', self.client_id_var.get())

            # Trading Settings
            self.config_manager.set('trading', 'underlying_symbol', self.underlying_var.get())
            self.config_manager.set('trading', 'trade_delta', self.trade_delta_var.get())
            self.config_manager.set('trading', 'runner', self.runner_var.get())
            self.config_manager.set('trading', 'max_trade_value', self.max_trade_value_var.get())

            # Debug Settings
            self.config_manager.set('debug', 'master_debug', self.master_debug_var.get())
            
            # Debug modules (log levels)
            debug_modules = {}
            for module_name, var in self.debug_modules_vars.items():
                debug_modules[module_name] = var.get()
            self.config_manager.set('debug', 'modules', debug_modules)

            # Risk Levels
            rows = []
            for item in self.pref_risk_table.get_children():
                values = self.pref_risk_table.item(item, "values")
                row = {
                    "loss_threshold": values[0] if values[0] != "—" else "",
                    "account_trade_limit": values[1] if values[1] != "—" else "",
                    "stop_loss": values[2] if values[2] != "—" else "",
                    "profit_gain": values[3] if values[3] != "—" else ""
                }
                rows.append(row)
            
            def sort_key(r):
                try:
                    return float(r['loss_threshold'])
                except (ValueError, TypeError):
                    return float('inf')

            rows.sort(key=sort_key)
            
            self.config_manager.set('trading', 'risk_levels', rows)
            
            self.config_manager.save_config()
            popup.destroy()
            messagebox.showinfo("Preferences", "Settings have been saved!")
            logger.info("Preferences saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preferences: {e}")
            logger.error(f"Failed to save preferences: {e}")

    def _load_risk_levels_to_preferences(self):
        """Loads risk levels from config manager into the preferences table."""
        if hasattr(self, 'pref_risk_table'):
            # Clear existing items
            for item in self.pref_risk_table.get_children():
                self.pref_risk_table.delete(item)
            
            # Load risk levels from config manager
            risk_levels = self.config_manager.get('trading', 'risk_levels', [])
            logger.info(f"Loading {len(risk_levels)} risk levels from config manager")
            
            # If no risk levels found, use defaults
            if not risk_levels:
                logger.warning("Warning: No risk levels found in config, using defaults")
                risk_levels = [
                    {"loss_threshold": "0", "account_trade_limit": "30", "stop_loss": "20", "profit_gain": ""},
                    {"loss_threshold": "15", "account_trade_limit": "10", "stop_loss": "15", "profit_gain": ""},
                    {"loss_threshold": "25", "account_trade_limit": "5", "stop_loss": "5", "profit_gain": ""}
                ]
            
            # Insert each risk level into the table
            for i, row in enumerate(risk_levels):
                values = [
                    row.get("loss_threshold", "") or "—",
                    row.get("account_trade_limit", "") or "—", 
                    row.get("stop_loss", "") or "—",
                    row.get("profit_gain", "") or "—"
                ]
                self.pref_risk_table.insert("", tk.END, values=values)
            
            logger.info(f"Risk levels table now has {len(self.pref_risk_table.get_children())} items")

    def _add_pref_risk_row(self):
        """Adds an empty row to the risk table in the popup."""
        self.pref_risk_table.insert("", tk.END, values=["—", "—", "—", "—"])

    def _remove_pref_risk_row(self):
        """Removes the selected row from the risk table in the popup."""
        selected = self.pref_risk_table.selection()
        if selected:
            self.pref_risk_table.delete(selected[0])
            
    def _edit_risk_table_cell(self, event):
        """Handle double-click to edit a cell in the risk levels table."""
        region = self.pref_risk_table.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.pref_risk_table.identify_row(event.y)
        column_id = self.pref_risk_table.identify_column(event.x)
        column_index = int(column_id.replace("#", "")) - 1
        
        x, y, width, height = self.pref_risk_table.bbox(row_id, column_id)
        
        value = self.pref_risk_table.item(row_id, "values")[column_index]
        if value == "—":
            value = ""
            
        entry = ttk.Entry(self.pref_risk_table)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def on_focus_out(event):
            new_value = entry.get() or "—"
            values = list(self.pref_risk_table.item(row_id, "values"))
            values[column_index] = new_value
            self.pref_risk_table.item(row_id, values=values)
            entry.destroy()

        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Return>", on_focus_out)

    def _format_max_trade_value(self, event):
        """Formats the Max Trade Value entry to two decimal places on focus out."""
        try:
            value = self.max_trade_value_var.get()
            # Round the value to 2 decimal places and set it back.
            # The DoubleVar will handle the float type.
            self.max_trade_value_var.set(round(value, 2))
        except (ValueError, tk.TclError):
            # If the entry is invalid (e.g., empty or non-numeric), default to 0.0
            self.max_trade_value_var.set(0.0)


    def _populate_with_fake_data(self):
        """Populates the GUI with comprehensive demo data for standalone viewing."""
        from datetime import datetime, timedelta
        
        # Get tomorrow's date for expiration
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Update current time
        self.current_time_var.set(datetime.now().strftime("%I:%M:%S %p"))
        
        # Update underlying price
        self.update_underlying_price({'symbol': 'SPY', 'price': 501.75})
        
        # Update forex rates (USD/CAD) - fix the data format
        self.update_forex_rates({
            'from_currency': 'USD',
            'to_currency': 'CAD', 
            'rate': 1.3750,
            'reciprocal_rate': 0.7272
        })
        
        # Update with SPY options for tomorrow's expiration (use only one to avoid overwriting)
        self.update_option_chain({
            'strike': 502, 
            'expiration': tomorrow_str,
            'call_data': {
                'price': '$3.10', 'bid': '$3.09', 'ask': '$3.11', 
                'delta': '0.55', 'gamma': '0.04', 'theta': '-0.06', 'vega': '0.13', 
                'oi': '12,345', 'volume': '6,789'
            },
            'put_data': {
                'price': '$2.80', 'bid': '$2.79', 'ask': '$2.81', 
                'delta': '-0.45', 'gamma': '0.04', 'theta': '-0.05', 'vega': '0.13', 
                'oi': '18,765', 'volume': '4,321'
            }
        })
        
        # Update account metrics with positive performance
        self.update_account_metrics({
            'account_value': '$105,123.45', 
            'starting_value': '$100,000.00', 
            'high_water_mark': '$106,543.21', 
            'daily_pnl': '$5,123.45', 
            'daily_pnl_percent': '5.12%'
        })
        
        # Update trade stats
        self.update_trade_stats({
            'win_rate': '75.00%', 
            'win_count': '15', 
            'win_sum': '$7,500.00', 
            'loss_count': '5', 
            'loss_sum': '$2,500.00', 
            'total_trades': '20'
        })
        
        # Update active contracts with positive profit
        self.update_active_contract({
            'symbol': 'SPY 502C', 
            'quantity': '10', 
            'pnl_usd': '$425.00', 
            'pnl_pct': '25.00%'
        })
        
        # Force GUI update to ensure active contract data is displayed
        self.root.update()
        
        # Emit additional active contracts for demo
        if self.event_bus:
            # Emit multiple active contracts with positive profit
            active_contracts = [
                {
                    'symbol': 'SPY 500C',
                    'quantity': '10',
                    'pnl_usd': '$425.00',
                    'pnl_pct': '25.00%',
                    'contract': {
                        'symbol': 'SPY',
                        'secType': 'OPT',
                        'expiration': tomorrow_str,
                        'strike': 500,
                        'right': 'C'
                    }
                },
                {
                    'symbol': 'SPY 502C',
                    'quantity': '5',
                    'pnl_usd': '$155.00',
                    'pnl_pct': '15.50%',
                    'contract': {
                        'symbol': 'SPY',
                        'secType': 'OPT',
                        'expiration': tomorrow_str,
                        'strike': 502,
                        'right': 'C'
                    }
                },
                {
                    'symbol': 'SPY 505C',
                    'quantity': '3',
                    'pnl_usd': '$85.50',
                    'pnl_pct': '18.44%',
                    'contract': {
                        'symbol': 'SPY',
                        'secType': 'OPT',
                        'expiration': tomorrow_str,
                        'strike': 505,
                        'right': 'C'
                    }
                }
            ]
            
            # Emit active contract status update
            self.event_bus.emit('active_contract_status_update', {
                'active_contracts': active_contracts
            })
            
            # Emit forex update
            self.event_bus.emit('forex_update', {
                'from_currency': 'USD',
                'to_currency': 'CAD',
                'rate': 1.3750,
                'reciprocal_rate': 0.7272,
                'timestamp': datetime.now().isoformat()
            })
            
            # Emit underlying price update
            self.event_bus.emit('underlying_price_update', {
                'symbol': 'SPY',
                'price': 501.75,
                'timestamp': datetime.now().isoformat()
            })
        
        self.status_connection_var.set("Connected (Demo)")

    def _start_config_polling(self):
        """Starts a periodic task to sync the GUI with the config manager and check connection state."""
        self.root.after(5000, self._sync_with_config)  # Sync every 5 seconds
        self.root.after(10000, self._request_active_contract_status)  # Request active contract status every 10 seconds

    def _sync_with_config(self):
        """Synchronizes the GUI with the config manager and checks connection state."""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                config_path = self.config_manager.config_path
                if os.path.exists(config_path):
                    file_mtime = os.path.getmtime(config_path)
                    if not hasattr(self, '_last_config_mtime') or file_mtime > self._last_config_mtime:
                        logger.info("Config file modified, refreshing...")
                        self._load_preferences_from_config()
                        self._last_config_mtime = file_mtime
                        logger.debug("Config sync completed")
            
        except Exception as e:
            logger.error(f"Error during config sync: {e}")
        
        # Schedule next sync
        self.root.after(5000, self._sync_with_config)
        
    def _request_active_contract_status(self):
        """Periodically request active contract status updates."""
        try:
            if self.event_bus:
                self.event_bus.emit("get_active_contract_status", {})
                logger.debug("Requested active contract status update")
        except Exception as e:
            logger.error(f"Error requesting active contract status: {e}")
        
        # Schedule next request
        self.root.after(10000, self._request_active_contract_status)

    def force_config_refresh(self):
        """Forces a refresh of all configuration data from the config manager."""
        """This can be called when external changes are detected."""
        try:
            logger.info("Forcing configuration refresh...")
            self._load_preferences_from_config()
            
            # Refresh risk levels if preferences popup is open
            if hasattr(self, 'pref_risk_table'):
                self._load_risk_levels_to_preferences()
                
            logger.info("Configuration refresh completed.")
        except Exception as e:
            logger.error(f"Error during configuration refresh: {e}")

    # --- IB Connection Event Handlers ---
    def on_ib_connected(self, data):
        logger.info("✓ GUI: IB connection established.")
        logger.info(f"✓ GUI: Connection data received: {data}")
        
        # Update GUI status variables
        try:
            self.conn_status_var.set("Connected")
            self.status_connection_var.set("Connected")
            logger.info("✓ GUI: Connection status variables updated")
        except Exception as e:
            logger.error(f"GUI: Error updating connection status variables: {e}")
        
        self.on_error("IB connection established.")
        
        # Automatically subscribe to SPY market data
        if self.event_bus:
            try:
                self.event_bus.emit("market_data.subscribe", {
                    'contract': {
                        'symbol': 'SPY',
                        'secType': 'STK',
                        'exchange': 'SMART',
                        'currency': 'USD'
                    }
                })
                logger.info("✓ GUI: Subscribed to SPY market data")
                
                # Subscribe to account data
                self.event_bus.emit("account.request_summary", {'action': 'subscribe'})
                self.event_bus.emit("account.request_pnl", {'action': 'subscribe'})
                logger.info("✓ GUI: Subscribed to account data")
            except Exception as e:
                logger.error(f"GUI: Error subscribing to data: {e}")
        else:
            logger.warning("GUI: No event bus available for subscriptions")

    def on_ib_disconnected(self, data):
        logger.info("IB connection closed.")
        self.conn_status_var.set("Disconnected")
        self.status_connection_var.set("Disconnected")
        self.on_error("IB connection closed.")

    def on_ib_error(self, error_message):
        """Handle general IB errors with enhanced categorization."""
        logger.error(f"IB Error: {error_message}")
        
        # Extract error details if available
        if isinstance(error_message, dict):
            error_code = error_message.get('errorCode', 'Unknown')
            error_string = error_message.get('errorString', 'Unknown error')
            category = error_message.get('category', 'general')
            recovery_strategy = error_message.get('recovery_strategy', 'log_only')
            
            # Update GUI status based on error category
            if category == 'connection':
                self.conn_status_var.set("Connection Error")
                self.status_connection_var.set("Connection Error")
            elif category == 'order':
                self.conn_status_var.set("Order Error")
            elif category == 'market_data':
                self.conn_status_var.set("Market Data Error")
            
            # Log with recovery strategy
            self.on_error(f"IB {category.title()} Error {error_code}: {error_string} (Recovery: {recovery_strategy})")
        else:
            self.on_error(f"IB Error: {error_message}")

    def on_ib_connection_error(self, error_message):
        """Handle connection-specific errors with recovery status."""
        logger.error(f"IB Connection Error: {error_message}")
        
        if isinstance(error_message, dict):
            error_code = error_message.get('errorCode', 'Unknown')
            recovery_strategy = error_message.get('recovery_strategy', 'auto_reconnect')
            
            # Update connection status
            self.conn_status_var.set("Connection Error")
            self.status_connection_var.set("Reconnecting...")
            
            self.on_error(f"IB Connection Error {error_code}: Auto-reconnect in progress")
        else:
            self.on_error(f"IB Connection Error: {error_message}")

    def on_ib_order_error(self, error_message):
        """Handle order-specific errors with circuit breaker status."""
        logger.error(f"IB Order Error: {error_message}")
        
        if isinstance(error_message, dict):
            error_code = error_message.get('errorCode', 'Unknown')
            recovery_strategy = error_message.get('recovery_strategy', 'retry_order')
            
            # Check for circuit breaker activation
            if 'circuit_breaker_activated' in str(error_message):
                self.on_error(f"IB Order Circuit Breaker: Order operations temporarily disabled")
            else:
                self.on_error(f"IB Order Error {error_code}: {recovery_strategy}")
        else:
            self.on_error(f"IB Order Error: {error_message}")

    def on_ib_market_data_error(self, error_message):
        """Handle market data errors with backoff status."""
        logger.error(f"IB Market Data Error: {error_message}")
        
        if isinstance(error_message, dict):
            error_code = error_message.get('errorCode', 'Unknown')
            recovery_strategy = error_message.get('recovery_strategy', 'retry_subscription')
            
            # Check for backoff activation
            if 'backoff_activated' in str(error_message):
                self.on_error(f"IB Market Data Backoff: Subscriptions temporarily throttled")
            else:
                self.on_error(f"IB Market Data Error {error_code}: {recovery_strategy}")
        else:
            self.on_error(f"IB Market Data Error: {error_message}")
    
    def on_ib_circuit_breaker_activated(self, data):
        """Handle circuit breaker activation events."""
        logger.warning(f"Circuit breaker activated: {data}")
        self.on_error("System: Circuit breaker activated - automatic recovery in progress")
    
    def on_ib_order_circuit_breaker_activated(self, data):
        """Handle order circuit breaker activation events."""
        logger.warning(f"Order circuit breaker activated: {data}")
        self.on_error("System: Order circuit breaker activated - order operations temporarily disabled")
    
    def on_ib_market_data_backoff_activated(self, data):
        """Handle market data backoff activation events."""
        logger.warning(f"Market data backoff activated: {data}")
        self.on_error("System: Market data backoff activated - subscriptions temporarily throttled")

    # --- Market Data Event Handlers ---
    def on_market_data_tick(self, data):
        """Handle market data tick updates with filtering for configured symbol."""
        try:
            contract = data.get('contract', {})
            symbol = contract.get('symbol', '')
            
            # Only process ticks for the configured underlying symbol
            configured_symbol = self.config_manager.get('trading', 'underlying_symbol', 'SPY')
            if symbol != configured_symbol:
                logger.debug(f"Ignoring market data tick for {symbol}, configured symbol is {configured_symbol}")
                return
            
            # Process the tick data
            last_price = data.get('last')
            bid = data.get('bid')
            ask = data.get('ask')
            
            if last_price and last_price > 0:
                # Update underlying price display
                self.update_underlying_price({
                    'symbol': symbol,
                    'price': last_price
                })
                
                logger.debug(f"Processed market data tick: {symbol} ${last_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error handling market data tick: {e}")
    
    def on_market_data_subscribed(self, data):
        logger.debug(f"Market data subscribed: {data}")

    def on_market_data_unsubscribed(self, data):
        logger.debug(f"Market data unsubscribed: {data}")

    def on_market_data_error(self, error_message):
        logger.error(f"Market Data Error: {error_message}")
        self.on_error(f"Market Data Error: {error_message}")

    # --- Order Event Handlers ---
    def on_order_status_update(self, data):
        logger.debug(f"Order Status Update: {data}")
        # This handler is for general order status updates,
        # specific order status updates (like filled, rejected, chased)
        # would require more specific handlers.

    def on_order_fill(self, data):
        logger.debug(f"Order Fill: {data}")
        # This handler is for general order fill updates,
        # specific fill details would require more specific handlers.

    def on_order_commission_report(self, data):
        logger.debug(f"Order Commission Report: {data}")
        # This handler is for general commission report updates.

    def on_order_rejected(self, data):
        logger.error(f"Order Rejected: {data}")
        self.on_error(f"Order Rejected: {data}")

    def on_order_chased(self, data):
        logger.debug(f"Order Chased: {data}")
        # This handler is for general order chase updates.

    # --- Account Event Handlers ---
    def on_account_summary_update(self, data):
        """Thread-safe handle account summary updates with improved timing and accuracy."""
        def _update():
            try:
                # Extract key account values
                account = data.get('account', '')
                tag = data.get('tag', '')
                value = data.get('value', '')
                currency = data.get('currency', '')
                
                # Handle different account summary tags
                if tag == 'NetLiquidation':
                    # This is the most important account value
                    try:
                        net_liquidation = float(value) if value else 0
                        self.account_balance_var.set(f"${net_liquidation:,.2f}")
                        logger.info(f"Updated Net Liquidation: ${net_liquidation:,.2f}")
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse NetLiquidation value: {value}")
                        
                elif tag == 'AvailableFunds':
                    try:
                        available_funds = float(value) if value else 0
                        self.available_funds_var.set(f"${available_funds:,.2f}")
                        logger.debug(f"Updated Available Funds: ${available_funds:,.2f}")
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse AvailableFunds value: {value}")
                        
                elif tag == 'BuyingPower':
                    try:
                        buying_power = float(value) if value else 0
                        self.buying_power_var.set(f"${buying_power:,.2f}")
                        logger.debug(f"Updated Buying Power: ${buying_power:,.2f}")
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse BuyingPower value: {value}")
                
                # Record the update
                self._record_update()
                
            except Exception as e:
                logger.error(f"Error handling account summary update: {e}")
        
        # Schedule update on main thread
        if hasattr(self, 'root') and self.root:
            try:
                self.root.after(0, _update)
            except Exception as e:
                # Fallback: execute directly if main loop is not running
                logger.debug(f"Main loop not running, executing update directly: {e}")
                _update()
        else:
            logger.warning("GUI root not available for update")
    
    def on_account_pnl_update(self, data):
        """Thread-safe handle account P&L updates."""
        def _update():
            try:
                daily_pnl = data.get('dailyPnL', 0)
                unrealized_pnl = data.get('unrealizedPnL', 0)
                realized_pnl = data.get('realizedPnL', 0)
                
                # Update P&L displays
                if daily_pnl is not None:
                    self.daily_pnl_var.set(f"${daily_pnl:,.2f}")
                    
                if unrealized_pnl is not None:
                    self.unrealized_pnl_var.set(f"${unrealized_pnl:,.2f}")
                    
                if realized_pnl is not None:
                    self.realized_pnl_var.set(f"${realized_pnl:,.2f}")
                
                self._record_update()
                logger.debug(f"Updated P&L: Daily=${daily_pnl:,.2f}, Unrealized=${unrealized_pnl:,.2f}, Realized=${realized_pnl:,.2f}")
                
            except Exception as e:
                logger.error(f"Error handling account P&L update: {e}")
        
        # Schedule update on main thread
        if hasattr(self, 'root') and self.root:
            try:
                self.root.after(0, _update)
            except Exception as e:
                # Fallback: execute directly if main loop is not running
                logger.debug(f"Main loop not running, executing update directly: {e}")
                _update()
        else:
            logger.warning("GUI root not available for update")
    
    def update_option_chain(self, data):
        """Updates all fields in the Option Information section with color coding."""
        logger.debug(f"Updating option chain: strike={data.get('strike', '-')}")
        self._record_update()
        strike = data.get('strike', '-')
        self.strike_info_var.set(f"${strike}")
        self.expiration_info_var.set(data.get('expiration', '-'))
        
        call_data = data.get('call_data', {})
        for key, var in self.call_vars.items():
            var.set(call_data.get(key, "-"))
        
        put_data = data.get('put_data', {})
        for key, var in self.put_vars.items():
            var.set(put_data.get(key, "-"))
        
        # Color coding logic for call and put price movement
        default_color = 'black'
        
        # Call price color coding
        call_price_str = call_data.get('price', '-').replace('$', '').replace(',', '')
        if call_price_str != '-':
            try:
                call_price = float(call_price_str)
                call_color = default_color
                if self.previous_prices['call_price'] > 0:  # Skip first update
                    if call_price > self.previous_prices['call_price']:
                        call_color = 'green'
                    elif call_price < self.previous_prices['call_price']:
                        call_color = 'red'
                if hasattr(self, 'call_price_label'):
                    self.call_price_label.config(foreground=call_color)
                self.previous_prices['call_price'] = call_price
                logger.debug(f"Call price: ${call_price:,.2f}, color: {call_color}")
            except (ValueError, TypeError):
                logger.debug(f"Could not parse call price: '{call_price_str}'")
        
        # Put price color coding
        put_price_str = put_data.get('price', '-').replace('$', '').replace(',', '')
        if put_price_str != '-':
            try:
                put_price = float(put_price_str)
                put_color = default_color
                if self.previous_prices['put_price'] > 0:  # Skip first update
                    if put_price > self.previous_prices['put_price']:
                        put_color = 'green'
                    elif put_price < self.previous_prices['put_price']:
                        put_color = 'red'
                if hasattr(self, 'put_price_label'):
                    self.put_price_label.config(foreground=put_color)
                self.previous_prices['put_price'] = put_price
                logger.debug(f"Put price: ${put_price:,.2f}, color: {put_color}")
            except (ValueError, TypeError):
                logger.debug(f"Could not parse put price: '{put_price_str}'")
        
        logger.debug(f"Option chain updated: strike=${strike}, expiration={data.get('expiration', '-')}")
    
    def on_account_transactions_update(self, data):
        logger.debug(f"Account Transactions Update: {data}")
        # This handler is for general account transaction updates.

    def on_account_summary_error(self, error_message):
        logger.error(f"Account Summary Error: {error_message}")
        self.on_error(f"Account Summary Error: {error_message}")

    def on_account_pnl_error(self, error_message):
        logger.error(f"Account PnL Error: {error_message}")
        self.on_error(f"Account PnL Error: {error_message}")

    def on_account_transactions_error(self, error_message):
        logger.error(f"Account Transactions Error: {error_message}")
        self.on_error(f"Account Transactions Error: {error_message}")

    # --- Position and Trade Event Handlers ---
    def on_positions_update(self, data):
        logger.debug(f"GUI RECEIVED: positions_update - Data: {data}")
        # This handler is for general position updates.

    def on_open_orders_update(self, data):
        logger.debug(f"GUI RECEIVED: open_orders_update - Data: {data}")
        # This handler is for general open order updates.

    def on_active_contract_status_update(self, data):
        logger.debug(f"Active Contract Status Update: {data}")
        # Update active contract display with real data
        try:
            active_contracts = data.get('active_contracts', [])
            if active_contracts:
                # Use the first active contract
                contract = active_contracts[0]
                symbol = contract.get('symbol', '-')
                quantity = contract.get('quantity', 0)
                unrealized_pnl = contract.get('unrealized_pnl', 0)
                
                self.active_contract_vars['symbol'].set(symbol)
                self.active_contract_vars['quantity'].set(str(quantity))
                self.active_contract_vars['pnl_usd'].set(f"${unrealized_pnl:,.2f}")
                
                # Calculate percentage (assuming entry price)
                if unrealized_pnl != 0:
                    pnl_percent = (unrealized_pnl / abs(unrealized_pnl)) * 10  # Simplified calculation
                    self.active_contract_vars['pnl_pct'].set(f"{pnl_percent:.2f}%")
                else:
                    self.active_contract_vars['pnl_pct'].set("0.00%")
                
                logger.debug(f"Updated active contract: {symbol}, Qty: {quantity}, P&L: ${unrealized_pnl:,.2f}")
            else:
                # Clear active contract display if no active contracts
                self.active_contract_vars['symbol'].set("-")
                self.active_contract_vars['quantity'].set("-")
                self.active_contract_vars['pnl_usd'].set("-")
                self.active_contract_vars['pnl_pct'].set("-")
                logger.debug("No active contracts, cleared display")
        except Exception as e:
            logger.error(f"Error updating active contract status: {e}")

    def on_trade_status_update(self, data):
        logger.debug(f"Trade Status Update: {data}")
        # This handler is for general trade status updates.

    # --- Options Event Handlers ---
    def on_options_chain_update(self, data):
        """Handle options chain updates from subscription manager."""
        logger.debug(f"GUI RECEIVED: options.chain_update - Data: {data}")
        try:
            options = data.get('options', [])
            underlying_symbol = data.get('underlying_symbol', 'SPY')
            
            if options:
                # Find the current strike and expiration being tracked
                current_strike = None
                current_expiration = None
                
                # Look for the currently subscribed options
                for option in options:
                    if option.get('subscribed', False):
                        current_strike = option.get('strike')
                        current_expiration = option.get('expiration')
                        break
                
                if current_strike and current_expiration:
                    # Find call and put data for current strike/expiration
                    call_data = {}
                    put_data = {}
                    
                    for option in options:
                        if (option.get('strike') == current_strike and 
                            option.get('expiration') == current_expiration):
                            
                            if option.get('right') == 'C':
                                call_data = {
                                    'price': f"${option.get('last', 0):.2f}" if option.get('last') else "-",
                                    'bid': f"${option.get('bid', 0):.2f}" if option.get('bid') else "-",
                                    'ask': f"${option.get('ask', 0):.2f}" if option.get('ask') else "-",
                                    'volume': f"{option.get('volume', 0):,}" if option.get('volume') else "-",
                                    'open_interest': f"{option.get('openInterest', 0):,}" if option.get('openInterest') else "-",
                                    'delta': f"{option.get('delta', 0):.3f}" if option.get('delta') else "-",
                                    'gamma': f"{option.get('gamma', 0):.4f}" if option.get('gamma') else "-",
                                    'theta': f"{option.get('theta', 0):.3f}" if option.get('theta') else "-",
                                    'vega': f"{option.get('vega', 0):.2f}" if option.get('vega') else "-"
                                }
                            elif option.get('right') == 'P':
                                put_data = {
                                    'price': f"${option.get('last', 0):.2f}" if option.get('last') else "-",
                                    'bid': f"${option.get('bid', 0):.2f}" if option.get('bid') else "-",
                                    'ask': f"${option.get('ask', 0):.2f}" if option.get('ask') else "-",
                                    'volume': f"{option.get('volume', 0):,}" if option.get('volume') else "-",
                                    'open_interest': f"{option.get('openInterest', 0):,}" if option.get('openInterest') else "-",
                                    'delta': f"{option.get('delta', 0):.3f}" if option.get('delta') else "-",
                                    'gamma': f"{option.get('gamma', 0):.4f}" if option.get('gamma') else "-",
                                    'theta': f"{option.get('theta', 0):.3f}" if option.get('theta') else "-",
                                    'vega': f"{option.get('vega', 0):.2f}" if option.get('vega') else "-"
                                }
                    
                    # Update the option chain display
                    option_chain_data = {
                        'strike': current_strike,
                        'expiration': current_expiration,
                        'call_data': call_data,
                        'put_data': put_data
                    }
                    
                    self.update_option_chain(option_chain_data)
                    logger.debug(f"Updated option chain: strike=${current_strike}, expiration={current_expiration}")
            
        except Exception as e:
            logger.error(f"Error handling options chain update: {e}")

    def on_options_chain_error(self, error_message):
        logger.error(f"Options Chain Error: {error_message}")
        self.on_error(f"Options Chain Error: {error_message}")

    def on_options_selection_update(self, data):
        """Handle options selection updates from subscription manager."""
        try:
            expiration = data.get('expiration', '')
            strike = data.get('strike', 0)
            underlying_symbol = data.get('underlying_symbol', 'SPY')
            
            # Update the strike and expiration display
            if strike > 0 and expiration:
                self.strike_info_var.set(f"${strike:.2f}")
                self.expiration_info_var.set(expiration)
                
                logger.debug(f"Updated options selection: {underlying_symbol} {expiration} ${strike:.2f}")
            
        except Exception as e:
            logger.error(f"Error handling options selection update: {e}")

# --- Example Usage and Demonstration ---

class MockEventBus:
    """A simple event bus for demonstration purposes."""
    def __init__(self):
        self.listeners = {}
    def on(self, event_name, callback):
        if event_name not in self.listeners: self.listeners[event_name] = []
        self.listeners[event_name].append(callback)
    def emit(self, event_name, data=None, priority=EventPriority.NORMAL):
        if event_name in self.listeners:
            for callback in self.listeners[event_name]: callback(data)

class MockConfigManager:
    """A simple config manager for demonstration purposes."""
    def __init__(self, initial_config):
        self.config = initial_config
        self.config_path = "mock_config.json"
    def get(self, section, key, default=None):
        return self.config.get(section, {}).get(key, default)
    def set(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    def save_config(self):
        pass
    def get_available_modules(self):
        return list(self.config.get('debug', {}).get('modules', {}).keys())
    def get_log_levels(self):
        return self.config.get('debug', {}).get('modules', {})

def mock_backend_updates(gui, event_bus):
    """Simulates a backend process sending data updates to the GUI."""
    while True:
        try:
            price = round(random.uniform(498.0, 502.0), 2)
            event_bus.emit("underlying_price_update", {"symbol": "SPY", "price": price}, priority=EventPriority.NORMAL)
            time.sleep(random.uniform(0.5, 4.0)) # Random delay
        except:
            break

if __name__ == "__main__":
    # When run directly, always run in demo mode with comprehensive data
    logger.info("Running GUI in demo mode with comprehensive data")
    
    # Create mock config manager for demo
    mock_config = {
        'connection': {
            'host': '127.0.0.1',
            'port': '7497',
            'client_id': '1'
        },
        'trading': {
            'max_trade_value': '10000',
            'risk_levels': [
                {'level': 'Low', 'max_loss': '100', 'max_trade': '500'},
                {'level': 'Medium', 'max_loss': '500', 'max_trade': '2000'},
                {'level': 'High', 'max_loss': '1000', 'max_trade': '5000'}
            ]
        },
        'debug': {
            'modules': {
                'main': 'INFO',
                'gui': 'INFO',
                'event_bus': 'INFO',
                'subscription_manager': 'INFO'
            }
        }
    }
    
    config_mgr = MockConfigManager(mock_config)
    event_bus = MockEventBus()
    
    # Initialize GUI in standalone mode with comprehensive demo data
    app = IBTradingGUI(
        event_bus=event_bus,
        config_manager=config_mgr,
        standalone_mode=True  # This ensures _populate_with_fake_data is called
    )
    
    # Register event listeners
    app.register_event_listeners()
    
    # Start mock backend updates
    backend_thread = threading.Thread(target=mock_backend_updates, args=(app, event_bus), daemon=True)
    backend_thread.start()
    
    logger.info("Starting GUI in demo mode with comprehensive data")
    app.run()