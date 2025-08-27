import asyncio
from typing import Optional, Dict, Any, List
from ib_async import IB, Stock, Option, Forex
import pandas as pd
from datetime import datetime, date, timedelta, time
import pytz
from threading import Thread, Event
import time
from .logger import get_logger, log_connection_event, log_error_with_context
from .performance_monitor import monitor_function, monitor_async_function
from .trading_manager import TradingManager
from collections import defaultdict, deque

logger = get_logger("IB_CONNECTION")


class IBDataCollector:
    """
    Improved IB Data Collector with better error handling and resource management
    """
    
    def __init__(self, host='127.0.0.1', port=7497, clientId=1, timeout=30, trading_config=None, account_config=None):
        self.underlying_symbol_qualified = None
        self.ib = IB()
        self.trading_config = trading_config
        self.account_config = account_config
        self.underlying_symbol = trading_config.get('underlying_symbol')
        self.host = host
        self.port = port
        self.clientId = clientId
        self.timeout = timeout
        self.spy_price = 0
        self.underlying_symbol_price = 0
        self.daily_pnl = 0
        self.account_liquidation = 0
        self.fx_ratio = 0
        self.option_strike = 0
        self._active_subscriptions = set()  # Track active market data subscriptions
        self.pos = None
        self.pos_type = ""
        self.closed_trades = None
        
        self.option_p_mark = 0
        self.option_c_mark = 0
        
        # Dynamic strike price and expiration monitoring
        self._previous_strike = 0
        self._current_expiration = None
        self._monitoring_active = False
        self._monitor_thread = None
        self._stop_monitoring = Event()
        self._est_timezone = pytz.timezone('US/Eastern')
        
        # Option contracts cache for quick resubscription
        self._cached_option_contracts = {}  # {strike: {expiration: {call: contract, put: contract}}}

        # Initialize trading manager
        self.trading_manager = TradingManager(self.ib, trading_config, account_config)

        self._register_ib_callbacks()
        # Event loop used for scheduling coroutines from background threads
        self._loop = None

    def _cancel_all_market_data_subscriptions(self):
        """Cancel all active market data subscriptions (stock/options/forex)."""
        try:
            contracts_to_remove = set()
            for contract in list(self._active_subscriptions):
                try:
                    self.ib.cancelMktData(contract)
                    contracts_to_remove.add(contract)
                except Exception as e:
                    logger.warning(f"Error canceling market data for {contract}: {e}")
            if contracts_to_remove:
                self._active_subscriptions.difference_update(contracts_to_remove)
                logger.info(f"Cancelled {len(contracts_to_remove)} market data subscriptions")
        except Exception as e:
            logger.error(f"Error cancelling market data subscriptions: {e}")

    async def refresh_for_new_symbol(self, symbol: str):
        """Handle underlying symbol change by resetting state and resubscribing."""
        try:
            if not symbol:
                return
            logger.info(f"Refreshing data subscriptions for new underlying symbol: {symbol}")

            # Cancel current subscriptions to avoid mixing symbols
            self._cancel_all_market_data_subscriptions()

            # Reset cached state related to previous symbol
            self.underlying_symbol = symbol
            self.underlying_symbol_price = 0
            self.option_strike = 0
            self._previous_strike = 0
            self._current_expiration = None
            self._cached_option_contracts = {}
            self._available_expirations = []
            # Reset closed trades when switching symbols
            logger.info("Resetting closed_trades for new symbol")
            self.closed_trades = []

            # Notify trading manager to clear its expirations cache
            try:
                if hasattr(self, 'trading_manager') and self.trading_manager:
                    if hasattr(self.trading_manager, 'update_available_expirations'):
                        self.trading_manager.update_available_expirations([])
                    # Also notify trading manager of underlying symbol change so cached prices are cleared
                    if hasattr(self.trading_manager, 'update_trading_config'):
                        self.trading_manager.update_trading_config({'underlying_symbol': symbol})
            except Exception as tm_err:
                logger.debug(f"Could not notify trading manager about expiration reset: {tm_err}")

            # Obtain new price stream and resubscribe to options for the new symbol
            await self.get_underlying_symbol_price(symbol)
            # Ensure we have an initial option chain/subscriptions for the symbol
            await self._get_and_subscribe_to_options()

            logger.info(f"Symbol refresh completed for {symbol}")
        except Exception as e:
            logger.error(f"Error refreshing for new symbol {symbol}: {e}")

    def _calculate_nearest_strike(self, price: float) -> int:
        """Calculate the nearest valid strike price for options trading"""
        try:
            if price <= 0:
                return 0
            
            # For SPY and most liquid options, strikes are typically in $1 increments
            # Round to nearest dollar
            rounded_strike = round(price)
            
            # Ensure we have a valid strike (whole number)
            valid_strike = int(rounded_strike)
            
            # logger.info(f"Strike calculation: Price=${price:.2f} -> Rounded=${rounded_strike} -> Valid Strike={valid_strike}")
            
            return valid_strike
            
        except Exception as e:
            logger.error(f"Error calculating strike price: {e}")
            # Fallback to simple rounding
            return int(round(price)) if price > 0 else 0

    def _should_update_strike(self, new_strike: int) -> bool:
        """Check if the strike price has changed and needs updating"""
        return new_strike != self._previous_strike and new_strike > 0
    
    def _validate_strike_availability(self, strike: int) -> bool:
        """Validate if a strike price is available in the option chain"""
        try:
            # Basic validation
            if not isinstance(strike, (int, float)) or strike <= 0:
                logger.warning(f"Invalid strike price: {strike}")
                return False
            
            # For now, assume strikes in $1 increments are valid
            # In a more sophisticated implementation, you could check against actual available strikes
            # from the option chain data
            valid_strike = int(round(strike))
            
            logger.debug(f"Strike validation: {strike} -> {valid_strike} (assumed valid for liquid options)")
            return True
            
        except Exception as e:
            logger.error(f"Error validating strike availability: {e}")
            return False

    def _should_switch_to_next_expiration(self) -> bool:
        """Check if it's time to switch from 0DTE to 1DTE contracts (12:00 PM EST)"""
        try:
            est_now = datetime.now(self._est_timezone)
            return est_now.hour == 12 and est_now.minute == 0 and est_now.second == 0
        except Exception as e:
            logger.warning(f"Error checking expiration switch time: {e}")
            return False

    def _should_switch_expiration_smart(self) -> bool:
        """Smart expiration switching that checks if current expiration is still valid and if switching is beneficial"""
        try:
            if not hasattr(self, '_available_expirations') or not self._available_expirations:
                # No available expirations, use time-based switching
                return self._should_switch_to_next_expiration()
            
            if not self._current_expiration:
                return False
            
            est_now = datetime.now(self._est_timezone)
            current_date = est_now.date()
            current_time = est_now.time()
            
            # Parse current expiration
            try:
                if ' ' in self._current_expiration:
                    current_exp_str = self._current_expiration.split()[0]
                else:
                    current_exp_str = self._current_expiration
                current_exp_date = datetime.strptime(current_exp_str, "%Y%m%d").date()
            except Exception as e:
                logger.warning(f"Could not parse current expiration {self._current_expiration}: {e}")
                return self._should_switch_to_next_expiration()
            
            # Check if current expiration is today and it's after 12:00 PM
            if current_exp_date == current_date and current_time.hour >= 12:
                # Current expiration is today and it's after noon - should switch
                logger.info(f"Current expiration {self._current_expiration} is today and it's after 12:00 PM - switching recommended")
                return True
            
            # Check if current expiration is in the past
            if current_exp_date < current_date:
                logger.warning(f"Current expiration {self._current_expiration} is in the past - switching required")
                return True
            
            # Check if there's a better expiration available
            if self._is_better_expiration_available(current_exp_date, current_date, current_time):
                logger.info(f"Better expiration available - switching recommended")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in smart expiration switching check: {e}")
            return self._should_switch_to_next_expiration()
    
    def _is_better_expiration_available(self, current_exp_date: date, current_date: date, current_time: time) -> bool:
        """Check if there's a better expiration available than the current one"""
        try:
            if not hasattr(self, '_available_expirations') or not self._available_expirations:
                return False
            
            # Calculate current expiration's difference from ideal target
            current_diff = abs((current_exp_date - current_date).days)
            
            # Determine ideal target date based on time
            if current_time.hour < 12:
                # Before noon - prefer today (0DTE)
                target_date = current_date
            else:
                # After noon - prefer next business day (1DTE)
                target_date = current_date + timedelta(days=1)
                # Skip weekends
                while target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    target_date += timedelta(days=1)
            
            # Check if target date is available and better than current
            for exp_str in self._available_expirations:
                try:
                    if ' ' in exp_str:
                        exp_str_clean = exp_str.split()[0]
                    else:
                        exp_str_clean = exp_str
                    exp_date = datetime.strptime(exp_str_clean, "%Y%m%d").date()
                    
                    # Skip if this is the current expiration
                    if exp_str == self._current_expiration:
                        continue
                    
                    # Calculate this expiration's difference from ideal target
                    exp_diff = abs((exp_date - target_date).days)
                    
                    if exp_diff < current_diff:
                        logger.info(f"Found better expiration {exp_str} (diff: {exp_diff}) vs current {self._current_expiration} (diff: {current_diff})")
                        return True
                        
                except Exception as e:
                    logger.warning(f"Could not parse expiration {exp_str}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for better expiration: {e}")
            return False

    def _get_next_expiration(self, current_expiration: str) -> Optional[str]:
        """Get the next available expiration after the current one with smart selection"""
        try:
            if not hasattr(self, '_available_expirations') or not self._available_expirations:
                return None
            
            if not current_expiration:
                # No current expiration, return first available
                return self._available_expirations[0] if self._available_expirations else None
            
            est_now = datetime.now(self._est_timezone)
            current_date = est_now.date()
            current_time = est_now.time()
            
            # Parse current expiration
            try:
                if ' ' in current_expiration:
                    current_exp_str = current_expiration.split()[0]
                else:
                    current_exp_str = current_expiration
                current_exp_date = datetime.strptime(current_exp_str, "%Y%m%d").date()
            except Exception as e:
                logger.warning(f"Could not parse current expiration {current_expiration}: {e}")
                # Fallback to simple next in list
                expirations = sorted(self._available_expirations)
                try:
                    current_index = expirations.index(current_expiration)
                    if current_index + 1 < len(expirations):
                        return expirations[current_index + 1]
                except ValueError:
                    pass
                return expirations[0] if expirations else None
            
            # Determine target date based on current time
            if current_time.hour < 12:
                # Before noon - prefer today (0DTE)
                target_date = current_date
            else:
                # After noon - prefer next business day (1DTE)
                target_date = current_date + timedelta(days=1)
                # Skip weekends
                while target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    target_date += timedelta(days=1)
            
            logger.info(f"Looking for next expiration. Current: {current_expiration}, Target date: {target_date}")
            
            # Strategy 1: Find exact target date if available
            for exp_str in self._available_expirations:
                try:
                    if ' ' in exp_str:
                        exp_str_clean = exp_str.split()[0]
                    else:
                        exp_str_clean = exp_str
                    exp_date = datetime.strptime(exp_str_clean, "%Y%m%d").date()
                    
                    if exp_date == target_date:
                        logger.info(f"Found exact target expiration: {exp_str}")
                        return exp_str
                        
                except Exception as e:
                    logger.warning(f"Could not parse expiration {exp_str}: {e}")
                    continue
            
            # Strategy 2: Find nearest available expiration to target date
            best_exp = None
            min_days_diff = float('inf')
            
            for exp_str in self._available_expirations:
                try:
                    if ' ' in exp_str:
                        exp_str_clean = exp_str.split()[0]
                    else:
                        exp_str_clean = exp_str
                    exp_date = datetime.strptime(exp_str_clean, "%Y%m%d").date()
                    
                    # Only consider future expirations
                    if exp_date > current_exp_date:
                        days_diff = abs((exp_date - target_date).days)
                        if days_diff < min_days_diff:
                            min_days_diff = days_diff
                            best_exp = exp_str
                            
                except Exception as e:
                    logger.warning(f"Could not parse expiration {exp_str}: {e}")
                    continue
            
            if best_exp:
                logger.info(f"Selected best available expiration: {best_exp} (days diff from target: {min_days_diff})")
                return best_exp
            
            # Strategy 3: Find next chronological expiration
            expirations = sorted(self._available_expirations)
            try:
                current_index = expirations.index(current_expiration)
                if current_index + 1 < len(expirations):
                    next_exp = expirations[current_index + 1]
                    logger.info(f"Using next chronological expiration: {next_exp}")
                    return next_exp
            except ValueError:
                pass
            
            # Strategy 4: Fallback to first available expiration
            logger.warning("No suitable next expiration found, using first available")
            return self._available_expirations[0] if self._available_expirations else None
                
        except Exception as e:
            logger.warning(f"Error getting next expiration: {e}")
            return None

    def _get_expiration_type(self, expiration: str) -> str:
        """Get the expiration type (0DTE, 1DTE, etc.)"""
        try:
            if not expiration:
                return "Unknown"
            
            # Parse expiration date (assuming format like "20241220" or "20241220 16:00:00")
            exp_date_str = expiration.split()[0]  # Remove time if present
            exp_date = datetime.strptime(exp_date_str, "%Y%m%d")
            
            # Get current EST date
            est_now = datetime.now(self._est_timezone)
            current_date = est_now.date()
            exp_date_only = exp_date.date()
            
            # Calculate days to expiration
            days_to_expiry = (exp_date_only - current_date).days
            
            if days_to_expiry == 0:
                return "0DTE"
            elif days_to_expiry == 1:
                return "1DTE"
            elif days_to_expiry == 2:
                return "2DTE"
            elif days_to_expiry <= 7:
                return f"{days_to_expiry}DTE"
            elif days_to_expiry <= 30:
                return f"{days_to_expiry}DTE"
            else:
                return f"{days_to_expiry}DTE"
                
        except Exception as e:
            logger.warning(f"Error determining expiration type: {e}")
            return "Unknown"

    def _register_ib_callbacks(self):
        """Register IB event callbacks for real-time data streaming."""
        # Core connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        # self.ib.errorEvent += self._on_error

        # Trading events
        # self.ib.orderStatusEvent += self._on_order_status_update
        # self.ib.execDetailsEvent += self._on_exec_details
        # self.ib.commissionReportEvent += self._on_commission_report
        #
        # Account events
        self.ib.accountSummaryEvent += self.on_account_summary_update
        self.ib.pnlEvent += self.on_pnl_update
        
        logger.info("Account event handlers registered successfully")
        
        # Test if the event handlers are properly attached
        logger.info(f"Account summary event handler count: {len(self.ib.accountSummaryEvent)}")
        logger.info(f"P&L event handler count: {len(self.ib.pnlEvent)}")

        logger.debug("IB event callbacks registered")

    async def _on_connected(self):
        """Handle IB connection success."""
        try:
            logger.info("IB Connection established successfully")
            self._connected = True
            self.connection_attempts = 0
            
            # Set up account monitoring
            await self._setup_account_monitoring()
            
            # Emit connection success event
            connection_data = {
                'host': self.host,
                'port': self.port,
                'client_id': self.clientId,
                'timestamp': datetime.now().isoformat()
            }
            logger.info(f"Connection data: {connection_data}")
            
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'connection_success'):
                self.data_worker.connection_success.emit({
                    'status': 'Connected',
                    'message': f'Successfully connected to {self.host}:{self.port} (Client ID: {self.clientId})'
                })
        except Exception as e:
            logger.error(f"Error in connection success handler: {e}")
    
    async def _setup_account_monitoring(self):
        """Set up continuous account monitoring"""
        try:
            logger.info("Setting up account monitoring...")
            
            # Get managed accounts
            managed_accounts = self.ib.managedAccounts()
            if not managed_accounts:
                logger.warning("No managed accounts found for monitoring")
                return
            
            account = managed_accounts[0]  # Get first managed account
            logger.info(f"Setting up monitoring for account: {account}")
            
            # Subscribe to P&L updates
            try:
                pnl = self.ib.reqPnL(account)
                logger.info(f"P&L subscription set up: {pnl}")
            except Exception as e:
                logger.warning(f"Could not set up P&L subscription: {e}")
            
            # Subscribe to account summary updates and get initial value
            try:
                # Request initial account summary to trigger subscription and get current value
                # Use the specific account for the request
                account_summary = await self.ib.accountSummaryAsync(account)
                if account_summary:
                    logger.info(f"Initial account summary received: {len(account_summary)} items")
                    # Process the initial account summary to set current account value
                    for item in account_summary:
                        if item.tag == 'NetLiquidation':
                            initial_value = float(item.value)
                            if initial_value > 0:
                                self.account_liquidation = initial_value
                                logger.info(f"Initial account liquidation value set to: {initial_value}")
                                # Update trading manager with initial account value
                                if hasattr(self, 'trading_manager'):
                                    self.trading_manager.update_market_data(account_value=initial_value)
                                    logger.info(f"Trading manager updated with initial account value: {initial_value}")
                            break
                logger.info("Account summary subscription set up successfully")
                
                # Also set up periodic account value refresh as a backup
                self._setup_periodic_account_refresh(account)
                
            except Exception as e:
                logger.warning(f"Could not set up account summary subscription: {e}")
                
            # Fallback: Try to get account value from account download
            try:
                logger.info("Attempting fallback account value retrieval...")
                account_values = await self.ib.accountDownloadAsync(account)
                if account_values:
                    logger.info(f"Account download received: {len(account_values)} values")
                    for item in account_values:
                        if item.tag == 'NetLiquidation':
                            fallback_value = float(item.value)
                            if fallback_value > 0:
                                self.account_liquidation = fallback_value
                                logger.info(f"Fallback account liquidation value set to: {fallback_value}")
                                # Update trading manager with fallback account value
                                if hasattr(self, 'trading_manager'):
                                    self.trading_manager.update_market_data(account_value=fallback_value)
                                    logger.info(f"Trading manager updated with fallback account value: {fallback_value}")
                            break
            except Exception as fallback_e:
                logger.warning(f"Fallback account value retrieval also failed: {fallback_e}")
                
            # Additional fallback: Try to manually request account summary
            try:
                logger.info("Attempting manual account summary request...")
                manual_summary = await self.ib.accountSummaryAsync(account)
                if manual_summary:
                    logger.info(f"Manual account summary received: {len(manual_summary)} items")
                    for item in manual_summary:
                        if item.tag == 'NetLiquidation':
                            manual_value = float(item.value)
                            if manual_value > 0:
                                self.account_liquidation = manual_value
                                logger.info(f"Manual account liquidation value set to: {manual_value}")
                                # Update trading manager with manual account value
                                if hasattr(self, 'trading_manager'):
                                    self.trading_manager.update_market_data(account_value=manual_value)
                                    logger.info(f"Trading manager updated with manual account value: {manual_value}")
                            break
            except Exception as manual_e:
                logger.warning(f"Manual account summary request also failed: {manual_e}")
                
        except Exception as e:
            logger.error(f"Error setting up account monitoring: {e}")
            
    async def refresh_account_value(self):
        """Manually refresh account value - can be called from UI if needed"""
        try:
            logger.info("Manual account value refresh requested...")
            if not self.ib.isConnected():
                logger.warning("Not connected to IB, cannot refresh account value")
                return False
                
            managed_accounts = self.ib.managedAccounts()
            if not managed_accounts:
                logger.warning("No managed accounts found for refresh")
                return False
                
            account = managed_accounts[0]
            logger.info(f"Refreshing account value for: {account}")
            
            # Try account summary first
            try:
                account_summary = await self.ib.accountSummaryAsync(account)
                if account_summary:
                    for item in account_summary:
                        if item.tag == 'NetLiquidation':
                            refresh_value = float(item.value)
                            if refresh_value > 0:
                                self.account_liquidation = refresh_value
                                logger.info(f"Account value refreshed to: {refresh_value}")
                                # Update trading manager
                                if hasattr(self, 'trading_manager'):
                                    self.trading_manager.update_market_data(account_value=refresh_value)
                                    logger.info(f"Trading manager updated with refreshed account value: {refresh_value}")
                                return True
            except Exception as e:
                logger.warning(f"Account summary refresh failed: {e}")
                
            # Fallback to account download
            try:
                account_values = await self.ib.accountDownloadAsync(account)
                if account_values:
                    for item in account_values:
                        if item.tag == 'NetLiquidation':
                            refresh_value = float(item.value)
                            if refresh_value > 0:
                                self.account_liquidation = refresh_value
                                logger.info(f"Account value refreshed via download to: {refresh_value}")
                                # Update trading manager
                                if hasattr(self, 'trading_manager'):
                                    self.trading_manager.update_market_data(account_value=refresh_value)
                                    logger.info(f"Trading manager updated with refreshed account value: {refresh_value}")
                                return True
            except Exception as e:
                logger.warning(f"Account download refresh failed: {e}")
                
            logger.warning("All account value refresh methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error in manual account value refresh: {e}")
            return False
            
    def _setup_periodic_account_refresh(self, account: str):
        """Set up periodic account value refresh as a backup to real-time updates"""
        try:
            logger.info("Setting up periodic account value refresh...")
            
            # Start a background thread to periodically refresh account value
            def periodic_refresh():
                import time
                while self.ib.isConnected():
                    try:
                        # Refresh every 30 seconds as a backup
                        time.sleep(30)
                        if not self.ib.isConnected():
                            break
                            
                        # Use asyncio.run_coroutine_threadsafe to call the async method
                        if hasattr(self, '_loop') and self._loop and self._loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self._periodic_account_refresh(account),
                                self._loop
                            )
                    except Exception as e:
                        logger.warning(f"Error in periodic account refresh: {e}")
                        time.sleep(5)  # Wait a bit before retrying
                        
            # Start the periodic refresh thread
            import threading
            refresh_thread = threading.Thread(target=periodic_refresh, daemon=True)
            refresh_thread.start()
            logger.info("Periodic account refresh thread started")
            
        except Exception as e:
            logger.error(f"Error setting up periodic account refresh: {e}")
            
    async def _periodic_account_refresh(self, account: str):
        """Periodic account value refresh - called from background thread"""
        try:
            # Only refresh if we don't have a valid account value
            if self.account_liquidation <= 0:
                logger.info("Periodic refresh: Account value is 0, attempting refresh...")
                await self.refresh_account_value()
            else:
                logger.debug("Periodic refresh: Account value is valid, skipping refresh")
                
        except Exception as e:
            logger.warning(f"Error in periodic account refresh: {e}")

    async def _on_disconnected(self):
        """Handle IB disconnection."""
        try:
            logger.info("IB Connection disconnected")
            self._connected = False
            
            # Emit disconnection event
            disconnection_data = {
                'host': self.host,
                'port': self.port,
                'client_id': self.clientId,
                'timestamp': datetime.now().isoformat()
            }
            logger.info(f"Disconnection data: {disconnection_data}")
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'connection_disconnected'):
                self.data_worker.connection_disconnected.emit({
                    'status': 'Disconnected',
                    'message': f'Disconnected from {self.host}:{self.port} (Client ID: {self.clientId})'
                })
            
        except Exception as e:
            logger.error(f"Error in disconnection handler: {e}")
    
    @monitor_async_function("IB_CONNECTION.connect", threshold_ms=5000)
    async def connect(self) -> bool:
        """Connect to TWS/IB Gateway with timeout and retry logic"""
        try:
            log_connection_event("CONNECT_ATTEMPT", self.host, self.port, "Connecting")
            
            # Emit connection attempt event
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'connection_success'):
                self.data_worker.connection_success.emit({
                    'status': 'Connecting...',
                    'message': f'Attempting to connect to {self.host}:{self.port} (Client ID: {self.clientId})'
                })
            
            # Set connection timeout
            await asyncio.wait_for(
                self.ib.connectAsync(self.host, self.port, clientId=self.clientId),
                timeout=self.timeout
            )
            
            log_connection_event("CONNECT_SUCCESS", self.host, self.port, "Connected")
            logger.info("Successfully connected to Interactive Brokers")
            # Capture the running event loop for cross-thread coroutine scheduling
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None
            
            # Start dynamic monitoring after successful connection
            self.start_dynamic_monitoring()
            
            return True
            
        except asyncio.TimeoutError:
            log_connection_event("CONNECT_TIMEOUT", self.host, self.port, "Timeout")
            logger.error(f"Connection timeout after {self.timeout} seconds")
            # Emit timeout error
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'error_occurred'):
                self.data_worker.error_occurred.emit(f"Connection timeout after {self.timeout} seconds")
            return False
        except Exception as e:
            log_connection_event("CONNECT_FAILED", self.host, self.port, "Failed")
            log_error_with_context(e, "Connection attempt failed", host=self.host, port=self.port, client_id=self.clientId)
            # Emit connection error
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'error_occurred'):
                self.data_worker.error_occurred.emit(f"Connection failed: {str(e)}")
            return False
    
    @monitor_function("IB_CONNECTION.disconnect")
    def disconnect(self):
        """Safely disconnect from IB and cleanup resources"""
        try:
            log_connection_event("DISCONNECT_ATTEMPT", self.host, self.port, "Disconnecting")
            
            # Emit disconnection attempt event
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'connection_disconnected'):
                self.data_worker.connection_disconnected.emit({
                    'status': 'Disconnecting...',
                    'message': f'Disconnecting from {self.host}:{self.port} (Client ID: {self.clientId})'
                })
            
            # Stop dynamic monitoring
            self.stop_dynamic_monitoring()
            
            # Cancel all active market data subscriptions
            for contract in self._active_subscriptions:
                try:
                    self.ib.cancelMktData(contract)
                except Exception as e:
                    logger.warning(f"Error canceling market data for {contract}: {e}")
            
            self._active_subscriptions.clear()
            
            # Disconnect from IB
            if self.ib.isConnected():
                self.ib.disconnect()
                log_connection_event("DISCONNECT_SUCCESS", self.host, self.port, "Disconnected")
                logger.info("Disconnected from Interactive Brokers")
            # Clear stored loop reference
            self._loop = None
                
        except Exception as e:
            log_connection_event("DISCONNECT_FAILED", self.host, self.port, "Failed")
            log_error_with_context(e, "Disconnect operation failed", host=self.host, port=self.port, client_id=self.clientId)
            # Emit disconnect error
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'error_occurred'):
                self.data_worker.error_occurred.emit(f"Error during disconnect: {str(e)}")
    
    async def get_underlying_symbol_price(self, symbol: str) -> Optional[float]:
        """Get current underlying symbol price with improved error handling.
        Returns the best available price as a float, or None on failure.
        """
        try:
            underlying_symbol = Stock(symbol, 'SMART', 'USD')
            
            # Qualify the contract with timeout
            underlying_symbol_qualified = await self.ib.qualifyContractsAsync(underlying_symbol)

            self.underlying_symbol_qualified = underlying_symbol_qualified

            # Request market data and set up real-time updates
            underlying_symbol_ticker = self.ib.reqMktData(underlying_symbol_qualified[0])
            self._active_subscriptions.add(underlying_symbol_qualified[0])
            
            # Set up callback for real-time updates with symbol context
            underlying_symbol_ticker.updateEvent += lambda ticker, sym=symbol: self._on_underlying_price_update(ticker, sym)
            
            # Wait for initial price data
            await asyncio.sleep(2)
            
            # Return the current price if available
            if self.underlying_symbol_price > 0:
                return self.underlying_symbol_price
            else:
                logger.warning(f"No price data available for {symbol} after waiting")
                return None

        except Exception as e:
            logger.error(f"Error getting {symbol} price: {e}")
            return None

    def _on_underlying_price_update(self, ticker, symbol=None):
        """Callback handler for real-time underlying symbol price updates"""
        try:
            # Ignore updates from tickers that don't match the current underlying symbol
            if symbol is not None and symbol != self.underlying_symbol:
                return
            old_price = self.underlying_symbol_price
            ticker_type = ""
            if ticker.last and ticker.last > 0:
                self.underlying_symbol_price = float(ticker.last)
                ticker_type = "last"
                # logger.info(f"Real-time {symbol or self.underlying_symbol} Last Price: ${self.underlying_symbol_price}")
            elif ticker.close and ticker.close > 0:
                self.underlying_symbol_price = float(ticker.close)
                ticker_type = "close"
                # logger.info(f"Real-time {symbol or self.underlying_symbol} Previous Close: ${self.underlying_symbol_price}")
            elif ticker.bid and ticker.ask:
                self.underlying_symbol_price = float((ticker.bid + ticker.ask) / 2)
                ticker_type = "mid"
                # logger.info(f"Real-time {symbol or self.underlying_symbol} Mid Price: ${self.underlying_symbol_price:.2f} (Bid: ${ticker.bid}, Ask: ${ticker.ask})")
            else:
                logger.debug("No real-time price data available")
                logger.debug(f"Last: {ticker.last}, Bid: {ticker.bid}, Ask: {ticker.ask}")
                logger.debug(f"Close: {ticker.close}, Open: {ticker.open}")
                return
            
            # Check if strike price needs updating
            if old_price != self.underlying_symbol_price and self.underlying_symbol_price > 0:
                new_strike = self._calculate_nearest_strike(self.underlying_symbol_price)
                if self._should_update_strike(new_strike) and self._validate_strike_availability(new_strike):
                    logger.info(f"Underlying price changed from ${old_price:.2f} to type: {ticker_type}  ${self.underlying_symbol_price:.2f}, new strike: {new_strike}")
                    # Schedule strike update
                    asyncio.create_task(self._switch_option_subscriptions(new_strike=new_strike))
                elif not self._validate_strike_availability(new_strike):
                    logger.warning(f"Calculated strike {new_strike} is not valid, keeping current strike {self.option_strike}")

                # Emit signal for UI update if we have a data worker
                if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'price_updated'):
                    self.data_worker.price_updated.emit({
                        'symbol': self.underlying_symbol,
                        'price': self.underlying_symbol_price,
                        'timestamp': datetime.now().isoformat()
                    })

                # Update trading manager with underlying price
                if hasattr(self, 'trading_manager'):
                    self.trading_manager.update_market_data(underlying_price=self.underlying_symbol_price)

        except Exception as e:
            logger.error(f"Error in price update callback: {e}")



    async def get_fx_ratio(self):
        """Get current USD/CAD ratio with improved error handling"""
        try:
            contract = Forex('USDCAD', 'IDEALPRO')
            await self.ib.qualifyContractsAsync(contract)  # Qualify the contract to populate conId
            ticker = self.ib.reqMktData(contract, '', False, False)
            # Track this subscription like others
            self._active_subscriptions.add(contract)
            ticker.updateEvent += self._on_fx_ratio_update
            await asyncio.sleep(1)
            
            return self.fx_ratio
        except Exception as e:
            logger.error(f"Error getting USD/CAD ratio: {e}")
            return None
    
    def _on_fx_ratio_update(self, ticker):
        """Callback handler for real-time USD/CAD ratio updates"""
        if ticker.last and ticker.last > 0:
            new_ratio = ticker.last
            # logger.info(f"USD/CAD Ratio (last): {new_ratio}")
        elif ticker.close and ticker.close > 0:
            new_ratio = ticker.close
            # logger.info(f"USD/CAD Ratio (close): {new_ratio}")

        elif ticker.bid and ticker.ask:
            new_ratio = (ticker.bid + ticker.ask) / 2
            # logger.info(f"USD/CAD Ratio (mid): {new_ratio}")
            
        else:
            new_ratio = 0
            logger.info(f"USD/CAD Ratio (no data): {new_ratio}")
            
        # Emit only when the ratio actually changes
        if new_ratio != self.fx_ratio:
            self.fx_ratio = new_ratio
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'fx_rate_updated'):
                self.data_worker.fx_rate_updated.emit({
                    'symbol': 'USDCAD',
                    'rate': self.fx_ratio,
                    'timestamp': datetime.now().isoformat()
                })
    
    async def get_option_chain(self) -> pd.DataFrame:
        """Get option chain data with improved error handling and validation"""
        try:
            symbol = self.underlying_symbol
            # Calculate and update strike price
            logger.info(f"Current underlying_symbol_price: {self.underlying_symbol_price}")
            if self.underlying_symbol_price > 0:
                new_strike = int(round(self.underlying_symbol_price))
                logger.info(f"Calculated new strike: {new_strike}")
                if new_strike != self.option_strike:
                    self.option_strike = new_strike
                    self._previous_strike = new_strike
                    logger.info(f"Updated strike price to: {self.option_strike}")
            else:
                self.option_strike = int(round(self.underlying_symbol_price)) if self.underlying_symbol_price > 0 else 0
                logger.info(f"Set option_strike to: {self.option_strike}")
            
            logger.info(f"Final option_strike: {self.option_strike}")
            if not self.option_strike:
                logger.warning("No underlying price available for strike calculation")
                return pd.DataFrame()

            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            stock_qualified = await self.ib.qualifyContractsAsync(stock)

            if not stock_qualified or stock_qualified[0] is None:
                logger.error(f"Could not qualify {symbol} contract")
                return pd.DataFrame()

            # Get option chain
            logger.info(f"Requesting option chain for {stock_qualified[0].symbol}")
            chains = await self.ib.reqSecDefOptParamsAsync(
                stock_qualified[0].symbol,
                '',
                stock_qualified[0].secType,
                stock_qualified[0].conId
            )

            if not chains:
                logger.warning("No option chains found")
                return pd.DataFrame()

            logger.info(f"Found {len(chains)} option chains")
            # Get the first chain (usually the most liquid exchange)
            chain = chains[0]
            logger.info(f"Using chain: {chain.exchange}, {len(chain.strikes)} strikes, {len(chain.expirations)} expirations")
            
            # Store available expirations for dynamic switching
            self._available_expirations = sorted(chain.expirations)
            logger.info(f"Available expirations: {self._available_expirations[:5]}...")  # Show first 5
            
            # Notify trading manager about available expirations
            self._notify_trading_manager_expirations(self._available_expirations)
            
            # Set initial expiration if not set
            if not self._current_expiration:
                self._current_expiration = self._available_expirations[0] if self._available_expirations else None
                logger.info(f"Set initial expiration to: {self._current_expiration}")

            # Get nearest expirations (focus on current expiration and next few)
            if self._current_expiration in self._available_expirations:
                current_index = self._available_expirations.index(self._current_expiration)
                expirations = [self._current_expiration] + self._available_expirations[current_index+1:current_index+3]
            else:
                expirations = sorted(chain.expirations)[:3]  # Fallback to first 3 expirations
            
            logger.info(f"Selected expirations: {expirations}")
            logger.info(f"Looking for options with strike: {self.option_strike}")

            option_data = []
            contracts_cache = {}

                
            expiration = expirations[0]
            try:
                logger.info(f"Processing expiration: {expiration}")
                # Create CALL option
                call_option = Option(symbol, expiration, self.option_strike, 'C', 'SMART')
                # Create PUT option
                put_option = Option(symbol, expiration, self.option_strike, 'P', 'SMART')

                logger.info(f"Created options: CALL {call_option}, PUT {put_option}")
                # Qualify contracts
                call_qualified = await self.ib.qualifyContractsAsync(call_option)
                put_qualified = await self.ib.qualifyContractsAsync(put_option)
                
                logger.info(f"Call qualification result: {call_qualified}")
                logger.info(f"Put qualification result: {put_qualified}")

                # Cache contracts for quick resubscription, keyed by symbol as well
                cache_key = f"{symbol}_{self.option_strike}_{expiration}"
                contracts_cache[cache_key] = {
                    'call': call_qualified[0] if call_qualified and call_qualified[0] else None,
                    'put': put_qualified[0] if put_qualified and put_qualified[0] else None
                }
                self._cached_option_contracts[cache_key] = contracts_cache[cache_key]

                # Process CALL option
                if call_qualified and call_qualified[0]:
                    call_option_data = {
                        'Symbol': call_qualified[0].symbol,
                        'Expiration': call_qualified[0].lastTradeDateOrContractMonth,
                        'Strike': call_qualified[0].strike,
                        'Type': 'CALL'
                    }
                    option_data.append(call_option_data)
                    logger.info(f"Added CALL option data: {call_option_data}")

                    call_option_ticker = self.ib.reqMktData(call_qualified[0], '100,101,104,106', False, False)
                    # Pass symbol/strike/expiration context to filter updates to current selection only
                    call_option_ticker.updateEvent += (lambda option_ticker, sym=symbol, st=self.option_strike, exp=expiration: self._on_update_calloption(option_ticker, sym, st, exp))
                    self._active_subscriptions.add(call_qualified[0])
                    await asyncio.sleep(1)

                # Process PUT option
                if put_qualified and put_qualified[0]:
                    put_option_data = {
                        'Symbol': put_qualified[0].symbol,
                        'Expiration': put_qualified[0].lastTradeDateOrContractMonth,
                        'Strike': put_qualified[0].strike,
                        'Type': 'PUT'
                    }
                    option_data.append(put_option_data)
                    logger.info(f"Added PUT option data: {put_option_data}")

                    put_option_ticker = self.ib.reqMktData(put_qualified[0], '100,101,104,106', False, False)
                    # Pass symbol/strike/expiration context to filter updates to current selection only
                    put_option_ticker.updateEvent += (lambda option_ticker, sym=symbol, st=self.option_strike, exp=expiration: self._on_update_putoption(option_ticker, sym, st, exp))
                    self._active_subscriptions.add(put_qualified[0])
                    await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Error processing option {symbol} {expiration} {self.option_strike}: {e}")

            logger.info(f"Finished processing all expirations. Total option_data collected: {len(option_data)}")
            if option_data:
                logger.info(f"Creating DataFrame with {len(option_data)} option contracts")
                logger.info(f"Option data: {option_data}")
                df = pd.DataFrame(option_data)
                logger.info(f"Retrieved {len(option_data)} option contracts for strike {self.option_strike}, expiration {self._current_expiration}")
                return df
            else:
                logger.warning("No option data retrieved")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return pd.DataFrame()


    def _on_update_calloption(self, option_ticker, symbol_ctx=None, strike_ctx=None, expiration_ctx=None):
        # logger.info(f"Getting real-time Call Option Data in UI")

        tmp_data = {
            'Bid': option_ticker.bid if option_ticker.bid else 0,
            'Ask': option_ticker.ask if option_ticker.ask else 0,
            'Last': option_ticker.last if option_ticker.last else 0,
            'Volume': option_ticker.volume if option_ticker.volume else 0,
            'Call_Open_Interest': getattr(option_ticker, 'callOpenInterest', 0),
            'Delta': getattr(option_ticker.modelGreeks, 'delta', 0),
            'Gamma': getattr(option_ticker.modelGreeks, 'gamma', 0),
            'Theta': getattr(option_ticker.modelGreeks, 'theta', 0),
            'Vega': getattr(option_ticker.modelGreeks, 'vega', 0),
            'Implied_Volatility': getattr(option_ticker.modelGreeks, 'impliedVol', 0) * 100
        }
        # Ensure this update corresponds to current underlying/strike/expiration
        try:
            if symbol_ctx and symbol_ctx != self.underlying_symbol:
                return
            if strike_ctx and strike_ctx != self.option_strike:
                return
            if expiration_ctx and expiration_ctx != self._current_expiration:
                return
        except Exception:
            pass

        self.option_c_mark = (option_ticker.bid + option_ticker.ask) / 2
        if self.pos_type == 'C':
            logger.info("Update PNL in Call option Update")

            pnl_results = self.calculate_pnl_detailed(self.pos, self.option_c_mark, self.option_p_mark)
            if pnl_results:
                payload = pnl_results[0] if isinstance(pnl_results, list) else pnl_results

                # Only emit if PnL results have changed
                if not hasattr(self, '_last_put_pnl_payload') or self._last_put_pnl_payload != payload:
                    self._last_put_pnl_payload = payload
                    self.data_worker.active_contracts_pnl_refreshed.emit(payload)
                else:
                    logger.debug("Put option PnL results unchanged, skipping emit")

        self.data_worker.calls_option_updated.emit(tmp_data)
        
        # Update trading manager with call option data
        if hasattr(self, 'trading_manager'):
            self.trading_manager.update_market_data(call_option=tmp_data)


    def _on_update_putoption(self, option_ticker, symbol_ctx=None, strike_ctx=None, expiration_ctx=None):
        # logger.info(f"Getting real-time Puts Option Data in UI")
        # logger.info(f"Puts Option ticker: {option_ticker}")

            
        tmp_data = {
            'Bid': option_ticker.bid if option_ticker.bid else 0,
            'Ask': option_ticker.ask if option_ticker.ask else 0,
            'Last': option_ticker.last if option_ticker.last else 0,
            'Volume': option_ticker.volume if option_ticker.volume else 0,
            'Put_Open_Interest': getattr(option_ticker, 'putOpenInterest', 0),
            'Delta': getattr(option_ticker.modelGreeks, 'delta', 0),
            'Gamma': getattr(option_ticker.modelGreeks, 'gamma', 0),
            'Theta': getattr(option_ticker.modelGreeks, 'theta', 0),
            'Vega': getattr(option_ticker.modelGreeks, 'vega', 0),
            'Implied_Volatility': getattr(option_ticker.modelGreeks, 'impliedVol', 0) * 100
        }
        # Ensure this update corresponds to current underlying/strike/expiration
        try:
            if symbol_ctx and symbol_ctx != self.underlying_symbol:
                return
            if strike_ctx and strike_ctx != self.option_strike:
                return
            if expiration_ctx and expiration_ctx != self._current_expiration:
                return
        except Exception:
            pass

        self.option_p_mark = (option_ticker.bid + option_ticker.ask) / 2
        if self.pos_type == 'P':
            logger.info("Update PNL in Put option Update")
            pnl_results = self.calculate_pnl_detailed(self.pos, self.option_c_mark, self.option_p_mark)
            if pnl_results:
                payload = pnl_results[0] if isinstance(pnl_results, list) else pnl_results

                # Only emit if PnL results have changed
                if not hasattr(self, '_last_put_pnl_payload') or self._last_put_pnl_payload != payload:
                    self._last_put_pnl_payload = payload
                    self.data_worker.active_contracts_pnl_refreshed.emit(payload)
                else:
                    logger.debug("Put option PnL results unchanged, skipping emit")

        self.data_worker.puts_option_updated.emit(tmp_data)
        
        # Update trading manager with put option data
        if hasattr(self, 'trading_manager'):
            self.trading_manager.update_market_data(put_option=tmp_data)

    def calculate_pnl_detailed(self, pos, option_c_mark, option_p_mark):
        """
        Calculate detailed PnL for a given position, handling options, stocks, and forex.
        Returns a list with a single dict of PnL details.
        """
        self.pos = pos
        self.pos_type = getattr(self.pos.contract, 'right', None)

        logger.info(f"Position: {pos}, Option_C_mark: {option_c_mark}, Option_P_mark: {option_p_mark}")
        results = []

        # Determine if position is long or short
        is_long = pos.position > 0
        position_size = abs(pos.position)

        # Determine current price based on contract type
        contract_str = str(pos.contract)
        contract_symbol = getattr(pos.contract, 'symbol', None)
        contract_right = getattr(pos.contract, 'right', None)
        avg_cost = getattr(pos, 'avgCost', 0)

        current_price = None
        currency = None

        # Option contracts
        if contract_right == 'C':
            current_price = option_c_mark * 100
            currency = 'USD'
        elif contract_right == 'P':
            current_price = option_p_mark * 100
            currency = 'USD'
        # Forex
        elif 'USDCAD' in contract_str:
            current_price = self.fx_ratio
            currency = 'CAD'
        # Stocks or unknown
        else:
            # If not an option or forex, fallback to USD
            currency = 'USD'

        # If we still don't have a price, skip
        if current_price is None:
            logger.warning(f"Could not get price for {contract_symbol}, skipping position")
            return results

        # Calculate PnL
        try:
            if is_long:
                price_diff = current_price - avg_cost
                pnl_dollar = position_size * price_diff
                pnl_percent = (price_diff / avg_cost) * 100 if avg_cost else 0
            else:
                price_diff = avg_cost - current_price
                pnl_dollar = position_size * price_diff
                pnl_percent = (price_diff / avg_cost) * 100 if avg_cost else 0
        except ZeroDivisionError:
            pnl_dollar = 0
            pnl_percent = 0

        # Symbol resolution
        symbol = getattr(pos.contract, 'localSymbol', None) or contract_symbol or 'USDCAD'

        results.append({
            'symbol': symbol,
            'position_size': pos.position,
            'position_type': 'LONG' if is_long else 'SHORT',
            'avg_cost': avg_cost,
            'current_price': current_price,
            'pnl_dollar': round(pnl_dollar, 2),
            'pnl_percent': round(pnl_percent, 2),
            'currency': currency,
            'contract': pos.contract
        })

        return results

    def _handle_position_event(self, position):
        """Handle position event and update active position data"""
        logger.info(f"Received position update for {position}")
        if position.contract.symbol == self.underlying_symbol:
            try:
                # Store the first matching position for real-time updates
                # if not self.pos:
                self.pos = position
                self.pos_type = getattr(self.pos.contract, 'right', None)

                logger.info(f"Handled Position: {self.pos}")
                pnl_results = self.calculate_pnl_detailed(self.pos, self.option_c_mark, self.option_p_mark)
                
                if pnl_results:
                    payload = pnl_results[0] if isinstance(pnl_results, list) and pnl_results else pnl_results
                    
                    # Only emit if PnL results have changed
                    if not hasattr(self, '_last_pnl_payload') or self._last_pnl_payload != payload:
                        self._last_pnl_payload = payload
                        self.data_worker.active_contracts_pnl_refreshed.emit(payload)
                        logger.info(f"Active contracts PnL refreshed: {payload}")
                    else:
                        logger.debug("PnL results unchanged, skipping emit")

                if hasattr(self.trading_manager, 'update_active_contract_items'):
                    self.trading_manager.update_active_contract_items(self.pos)

            except Exception as e:
                logger.warning(f"Error processing position: {e}")
                


    async def get_active_positions(self, underlying_symbol) -> pd.DataFrame:
        """Get active positions with improved error handling"""
        try:

            positions = self.ib.positions()

            if not positions:
                logger.info("No active positions found")
                return pd.DataFrame()
            
            pnl_detailed = []

            for position in positions:
                logger.info(f"Position: {position}")
                if position.contract.symbol == underlying_symbol:
                    try:
                        # Store the first matching position for real-time updates
                        if not self.pos:
                            self.pos = position
                            self.pos_type = getattr(self.pos.contract, 'right', None)
                            
                        # Accumulate results for matching positions using the symbol-specific price
                        logger.info("PNL update in Get active position")
                        pnl_results = self.calculate_pnl_detailed(position, self.option_c_mark, self.option_p_mark)
                        pnl_detailed.extend(pnl_results)

                    except Exception as e:
                        logger.warning(f"Error processing position: {e}")
                        continue
            
            df = pd.DataFrame(pnl_detailed)
            self.ib.positionEvent += self._handle_position_event
            

            return df
                
        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return pd.DataFrame()
    # Define an event handler for P&L updates
    def on_pnl_update(self, pnl_obj, *args, **kwargs):
        logger.info(f"Account P&L Update: Unrealized: ${pnl_obj.unrealizedPnL:.2f}, Realized: ${pnl_obj.realizedPnL:.2f}, Daily: ${pnl_obj.dailyPnL:.2f}")
        if args:
            logger.info(f"P&L additional args: {args}")
        if kwargs:
            logger.info(f"P&L additional kwargs: {kwargs}")
        new_daily_pnl = pnl_obj.dailyPnL
        if new_daily_pnl != self.daily_pnl:
            self.daily_pnl = new_daily_pnl
            # Avoid division by zero
            if self.account_liquidation > 0:
                daily_pnl_percent = 100 * self.daily_pnl / (self.account_liquidation - self.daily_pnl)
            else:
                daily_pnl_percent = 0.0
            self.data_worker.daily_pnl_update.emit({
                'daily_pnl_price': self.daily_pnl,
                'daily_pnl_percent': daily_pnl_percent
            })
            # Update trading manager with daily PnL data
            if hasattr(self, 'trading_manager'):
                self.trading_manager.update_market_data(daily_pnl_percent=daily_pnl_percent)

    def on_account_summary_update(self, account_summary, *args, **kwargs):
        logger.debug(f"Account summary update received: {len(account_summary) if account_summary else 0} items")
        logger.debug(f"Account summary type: {type(account_summary)}")
        logger.debug(f"Account summary content: {account_summary}")
        if args:
            logger.debug(f"Additional args: {args}")
        if kwargs:
            logger.debug(f"Additional kwargs: {kwargs}")
        
        # Handle case where account_summary might be None or empty
        if not account_summary:
            logger.warning("Empty account summary received")
            return
            
        new_account_liquidation = 0
        for item in account_summary:
            logger.debug(f"Account item: {item.tag} = {item.value}")
            if item.tag == 'NetLiquidation':
                try:
                    new_account_liquidation = float(item.value)
                    logger.info(f"Found NetLiquidation: {new_account_liquidation}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting NetLiquidation value '{item.value}' to float: {e}")
                    continue
                break
            
        logger.info(f"Current account_liquidation: {self.account_liquidation}, New value: {new_account_liquidation}")
        if new_account_liquidation > 0 and new_account_liquidation != self.account_liquidation:
            self.account_liquidation = new_account_liquidation
            starting_value = self.account_liquidation - self.daily_pnl
            # Treat high_water_mark as a value in currency units consistently
            high_water_mark = self.account_config.get('high_water_mark') if self.account_config else None
            logger.info(f"High water mark: {high_water_mark}")

            if high_water_mark is None:
                high_water_mark = self.account_liquidation
            else:
                try:
                    high_water_mark = float(high_water_mark)
                except Exception:
                    # If persisted as string previously, coerce to float
                    high_water_mark = self.account_liquidation

            if self.account_liquidation > high_water_mark:
                high_water_mark = self.account_liquidation
                if self.account_config is not None:
                    self.account_config['high_water_mark'] = high_water_mark
                logger.info(f"High water mark updated to {high_water_mark}")

            # Create DataFrame with common metrics
            metrics = {
                'NetLiquidation': self.account_liquidation,
                'StartingValue': starting_value,
                'HighWaterMark': high_water_mark,
            }
            logger.info(f"Updated Account Metrics: {metrics}")
            self.data_worker.account_summary_update.emit(metrics)
            
            # Update trading manager with account value
            if hasattr(self, 'trading_manager'):
                self.trading_manager.update_market_data(account_value=self.account_liquidation)
                logger.info(f"Trading manager updated with account value: {self.account_liquidation}")
        elif new_account_liquidation <= 0:
            logger.warning(f"Invalid account liquidation value received: {new_account_liquidation}")
        else:
            logger.debug("Account liquidation value unchanged")


    async def get_account_metrics(self) -> pd.DataFrame:
        """Get account metrics with improved error handling.
        High water mark is tracked consistently as a realized PnL value (currency units).
        """
        try:
            # Check connection first
            if not self.ib.isConnected():
                logger.error("Not connected to IB when getting account metrics")
                return pd.DataFrame()
            
            # Get account summary
            try:
                managed_accounts = self.ib.managedAccounts()
                if not managed_accounts:
                    logger.error("No managed accounts found")
                    return pd.DataFrame()
                account = managed_accounts[0]  # Get first managed account
                logger.info(f"Account: {account}")
            except Exception as e:
                logger.error(f"Error getting managed accounts: {e}")
                return pd.DataFrame()
            
            # Subscribe to P&L updates for the account
            try:
                pnl = self.ib.reqPnL(account)
                logger.info(f"P&L request submitted: {pnl}")
                # Note: Event handlers are now set up in _setup_account_monitoring
            except Exception as e:
                logger.warning(f"Error requesting P&L updates: {e}")
                # Continue without P&L updates

            # Get account summary values
            try:
                account_values = await self.ib.accountSummaryAsync()
                logger.info(f"Received {len(account_values) if account_values else 0} account values")
            except Exception as e:
                logger.error(f"Error getting account summary: {e}")
                return pd.DataFrame()

            if not account_values:
                logger.warning("No account values received")
                return pd.DataFrame()

            # Create account data dictionary
            account_data = {}
            for value in account_values:
                try:
                    account_data[value.tag] = value.value
                except Exception as e:
                    logger.warning(f"Error processing account value {value.tag}: {e}")
                    continue
            
            # Extract key values with better error handling
            try:
                self.account_liquidation = float(account_data.get('NetLiquidation', 0) or 0)
                starting_value = self.account_liquidation - self.daily_pnl
                logger.info(f"Account liquidation: {self.account_liquidation}, Starting value: {starting_value}")
            except Exception as e:
                logger.error(f"Error processing account liquidation value: {e}")
                self.account_liquidation = 0
                starting_value = 0

            # Treat high_water_mark as a value in currency units consistently
            high_water_mark = self.account_config.get('high_water_mark') if self.account_config else None
            logger.info(f"High water mark: {high_water_mark}")

            if high_water_mark is None:
                high_water_mark = self.account_liquidation
            else:
                try:
                    high_water_mark = float(high_water_mark)
                except Exception:
                    # If persisted as string previously, coerce to float
                    high_water_mark = self.account_liquidation

            if self.account_liquidation > high_water_mark:
                high_water_mark = self.account_liquidation
                if self.account_config is not None:
                    self.account_config['high_water_mark'] = high_water_mark
                logger.info(f"High water mark updated to {high_water_mark}")

            # Create DataFrame with common metrics
            metrics = {
                'NetLiquidation': self.account_liquidation,
                'StartingValue': starting_value,
                'HighWaterMark': high_water_mark,
            }

            df = pd.DataFrame([metrics])
            logger.info("Account metrics retrieved successfully")
            return df

        except Exception as e:
            logger.error(f"Error getting account metrics: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return pd.DataFrame()

    async def get_today_option_executions(self, symbol='SPY'):
        executions = await self.ib.reqExecutionsAsync()
        today = date.today()
        trades = []

        for trade in executions:
            exec_date = trade.execution.time.astimezone().date()
            contract = trade.contract

            if (
                    exec_date == today and
                    contract.secType == 'OPT' and
                    contract.symbol == symbol and
                    contract.right in ['C', 'P']
            ):
                trades.append(trade)

        return trades

    async def match_trades_and_calculate_pnl(self, trades):
        open_positions = defaultdict(deque)  # {contract key: deque of fills}
        closed_trades = []

        for trade in trades:
            contract = trade.contract
            exec = trade.execution
            side = exec.side.upper()  # BOT or SLD
            quantity = exec.shares
            price = exec.price
            time = exec.time
            multiplier = int(contract.multiplier) if contract.multiplier else 100
            key = (contract.symbol, contract.lastTradeDateOrContractMonth,
                   contract.strike, contract.right)

            position = {
                'time': time,
                'side': side,
                'qty': quantity,
                'price': price,
                'contract': contract
            }

            if side == 'BOT':
                open_positions[key].append(position)
            elif side == 'SLD':
                # Try to find matching buy(s)
                remaining_qty = quantity
                while remaining_qty > 0 and open_positions[key]:
                    buy_trade = open_positions[key][0]
                    match_qty = min(remaining_qty, buy_trade['qty'])

                    pnl = (price - buy_trade['price']) * match_qty * multiplier

                    closed_trades.append({
                        'buy_time': buy_trade['time'],
                        'sell_time': time,
                        'contract': contract,
                        'buy_price': buy_trade['price'],
                        'sell_price': price,
                        'qty': match_qty,
                        'pnl': pnl
                    })

                    # Adjust unmatched quantities
                    buy_trade['qty'] -= match_qty
                    remaining_qty -= match_qty

                    if buy_trade['qty'] == 0:
                        open_positions[key].popleft()
            # You can repeat the same if you short first and buy-to-cover later.
            # For simplicity, we're only handling BOT then SLD
        return closed_trades

    def on_exec_details(self, trade, fill):
        open_positions = defaultdict(deque)  # key: contract id tuple -> deque of opens
        multiplier_default = 100
        today = date.today()
        
        # Initialize closed_trades as a list if it's None
        self._ensure_closed_trades_initialized()
        
        contract = trade.contract
        exec = fill.execution

        # Filter only options trades (calls/puts) and only today's trades
        if (
                contract.secType != 'OPT' or
                contract.right not in ['C', 'P'] or
                contract.symbol != self.underlying_symbol
        ):
            return

        symbol_key = (
            contract.symbol,
            contract.lastTradeDateOrContractMonth,
            contract.strike,
            contract.right
        )

        side = exec.side.upper()  # BOT or SLD
        time_filled = exec.time
        fill_qty = exec.shares
        price = exec.price
        multiplier = int(contract.multiplier) if contract.multiplier else multiplier_default

        if time_filled.astimezone().date() != today:
            return

        fill_data = {
            'contract': contract,
            'side': side,
            'time': time_filled,
            'qty': fill_qty,
            'price': price,
            'multiplier': multiplier,
        }

        if side == 'BOT':
            open_positions[symbol_key].append(fill_data)
        elif side == 'SLD':
            # match to existing buys FIFO
            remain_to_match = fill_qty
            while remain_to_match > 0 and open_positions[symbol_key]:
                opener = open_positions[symbol_key][0]
                match_qty = min(opener['qty'], remain_to_match)
                pnl = (price - opener['price']) * match_qty * multiplier

                trade_data = {
                    'contract': contract,
                    'qty': match_qty,
                    'buy_price': opener['price'],
                    'sell_price': price,
                    'pnl': pnl,
                    'buy_time': opener['time'],
                    'sell_time': time_filled
                }
                self.closed_trades.append(trade_data)
                logger.debug(f"Added closed trade: {trade_data}")

                logger.info(f"Closed Trade: {match_qty}x {symbol_key} P&L = {pnl:.2f}")

                # Adjust remaining qtys
                opener['qty'] -= match_qty
                remain_to_match -= match_qty

                if opener['qty'] == 0:
                    open_positions[symbol_key].popleft()

        # Calculate statistics
        wins = []
        losses = []

        # Ensure closed_trades is a list before iterating
        self._ensure_closed_trades_initialized()
        
        try:
            for trade in self.closed_trades:
                try:
                    if not isinstance(trade, dict):
                        logger.warning(f"Trade is not a dict: {type(trade)}, skipping")
                        continue
                        
                    pnl = trade.get('pnl')
                    if pnl is None:
                        logger.warning(f"Trade missing 'pnl' key: {trade}")
                        continue

                    if pnl > 0:
                        wins.append(pnl)
                    elif pnl < 0:
                        losses.append(abs(pnl))

                except Exception as e:
                    logger.warning(f"Error calculating P&L for trade: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error iterating over closed_trades: {e}")
            return self._create_empty_stats()

        # Calculate statistics
        total_trades = len(wins) + len(losses)
        if total_trades == 0:
            return self._create_empty_stats()

        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0

        stats = {
            'Win_Rate': win_rate,
            'Total_Wins_Count': len(wins),
            'Total_Wins_Sum': sum(wins),
            'Total_Losses_Count': len(losses),
            'Total_Losses_Sum': sum(losses),
            'Total_Trades': total_trades,
            'Average_Win': sum(wins) / len(wins) if wins else 0,
            'Average_Loss': sum(losses) / len(losses) if losses else 0,
            'Profit_Factor': sum(wins) / sum(losses) if losses else float('inf')
        }
        
        self.data_worker.closed_trades_update.emit(stats)
        
    async def get_trade_statistics(self) -> pd.DataFrame:
        """Get trade statistics with improved error handling"""
        try:

            # Get completed orders
            all_trades = await self.get_today_option_executions(self.underlying_symbol)
            self.closed_trades = await self.match_trades_and_calculate_pnl(all_trades)
            logger.info(f"Retrieved {len(self.closed_trades) if isinstance(self.closed_trades, list) else 'unknown'} closed trades")
        
            # Calculate statistics
            wins = []
            losses = []
            
            # Ensure closed_trades is a list before iterating
            self._ensure_closed_trades_initialized()
            
            try:
                for trade in self.closed_trades:
                    try:
                        if not isinstance(trade, dict):
                            logger.warning(f"Trade is not a dict: {type(trade)}, skipping")
                            continue
                            
                        pnl = trade.get('pnl')
                        if pnl is None:
                            logger.warning(f"Trade missing 'pnl' key: {trade}")
                            continue
                        
                        if pnl > 0:
                            wins.append(pnl)
                        elif pnl < 0:
                            losses.append(abs(pnl))
                            
                    except Exception as e:
                        logger.warning(f"Error calculating P&L for trade: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error iterating over closed_trades: {e}")
                return self._create_empty_stats()
            
            # Calculate statistics
            total_trades = len(wins) + len(losses)
            if total_trades == 0:
                return self._create_empty_stats()
            
            win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
            
            stats = {
                'Win_Rate': win_rate,
                'Total_Wins_Count': len(wins),
                'Total_Wins_Sum': sum(wins),
                'Total_Losses_Count': len(losses),
                'Total_Losses_Sum': sum(losses),
                'Total_Trades': total_trades,
                'Average_Win': sum(wins) / len(wins) if wins else 0,
                'Average_Loss': sum(losses) / len(losses) if losses else 0,
                'Profit_Factor': sum(wins) / sum(losses) if losses else float('inf')
            }
            self.ib.execDetailsEvent += self.on_exec_details
            logger.info(f"Trade statistics calculated: {total_trades} trades, {win_rate:.2f}% win rate")
            return pd.DataFrame([stats])
            
        except Exception as e:
            logger.error(f"Error getting trade statistics: {e}")
            return self._create_empty_stats()
    
    def _create_empty_stats(self) -> pd.DataFrame:
        """Create empty statistics DataFrame"""
        return pd.DataFrame([{
            'Win_Rate': 0,
            'Total_Wins_Count': 0,
            'Total_Wins_Sum': 0,
            'Total_Losses_Count': 0,
            'Total_Losses_Sum': 0,
            'Total_Trades': 0,
            'Average_Win': 0,
            'Average_Loss': 0,
            'Profit_Factor': 0
        }])
    
    async def collect_all_data(self) -> Optional[Dict[str, Any]]:
        """Collect all requested data with improved error handling"""
        logger.info("Starting comprehensive data collection...")
        
        # Check connection
        if not self.ib.isConnected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not await self.connect():
                logger.error("Failed to connect to IB")
                return None
        
        try:
            data = {}
            self.underlying_symbol = self.trading_config.get('underlying_symbol')

            # Get underlying symbol price first (this sets up real-time monitoring)
            logger.info(f"Getting {self.underlying_symbol} price...")
            price = await self.get_underlying_symbol_price(self.underlying_symbol)
            if price is None:
                logger.error(f"Failed to get {self.underlying_symbol} price")
                return None
            logger.info(f"Got {self.underlying_symbol} price: ${price}")

            # Get USD/CAD ratio
            logger.info("Getting USD/CAD ratio...")
            data["fx_ratio"] = await self.get_fx_ratio()

            # Get account metrics
            logger.info("Getting account metrics...")
            account_df = await self.get_account_metrics()
            data['account'] = account_df

            # Get option chain (this will set initial strike and expiration)
            logger.info("Getting option chain...")
            options_df = await self.get_option_chain()
            data['options'] = options_df

            # Get active positions
            logger.info("Getting active positions...")
            positions_df = await self.get_active_positions(self.underlying_symbol)
            data['active_contract'] = positions_df
            
            # Update trading manager with position data
            if hasattr(self, 'trading_manager') and not positions_df.empty:
                for _, position in positions_df.iterrows():
                    position_data = position.to_dict()
                    self.trading_manager.update_position(position_data)

            # # Get trade statistics
            logger.info("Getting trade statistics...")
            stats_df = await self.get_trade_statistics()
            data['statistics'] = stats_df
            
            logger.info("Data collection completed successfully")
            return data
            
        except Exception as e:
            logger.error(f"Error during data collection: {e}")
            return None
    
    async def _switch_option_subscriptions(self, new_strike: int = None, new_expiration: str = None):
        """Switch option subscriptions when strike price or expiration changes"""
        try:
            # Unsubscribe from current options
            await self._unsubscribe_from_current_options()
            
            # Update strike and expiration if provided
            if new_strike is not None:
                self.option_strike = new_strike
                self._previous_strike = new_strike
                logger.info(f"Switched to new strike price: {new_strike}")
            
            if new_expiration is not None:
                self._current_expiration = new_expiration
                logger.info(f"Switched to new expiration: {new_expiration}")
            
            # Subscribe to new options
            await self._subscribe_to_new_options()
            
        except Exception as e:
            logger.error(f"Error switching option subscriptions: {e}")

    async def _unsubscribe_from_current_options(self):
        """Unsubscribe from all current option contracts"""
        try:
            contracts_to_remove = set()
            for contract in self._active_subscriptions:
                if hasattr(contract, 'secType') and contract.secType == 'OPT':
                    try:
                        self.ib.cancelMktData(contract)
                        contracts_to_remove.add(contract)
                        logger.debug(f"Unsubscribed from option: {contract}")
                    except Exception as e:
                        logger.warning(f"Error unsubscribing from option {contract}: {e}")
            
            # Remove from active subscriptions
            self._active_subscriptions.difference_update(contracts_to_remove)
            
        except Exception as e:
            logger.error(f"Error unsubscribing from current options: {e}")

    async def _subscribe_to_new_options(self):
        """Subscribe to new option contracts based on current strike and expiration"""
        try:
            if not self.option_strike or not self._current_expiration:
                logger.warning("Cannot subscribe to new options: missing strike or expiration")
                return
            
            # Check if we have cached contracts for this symbol+strike+expiration
            cache_key = f"{self.underlying_symbol}_{self.option_strike}_{self._current_expiration}"
            if cache_key in self._cached_option_contracts:
                contracts = self._cached_option_contracts[cache_key]
                await self._subscribe_to_cached_contracts(contracts)
            else:
                # Get contracts without full subscription process
                contracts = await self._get_option_contracts_only(
                    self.underlying_symbol, 
                    self.option_strike, 
                    self._current_expiration
                )
                if contracts['call'] or contracts['put']:
                    await self._subscribe_to_cached_contracts(contracts)
                else:
                    logger.warning(f"No contracts found for strike {self.option_strike}, expiration {self._current_expiration}")
                
        except Exception as e:
            logger.error(f"Error subscribing to new options: {e}")

    async def _subscribe_to_cached_contracts(self, contracts: Dict[str, Any]):
        """Subscribe to cached option contracts"""
        try:
            for option_type, contract in contracts.items():
                if contract:
                    try:
                        ticker = self.ib.reqMktData(contract)
                        self._active_subscriptions.add(contract)
                        logger.info(f"Subscribed to cached {option_type} option: {contract}")
                    except Exception as e:
                        logger.warning(f"Error subscribing to cached {option_type} option: {e}")
                        
        except Exception as e:
            logger.error(f"Error subscribing to cached contracts: {e}")

    async def _get_and_subscribe_to_options(self):
        """Get new option chain and subscribe to contracts"""
        try:
            # Get option chain for current strike and expiration
            options_df = await self.get_option_chain()
            if not options_df.empty:
                logger.info(f"Successfully subscribed to new options for strike {self.option_strike}, expiration {self._current_expiration}")
            else:
                logger.warning(f"No options found for strike {self.option_strike}, expiration {self._current_expiration}")
                
        except Exception as e:
            logger.error(f"Error getting and subscribing to new options: {e}")

    async def _get_option_contracts_only(self, symbol: str, strike: int, expiration: str) -> Dict[str, Any]:
        """Get option contracts without subscribing to market data (for caching)"""
        try:
            # Create CALL option
            call_option = Option(symbol, expiration, strike, 'C', 'SMART')
            # Create PUT option
            put_option = Option(symbol, expiration, strike, 'P', 'SMART')

            # Qualify contracts
            call_qualified = await self.ib.qualifyContractsAsync(call_option)
            put_qualified = await self.ib.qualifyContractsAsync(put_option)

            contracts = {
                'call': call_qualified[0] if call_qualified and call_qualified[0] else None,
                'put': put_qualified[0] if put_qualified and put_qualified[0] else None
            }
            
            # Cache the contracts keyed by symbol+strike+expiration
            cache_key = f"{symbol}_{strike}_{expiration}"
            self._cached_option_contracts[cache_key] = contracts
            
            return contracts
            
        except Exception as e:
            logger.error(f"Error getting option contracts for {symbol} {strike} {expiration}: {e}")
            return {'call': None, 'put': None}

    def _continuous_monitoring_loop(self):
        """Continuous monitoring loop for strike price and expiration changes"""
        logger.info("Starting continuous monitoring for dynamic strike and expiration changes")
        
        while not self._stop_monitoring.is_set():
            try:
                # Check if underlying price has changed significantly
                if self.underlying_symbol_price > 0:
                    new_strike = self._calculate_nearest_strike(self.underlying_symbol_price)
                    
                    if self._should_update_strike(new_strike):
                        logger.info(f"Strike price changed from {self._previous_strike} to {new_strike}")
                        # Schedule strike update in main thread
                        if self._loop and self._loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self._switch_option_subscriptions(new_strike=new_strike),
                                self._loop
                            )
                        else:
                            logger.error("Cannot schedule strike update: event loop is not available or not running")
                
                # Check if it's time to switch expiration (12:00 PM EST)
                if self._should_switch_expiration_smart():
                    current_exp_type = self._get_expiration_type(self._current_expiration)
                    logger.info(f"Smart expiration switching triggered. Current: {self._current_expiration} ({current_exp_type})")
                    
                    # Get the best available expiration for switching
                    best_expiration = self._get_best_available_expiration()
                    
                    if best_expiration and best_expiration != self._current_expiration:
                        # Validate that the new expiration is available
                        if self._validate_expiration_availability(best_expiration):
                            next_exp_type = self._get_expiration_type(best_expiration)
                            logger.info(f"Switching from {current_exp_type} ({self._current_expiration}) to {next_exp_type} ({best_expiration})")
                            
                            # Schedule expiration update in main thread
                            if self._loop and self._loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self._switch_option_subscriptions(new_expiration=best_expiration),
                                    self._loop
                                )
                            else:
                                logger.error("Cannot schedule expiration update: event loop is not available or not running")
                        else:
                            logger.warning(f"Selected expiration {best_expiration} is not available, skipping switch")
                    else:
                        logger.info(f"No better expiration found for switching. Keeping current: {self._current_expiration}")
                
                # Sleep for 1 second before next check
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in continuous monitoring loop: {e}")
                time.sleep(5)  # Longer sleep on error
        
        logger.info("Continuous monitoring stopped")

    def start_dynamic_monitoring(self):
        """Start the dynamic strike price and expiration monitoring"""
        if self._monitoring_active:
            logger.warning("Dynamic monitoring is already active")
            return
        
        try:
            self._stop_monitoring.clear()
            self._monitor_thread = Thread(target=self._continuous_monitoring_loop, daemon=True)
            self._monitor_thread.start()
            self._monitoring_active = True
            logger.info("Dynamic monitoring started successfully")
            
        except Exception as e:
            logger.error(f"Error starting dynamic monitoring: {e}")

    def stop_dynamic_monitoring(self):
        """Stop the dynamic strike price and expiration monitoring"""
        if not self._monitoring_active:
            logger.warning("Dynamic monitoring is not active")
            return
        
        try:
            self._stop_monitoring.set()
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            self._monitoring_active = False
            logger.info("Dynamic monitoring stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping dynamic monitoring: {e}")

    def get_dynamic_monitoring_status(self) -> Dict[str, Any]:
        """Get the current status of dynamic monitoring"""
        try:
            status = {
                'monitoring_active': self._monitoring_active,
                'current_strike': self.option_strike,
                'previous_strike': self._previous_strike,
                'current_expiration': self._current_expiration,
                'current_expiration_type': self._get_expiration_type(self._current_expiration) if self._current_expiration else "Unknown",
                'underlying_price': self.underlying_symbol_price,
                'available_expirations': getattr(self, '_available_expirations', []),
                'cached_contracts_count': len(self._cached_option_contracts),
                'active_subscriptions_count': len(self._active_subscriptions),
                'monitor_thread_alive': self._monitor_thread.is_alive() if self._monitor_thread else False
            }
            return status
        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            return {}

    def log_dynamic_monitoring_status(self):
        """Log the current status of dynamic monitoring"""
        try:
            status = self.get_dynamic_monitoring_status()
            logger.info("=== Dynamic Monitoring Status ===")
            logger.info(f"Monitoring Active: {status.get('monitoring_active', False)}")
            logger.info(f"Current Strike: {status.get('current_strike', 'N/A')}")
            logger.info(f"Previous Strike: {status.get('previous_strike', 'N/A')}")
            logger.info(f"Current Expiration: {status.get('current_expiration', 'N/A')}")
            logger.info(f"Expiration Type: {status.get('current_expiration_type', 'N/A')}")
            logger.info(f"Underlying Price: ${status.get('underlying_price', 0):.2f}")
            logger.info(f"Available Expirations: {len(status.get('available_expirations', []))}")
            logger.info(f"Cached Contracts: {status.get('cached_contracts_count', 0)}")
            logger.info(f"Active Subscriptions: {status.get('active_subscriptions_count', 0)}")
            logger.info(f"Monitor Thread Alive: {status.get('monitor_thread_alive', False)}")
            logger.info("================================")
        except Exception as e:
            logger.error(f"Error logging monitoring status: {e}")


    async def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get historical price data for a symbol from IB"""
        try:
            if not self.ib.isConnected():
                logger.warning("Not connected to IB. Attempting to connect...")
                if not await self.connect():
                    logger.error("Failed to connect to IB for historical data")
                    return []
            logger.info(f"Getting historical data for {symbol} from {start_date} to {end_date}")
            # Create a Stock contract for the symbol
            qualified_contracts = self.underlying_symbol_qualified
            contract = qualified_contracts[0]
            logger.debug(f"Contract: {contract}")
            start_date = datetime.now() - timedelta(days=30)
            end_date = datetime.now()

            # Format dates for IB API (YYYYMMDD HH:mm:ss)
            start_str = start_date.strftime('%Y%m%d %H:%M:%S')
            end_str = end_date.strftime('%Y%m%d %H:%M:%S')
            logger.debug(f"Start date: {start_str}, End date: {end_str}")
            # Request historical data
            # Using 1 day bars for daily data
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                end_str,
                f"{int((end_date - start_date).days)} D",  # Duration
                "1 day",  # Bar size
                "TRADES",  # What to show
                1,  # Use RTH
                1,  # Format date
                False,  # Keep up to date after bar
                []  # Chart options
            )
            logger.debug(f"Bars: {bars}")
            if not bars:
                logger.warning(f"No historical data returned for {contract.symbol}")
                exit()

            # Convert bars to list of dictionaries
            historical_data = []
            for bar in bars:
                historical_data.append({
                    'timestamp': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                })

            logger.info(f"Retrieved {len(historical_data)} historical data points for {contract.symbol}")

            return historical_data

        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return []


    def _validate_expiration_availability(self, expiration: str) -> bool:
        """Validate if an expiration is available in the option chain"""
        try:
            if not hasattr(self, '_available_expirations') or not self._available_expirations:
                return False
            
            # Clean expiration string
            if ' ' in expiration:
                exp_str = expiration.split()[0]
            else:
                exp_str = expiration
            
            # Check if expiration exists in available list
            is_available = exp_str in self._available_expirations
            
            if is_available:
                logger.debug(f"Expiration {expiration} is available")
            else:
                logger.warning(f"Expiration {expiration} is NOT available in chain")
            
            return is_available
            
        except Exception as e:
            logger.error(f"Error validating expiration availability: {e}")
            return False
    
    def _get_best_available_expiration(self, target_date: date = None) -> Optional[str]:
        """Get the best available expiration based on target date or current time"""
        try:
            if not hasattr(self, '_available_expirations') or not self._available_expirations:
                return None
            
            if not target_date:
                # Determine target date based on current time
                est_now = datetime.now(self._est_timezone)
                current_date = est_now.date()
                current_time = est_now.time()
                
                if current_time.hour < 12:
                    # Before noon - prefer today (0DTE)
                    target_date = current_date
                else:
                    # After noon - prefer next business day (1DTE)
                    target_date = current_date + timedelta(days=1)
                    # Skip weekends
                    while target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                        target_date += timedelta(days=1)
            
            logger.info(f"Looking for best available expiration for target date: {target_date}")
            
            # Strategy 1: Find exact target date
            for exp_str in self._available_expirations:
                try:
                    if ' ' in exp_str:
                        exp_str_clean = exp_str.split()[0]
                    else:
                        exp_str_clean = exp_str
                    exp_date = datetime.strptime(exp_str_clean, "%Y%m%d").date()
                    
                    if exp_date == target_date:
                        logger.info(f"Found exact target expiration: {exp_str}")
                        return exp_str
                        
                except Exception as e:
                    logger.warning(f"Could not parse expiration {exp_str}: {e}")
                    continue
            
            # Strategy 2: Find nearest available expiration to target date
            best_exp = None
            min_days_diff = float('inf')
            
            for exp_str in self._available_expirations:
                try:
                    if ' ' in exp_str:
                        exp_str_clean = exp_str.split()[0]
                    else:
                        exp_str_clean = exp_str
                    exp_date = datetime.strptime(exp_str_clean, "%Y%m%d").date()
                    
                    # Only consider future expirations
                    if exp_date >= target_date:
                        days_diff = abs((exp_date - target_date).days)
                        if days_diff < min_days_diff:
                            min_days_diff = days_diff
                            best_exp = exp_str
                            
                except Exception as e:
                    logger.warning(f"Could not parse expiration {exp_str}: {e}")
                    continue
            
            if best_exp:
                logger.info(f"Selected best available expiration: {best_exp} (days diff from target: {min_days_diff})")
                return best_exp
            
            # Strategy 3: Fallback to first available expiration
            logger.warning("No suitable expiration found, using first available")
            return self._available_expirations[0] if self._available_expirations else None
            
        except Exception as e:
            logger.error(f"Error getting best available expiration: {e}")
            return None

    def _ensure_closed_trades_initialized(self):
        """Ensure closed_trades is initialized as a list"""
        if self.closed_trades is None:
            self.closed_trades = []
            logger.debug("Initialized closed_trades as empty list")
        elif not isinstance(self.closed_trades, list):
            logger.warning(f"closed_trades is not a list: {type(self.closed_trades)}, reinitializing")
            self.closed_trades = []
        else:
            logger.debug(f"closed_trades is already a list with {len(self.closed_trades)} items")

    def _notify_trading_manager_expirations(self, expirations: List[str]):
        """Notify trading manager about available expirations"""
        try:
            if hasattr(self, 'trading_manager') and self.trading_manager:
                if hasattr(self.trading_manager, 'update_available_expirations'):
                    self.trading_manager.update_available_expirations(expirations)
                    logger.info(f"Notified trading manager about {len(expirations)} available expirations")
                else:
                    logger.debug("Trading manager doesn't have update_available_expirations method")
            else:
                logger.debug("No trading manager available for expiration notification")
                
        except Exception as e:
            logger.error(f"Error notifying trading manager about expirations: {e}")
    
    def manual_expiration_switch(self, target_expiration: str = None) -> bool:
        """Manually trigger expiration switching to a specific expiration or best available"""
        try:
            if not target_expiration:
                # Get best available expiration
                target_expiration = self._get_best_available_expiration()
            
            if not target_expiration:
                logger.error("No target expiration available for manual switch")
                return False
            
            # Validate expiration availability
            if not self._validate_expiration_availability(target_expiration):
                logger.error(f"Target expiration {target_expiration} is not available")
                return False
            
            if target_expiration == self._current_expiration:
                logger.info(f"Already using target expiration {target_expiration}")
                return True
            
            logger.info(f"Manual expiration switch from {self._current_expiration} to {target_expiration}")
            
            # Schedule expiration update in main thread
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._switch_option_subscriptions(new_expiration=target_expiration),
                    self._loop
                )
            else:
                logger.error("Cannot schedule manual expiration update: event loop is not available or not running")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in manual expiration switch: {e}")
            return False
    
    def get_expiration_status(self) -> Dict[str, Any]:
        """Get detailed expiration status for monitoring"""
        try:
            status = {
                'current_expiration': self._current_expiration,
                'current_expiration_type': self._get_expiration_type(self._current_expiration) if self._current_expiration else "Unknown",
                'available_expirations': getattr(self, '_available_expirations', []),
                'available_expirations_count': len(getattr(self, '_available_expirations', [])),
                'next_recommended_expiration': self._get_best_available_expiration(),
                'should_switch': self._should_switch_expiration_smart(),
                'current_time_est': datetime.now(self._est_timezone).strftime("%Y-%m-%d %H:%M:%S EST"),
                'expiration_switch_enabled': True
            }
            
            # Add detailed analysis of available expirations
            if hasattr(self, '_available_expirations') and self._available_expirations:
                exp_analysis = []
                for exp_str in self._available_expirations[:5]:  # Show first 5
                    try:
                        if ' ' in exp_str:
                            exp_str_clean = exp_str.split()[0]
                        else:
                            exp_str_clean = exp_str
                        exp_date = datetime.strptime(exp_str_clean, "%Y%m%d").date()
                        current_date = datetime.now(self._est_timezone).date()
                        days_diff = (exp_date - current_date).days
                        exp_type = self._get_expiration_type(exp_str)
                        exp_analysis.append({
                            'expiration': exp_str,
                            'days_diff': days_diff,
                            'type': exp_type,
                            'is_current': exp_str == self._current_expiration
                        })
                    except Exception as e:
                        exp_analysis.append({
                            'expiration': exp_str,
                            'days_diff': 'Unknown',
                            'type': 'Unknown',
                            'is_current': exp_str == self._current_expiration,
                            'error': str(e)
                        })
                
                status['expiration_analysis'] = exp_analysis
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting expiration status: {e}")
            return {'error': str(e)}
        
