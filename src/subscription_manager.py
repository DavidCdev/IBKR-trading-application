"""
Subscription Manager - Event-driven subscription management for IB trading system
================================================================================

Manages all market data subscriptions through the event bus:
- Underlying symbol subscriptions
- Currency conversion subscriptions
- Options chain subscriptions with dynamic strike/expiration selection
- Active contract tracking and management
- Automatic reconnection and resubscription

Key Features:
- Waits for ib.connected before proceeding with startup
- Dynamic options selection based on time and price
- Automatic resubscription on reconnection
- Error handling with retry logic
- Timezone-aware expiration selection
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pytz
from logger import get_logger
from event_bus import EventBus, EventPriority
from config_manager import ConfigManager

logger = get_logger('SUBSCRIPTION_MANAGER')

class SubscriptionState(Enum):
    """States for subscription management."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    ERROR = "error"

@dataclass
class ActiveContract:
    """Tracks an active contract for subscription management."""
    contract: Dict[str, Any]
    order_id: int
    timestamp: datetime
    is_option: bool = True
    is_active: bool = True

@dataclass
class SubscriptionConfig:
    """Configuration for subscription management."""
    underlying_symbol: str
    account_currency: Optional[str] = None
    underlying_currency: Optional[str] = None
    market_timezone: str = "US/Eastern"
    retry_attempts: int = 3
    retry_delay: float = 2.0
    max_order_delay_ms: int = 750

class SubscriptionManager:
    """
    Manages all market data subscriptions through the event bus.
    
    Responsibilities:
    - Subscribe to underlying based on config
    - Handle currency conversion subscriptions
    - Manage options chain subscriptions with dynamic selection
    - Track active contracts and maintain subscriptions
    - Handle reconnection and resubscription
    """
    
    def __init__(self, event_bus: EventBus, config_manager: ConfigManager):
        """
        Initialize the subscription manager.
        
        Args:
            event_bus: The event bus for communication
            config_manager: Configuration manager for settings
        """
        logger.info("Initializing SubscriptionManager")
        
        # Start background thread to monitor for noon resubscription
        threading.Thread(target=self._noon_resubscription_monitor, daemon=True).start()


        self.event_bus = event_bus
        self.config_manager = config_manager
        self.config = SubscriptionConfig(
            underlying_symbol=config_manager.get('trading', 'underlying_symbol', 'SPY')
        )
        
        # State management
        self.state = SubscriptionState.DISCONNECTED
        self.ib_connected = False
        self.startup_complete = False
        
        # Subscription tracking
        self.current_subscriptions: Dict[str, Dict[str, Any]] = {}
        self.active_contracts: List[ActiveContract] = []
        self.options_chain: List[Dict[str, Any]] = []
        self.underlying_price: Optional[float] = None
        self.account_currency: Optional[str] = None
        
        # Retry tracking
        self.retry_counts: Dict[str, int] = {}
        self.last_retry_time: Dict[str, float] = {}
        
        # Register event handlers
        self._register_event_handlers()
        
        logger.info("SubscriptionManager initialized successfully")
    
    def _noon_resubscription_monitor(self):
        """Monitor system time and trigger resubscription at 12:00:00 PM EST."""
        est = pytz.timezone(self.config.market_timezone)
        already_triggered = False
        while True:
            now = datetime.now(est)
            if now.hour == 12 and now.minute == 0 and now.second == 0:
                if not already_triggered:
                    logger.info("Noon EST reached, triggering resubscription to 1DTE contracts")
                    self._select_and_subscribe_options()
                    already_triggered = True
            else:
                already_triggered = False
            time.sleep(1)

    def _register_event_handlers(self):
        """Register all event handlers for subscription management."""
        logger.debug("Registering event handlers")
        
        # Connection events
        self.event_bus.on('ib.connected', self._on_ib_connected, priority=EventPriority.HIGH)
        self.event_bus.on('ib.disconnected', self._on_ib_disconnected, priority=EventPriority.HIGH)
        self.event_bus.on('ib.error', self._on_ib_error)
        
        # Market data events
        self.event_bus.on('market_data.subscribed', self._on_market_data_subscribed)
        self.event_bus.on('market_data.error', self._on_market_data_error)
        self.event_bus.on('market_data.tick_update', self._on_market_data_tick)
        
        # Options chain events
        self.event_bus.on('option_chain_update', self._on_options_chain_update)
        self.event_bus.on('options.chain_error', self._on_options_chain_error)
        
        # Account events
        self.event_bus.on('account.summary_update', self._on_account_summary_update)
        self.event_bus.on('positions_update', self._on_positions_update)
        self.event_bus.on('open_orders_update', self._on_open_orders_update)
        
        # Order events
        self.event_bus.on('order.place', self._on_order_place)
        self.event_bus.on('order.fill', self._on_order_fill)
        
        logger.info("Event handlers registered successfully")
    
    def _on_ib_connected(self, data: Dict[str, Any]):
        """Handle IB connection established."""
        logger.info("✓ SubscriptionManager: IB connection established")
        self.ib_connected = True
        self.state = SubscriptionState.CONNECTED
        
        # Start subscription process
        self._start_subscription_process()
    
    def _on_ib_disconnected(self, data: Dict[str, Any]):
        """Handle IB disconnection."""
        logger.warning("SubscriptionManager: IB connection lost")
        self.ib_connected = False
        self.state = SubscriptionState.DISCONNECTED
        self.startup_complete = False
        
        # Clear current subscriptions
        self.current_subscriptions.clear()
        self.retry_counts.clear()
        self.last_retry_time.clear()
    
    def _on_ib_error(self, error_data=None, **kwargs):
        """Enhanced IB error handling with categorization and recovery strategies."""
        # Handle both string and dict error formats, and keyword arguments
        if error_data is None and kwargs:
            # Handle keyword arguments (e.g., error_message='...')
            if 'error_message' in kwargs:
                error_string = kwargs['error_message']
                error_code = 0
                category = 'general'
                recovery_strategy = 'log_only'
            else:
                # Use kwargs as error_data
                error_data = kwargs
                error_code = error_data.get('errorCode', 0)
                error_string = error_data.get('errorString', error_data.get('message', 'Unknown error'))
                category = error_data.get('category', 'general')
                recovery_strategy = error_data.get('recovery_strategy', 'log_only')
        elif isinstance(error_data, str):
            error_string = error_data
            error_code = 0
            category = 'general'
            recovery_strategy = 'log_only'
        else:
            error_code = error_data.get('errorCode', 0)
            error_string = error_data.get('errorString', error_data.get('message', 'Unknown error'))
            category = error_data.get('category', 'general')
            recovery_strategy = error_data.get('recovery_strategy', 'log_only')
        
        logger.error(f"IB Error {error_code} ({category}): {error_string} (Recovery: {recovery_strategy})")
        
        # Handle errors based on category
        if category == 'connection':
            self._handle_connection_error(error_code, error_string)
        elif category == 'market_data':
            self._handle_market_data_error(error_code, error_string)
        elif category == 'order':
            self._handle_order_error(error_code, error_string)
        else:
            # General error handling
            logger.warning(f"Unhandled error category: {category}")
    
    def _handle_order_error(self, error_code: int, error_string: str):
        """Handle order-related errors."""
        logger.warning(f"Order error {error_code}: {error_string}")
        
        # Track order errors for circuit breaker
        if not hasattr(self, '_order_error_count'):
            self._order_error_count = 0
        if not hasattr(self, '_order_circuit_breaker_activated'):
            self._order_circuit_breaker_activated = False
        
        self._order_error_count += 1
        
        if self._order_error_count >= 3 and not self._order_circuit_breaker_activated:
            logger.error("Order error threshold reached, implementing circuit breaker")
            self._order_circuit_breaker_activated = True
            self.event_bus.emit('subscription.order_circuit_breaker_activated', {
                'error_count': self._order_error_count,
                'error_code': error_code,
                'timestamp': datetime.now().isoformat()
            }, priority=EventPriority.CRITICAL)
    
    def _handle_connection_error(self, error_code: int, error_string: str):
        """Handle connection-related errors."""
        logger.warning(f"Connection error {error_code}: {error_string}")
        # Connection errors will be handled by the main connection manager
        # We just need to wait for reconnection
    
    def _handle_market_data_error(self, error_code: int, error_string: str):
        """Handle market data subscription errors."""
        logger.warning(f"Market data error {error_code}: {error_string}")
        
        # Retry subscription based on error type
        if error_code in [10167, 10168, 10169]:  # Subscription limit errors
            logger.info("Subscription limit reached, will retry later")
            self._schedule_retry('market_data', error_code)
        elif error_code in [10182, 10183, 10184]:  # Invalid contract errors
            logger.error("Invalid contract specification")
            # Don't retry invalid contracts
        else:
            # Generic retry for other market data errors
            self._schedule_retry('market_data', error_code)
    
    def _start_subscription_process(self):
        """Start the subscription process after connection."""
        logger.info("Starting subscription process")
        self.state = SubscriptionState.SUBSCRIBING
        
        # Step 1: Request account data
        self._request_account_data()
        
        # Step 2: Subscribe to underlying
        self._subscribe_to_underlying()
    
    def _request_account_data(self):
        """Request account data including summary, positions, and open orders."""
        logger.info("Requesting account data")
        
        # Request account summary
        self.event_bus.emit('account.request_summary', {}, priority=EventPriority.HIGH)
        logger.debug("SUBSCRIPTION MANAGER: Emitted account.request_summary")
        
        # Request P&L data
        self.event_bus.emit('account.request_pnl', {}, priority=EventPriority.HIGH)
        logger.debug("SUBSCRIPTION MANAGER: Emitted account.request_pnl")
        
        # Request positions
        self.event_bus.emit('get_positions', {}, priority=EventPriority.HIGH)
        logger.debug("SUBSCRIPTION MANAGER: Emitted get_positions")
        
        # Request open orders
        self.event_bus.emit('get_open_orders', {}, priority=EventPriority.HIGH)
        logger.debug("SUBSCRIPTION MANAGER: Emitted get_open_orders")
        
        logger.info("Account data requests sent")

    def _subscribe_to_underlying(self):
        """Subscribe to the underlying symbol."""
        logger.info(f"Subscribing to underlying: {self.config.underlying_symbol}")
        
        subscription_data = {
            'contract': {
                'symbol': self.config.underlying_symbol,
                'secType': 'STK',
                'exchange': 'SMART',
                'currency': 'USD'
            }
        }
        
        self.event_bus.emit('market_data.subscribe', subscription_data, priority=EventPriority.HIGH)
        self.current_subscriptions['underlying'] = subscription_data
    
    def _on_market_data_subscribed(self, data: Dict[str, Any]):
        """Handle successful market data subscription."""
        try:
            contract = data.get('contract', {})
            symbol = contract.get('symbol', '')
            
            logger.info(f"✓ Market data subscribed: {symbol}")
            
            if symbol == self.config.underlying_symbol:
                # Underlying subscribed, check for currency conversion
                self._check_currency_conversion()
            elif 'currency' in data.get('contract', {}):
                # Currency conversion subscribed
                logger.info("✓ Currency conversion subscribed")
                self._request_options_chain()
        except Exception as e:
            logger.error(f"Error handling market data subscription: {e}")
    
    def _on_market_data_error(self, error_data: Dict[str, Any]):
        """Handle market data subscription errors."""
        contract = error_data.get('contract', {})
        symbol = contract.get('symbol', '')
        error_code = error_data.get('errorCode', 0)
        
        logger.error(f"Market data error for {symbol}: {error_data}")
        
        if symbol == self.config.underlying_symbol:
            self._retry_subscription('underlying', error_data)
        elif 'currency' in contract:
            self._retry_subscription('currency', error_data)
    
    def _check_currency_conversion(self):
        """Check if currency conversion subscription is needed."""
        if not self.account_currency:
            logger.info("Account currency not yet available, waiting...")
            return
        
        if self.account_currency == 'USD':
            logger.info("Account currency is USD, no conversion needed")
            self._request_options_chain()
            return
        
        # Determine underlying currency (assume USD for US stocks)
        underlying_currency = 'USD'  # Could be made configurable
        
        if self.account_currency != underlying_currency:
            logger.info(f"Subscribing to currency conversion: {underlying_currency}/{self.account_currency}")
            
            conversion_data = {
                'contract': {
                    'symbol': f"{underlying_currency}{self.account_currency}",
                    'secType': 'CASH',
                    'exchange': 'IDEALPRO',
                    'currency': self.account_currency
                }
            }
            
            self.event_bus.emit('market_data.subscribe', conversion_data, priority=EventPriority.NORMAL)
            self.current_subscriptions['currency'] = conversion_data
            
            # Emit forex update for GUI
            self.event_bus.emit('forex_update', {
                'pair1': f"{underlying_currency}/{self.account_currency}",
                'pair2': f"Rate: Loading..."
            })
        else:
            self._request_options_chain()
    
    def _request_options_chain(self):
        """Request options chain for the underlying symbol."""
        logger.info(f"Requesting options chain for {self.config.underlying_symbol}")
        
        chain_request = {
            'symbol': self.config.underlying_symbol,
            'secType': 'OPT',
            'exchange': 'SMART',
            'currency': 'USD'
        }
        
        self.event_bus.emit('options.request_chain', chain_request, priority=EventPriority.NORMAL)
    
    def _on_options_chain_update(self, data: Dict[str, Any]):
        """Handle options chain updates."""
        logger.info("✓ Options chain received")
        
        self.options_chain = data.get('options', [])
        logger.info(f"Received {len(self.options_chain)} options contracts")
        
        # Emit options chain update for GUI
        self.event_bus.emit('option_chain_update', {
            'options': self.options_chain,
            'underlying_symbol': self.config.underlying_symbol
        })
        
        # Select appropriate options based on current conditions
        self._select_and_subscribe_options()
    
    def _on_options_chain_error(self, error_data: Dict[str, Any]):
        """Handle options chain errors."""
        logger.error(f"Options chain error: {error_data}")
        self._retry_subscription('options_chain', error_data)
    
    def _select_expiration(self, is_before_noon: bool) -> Optional[str]:
        """Select expiration date based on time and availability."""
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        # Group options by expiration
        expirations = {}
        for option in self.options_chain:
            exp_date = option.get('expiration')
            if exp_date:
                if exp_date not in expirations:
                    expirations[exp_date] = []
                expirations[exp_date].append(option)
        
        if not expirations:
            return None
        
        # Sort expirations
        sorted_expirations = sorted(expirations.keys())
        
        # Select target expiration
        if is_before_noon:
            # Try today's expiration first
            target_date = today.strftime('%Y%m%d')
            if target_date in sorted_expirations:
                return target_date
        else:
            # Try tomorrow's expiration first
            target_date = tomorrow.strftime('%Y%m%d')
            if target_date in sorted_expirations:
                return target_date
        
        # Fallback to nearest expiration
        return sorted_expirations[0] if sorted_expirations else None
    
        def _select_strike_price(self, expiration: str) -> Optional[float]:
            """Select strike price by rounding underlying price to nearest integer."""
            if not self.underlying_price:
                return None

            # Round to nearest integer
            rounded_strike = round(self.underlying_price)

            # Check if this strike exists in the options chain for the given expiration
            expiration_options = [
                opt for opt in self.options_chain
                if opt.get('expiration') == expiration and opt.get('strike') == rounded_strike
            ]
            if expiration_options:
                logger.info(f"Selected rounded strike: {rounded_strike}")
                return rounded_strike
            else:
                # Fallback: find the closest available strike
                all_strikes = [
                    opt.get('strike') for opt in self.options_chain
                    if opt.get('expiration') == expiration and opt.get('strike') is not None
                ]
                if not all_strikes:
                    return None
                closest_strike = min(all_strikes, key=lambda x: abs(x - self.underlying_price))
                logger.info(f"Rounded strike not found, using closest: {closest_strike}")
                return closest_strike
    
    def _subscribe_to_options(self, expiration: str, strike: float):
        """Subscribe to call and put options for the selected expiration and strike."""
        logger.info(f"Subscribing to options: {expiration} {strike}")
        
        # Unsubscribe from current options if different
        self._unsubscribe_current_options()
        
        # Subscribe to call option
        call_data = {
            'contract': {
                'symbol': self.config.underlying_symbol,
                'secType': 'OPT',
                'exchange': 'SMART',
                'currency': 'USD',
                'expiration': expiration,
                'strike': strike,
                'right': 'C'
            }
        }
        
        put_data = {
            'contract': {
                'symbol': self.config.underlying_symbol,
                'secType': 'OPT',
                'exchange': 'SMART',
                'currency': 'USD',
                'expiration': expiration,
                'strike': strike,
                'right': 'P'
            }
        }
        
        self.event_bus.emit('market_data.subscribe', call_data, priority=EventPriority.NORMAL)
        self.event_bus.emit('market_data.subscribe', put_data, priority=EventPriority.NORMAL)
        
        self.current_subscriptions['call_option'] = call_data
        self.current_subscriptions['put_option'] = put_data
        
        logger.info("✓ Options subscriptions initiated")
    
    def _unsubscribe_current_options(self):
        """Unsubscribe from current options subscriptions."""
        for sub_type in ['call_option', 'put_option']:
            if sub_type in self.current_subscriptions:
                contract_data = self.current_subscriptions[sub_type]
                self.event_bus.emit('market_data.unsubscribe', contract_data, priority=EventPriority.NORMAL)
                logger.info(f"Unsubscribed from {sub_type}")
    
    def _on_account_summary_update(self, data: Dict[str, Any]):
        """Handle account summary updates to get account currency."""
        # Prevent infinite loops by checking if we've already processed this data
        current_net_liquidation = data.get('NetLiquidation', 0)
        
        # Only emit events if the data has actually changed
        if not hasattr(self, '_last_account_data') or self._last_account_data != data:
            # Emit account summary update for GUI (GUI expects this event name)
            self.event_bus.emit('account.summary_update', data)
            
            # Also emit account metrics update for backward compatibility
            self.event_bus.emit('account_metrics_update', data)
            
            # Track account balance for PnL calculations
            if hasattr(self, 'previous_net_liquidation'):
                if self.previous_net_liquidation > 0 and current_net_liquidation != self.previous_net_liquidation:
                    daily_pnl = current_net_liquidation - self.previous_net_liquidation
                    self.daily_pnl = daily_pnl
                    # Emit PnL update for GUI
                    self.event_bus.emit('account.pnl_update', {
                        'dailyPnL': daily_pnl,
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Store the last processed data to prevent duplicates
            self._last_account_data = data.copy()
        
        self.previous_net_liquidation = current_net_liquidation
        
        if not self.account_currency:
            # Extract currency from available funds
            available_funds = data.get('AvailableFunds', {})
            if isinstance(available_funds, dict):
                for currency, amount in available_funds.items():
                    if amount > 0:
                        self.account_currency = currency
                        logger.info(f"Account currency detected: {currency}")
                        break
            elif isinstance(available_funds, str):
                # Try to parse currency from string
                import re
                match = re.search(r'([A-Z]{3})', available_funds)
                if match:
                    self.account_currency = match.group(1)
                    logger.info(f"Account currency detected: {self.account_currency}")
            
            if self.account_currency and self.ib_connected:
                self._check_currency_conversion()
    
    def _broadcast_selected_options(self, expiration: str, strike: float):
        """Broadcast the selected strike and expiration for GUI filtering."""
        try:
            selection_data = {
                'expiration': expiration,
                'strike': strike,
                'underlying_symbol': self.config.underlying_symbol,
                'timestamp': datetime.now().isoformat()
            }
            
            # Emit the selection event for GUI to use as filter
            self.event_bus.emit('options.selection_update', selection_data)
            logger.info(f"Broadcasted options selection: {expiration} {strike}")
            
        except Exception as e:
            logger.error(f"Error broadcasting options selection: {e}")
    
    def _select_and_subscribe_options(self):
        """Select and subscribe to options with improved selection logic."""
        try:
            if not self.underlying_price:
                logger.warning("No underlying price available for options selection")
                return
            
            # Determine if it's before or after noon
            now = datetime.now(pytz.timezone(self.config.market_timezone))
            is_before_noon = now.hour < 12
            
            # Select expiration
            target_expiration = self._select_expiration(is_before_noon)
            if not target_expiration:
                logger.warning("Could not select expiration")
                return
            
            # Select strike price
            target_strike = self._select_strike_price(target_expiration)
            if not target_strike:
                logger.warning("Could not select strike price")
                return
            
            # Broadcast the selection for GUI filtering
            self._broadcast_selected_options(target_expiration, target_strike)
            
            # Subscribe to the selected options
            self._subscribe_to_options(target_expiration, target_strike)
            
        except Exception as e:
            logger.error(f"Error in options selection and subscription: {e}")
    
    def _subscribe_to_options(self, expiration: str, strike: float):
        """Subscribe to call and put options for the given expiration and strike."""
        try:
            # Unsubscribe from current options first
            self._unsubscribe_current_options()
            
            # Subscribe to call option
            call_contract = {
                'symbol': self.config.underlying_symbol,
                'secType': 'OPT',
                'exchange': 'SMART',
                'currency': 'USD',
                'expiration': expiration,
                'strike': strike,
                'right': 'C'
            }
            
            put_contract = {
                'symbol': self.config.underlying_symbol,
                'secType': 'OPT',
                'exchange': 'SMART',
                'currency': 'USD',
                'expiration': expiration,
                'strike': strike,
                'right': 'P'
            }
            
            # Emit subscription events
            self.event_bus.emit('market_data.subscribe', {'contract': call_contract})
            self.event_bus.emit('market_data.subscribe', {'contract': put_contract})
            
            # Track current subscriptions
            self.current_subscriptions['call_option'] = call_contract
            self.current_subscriptions['put_option'] = put_contract
            
            logger.info(f"Subscribing to options: {expiration} {strike}")
            
        except Exception as e:
            logger.error(f"Error subscribing to options: {e}")
    
    def _check_currency_conversion(self):
        """Check if currency conversion is needed and subscribe to forex."""
        try:
            if not self.account_currency or self.account_currency == 'USD':
                logger.info("No currency conversion needed (USD account)")
                return
            
            # Subscribe to USD/CAD forex for CAD accounts
            if self.account_currency == 'CAD':
                forex_contract = {
                    'symbol': 'USD',
                    'secType': 'CASH',
                    'exchange': 'IDEALPRO',
                    'currency': 'CAD'
                }
                
                self.event_bus.emit('market_data.subscribe', {'contract': forex_contract})
                logger.info("Subscribed to USD/CAD forex for currency conversion")
                
        except Exception as e:
            logger.error(f"Error setting up currency conversion: {e}")
    
    def _on_market_data_tick(self, data: Dict[str, Any]):
        """Handle market data ticks with improved underlying price tracking."""
        try:
            contract = data.get('contract', {})
            symbol = contract.get('symbol', '')
            sec_type = contract.get('secType', '')
            
            # Update underlying price for the configured symbol
            if symbol == self.config.underlying_symbol and sec_type == 'STK':
                last_price = data.get('last')
                if last_price and last_price > 0:
                    self.underlying_price = last_price
                    
                    # Emit underlying price update for GUI
                    self.event_bus.emit('underlying_price_update', {
                        'symbol': symbol,
                        'price': last_price,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    logger.debug(f"Underlying price update: ${last_price}")
                    
                    # Check if we need to reselect options
                    self._check_options_reselection()
            
            # Handle forex data for currency conversion
            elif sec_type == 'CASH' and symbol in ['USD', 'CAD']:
                last_price = data.get('last')
                if last_price and last_price > 0:
                    # Emit forex update for GUI
                    forex_data = {
                        'from_currency': 'USD',
                        'to_currency': 'CAD',
                        'rate': last_price,
                        'reciprocal_rate': 1.0 / last_price if last_price > 0 else 0,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.event_bus.emit('forex_update', forex_data)
                    logger.debug(f"Forex update: USD/CAD = {last_price}")
            
            # Handle options data
            elif sec_type == 'OPT':
                # Update options chain with current prices
                self._update_options_chain(data)
                
        except Exception as e:
            logger.error(f"Error handling market data tick: {e}")
    
    def _update_options_chain(self, tick_data: Dict[str, Any]):
        """Update options chain with current market data."""
        try:
            contract = tick_data.get('contract', {})
            symbol = contract.get('symbol', '')
            
            if symbol != self.config.underlying_symbol:
                return
            
            # Find the option in our chain and update its data
            for option in self.options_chain:
                if (option.get('expiration') == contract.get('expiration') and
                    option.get('strike') == contract.get('strike') and
                    option.get('right') == contract.get('right')):
                    
                    # Update option data
                    option.update({
                        'last': tick_data.get('last'),
                        'bid': tick_data.get('bid'),
                        'ask': tick_data.get('ask'),
                        'volume': tick_data.get('volume'),
                        'openInterest': tick_data.get('openInterest'),
                        'delta': tick_data.get('delta'),
                        'gamma': tick_data.get('gamma'),
                        'theta': tick_data.get('theta'),
                        'vega': tick_data.get('vega'),
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Emit updated options chain
                    self.event_bus.emit('option_chain_update', {
                        'options': self.options_chain,
                        'underlying_symbol': symbol
                    })
                    
                    break
                    
        except Exception as e:
            logger.error(f"Error updating options chain: {e}")
    
    def _check_options_reselection(self):
        """Check if options need to be reselected based on price changes."""
        try:
            if not self.underlying_price or not self.options_chain:
                return
            
            # Get current options
            current_call = self.current_subscriptions.get('call_option', {})
            current_put = self.current_subscriptions.get('put_option', {})
            
            if not current_call or not current_put:
                return
            
            current_strike = current_call.get('strike')
            if not current_strike:
                return
            
            # Check if current strike is still optimal
            now = datetime.now(pytz.timezone(self.config.market_timezone))
            is_before_noon = now.hour < 12
            
            target_expiration = self._select_expiration(is_before_noon)
            target_strike = self._select_strike_price(target_expiration) if target_expiration else None
            
            if target_strike and abs(target_strike - current_strike) > 0.01:
                logger.info(f"Strike price changed: {current_strike} -> {target_strike}")
                self._broadcast_selected_options(target_expiration, target_strike)
                self._subscribe_to_options(target_expiration, target_strike)
                
        except Exception as e:
            logger.error(f"Error checking options reselection: {e}")
    
    def _on_positions_update(self, data: Dict[str, Any]):
        """Handle position updates to track active contracts."""
        positions = data.get('positions', [])
        
        # Clear old active contracts
        self.active_contracts.clear()
        
        for position in positions:
            contract = position.get('contract', {})
            sec_type = contract.get('secType', '')
            
            # Only track options for the underlying
            if sec_type == 'OPT' and contract.get('symbol') == self.config.underlying_symbol:
                quantity = position.get('position', 0)
                if quantity != 0:  # Active position
                    active_contract = ActiveContract(
                        contract=contract,
                        order_id=position.get('orderId', 0),
                        timestamp=datetime.now()
                    )
                    self.active_contracts.append(active_contract)
                    logger.info(f"Active contract tracked: {contract}")
        
        # Ensure active contracts are subscribed
        self._subscribe_to_active_contracts()
        
        # Emit active contract update for GUI
        active_contracts_data = [
            {
                'symbol': ac.contract.get('symbol', ''),
                'secType': ac.contract.get('secType', ''),
                'expiration': ac.contract.get('expiration', ''),
                'strike': ac.contract.get('strike', ''),
                'right': ac.contract.get('right', ''),
                'is_active': ac.is_active
            }
            for ac in self.active_contracts if ac.is_active
        ]
        
        self.event_bus.emit('active_contract_update', {
            'contracts': active_contracts_data,
            'count': len(active_contracts_data)
        })
        
        # Also emit active contract status update for GUI
        self.event_bus.emit('active_contract_status_update', {
            'active_contracts': active_contracts_data
        })
    
    def _on_open_orders_update(self, data: Dict[str, Any]):
        """Handle open orders to track active contracts."""
        open_orders = data.get('open_orders', [])
        
        for order in open_orders:
            contract = order.get('contract', {})
            sec_type = contract.get('secType', '')
            
            # Only track options for the underlying
            if sec_type == 'OPT' and contract.get('symbol') == self.config.underlying_symbol:
                # Check if this contract is already tracked
                contract_id = self._get_contract_id(contract)
                existing = next((ac for ac in self.active_contracts 
                               if self._get_contract_id(ac.contract) == contract_id), None)
                
                if not existing:
                    active_contract = ActiveContract(
                        contract=contract,
                        order_id=order.get('orderId', 0),
                        timestamp=datetime.now()
                    )
                    self.active_contracts.append(active_contract)
                    logger.info(f"Active contract from open order: {contract}")
        
        # Ensure active contracts are subscribed
        self._subscribe_to_active_contracts()
        
        # Emit active contract update for GUI
        active_contracts_data = [
            {
                'symbol': ac.contract.get('symbol', ''),
                'secType': ac.contract.get('secType', ''),
                'expiration': ac.contract.get('expiration', ''),
                'strike': ac.contract.get('strike', ''),
                'right': ac.contract.get('right', ''),
                'is_active': ac.is_active
            }
            for ac in self.active_contracts if ac.is_active
        ]
        
        self.event_bus.emit('active_contract_update', {
            'contracts': active_contracts_data,
            'count': len(active_contracts_data)
        })
        
        # Also emit active contract status update for GUI
        self.event_bus.emit('active_contract_status_update', {
            'active_contracts': active_contracts_data
        })
    
    def _on_order_place(self, data: Dict[str, Any]):
        """Handle order placement to track new active contracts."""
        contract = data.get('contract', {})
        sec_type = contract.get('secType', '')
        
        if sec_type == 'OPT' and contract.get('symbol') == self.config.underlying_symbol:
            active_contract = ActiveContract(
                contract=contract,
                order_id=data.get('orderId', 0),
                timestamp=datetime.now()
            )
            self.active_contracts.append(active_contract)
            logger.info(f"New active contract from order: {contract}")
            
            # Subscribe to this contract
            self._subscribe_to_contract(contract)
            
            # Emit trade stats update for GUI
            self.event_bus.emit('trade_stats_update', {
                'new_order': True,
                'contract': contract,
                'order_id': data.get('orderId', 0)
            })
    
    def _on_order_fill(self, data: Dict[str, Any]):
        """Handle order fills to update active contract status."""
        contract = data.get('contract', {})
        sec_type = contract.get('secType', '')
        
        if sec_type == 'OPT' and contract.get('symbol') == self.config.underlying_symbol:
            # Check if this was a sell order that closed a position
            action = data.get('action', '').upper()
            if action == 'SELL':
                # Mark contract as inactive if position is closed
                contract_id = self._get_contract_id(contract)
                for active_contract in self.active_contracts:
                    if self._get_contract_id(active_contract.contract) == contract_id:
                        active_contract.is_active = False
                        logger.info(f"Active contract closed: {contract}")
                        break
    
    def _subscribe_to_active_contracts(self):
        """Subscribe to all active contracts."""
        for active_contract in self.active_contracts:
            if active_contract.is_active:
                self._subscribe_to_contract(active_contract.contract)
    
    def _subscribe_to_contract(self, contract: Dict[str, Any]):
        """Subscribe to a specific contract."""
        contract_id = self._get_contract_id(contract)
        
        # Check if already subscribed
        if contract_id in self.current_subscriptions:
            return
        
        subscription_data = {'contract': contract}
        self.event_bus.emit('market_data.subscribe', subscription_data, priority=EventPriority.NORMAL)
        self.current_subscriptions[contract_id] = subscription_data
        
        logger.info(f"Subscribed to active contract: {contract_id}")
    
    def _get_contract_id(self, contract: Dict[str, Any]) -> str:
        """Generate a unique contract identifier."""
        symbol = contract.get('symbol', '')
        sec_type = contract.get('secType', '')
        exchange = contract.get('exchange', '')
        currency = contract.get('currency', '')
        
        if sec_type == 'OPT':
            expiration = contract.get('expiration', '')
            strike = contract.get('strike', '')
            right = contract.get('right', '')
            return f"{symbol}_{sec_type}_{expiration}_{strike}_{right}"
        else:
            return f"{symbol}_{sec_type}_{exchange}_{currency}"
    
    def _retry_subscription(self, subscription_type: str, error_data: Dict[str, Any]):
        """Retry a failed subscription."""
        retry_count = self.retry_counts.get(subscription_type, 0)
        
        if retry_count >= self.config.retry_attempts:
            logger.error(f"Max retries reached for {subscription_type}")
            return
        
        current_time = time.time()
        last_retry = self.last_retry_time.get(subscription_type, 0)
        
        # Check if enough time has passed
        if current_time - last_retry < self.config.retry_delay:
            return
        
        logger.info(f"Retrying {subscription_type} subscription (attempt {retry_count + 1})")
        
        # Increment retry count first
        self.retry_counts[subscription_type] = retry_count + 1
        self.last_retry_time[subscription_type] = current_time
        
        # Retry based on subscription type
        if subscription_type == 'underlying':
            self._subscribe_to_underlying()
        elif subscription_type == 'currency':
            self._check_currency_conversion()
        elif subscription_type == 'options_chain':
            self._request_options_chain()
        elif subscription_type == 'market_data':
            # Generic market data retry
            pass
    
    def _schedule_retry(self, subscription_type: str, error_code: int):
        """Schedule a retry for a subscription."""
        # Implement exponential backoff based on error code
        base_delay = self.config.retry_delay
        
        if error_code in [10167, 10168, 10169]:  # Rate limit errors
            delay = base_delay * 2
        elif error_code in [10182, 10183, 10184]:  # Invalid contract
            delay = base_delay * 5
        else:
            delay = base_delay
        
        logger.info(f"Scheduling retry for {subscription_type} in {delay} seconds")
        
        def delayed_retry():
            time.sleep(delay)
            if self.ib_connected:
                self._retry_subscription(subscription_type, {'errorCode': error_code})
        
        retry_thread = threading.Thread(target=delayed_retry, daemon=True)
        retry_thread.start()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current subscription manager status."""
        return {
            'state': self.state.value,
            'ib_connected': self.ib_connected,
            'startup_complete': self.startup_complete,
            'underlying_price': self.underlying_price,
            'account_currency': self.account_currency,
            'active_contracts_count': len([ac for ac in self.active_contracts if ac.is_active]),
            'current_subscriptions_count': len(self.current_subscriptions),
            'options_chain_count': len(self.options_chain)
        }
