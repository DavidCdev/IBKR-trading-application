"""
IBConnection Module - Interactive Brokers API Integration (Refactored)
====================================================================

Production-ready, event-driven interface to Interactive Brokers using ib_async.

Key Features:
- Pure async/await architecture with event-driven design
- Active trade detection and bracket order management
- Real-time market data for stocks, options, and forex
- Comprehensive account data and transaction tracking
- Automatic reconnection and configuration management
- **NEW: Limit sell orders automatically convert to market orders after a 10-second timeout.**
- **UPDATED: Standardized async patterns with proper error handling and IB API compliance**

Usage via Event Bus:
- Connect: event_bus.emit('ib.connect')
- Place Order: event_bus.emit('order.place', order_data)
- Subscribe Data: event_bus.emit('market_data.subscribe', contract_data)
- Request Account: event_bus.emit('account.request_summary')

Configuration Required:
- connection: host, port, client_id, account
- trading: underlying_symbol
- options_filter: transaction filtering

IMPORTANT UPDATES:
- Standardized on async patterns throughout
- Added 1-second disconnect delay for data integrity
- Updated error handling to match IB API best practices
- Fixed contract qualification to handle None returns
- Improved bracket order sequencing
- Enhanced market data subscription management
- Updated error categorization with accurate IB error codes
"""

"""
IBConnection Module - Interactive Brokers API Integration (Refactored)
====================================================================

Production-ready, event-driven interface to Interactive Brokers using ib_async.

Key Features:
- Pure async/await architecture with event-driven design
- Active trade detection and bracket order management
- Real-time market data for stocks, options, and forex
- Comprehensive account data and transaction tracking
- Automatic reconnection and configuration management
- **NEW: Limit sell orders automatically convert to market orders after a 10-second timeout.**
- **UPDATED: Standardized async patterns with proper error handling and IB API compliance**

Usage via Event Bus:
- Connect: event_bus.emit('ib.connect')
- Place Order: event_bus.emit('order.place', order_data)
- Subscribe Data: event_bus.emit('market_data.subscribe', contract_data)
- Request Account: event_bus.emit('account.request_summary')

Configuration Required:
- connection: host, port, client_id, account
- trading: underlying_symbol
- options_filter: transaction filtering

IMPORTANT UPDATES:
- Standardized on async patterns throughout
- Added 1-second disconnect delay for data integrity
- Updated error handling to match IB API best practices
- Fixed contract qualification to handle None returns
- Improved bracket order sequencing
- Enhanced market data subscription management
- Updated error categorization with accurate IB error codes
"""

import asyncio
import logging
import time
from datetime import date, timedelta, datetime
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from functools import wraps
from ib_async import IB, Contract, Order, Trade, Ticker, Stock, Option, Forex
from ib_async import MarketOrder, LimitOrder, StopOrder, util, ExecutionFilter
from ib_async.objects import Fill, CommissionReport, PnL, AccountValue
from logger import get_logger
from enhanced_logging import log_connection_state, log_performance
from event_bus import EventBus, EventPriority
from config_manager import ConfigManager

logger = get_logger('IB_CONNECTION')

# === DECORATORS ===

def require_connection(error_event: str = 'ib.error'):
    """
    Decorator to ensure IB connection before method execution.
    
    Usage: @require_connection('custom.error.event')
    
    Automatically checks self._connected and emits error if not connected.
    Eliminates 12+ repetitive connection checks throughout the codebase.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not self._connected:
                error_msg = f"Not connected - cannot execute {func.__name__}"
                logger.error(error_msg)
                self.event_bus.emit(error_event, {'message': error_msg})
                return None
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator

def handle_errors(success_event: Optional[str] = None, error_event: str = 'ib.error'):
    """
    Decorator for standardized error handling and event emission.
    
    Usage: @handle_errors('success.event', 'error.event')
    
    Automatically wraps methods in try/catch, logs errors, and emits events.
    Eliminates 30+ repetitive error handling blocks throughout the codebase.
    If success_event is provided, result is automatically published on success.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                result = await func(self, *args, **kwargs)
                if success_event and result is not None:
                    self.event_bus.emit(success_event, result)
                    logger.debug(f"IB CONNECTION: Emitted {success_event} with result: {result}")
                return result
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {e}"
                logger.error(error_msg, exc_info=True)
                self.event_bus.emit(error_event, {'message': error_msg})
                return None
        return wrapper
    return decorator

# === DATA CLASSES ===

@dataclass
class ActiveContract:
    """
    Enhanced position tracking with real-time data.
    
    Tracks complete position state including:
    - Real-time prices and P&L calculation
    - Bracket order relationships for risk management
    - Entry conditions and timestamps
    """
    contract: Contract
    quantity: int
    entry_price: float
    current_price: Optional[float] = None
    parent_order_id: Optional[int] = None
    stop_loss_order_id: Optional[int] = None
    take_profit_order_id: Optional[int] = None
    entry_time: Optional[datetime] = field(default_factory=datetime.now)
    is_active: bool = True

    @property
    def unrealized_pnl(self) -> Optional[float]:
        """Calculates unrealized P&L on demand."""
        if self.current_price is not None and self.entry_price is not None:
            price_diff = self.current_price - self.entry_price
            multiplier = 100 if self.contract.secType == 'OPT' else 1
            return price_diff * self.quantity * multiplier
        return 0.0

# === CONTEXT MANAGER ===

class IBConnectionContext:
    """Context manager for IB connection lifecycle with comprehensive cleanup."""
    
    def __init__(self, ib_connection):
        self.ib_connection = ib_connection
        self._entered = False
    
    async def __aenter__(self):
        """Establish connection and return the connection manager."""
        try:
            await self.ib_connection._handle_connect()
            self._entered = True
            logger.info("IB connection context entered successfully")
            return self.ib_connection
        except Exception as e:
            logger.error(f"Failed to enter IB connection context: {e}")
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure proper cleanup of all resources."""
        if not self._entered:
            return
        
        logger.info("Exiting IB connection context with cleanup")
        
        try:
            # Comprehensive shutdown sequence
            await self.ib_connection.shutdown_async()
            await self.ib_connection.cleanup_all_async_tasks()
            
            # Verify clean shutdown
            if self.ib_connection.verify_clean_shutdown():
                logger.info("IB connection context exited cleanly")
            else:
                logger.warning("IB connection context exited with issues")
                
        except Exception as e:
            logger.error(f"Error during IB connection context cleanup: {e}")
            # Force cleanup as fallback
            try:
                if hasattr(self.ib_connection, 'ib') and self.ib_connection.ib:
                    self.ib_connection.ib.disconnect()
            except Exception:
                pass

# === MAIN CLASS ===

class IBConnectionManager:
    """
    Enhanced IB connection manager with pure async architecture and event-driven design.
    
    ARCHITECTURE:
    ============
    - Pure async/await (no ThreadPoolExecutor)
    - Event-driven with comprehensive publish/subscribe
    - Decorator-based optimization for connection/error handling
    - Legacy compatibility through automatic event transformation
    - Active trade detection prevents overlapping positions
    
    INITIALIZATION:
    ==============
    manager = IBConnectionManager(event_bus, config_manager)
    # Automatically registers all event handlers and IB callbacks
    # Ready to receive commands via event_bus.emit()
    
    STATE MANAGEMENT:
    ================
    - _active_contracts: Live position tracking with P&L
    - _market_data_subscriptions: Real-time price feeds
    - _bracket_orders: Parent-child order relationships
    - _pending_orders: Order execution tracking
    - _active_trade_flag: Overlapping trade prevention
    """
    
    def __init__(self, event_bus: EventBus, config_manager: ConfigManager):
        """
        Initialize with comprehensive state management and event handling.
        
        Sets up:
        - IB connection management with auto-reconnection
        - Event handlers for all trading operations
        - Legacy compatibility mappings
        - Market data subscription tracking
        - Active position monitoring
        """
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.ib = IB()
        
        # Connection management
        self._connected = False
        self._connection_task: Optional[asyncio.Task] = None
        self._connection_params: Dict[str, Any] = {}
        
        # Trade and position management
        self._active_contracts: Dict[str, ActiveContract] = {}
        self._active_trade_flag: bool = False
        self._underlying_symbol: str = ""
        
        # Subscription management
        self._market_data_subscriptions: Dict[int, Dict[str, Any]] = {}
        self._bracket_orders: Dict[int, Dict[str, Optional[int]]] = {}
        self._pending_orders: Dict[int, Dict[str, Any]] = {}
        self._account_subscription_active = False
        self._pnl_subscription_active = False
        
        # Data storage for tests and event handling
        self.account_summary = []
        self.positions = []
        self.open_orders = []
        self.option_contracts = []
        self.last_order_id = None
        self.last_bracket_info = None
        self.current_spy_price = None
        
        # Central map for all primary event handlers
        self._handler_map = {
            'ib.connect': self._handle_connect,
            'ib.disconnect': self._handle_disconnect,
            'config_updated': self._handle_config_update,
            'account.request_summary': self._handle_request_account_summary,
            'account.request_pnl': self._handle_request_pnl,
            'account.request_transactions': self._handle_request_transactions,
            'options.request_chain': self._handle_request_option_chain,
            'get_positions': self._handle_get_positions,
            'get_open_orders': self._handle_get_open_orders,
            'market_data.subscribe': self._handle_subscribe_market_data,
            'market_data.unsubscribe': self._handle_unsubscribe_market_data,
            'order.place': self._handle_place_order,
            'sell_active_position': self._handle_sell_active_position,
            'cancel_order': self._handle_cancel_order,
            'get_active_contract_status': self._handle_get_active_contract_status,
            'test_event': self._handle_test_event,
            'market_data.request_historical': self._handle_request_historical_data,
            'fx.request_rate': self._handle_request_fx_rate,
        }

        # Event mapping for legacy compatibility - automatically transforms old events to new format
        self._event_mappings = {
            # Legacy -> New mappings (maintains backward compatibility)
            'subscribe_to_instrument': ('market_data.subscribe', self._transform_legacy_subscription),
            'unsubscribe_from_instrument': ('market_data.unsubscribe', self._transform_legacy_subscription),
            'buy_option': ('order.place', self._transform_option_order),
            'buy_stock': ('order.place', self._transform_stock_order),
            'sell_stock': ('order.place', self._transform_stock_sell_order),
        }
        
        self._register_ib_callbacks()
        self._subscribe_to_events()
        
        logger.info("IBConnectionManager Initialized")
    
    # === EVENT SYSTEM ===
    
    def _register_ib_callbacks(self):
        """Register IB event callbacks for real-time data streaming."""
        # Core connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error
        
        # Trading events
        self.ib.orderStatusEvent += self._on_order_status_update
        self.ib.execDetailsEvent += self._on_exec_details
        self.ib.commissionReportEvent += self._on_commission_report
        
        # Account events  
        self.ib.accountSummaryEvent += self._on_account_summary_update
        self.ib.pnlEvent += self._on_pnl_update
        
        logger.debug("IB event callbacks registered")
    
    def _subscribe_to_events(self):
        """
        Register comprehensive event bus handlers.
        
        Maps external event names to internal methods using a clean dictionary approach.
        Also registers legacy compatibility handlers that automatically transform data.
        """
        # Register all handlers in one loop from the central map
        for event, handler in self._handler_map.items():
            self.event_bus.on(event, handler)
        
        # Register legacy compatibility handlers - maintains backward compatibility
        for legacy_event, (new_event, transformer) in self._event_mappings.items():
            self.event_bus.on(legacy_event, self._create_legacy_handler(new_event, transformer))
        
        # Register new handlers for historical data and FX rate
        self.event_bus.on('market_data.request_historical', self._handle_request_historical_data)
        self.event_bus.on('fx.request_rate', self._handle_request_fx_rate)
        
        logger.debug("Event bus handlers registered")
    
    def _create_legacy_handler(self, new_event: str, transformer: Callable):
        """
        Create a legacy compatibility handler that transforms and forwards events.
        
        This optimization replaces 5+ separate legacy handlers with a single pattern.
        Automatically transforms old event formats to new standardized format.
        """
        async def legacy_handler(data: Dict):
            try:
                transformed_data = transformer(data)
                target_handler = self._handler_map.get(new_event)
                if target_handler:
                    await target_handler(transformed_data)
                else:
                    logger.warning(f"No handler found for transformed event: {new_event}")
            except Exception as e:
                logger.error(f"Error in legacy handler for {new_event}: {e}", exc_info=True)
        return legacy_handler
    
    # === LEGACY DATA TRANSFORMERS ===
    
    def _transform_legacy_subscription(self, data: Dict) -> Dict:
        """Transform legacy subscription data to new format."""
        # Ensure data is a dictionary
        if not isinstance(data, dict):
            data = {}
        return {
            'contract': data.get('contract', data),
            'con_id': data.get('con_id')
        }
    
    def _transform_option_order(self, data: Dict) -> Dict:
        """
        Transform legacy option order to new format.
        
        Handles the old buy_option event format and converts to the new
        standardized order.place format with proper contract specification.
        """
        contract_data = {
            'secType': 'OPT',
            'exchange': 'SMART',
            'currency': 'USD'
        }
        
        # Extract contract data from legacy format
        if 'contract' in data:
            contract = data['contract']
            if hasattr(contract, '__dict__'):
                # Handle object-style contract
                for field in ['symbol', 'strike', 'right', 'lastTradeDateOrContractMonth', 'localSymbol']:
                    if hasattr(contract, field):
                        contract_data[field] = getattr(contract, field)
            elif isinstance(contract, dict):
                # Handle dictionary-style contract
                for field in ['symbol', 'strike', 'right', 'lastTradeDateOrContractMonth', 'localSymbol']:
                    if field in contract:
                        contract_data[field] = contract[field]
        
        order_data = {
            'action': 'BUY',
            'orderType': 'LMT',
            'totalQuantity': data.get('quantity', 1),
            'lmtPrice': data.get('limit_price', 0)
        }
        
        result = {'contract': contract_data, 'order': order_data}
        
        # Add bracket data if present
        bracket_data = {}
        if data.get('stop_loss_price'):
            bracket_data['stop_loss_price'] = data['stop_loss_price']
        if data.get('take_profit_price'):
            bracket_data['profit_taker_price'] = data['take_profit_price']
        if bracket_data:
            result['bracket'] = bracket_data
            
        return result
    
    def _transform_stock_order(self, data: Dict) -> Dict:
        """Transform legacy stock buy order to new format."""
        return self._create_stock_order_data(data, 'BUY')
    
    def _transform_stock_sell_order(self, data: Dict) -> Dict:
        """Transform legacy stock sell order to new format."""
        return self._create_stock_order_data(data, 'SELL')
    
    def _create_stock_order_data(self, data: Dict, action: str) -> Dict:
        """
        Create standardized stock order data.
        
        Unified method for both BUY and SELL stock orders,
        eliminating duplication between buy_stock and sell_stock handlers.
        """
        contract_data = {
            'secType': 'STK',
            'exchange': 'SMART', 
            'currency': 'USD'
        }
        
        # Extract symbol from various legacy formats
        if 'contract' in data:
            if hasattr(data['contract'], 'symbol'):
                contract_data['symbol'] = data['contract'].symbol
            elif isinstance(data['contract'], dict) and 'symbol' in data['contract']:
                contract_data['symbol'] = data['contract']['symbol']
            else:
                contract_data['symbol'] = data.get('symbol', '')
        else:
            contract_data['symbol'] = data.get('symbol', '')
        
        order_data = {
            'action': action,
            'orderType': 'LMT',
            'totalQuantity': data.get('quantity', 100),
            'lmtPrice': data.get('limit_price', 0)
        }
        
        result = {'contract': contract_data, 'order': order_data}
        
        # Add bracket data if present
        bracket_data = {}
        if data.get('stop_loss_price'):
            bracket_data['stop_loss_price'] = data['stop_loss_price']
        if data.get('take_profit_price'):
            bracket_data['profit_taker_price'] = data['take_profit_price']
        if bracket_data:
            result['bracket'] = bracket_data
            
        return result
    
    # === CONNECTION MANAGEMENT ===
    
    @handle_errors()
    async def _handle_connect(self, data: Optional[Dict] = None):
        """
        Handle connection requests with enhanced async architecture.
        
        Usage: event_bus.emit('ib.connect', {'host': '127.0.0.1', 'port': 7497})
        
        Features:
        - Automatic configuration loading from config_manager
        - Prevents multiple concurrent connection attempts  
        - Starts background connection loop with auto-reconnection
        - Optional parameter override (useful for testing different connections)
        """
        logger.info("_handle_connect called - starting connection process")
        
        if self._connection_task and not self._connection_task.done():
            logger.warning("Connection process already running")
            return
        
        # Cancel any existing connection task
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"Error cancelling existing connection task: {e}")
        
        # Load configuration and apply any overrides
        self._load_connection_config()
        if data:
            self._connection_params.update(data)
        
        logger.info(f"Connection parameters: {self._connection_params}")
        
        # Start connection loop in background
        self._connection_task = asyncio.create_task(self._connection_loop())
        logger.info("Connection process initiated")
    
    @handle_errors()
    async def _handle_disconnect(self, data: Optional[Dict] = None):
        """Enhanced disconnection with comprehensive cleanup and proper timing."""
        logger.info("Initiating enhanced disconnection process")
        
        # Cancel connection task with proper error handling
        if self._connection_task and not self._connection_task.done():
            try:
                self._connection_task.cancel()
                await self._connection_task
            except asyncio.CancelledError:
                logger.info("Connection task cancelled successfully")
            except Exception as e:
                logger.warning(f"Error cancelling connection task: {e}")
            finally:
                self._connection_task = None
        
        # Cleanup subscriptions with better error handling
        try:
            await self._cleanup_market_data_subscriptions()
        except Exception as e:
            logger.warning(f"Error during market data cleanup: {e}")
        
        try:
            await self._cleanup_account_subscriptions()
        except Exception as e:
            logger.warning(f"Error during account subscription cleanup: {e}")
        
        # Enhanced disconnection with proper timing
        if hasattr(self, 'ib') and self.ib and self.ib.isConnected():
            try:
                # Add recommended delay before disconnecting to flush pending data
                logger.info("Waiting 1 second before disconnecting to flush pending data...")
                await asyncio.sleep(1)
                
                self.ib.disconnect()
                logger.info("Disconnect command sent successfully")
                
                # Wait a bit more to ensure disconnection completes
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error during disconnection: {e}")
        
        # Reset all state
        self._connected = False
        self._active_contracts.clear()
        self._bracket_orders.clear()
        self._pending_orders.clear()
        self._active_trade_flag = False
        self._account_subscription_active = False
        self._pnl_subscription_active = False
        
        logger.info("Enhanced disconnection completed")
        
        # Emit disconnected event with error handling
        try:
            self.event_bus.emit('ib.disconnected', {
                'timestamp': datetime.now().isoformat(),
                'cleanup_completed': True
            })
        except Exception as e:
            logger.warning(f"Could not emit ib.disconnected event: {e}")
    
    async def shutdown_async(self):
        """Asynchronous shutdown method for proper cleanup."""
        logger.info("Initiating asynchronous shutdown")
        
        # Cancel connection task if it exists
        if self._connection_task and not self._connection_task.done():
            try:
                logger.info("Cancelling connection task...")
                self._connection_task.cancel()
                # Wait for the task to actually cancel (with timeout)
                try:
                    await asyncio.wait_for(self._connection_task, timeout=5.0)
                    logger.info("Connection task cancelled successfully")
                except asyncio.TimeoutError:
                    logger.warning("Connection task cancellation timed out")
                except asyncio.CancelledError:
                    logger.info("Connection task was cancelled")
            except Exception as e:
                logger.warning(f"Error cancelling connection task during shutdown: {e}")
        
        # Cleanup subscriptions first
        try:
            await self._cleanup_market_data_subscriptions()
            await self._cleanup_account_subscriptions()
        except Exception as e:
            logger.warning(f"Error during subscription cleanup: {e}")
        
        # Disconnect IB connection with timeout
        if hasattr(self, 'ib') and self.ib and self.ib.isConnected():
            try:
                logger.info("Disconnecting IB connection...")
                # Use a timeout for the disconnect operation
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, self.ib.disconnect),
                    timeout=10.0
                )
                logger.info("IB connection disconnected successfully")
            except asyncio.TimeoutError:
                logger.warning("IB disconnect timed out")
            except Exception as e:
                logger.warning(f"Error disconnecting IB during shutdown: {e}")
        
        # Reset state
        self._connected = False
        self._connection_task = None
        logger.info("Asynchronous shutdown completed")
    
    async def cleanup_all_async_tasks(self):
        """Cancel all pending asyncio tasks related to this connection."""
        try:
            loop = asyncio.get_event_loop()
            tasks = asyncio.all_tasks(loop)
            
            # Filter tasks that are related to this connection
            connection_tasks = []
            for task in tasks:
                task_name = task.get_name() if hasattr(task, 'get_name') else str(task)
                if any(keyword in task_name.lower() for keyword in ['ib', 'connection', 'market', 'order']):
                    connection_tasks.append(task)
            
            if connection_tasks:
                logger.info(f"Cancelling {len(connection_tasks)} IB-related tasks")
                for task in connection_tasks:
                    if not task.done():
                        task.cancel()
                
                # Wait for all tasks to be cancelled
                await asyncio.gather(*connection_tasks, return_exceptions=True)
                logger.info("All IB-related tasks cancelled successfully")
        except Exception as e:
            logger.warning(f"Error during async task cleanup: {e}")
    
    def verify_clean_shutdown(self):
        """Verify that all IB connection components are properly shut down."""
        verification_results = {
            'connection_task': self._connection_task is None or self._connection_task.done(),
            'connected_state': not self._connected,
            'subscriptions_cleared': len(self._market_data_subscriptions) == 0,
            'active_contracts_cleared': len(self._active_contracts) == 0,
            'ib_disconnected': not hasattr(self, 'ib') or not self.ib or not self.ib.isConnected()
        }
        
        all_clean = all(verification_results.values())
        if not all_clean:
            logger.warning("Shutdown verification failed:")
            for component, clean in verification_results.items():
                if not clean:
                    logger.warning(f"  - {component}: not clean")
        
        return all_clean
    
    def shutdown(self):
        """Synchronous shutdown method for application cleanup."""
        logger.info("Initiating synchronous shutdown")
        
        # Create a new event loop for shutdown if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, can't run async code here
                logger.warning("Cannot run async shutdown in running event loop")
                # Just cancel the task and hope for the best
                if self._connection_task and not self._connection_task.done():
                    self._connection_task.cancel()
                
                # Force disconnect
                if hasattr(self, 'ib') and self.ib and self.ib.isConnected():
                    try:
                        self.ib.disconnect()
                        logger.info("IB connection force-disconnected")
                    except Exception as e:
                        logger.warning(f"Error force-disconnecting IB: {e}")
            else:
                # We can run async code
                loop.run_until_complete(self.shutdown_async())
                # Additional cleanup of all async tasks
                loop.run_until_complete(self.cleanup_all_async_tasks())
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            # Fallback: force disconnect
            if hasattr(self, 'ib') and self.ib and self.ib.isConnected():
                try:
                    self.ib.disconnect()
                except Exception:
                    pass
        
        # Reset state
        self._connected = False
        self._connection_task = None
        
        # Verify clean shutdown
        if self.verify_clean_shutdown():
            logger.info("Synchronous shutdown completed successfully")
        else:
            logger.warning("Synchronous shutdown completed with issues")
        
        logger.info("Synchronous shutdown completed")
    
    @handle_errors()
    async def _handle_config_update(self, data: Optional[Dict] = None):
        """Handle configuration updates with intelligent reconnection."""
        logger.info("Configuration update detected")
        
        old_connection_params = self._connection_params.copy()
        old_underlying = self._underlying_symbol
        
        self._load_connection_config()
        
        # Check for connection parameter changes
        connection_changed = any(
            old_connection_params.get(key) != self._connection_params.get(key)
            for key in ['host', 'port', 'client_id']
        )
        
        if connection_changed and self._connected:
            logger.info("Connection parameters changed, reconnecting...")
            await self._handle_disconnect()
            await asyncio.sleep(2)
            await self._handle_connect()
        
        # Update underlying symbol
        new_underlying = str(self.config_manager.get('trading', 'underlying_symbol', 'SPY') or 'SPY')
        if new_underlying != old_underlying:
            self._underlying_symbol = new_underlying
            logger.info(f"Underlying symbol updated: {old_underlying} -> {new_underlying}")
            if self._connected:
                await self._update_active_trade_status()
    
    def _load_connection_config(self):
        """Enhanced configuration loading with performance settings."""
        self._connection_params = {
            'host': str(self.config_manager.get('connection', 'host', '127.0.0.1') or '127.0.0.1'),
            'port': int(self.config_manager.get('connection', 'port', 7497) or 7497),
            'clientId': int(self.config_manager.get('connection', 'client_id', 1) or 1),
            'timeout': int(self.config_manager.get('connection', 'timeout', 30) or 30),
            'readonly': bool(self.config_manager.get('connection', 'readonly', False) or False),
        }
        
        # Load performance settings
        self._max_reconnect_attempts = int(self.config_manager.get('connection', 'max_reconnect_attempts', 10) or 10)
        self._reconnect_delay = int(self.config_manager.get('connection', 'reconnect_delay', 15) or 15)
        self._max_reconnect_delay = int(self.config_manager.get('connection', 'max_reconnect_delay', 300) or 300)
        
        account = self.config_manager.get('connection', 'account')
        if account:
            self._connection_params['account'] = str(account)
        
        self._underlying_symbol = str(self.config_manager.get('trading', 'underlying_symbol', 'SPY') or 'SPY')
        
        # Log performance settings
        logger.info(f"Loaded enhanced connection config: {self._connection_params}")
        logger.info(f"Performance settings: max_attempts={self._max_reconnect_attempts}, "
                   f"reconnect_delay={self._reconnect_delay}, max_delay={self._max_reconnect_delay}")
        
        # Validate critical settings
        if self._connection_params['port'] not in [7497, 4001]:
            logger.warning(f"Unusual port {self._connection_params['port']} - expected 7497 (TWS) or 4001 (Gateway)")
        
        if self._connection_params['readonly']:
            logger.info("Running in READONLY mode - no orders will be placed")
    
    async def _connection_loop(self):
        """Enhanced connection management with automatic reconnection and better error handling."""
        reconnect_delay = self._reconnect_delay
        max_reconnect_delay = self._max_reconnect_delay
        connection_attempts = 0
        max_attempts = self._max_reconnect_attempts
        connection_id = f"ib_conn_{int(time.time())}"
        
        logger.info("Enhanced connection loop started")
        
        while True:
            try:
                # Check for cancellation first
                if asyncio.current_task().cancelled():
                    logger.info("Connection loop cancelled")
                    break
                
                # Check if we're already connected
                if self.ib.isConnected():
                    logger.info("Connection is active, maintaining...")
                    try:
                        await asyncio.sleep(5)  # Check every 5 seconds
                    except asyncio.CancelledError:
                        logger.info("Connection maintenance sleep cancelled")
                        break
                    continue
                
                # Try to connect if not connected
                connection_attempts += 1
                logger.info(f"Connection attempt {connection_attempts}/{max_attempts} to {self._connection_params['host']}:{self._connection_params['port']}")
                
                # Log connection attempt
                log_connection_state(connection_id, "connecting", 
                                   self._connection_params['host'], 
                                   self._connection_params['port'],
                                   retry_count=connection_attempts - 1)
                
                # Try to connect immediately (don't wait for reconnect delay on first attempt)
                if connection_attempts == 1:
                    logger.info("Attempting initial connection...")
                else:
                    logger.info(f"Reconnecting in {reconnect_delay} seconds... (attempt {connection_attempts}/{max_attempts})")
                    try:
                        await asyncio.sleep(reconnect_delay)
                    except asyncio.CancelledError:
                        logger.info("Reconnection sleep cancelled")
                        break
                
                # Enhanced connection with timeout and error handling
                connection_start_time = time.time()
                try:
                    await self.ib.connectAsync(
                        host=self._connection_params['host'],
                        port=self._connection_params['port'],
                        clientId=self._connection_params['clientId'],
                        timeout=self._connection_params['timeout'],
                        readonly=self._connection_params['readonly']
                    )
                    logger.info("connectAsync completed successfully")
                except ConnectionRefusedError:
                    connection_time = (time.time() - connection_start_time) * 1000
                    logger.error("TWS/Gateway not running or API not enabled")
                    
                    # Log connection failure
                    log_connection_state(connection_id, "error", 
                                       self._connection_params['host'], 
                                       self._connection_params['port'],
                                       latency_ms=connection_time,
                                       error_code=10061,  # Connection refused
                                       error_message="TWS/Gateway not running or API not enabled",
                                       retry_count=connection_attempts - 1)
                    
                    # Log performance metrics
                    log_performance("IB_CONNECTION", "connect_failed", connection_time)
                    raise
                except Exception as e:
                    connection_time = (time.time() - connection_start_time) * 1000
                    logger.error(f"Connection error: {e}")
                    
                    # Log connection failure
                    log_connection_state(connection_id, "error", 
                                       self._connection_params['host'], 
                                       self._connection_params['port'],
                                       latency_ms=connection_time,
                                       error_message=str(e),
                                       retry_count=connection_attempts - 1)
                    
                    # Log performance metrics
                    log_performance("IB_CONNECTION", "connect_failed", connection_time)
                    raise
                
                if self.ib.isConnected():
                    connection_time = (time.time() - connection_start_time) * 1000
                    logger.info("Connection established successfully")
                    connection_attempts = 0  # Reset counter on success
                    reconnect_delay = self._reconnect_delay  # Reset delay
                    
                    # Enhanced connection verification
                    verification_start_time = time.time()
                    try:
                        # Test connection with a simple request
                        accounts = self.ib.managedAccounts()
                        verification_time = (time.time() - verification_start_time) * 1000
                        logger.info(f"Connection verified - Managed accounts: {accounts}")
                        
                        # Log successful connection
                        log_connection_state(connection_id, "connected", 
                                           self._connection_params['host'], 
                                           self._connection_params['port'],
                                           latency_ms=connection_time + verification_time)
                        
                        # Log performance metrics
                        log_performance("IB_CONNECTION", "connect", connection_time)
                        log_performance("IB_CONNECTION", "verification", verification_time)
                        
                        # Set connection state and emit connected event
                        self._connected = True
                        logger.info("✓ Emitting ib.connected event...")
                        self.event_bus.emit('ib.connected', {
                            'timestamp': datetime.now().isoformat(),
                            'accounts': accounts
                        }, priority=EventPriority.HIGH)
                        logger.info("✓ ib.connected event emitted")
                        
                        # Don't wait for disconnection - just keep the connection active
                        logger.info("Connection established and verified successfully")
                        # Continue the loop to maintain connection
                        continue
                    except Exception as e:
                        verification_time = (time.time() - verification_start_time) * 1000
                        logger.error(f"Connection verification failed: {e}")
                        
                        # Log verification failure
                        log_connection_state(connection_id, "error", 
                                           self._connection_params['host'], 
                                           self._connection_params['port'],
                                           latency_ms=connection_time + verification_time,
                                           error_message=f"Verification failed: {e}",
                                           retry_count=connection_attempts - 1)
                        
                        # Log performance metrics
                        log_performance("IB_CONNECTION", "verification_failed", verification_time)
                        raise
                else:
                    connection_time = (time.time() - connection_start_time) * 1000
                    raise ConnectionError("Connection verification failed")
                
                # Check if we've exceeded max attempts
                if connection_attempts >= max_attempts:
                    logger.error(f"Maximum connection attempts ({max_attempts}) reached. Stopping reconnection.")
                    
                    # Log max attempts reached
                    log_connection_state(connection_id, "error", 
                                       self._connection_params['host'], 
                                       self._connection_params['port'],
                                       error_message=f"Maximum connection attempts ({max_attempts}) reached",
                                       retry_count=connection_attempts)
                    
                    self.event_bus.emit('ib.error', {
                        'message': f'Maximum connection attempts reached after {max_attempts} attempts',
                        'connection_attempts': connection_attempts
                    })
                    break
            
            except asyncio.CancelledError:
                logger.info("Connection task cancelled")
                break
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.event_bus.emit('ib.error', {
                    'message': f'Connection error: {e}',
                    'connection_attempts': connection_attempts
                })
            
            # Exponential backoff with maximum delay
            if connection_attempts < max_attempts:
                logger.info(f"Reconnecting in {reconnect_delay} seconds... (attempt {connection_attempts + 1}/{max_attempts})")
                try:
                    await asyncio.sleep(reconnect_delay)
                except asyncio.CancelledError:
                    logger.info("Backoff sleep cancelled")
                    break
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
            else:
                break
    
    # === ACCOUNT DATA MANAGEMENT ===
    
    @require_connection('account.summary_error')
    @handle_errors('account.summary_subscribed', 'account.summary_error')
    async def _handle_request_account_summary(self, data: Optional[Dict] = None):
        """Handle account summary requests with streaming data."""
        action = data.get('action', 'subscribe') if data else 'subscribe'
        
        if action == 'subscribe' and not self._account_subscription_active:
            try:
                # Use the async version directly to avoid event loop conflicts
                await self.ib.reqAccountSummaryAsync()
                self._account_subscription_active = True
                logger.info("Subscribed to account summary")
            except Exception as e:
                logger.error(f"Error requesting account summary: {e}")
                self._account_subscription_active = False
                raise
        elif action == 'unsubscribe' and self._account_subscription_active:
            self._account_subscription_active = False
            logger.info("Account summary subscription will be cancelled on disconnect")
    
    @require_connection('account.pnl_error')
    @handle_errors('account.pnl_subscribed', 'account.pnl_error')
    async def _handle_request_pnl(self, data: Optional[Dict] = None):
        """Handle P&L streaming requests."""
        account = self._connection_params.get('account')
        if not account:
            accounts = self.ib.managedAccounts()
            if accounts:
                account = accounts[0]
            else:
                raise ValueError("No account available for P&L subscription")
        
        action = data.get('action', 'subscribe') if data else 'subscribe'
        
        if action == 'subscribe' and not self._pnl_subscription_active:
            # P&L methods are not async in ib_async
            self.ib.reqPnL(account, '')
            self._pnl_subscription_active = True
            logger.info(f"Subscribed to P&L for account: {account}")
        elif action == 'unsubscribe' and self._pnl_subscription_active:
            self.ib.cancelPnL(account, '')
            self._pnl_subscription_active = False
            logger.info("Unsubscribed from P&L")
    
    @require_connection('account.transactions_error')
    @handle_errors('account.transactions_update', 'account.transactions_error')
    async def _handle_request_transactions(self, data: Optional[Dict] = None):
        """Handle transaction history requests with underlying filtering."""
        underlying_symbol = str(
            data.get('symbol') if data else 
            self.config_manager.get('trading', 'underlying_symbol', 'SPY') or 'SPY'
        )
        
        logger.info(f"Requesting today's transactions for underlying: {underlying_symbol}")
        
        execution_filter = ExecutionFilter(symbol=underlying_symbol)
        fills = await self.ib.reqExecutionsAsync(execution_filter)
        
        # Filter and process transactions
        transactions = []
        for fill in fills:
            if (getattr(fill.contract, 'symbol', None) == underlying_symbol and
                getattr(fill.contract, 'secType', None) == 'OPT'):
                
                transaction_data = {
                    'exec_id': fill.execution.execId,
                    'symbol': fill.contract.symbol,
                    'sec_type': fill.contract.secType,
                    'local_symbol': getattr(fill.contract, 'localSymbol', ''),
                    'strike': getattr(fill.contract, 'strike', None),
                    'right': getattr(fill.contract, 'right', ''),
                    'expiry': getattr(fill.contract, 'lastTradeDateOrContractMonth', ''),
                    'time': fill.execution.time,
                    'side': fill.execution.side,
                    'shares': fill.execution.shares,
                    'price': fill.execution.price,
                    'order_id': fill.execution.orderId,
                    'exchange': fill.execution.exchange,
                    'cum_qty': fill.execution.cumQty,
                    'avg_price': fill.execution.avgPrice
                }
                
                if hasattr(fill, 'commissionReport') and fill.commissionReport:
                    transaction_data.update({
                        'commission': fill.commissionReport.commission,
                        'currency': fill.commissionReport.currency,
                        'realized_pnl': fill.commissionReport.realizedPNL
                    })
                
                transactions.append(transaction_data)
        
        logger.info(f"Found {len(transactions)} filtered transactions for {underlying_symbol}")
        return {
            'underlying_symbol': underlying_symbol,
            'transactions': transactions,
            'count': len(transactions)
        }
    
    # === OPTION CHAIN MANAGEMENT ===
    
    @require_connection('options.chain_error')
    @handle_errors('options.chain_update', 'options.chain_error')
    async def _handle_request_option_chain(self, data: Dict):
        """Handle option chain requests for zero-DTE, one-DTE, and nearest expiration."""
        symbol = data.get('underlying_symbol', self._underlying_symbol)
        option_type = data.get('option_type', 'BOTH').upper()
        
        logger.info(f"Requesting option chain for {symbol} ({option_type})")
        
        # Create and qualify underlying
        underlying = Stock(symbol, 'SMART', 'USD')
        await self.ib.qualifyContractsAsync(underlying)
        
        if not underlying.conId:
            raise ValueError(f"Could not qualify underlying contract for {symbol}")
        
        # Request option chain parameters
        chains = await self.ib.reqSecDefOptParamsAsync(
            underlyingSymbol=underlying.symbol,
            futFopExchange='',
            underlyingSecType=underlying.secType,
            underlyingConId=underlying.conId
        )
        
        if not chains:
            raise ValueError(f"No option chains found for {symbol}")
        
        # Find target expiration with fallback logic
        today_str = date.today().strftime('%Y%m%d')
        tomorrow_str = (date.today() + timedelta(days=1)).strftime('%Y%m%d')
        
        all_expirations = set()
        for chain in chains:
            all_expirations.update(chain.expirations)
        sorted_expirations = sorted(all_expirations)
        
        # Try multiple expiration strategies
        target_expiration = None
        expiration_type = None
        
        # Strategy 1: Try 1DTE first (more reliable than 0DTE)
        if tomorrow_str in sorted_expirations:
            target_expiration = tomorrow_str
            expiration_type = "1DTE"
        # Strategy 2: Try 0DTE if 1DTE not available
        elif today_str in sorted_expirations:
            target_expiration = today_str
            expiration_type = "0DTE"
        # Strategy 3: Find nearest available expiration
        else:
            target_expiration = next((exp for exp in sorted_expirations if exp > today_str), None)
            expiration_type = "NEAREST"
        
        if not target_expiration:
            # Final fallback: use the first available expiration
            if sorted_expirations:
                target_expiration = sorted_expirations[0]
                expiration_type = "FALLBACK"
            else:
                raise ValueError(f"No suitable expiration found for {symbol}")
        
        logger.info(f"Using {expiration_type} expiration: {target_expiration}")
        
        # Collect strikes and create contracts
        strikes = set()
        for chain in chains:
            if target_expiration in chain.expirations:
                strikes.update(chain.strikes)
        
        # Limit strikes to avoid overwhelming the system
        sorted_strikes = sorted(strikes)
        if len(sorted_strikes) > 20:  # Limit to 20 strikes max
            # Take strikes around current price (if available)
            current_price = None
            try:
                # Try to get current price for strike selection
                ticker = self.ib.reqMktData(underlying, '', False, False)
                await asyncio.sleep(1)  # Wait for price
                current_price = ticker.last if ticker.last and not util.isNan(ticker.last) else ticker.close
                self.ib.cancelMktData(underlying)
            except:
                pass
            
            if current_price:
                # Select strikes around current price
                mid_index = len(sorted_strikes) // 2
                start_index = max(0, mid_index - 10)
                end_index = min(len(sorted_strikes), mid_index + 10)
                selected_strikes = sorted_strikes[start_index:end_index]
            else:
                # Take first 20 strikes
                selected_strikes = sorted_strikes[:20]
        else:
            selected_strikes = sorted_strikes
        
        rights = []
        if option_type in ['C', 'BOTH']:
            rights.append('C')
        if option_type in ['P', 'BOTH']:
            rights.append('P')
        
        contracts = []
        for strike in selected_strikes:
            for right in rights:
                contract = Option(
                    symbol=symbol,
                    lastTradeDateOrContractMonth=target_expiration,
                    strike=strike,
                    right=right,
                    exchange='SMART',
                    currency='USD'
                )
                contracts.append(contract)
        
        # Qualify in smaller batches with better error handling
        qualified_contracts = []
        batch_size = 25  # Smaller batches
        for i in range(0, len(contracts), batch_size):
            batch = contracts[i:i + batch_size]
            try:
                qualified_batch = await self.ib.qualifyContractsAsync(*batch)
                # Filter out None results from failed qualifications
                qualified_batch = [c for c in qualified_batch if c is not None]
                qualified_contracts.extend(qualified_batch)
                await asyncio.sleep(0.2)  # Longer delay between batches
            except Exception as e:
                logger.warning(f"Error qualifying batch {i//batch_size}: {e}")
                # Continue with next batch instead of failing completely
        
        # Convert to response format
        contract_data = []
        for contract in qualified_contracts:
            if contract.conId:
                contract_info = {
                    'symbol': contract.symbol,
                    'strike': contract.strike,
                    'right': contract.right,
                    'expiry': contract.lastTradeDateOrContractMonth,
                    'local_symbol': contract.localSymbol,
                    'con_id': contract.conId,
                    'exchange': contract.exchange,
                    'currency': contract.currency
                }
                contract_data.append(contract_info)
        
        logger.info(f"Retrieved {len(contract_data)} qualified option contracts for {symbol}")
        
        # Store for tests
        self.option_contracts = contract_data
        
        return {
            'underlying_symbol': symbol,
            'expiration': target_expiration,
            'expiration_type': expiration_type,
            'option_type': option_type,
            'contracts': contract_data,
            'count': len(contract_data)
        }
    
    # === MARKET DATA MANAGEMENT ===
    
    @require_connection('market_data.error')
    @handle_errors('market_data.subscribed', 'market_data.error')
    async def _handle_subscribe_market_data(self, data: Dict):
        """
        Handle market data subscription with comprehensive contract support.
        
        Usage Examples:
        
        # Stock market data
        event_bus.emit('market_data.subscribe', {'symbol': 'AAPL', 'secType': 'STK'})
        
        # Option market data  
        event_bus.emit('market_data.subscribe', {
            'symbol': 'SPY', 'secType': 'OPT', 'strike': 580, 'right': 'P'
        })
        
        # Forex market data
        event_bus.emit('market_data.subscribe', {'symbol': 'EURUSD', 'secType': 'CASH'})
        
        Features:
        - Automatic contract qualification and validation
        - Deduplication: prevents double subscriptions  
        - Real-time tick streaming via _on_market_data_tick()
        - Supports stocks, options, forex, and other instruments
        """
        # Create contract from provided data
        # Ensure data is a dictionary before calling .get()
        if not isinstance(data, dict):
            data = {}
        contract = self._create_contract_from_data(data.get('contract', data))
        if not contract:
            raise ValueError(f"Could not create contract from data: {data}")
        
        # Qualify with IB to get complete contract details
        qualified_contracts = await self.ib.qualifyContractsAsync(contract)
        if not qualified_contracts or qualified_contracts[0] is None:
            raise ValueError(f"Could not qualify contract: {contract}")
        
        qualified_contract = qualified_contracts[0]
        con_id = qualified_contract.conId
        
        # Check for existing subscription (deduplication)
        if con_id in self._market_data_subscriptions:
            logger.info(f"Already subscribed to market data for {qualified_contract.localSymbol}")
            return
        
        # Subscribe to market data stream
        ticker = self.ib.reqMktData(qualified_contract, '', False, False)
        
        # Store subscription details for management
        self._market_data_subscriptions[con_id] = {
            'contract': qualified_contract,
            'ticker': ticker,
            'subscription_time': datetime.now()
        }
        
        # Connect tick event handler for real-time updates
        ticker.updateEvent.connect(lambda t=ticker: self._on_market_data_tick(t))
        
        logger.info(f"Subscribed to market data for {qualified_contract.localSymbol}")
        return {
            'contract': util.tree(qualified_contract),
            'con_id': con_id
        }
    
    @require_connection()
    @handle_errors('market_data.unsubscribed')
    async def _handle_unsubscribe_market_data(self, data: Dict):
        """Handle market data unsubscription."""
        con_id = data.get('con_id')
        if not con_id and 'contract' in data:
            contract = self._create_contract_from_data(data['contract'])
            if contract:
                qualified = await self.ib.qualifyContractsAsync(contract)
                if qualified:
                    con_id = qualified[0].conId
        
        if not con_id or con_id not in self._market_data_subscriptions:
            logger.warning(f"Not subscribed to market data for con_id: {con_id}")
            return
        
        subscription = self._market_data_subscriptions[con_id]
        contract = subscription['contract']
        
        success = self.ib.cancelMktData(contract)
        if not success:
            logger.warning(f"Failed to cancel market data for {contract.localSymbol}")
        else:
            logger.info(f"Successfully unsubscribed from market data for {contract.localSymbol}")
        
        del self._market_data_subscriptions[con_id]
        return {
            'con_id': con_id,
            'contract': util.tree(contract)
        }
    
    # === ORDER MANAGEMENT ===
    
    @require_connection('order.rejected')
    @handle_errors(error_event='order.rejected')
    async def _handle_place_order(self, data: Dict):
        """
        Enhanced order placement with bracket support and trade protection.
        
        Usage Examples:
        
        # Simple Stock Order (Legacy Format)
        event_bus.emit('order.place', {
            'symbol': 'AAPL', 'action': 'BUY', 'orderType': 'LMT', 
            'totalQuantity': 100, 'lmtPrice': 150.0
        })
        
        # Simple Stock Order (New Format)
        event_bus.emit('order.place', {
            'contract': {'symbol': 'AAPL', 'secType': 'STK'},
            'order': {'action': 'BUY', 'orderType': 'LMT', 'totalQuantity': 100, 'lmtPrice': 150.0}
        })
        
        # Option with Bracket Orders
        event_bus.emit('order.place', {
            'contract': {'symbol': 'SPY', 'secType': 'OPT', 'strike': 580, 'right': 'P'},
            'order': {'action': 'BUY', 'orderType': 'LMT', 'totalQuantity': 1, 'lmtPrice': 4.0},
            'bracket': {'stop_loss_price': 2.0, 'profit_taker_price': 6.0}
        })
        
        Features:
        - Automatic contract qualification with IB
        - Active trade protection prevents overlapping positions
        - Bracket order support with proper IB transmit sequencing
        - Comprehensive order tracking and error handling
        - Backward compatibility with legacy data formats
        """
        # Record order start for delay monitoring
        order_id = f"order_{int(time.time() * 1000)}"
        if hasattr(self.event_bus, '_order_delay_monitor'):
            self.event_bus._order_delay_monitor.record_order_start(order_id)
        
        # Handle both legacy and new data formats
        if 'contract' in data and 'order' in data:
            # New format
            contract_data = data.get('contract', {})
            order_data = data.get('order', {})
            bracket_data = data.get('bracket')
        else:
            # Legacy format - transform to new format
            contract_data, order_data, bracket_data = self._transform_legacy_order_data(data)
        
        # Create and qualify contract with IB
        contract = self._create_contract_from_data(contract_data)
        if not contract:
            raise ValueError("Could not create contract from data")
        
        try:
            qualified_contracts = await self.ib.qualifyContractsAsync(contract)
            if not qualified_contracts or qualified_contracts[0] is None:
                raise ValueError("Could not qualify contract")
            
            qualified_contract = qualified_contracts[0]
            logger.info(f"Successfully qualified contract: {qualified_contract.localSymbol}")
            
        except Exception as e:
            logger.error(f"Contract qualification failed: {e}")
            raise ValueError(f"Could not qualify contract: {e}")
        
        # Active trade protection: prevent overlapping BUY orders for same underlying options
        if (order_data.get('action', '').upper() == 'BUY' and
            getattr(qualified_contract, 'symbol', None) == getattr(self, '_underlying_symbol', None) and
            getattr(qualified_contract, 'secType', None) == 'OPT'):
            
            if getattr(self, '_active_trade_flag', False):
                raise ValueError(f'Active trade exists for {qualified_contract.symbol}')
        
        # Create IB order object from provided parameters
        main_order = Order()
        for key, value in order_data.items():
            if hasattr(main_order, key):
                setattr(main_order, key, value)
        
        # Place order (bracket vs simple)
        if bracket_data:
            await self._place_bracket_order(qualified_contract, main_order, bracket_data)
        else:
            trade = self.ib.placeOrder(qualified_contract, main_order)
            logger.info(f"Placed simple order: {qualified_contract.localSymbol}")
            
            # Store order ID for tests
            self.last_order_id = main_order.orderId
            
            # Track the order for monitoring
            if hasattr(self, '_pending_orders'):
                self._pending_orders[main_order.orderId] = {
                    'contract': qualified_contract,
                    'order': main_order,
                    'trade': trade,
                    'type': 'simple'
                }
        
        # Update active trade status after placing order
        await self._update_active_trade_status()
    
    async def _place_bracket_order(self, contract: Contract, parent_order: Order, bracket_data: Dict):
        """
        Place bracket order with proper transmit sequencing.
        
        IB Bracket Order Pattern:
        1. Parent order: transmit=False (dont send yet)
        2. Child orders: proper parentId linkage  
        3. Last child: transmit=True (sends entire bracket)
        
        This ensures all orders are linked before transmission,
        preventing partial fills or orphaned child orders.
        
        Parameters:
        - profit_taker_price: Limit order to take profits
        - stop_loss_price: Stop order for risk management
        """
        profit_price = bracket_data.get('profit_taker_price')
        stop_price = bracket_data.get('stop_loss_price')
        
        if not profit_price and not stop_price:
            raise ValueError("Bracket order requires at least profit_taker_price or stop_loss_price")
        
        # Step 1: Set parent to not transmit (IB requirement)
        parent_order.transmit = False
        opposite_action = 'SELL' if parent_order.action.upper() == 'BUY' else 'BUY'
        
        # Place parent order (not transmitted yet)
        parent_trade = self.ib.placeOrder(contract, parent_order)
        
        self._pending_orders[parent_order.orderId] = {
            'contract': contract,
            'order': parent_order,
            'trade': parent_trade,
            'type': 'bracket_parent'
        }
        
        bracket_info = {}
        orders_to_place = []
        
        # Create child orders with proper sequencing
        if profit_price:
            profit_order = LimitOrder(
                action=opposite_action,
                totalQuantity=parent_order.totalQuantity,
                lmtPrice=profit_price,
                parentId=parent_order.orderId,
                transmit=False  # Don't transmit yet
            )
            orders_to_place.append(('profit_taker', profit_order))
            bracket_info['take_profit_id'] = profit_order.orderId
        
        if stop_price:
            stop_order = StopOrder(
                action=opposite_action,
                totalQuantity=parent_order.totalQuantity,
                stopPrice=stop_price,
                parentId=parent_order.orderId,
                transmit=False  # Don't transmit yet
            )
            orders_to_place.append(('stop_loss', stop_order))
            bracket_info['stop_loss_id'] = stop_order.orderId
        
        # Place child orders first
        for order_type, child_order in orders_to_place:
            child_trade = self.ib.placeOrder(contract, child_order)
            
            self._pending_orders[child_order.orderId] = {
                'contract': contract,
                'order': child_order,
                'trade': child_trade,
                'type': f'bracket_{order_type}',
                'parent_id': parent_order.orderId
            }
        
        # Now set the last child order to transmit (triggers entire bracket)
        if orders_to_place:
            last_order = orders_to_place[-1][1]
            last_order.transmit = True
            # Update the order in IB
            self.ib.placeOrder(contract, last_order)
        
        self._bracket_orders[parent_order.orderId] = bracket_info
        
        # Store bracket info for tests
        self.last_bracket_info = {
            'parent_id': parent_order.orderId,
            'bracket_info': bracket_info,
            'contract': contract.localSymbol,
            'stop_loss_id': bracket_info.get('stop_loss_id'),
            'take_profit_id': bracket_info.get('take_profit_id')
        }
        
        logger.info(f"Placed bracket order for {contract.localSymbol}")
        logger.info(f"Parent ID: {parent_order.orderId}, Bracket info: {bracket_info}")
    
    @require_connection()
    @handle_errors()
    async def _handle_sell_active_position(self, data: Dict):
        """
        Enhanced active position selling with comprehensive cleanup and timeout logic.
        """
        symbol = data.get('symbol', '')
        quantity = data.get('totalQuantity', 0)
        limit_price = data.get('lmtPrice', 0)
        
        if not symbol or quantity <= 0 or limit_price <= 0:
            raise ValueError("Invalid sell order data")
        
        logger.info(f"Selling position: {quantity} of {symbol} @ ${limit_price}")
        
        # Cancel any existing bracket orders for this symbol
        await self._cancel_bracket_orders_for_symbol(symbol)
        
        # Create contract for the sell order
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'
        
        # Place the primary limit sell order
        sell_order = LimitOrder(
            action='SELL',
            totalQuantity=quantity,
            lmtPrice=limit_price
        )
        
        sell_trade = self.ib.placeOrder(contract, sell_order)
        
        # Store order ID for tests
        self.last_order_id = sell_order.orderId
        
        self._pending_orders[sell_order.orderId] = {
            'contract': contract,
            'order': sell_order,
            'trade': sell_trade,
            'type': 'position_exit'
        }
        
        logger.info(f"Successfully placed sell order {sell_order.orderId} for {symbol}.")
        return True

    async def _chase_sell_order(self, order_id: int, contract: Contract):
        """
        After a timeout, checks a sell order. If not fully filled, it cancels
        the limit order and replaces it with a market order for the remaining
        quantity to ensure the position is closed.
        """
        await asyncio.sleep(10)

        try:
            # First, find the original order in open trades
            original_trade = next((t for t in self.ib.openTrades() if t.order.orderId == order_id), None)

            if not original_trade:
                logger.info(f"Chaser: Order {order_id} is no longer open. Assumed filled or cancelled.")
                return

            # If the order is still open, check current position size to prevent overselling
            # This is the most reliable source of truth
            current_position = 0
            for pos in self.ib.positions():
                if pos.contract.conId == contract.conId:
                    current_position = pos.position
                    break
            
            if current_position == 0:
                logger.info(f"Chaser: Position for {contract.localSymbol} is already 0. No action needed.")
                if original_trade.order.permId: # Check if order is still cancellable
                    self.ib.cancelOrder(original_trade.order)
                return

            # If we are here, the order is open and we still have a position
            remaining_to_sell = abs(current_position)
            logger.warning(f"Chaser: Limit sell order {order_id} timed out. {remaining_to_sell} shares remaining.")

            # Cancel the original limit order
            logger.info(f"Chaser: Cancelling limit order {order_id}.")
            self.ib.cancelOrder(original_trade.order)
            await asyncio.sleep(0.5) # Give cancellation a moment to process

            # Place a market order for the remaining shares
            logger.info(f"Chaser: Placing market sell for {remaining_to_sell} shares of {contract.localSymbol}.")
            market_sell_order = MarketOrder(action='SELL', totalQuantity=remaining_to_sell)
            self.ib.placeOrder(contract, market_sell_order)

            self.event_bus.emit('order.chased', {
                'original_order_id': order_id,
                'new_order_type': 'MKT',
                'quantity': remaining_to_sell,
                'contract': util.tree(contract)
            })

        except Exception as e:
            logger.error(f"Error in chaser task for order {order_id}: {e}", exc_info=True)

    @require_connection()
    @handle_errors()
    async def _handle_cancel_order(self, data: Dict):
        """Enhanced order cancellation handler."""
        order_id = data.get('order_id')
        if not order_id:
            raise ValueError("No order_id provided for cancellation")
        
        open_trades = self.ib.openTrades()
        
        for trade in open_trades:
            if (hasattr(trade, 'order') and
                hasattr(trade.order, 'orderId') and
                trade.order.orderId == order_id):
                
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order: {order_id}")
                
                if order_id in self._pending_orders:
                    del self._pending_orders[order_id]
                
                return True
        
        logger.warning(f"Order {order_id} not found in open orders")
        return False
    
    async def _cancel_bracket_orders_for_position(self, active_contract: ActiveContract):
        """Cancel bracket orders associated with a position."""
        orders_to_cancel = []
        
        # Method 1: Try to get order IDs from active contract
        if active_contract.stop_loss_order_id:
            orders_to_cancel.append(active_contract.stop_loss_order_id)
        if active_contract.take_profit_order_id:
            orders_to_cancel.append(active_contract.take_profit_order_id)
        
        # Method 2: If no order IDs in active contract, try to find bracket orders by parent ID
        if not orders_to_cancel and active_contract.parent_order_id:
            bracket_info = self._bracket_orders.get(active_contract.parent_order_id, {})
            if bracket_info:
                stop_loss_id = bracket_info.get('stop_loss_id')
                take_profit_id = bracket_info.get('take_profit_id')
                if stop_loss_id:
                    orders_to_cancel.append(stop_loss_id)
                if take_profit_id:
                    orders_to_cancel.append(take_profit_id)
        
        # Method 3: Find all bracket orders for this symbol
        if not orders_to_cancel:
            open_trades = self.ib.openTrades()
            for trade in open_trades:
                order = trade.order
                contract = trade.contract
                
                # Check if this is a bracket order for the same symbol
                if (hasattr(order, 'parentId') and order.parentId and
                    hasattr(contract, 'symbol') and contract.symbol == active_contract.contract.symbol):
                    orders_to_cancel.append(order.orderId)
                    logger.info(f"Found bracket order to cancel: {order.orderId} (parent: {order.parentId})")
        
        # Cancel the orders
        open_trades = self.ib.openTrades()
        cancelled_count = 0
        
        for order_id in orders_to_cancel:
            for trade in open_trades:
                if (hasattr(trade, 'order') and
                    hasattr(trade.order, 'orderId') and
                    trade.order.orderId == order_id):
                    try:
                        self.ib.cancelOrder(trade.order)
                        logger.info(f"Cancelled bracket order: {order_id}")
                        cancelled_count += 1
                        await asyncio.sleep(0.5)  # Small delay between cancellations
                    except Exception as e:
                        logger.warning(f"Error cancelling order {order_id}: {e}")
                    break
        
        # Clean up tracking
        if active_contract.parent_order_id and active_contract.parent_order_id in self._bracket_orders:
            del self._bracket_orders[active_contract.parent_order_id]
            logger.info(f"Cleaned up bracket order tracking for parent: {active_contract.parent_order_id}")
        
        logger.info(f"Cancelled {cancelled_count} bracket orders for position")
        return cancelled_count
    
    async def _cancel_bracket_orders_for_symbol(self, symbol: str):
        """Cancel all bracket orders for a specific symbol."""
        logger.info(f"Cancelling bracket orders for symbol: {symbol}")
        
        open_trades = self.ib.openTrades()
        orders_to_cancel = []
        
        # Find all bracket orders for this symbol
        for trade in open_trades:
            order = trade.order
            contract = trade.contract
            
            # Check if this is a bracket order for the specified symbol
            if (hasattr(order, 'parentId') and order.parentId and
                hasattr(contract, 'symbol') and contract.symbol == symbol):
                orders_to_cancel.append(order.orderId)
                logger.info(f"Found bracket order to cancel: {order.orderId} (parent: {order.parentId})")
        
        # Cancel the orders
        cancelled_count = 0
        for order_id in orders_to_cancel:
            for trade in open_trades:
                if (hasattr(trade, 'order') and
                    hasattr(trade.order, 'orderId') and
                    trade.order.orderId == order_id):
                    try:
                        self.ib.cancelOrder(trade.order)
                        logger.info(f"Cancelled bracket order: {order_id}")
                        cancelled_count += 1
                        await asyncio.sleep(0.5)  # Small delay between cancellations
                    except Exception as e:
                        logger.warning(f"Error cancelling order {order_id}: {e}")
                    break
        
        # Clean up tracking for this symbol
        symbols_to_remove = []
        for parent_id, bracket_info in self._bracket_orders.items():
            if bracket_info.get('contract', '').startswith(symbol):
                symbols_to_remove.append(parent_id)
        
        for parent_id in symbols_to_remove:
            del self._bracket_orders[parent_id]
            logger.info(f"Cleaned up bracket order tracking for parent: {parent_id}")
        
        logger.info(f"Cancelled {cancelled_count} bracket orders for {symbol}")
        return cancelled_count
    
    async def _cancel_all_bracket_orders(self):
        """
        Cancel all bracket orders in the system.
        This is useful for cleanup operations.
        """
        logger.info("Cancelling all bracket orders...")
        
        # Get all open orders
        open_trades = self.ib.openTrades()
        bracket_orders_cancelled = 0
        
        for trade in open_trades:
            order = trade.order
            if hasattr(order, 'parentId') and order.parentId:  # This is a bracket order
                try:
                    self.ib.cancelOrder(order.orderId)
                    logger.info(f"Cancelled bracket order {order.orderId} (parent: {order.parentId})")
                    bracket_orders_cancelled += 1
                    await asyncio.sleep(0.5)  # Small delay between cancellations
                except Exception as e:
                    logger.warning(f"Failed to cancel bracket order {order.orderId}: {e}")
        
        logger.info(f"Cancelled {bracket_orders_cancelled} bracket orders")
        return bracket_orders_cancelled
    
    # === DATA REQUEST HANDLERS ===
    
    @require_connection()
    @handle_errors('positions_update')
    async def _handle_get_positions(self, data: Optional[Dict] = None):
        """Enhanced positions handler with comprehensive data."""
        positions = self.ib.positions()
        
        position_data = []
        for pos in positions:
            # Extract contract information explicitly
            contract_info = {
                'symbol': getattr(pos.contract, 'symbol', ''),
                'secType': getattr(pos.contract, 'secType', ''),
                'exchange': getattr(pos.contract, 'exchange', ''),
                'currency': getattr(pos.contract, 'currency', ''),
                'localSymbol': getattr(pos.contract, 'localSymbol', ''),
                'tradingClass': getattr(pos.contract, 'tradingClass', ''),
                'conId': getattr(pos.contract, 'conId', 0)
            }
            
            pos_info = {
                'contract': contract_info,
                'position': pos.position,
                'avgCost': pos.avgCost,
                'account': pos.account,
                'marketPrice': getattr(pos, 'marketPrice', None),
                'marketValue': getattr(pos, 'marketValue', None),
                'unrealizedPNL': getattr(pos, 'unrealizedPNL', None),
                'realizedPNL': getattr(pos, 'realizedPNL', None)
            }
            position_data.append(pos_info)
        
        # Store for tests
        self.positions = position_data
        
        logger.debug(f"Retrieved {len(position_data)} positions")
        return {'positions': position_data}
    
    @require_connection()
    @handle_errors('open_orders_update')
    async def _handle_get_open_orders(self, data: Optional[Dict] = None):
        """Enhanced open orders handler."""
        open_trades = self.ib.openTrades()
        
        order_data = []
        for trade in open_trades:
            order_info = {
                'contract': util.tree(trade.contract),
                'order': util.tree(trade.order),
                'orderStatus': util.tree(trade.orderStatus),
                'log': [util.tree(log) for log in trade.log] if hasattr(trade, 'log') else []
            }
            order_data.append(order_info)
        
        # Store for tests
        self.open_orders = order_data
        
        logger.debug(f"Retrieved {len(order_data)} open orders")
        return {'orders': order_data}
    
    @handle_errors('active_contract_status_update')
    async def _handle_get_active_contract_status(self, data: Optional[Dict] = None):
        """Enhanced active contract status with comprehensive data."""
        active_contracts_info = []
        
        for symbol, contract in self._active_contracts.items():
            if contract.is_active and (not self._underlying_symbol or 
                                      (getattr(contract.contract, 'symbol', None) == self._underlying_symbol)):
                contract_info = {
                    'symbol': symbol,
                    'contract': util.tree(contract.contract),
                    'quantity': contract.quantity,
                    'entry_price': contract.entry_price,
                    'current_price': contract.current_price,
                    'unrealized_pnl': contract.unrealized_pnl, # Now a property
                    'entry_time': contract.entry_time.isoformat() if contract.entry_time else None,
                    'parent_order_id': contract.parent_order_id,
                    'has_stop_loss': contract.stop_loss_order_id is not None,
                    'has_take_profit': contract.take_profit_order_id is not None,
                    'is_active': contract.is_active
                }
                active_contracts_info.append(contract_info)
        
        status_data = {
            'has_active_contracts': len(active_contracts_info) > 0,
            'active_trade_flag': self._active_trade_flag,
            'underlying_symbol': self._underlying_symbol,
            'active_contracts': active_contracts_info
        }
        
        return status_data
    
    @handle_errors('test_event_response')
    async def _handle_test_event(self, data: Dict):
        """Enhanced test event handler."""
        logger.info(f"Test event received: {data}")
        return {
            'message': 'Test event processed successfully',
            'timestamp': datetime.now().isoformat(),
            'connected': self._connected,
            'active_trade_flag': self._active_trade_flag,
            'subscriptions': len(self._market_data_subscriptions),
            'data_received': data
        }
    
    # === ACTIVE TRADE MANAGEMENT ===
    
    async def _update_active_trade_status(self):
        """Enhanced active trade status detection with comprehensive analysis."""
        if not self._connected:
            return
        
        underlying_symbol = self._underlying_symbol
        if not underlying_symbol:
            return
        
        # Check open orders
        active_orders_found = False
        open_trades = self.ib.openTrades()
        
        for trade in open_trades:
            if (getattr(trade.contract, 'symbol', None) == underlying_symbol and
                getattr(trade.contract, 'secType', None) == 'OPT'):
                
                if getattr(trade.orderStatus, 'status', None) not in ['Cancelled', 'Filled', 'Inactive']:
                    active_orders_found = True
                    break
        
        # Check positions
        active_positions_found = False
        positions = self.ib.positions()
        
        for position in positions:
            if (getattr(position.contract, 'symbol', None) == underlying_symbol and
                getattr(position.contract, 'secType', None) == 'OPT' and
                position.position != 0):
                
                active_positions_found = True
                
                # Update active contracts
                contract_key = f"{position.contract.localSymbol}_{position.contract.conId}"
                if contract_key not in self._active_contracts:
                    self._active_contracts[contract_key] = ActiveContract(
                        contract=position.contract,
                        quantity=int(position.position),
                        entry_price=position.avgCost,
                        is_active=True
                    )
                else:
                    active_contract = self._active_contracts[contract_key]
                    active_contract.quantity = int(position.position)
                    active_contract.entry_price = position.avgCost
                    active_contract.is_active = position.position != 0
        
        # Update flag and publish if changed
        new_active_flag = active_orders_found or active_positions_found
        
        if self._active_trade_flag != new_active_flag:
            self._active_trade_flag = new_active_flag
            logger.info(f"Active trade flag for {underlying_symbol}: {self._active_trade_flag}")
            
            self.event_bus.emit('trade.status_update', {
                'underlying_symbol': underlying_symbol,
                'active_trade_flag': self._active_trade_flag,
                'has_active_orders': active_orders_found,
                'has_active_positions': active_positions_found,
                'timestamp': datetime.now().isoformat()
            })
        
        # Clean up inactive contracts
        inactive_keys = [
            key for key, contract in self._active_contracts.items()
            if not contract.is_active
        ]
        for key in inactive_keys:
            del self._active_contracts[key]
            logger.debug(f"Cleaned up inactive contract: {key}")
    
    # === UTILITY METHODS ===
    
    def _transform_legacy_order_data(self, data: Dict) -> tuple:
        """
        Transform legacy order data format to new format.
        
        Legacy format:
        {
            'symbol': 'SPY',
            'action': 'BUY',
            'orderType': 'LMT',
            'totalQuantity': 1,
            'lmtPrice': 500.0,
            'entry_price': 500.0,
            'take_profit_price': 510.0,
            'stop_loss_price': 490.0
        }
        
        Returns:
        - contract_data: Dict for contract creation
        - order_data: Dict for order creation
        - bracket_data: Dict for bracket orders (if applicable)
        """
        symbol = data.get('symbol', '')
        action = data.get('action', 'BUY')
        order_type = data.get('orderType', 'LMT')
        quantity = data.get('totalQuantity', 1)
        
        # Determine contract type based on data
        sec_type = data.get('secType', 'STK')
        if 'strike' in data or 'right' in data:
            sec_type = 'OPT'
        elif symbol in ['EURUSD', 'GBPUSD', 'USDJPY'] or len(symbol) == 6:
            sec_type = 'CASH'
        
        # Create contract data
        contract_data = {
            'symbol': symbol,
            'secType': sec_type,
            'exchange': data.get('exchange', 'SMART'),
            'currency': data.get('currency', 'USD')
        }
        
        # Add option-specific fields
        if sec_type == 'OPT':
            contract_data.update({
                'strike': data.get('strike', 0),
                'right': data.get('right', 'C'),
                'lastTradeDateOrContractMonth': data.get('lastTradeDateOrContractMonth', '')
            })
        
        # Create order data
        order_data = {
            'action': action,
            'orderType': order_type,
            'totalQuantity': quantity
        }
        
        # Add price fields based on order type
        if order_type == 'LMT':
            order_data['lmtPrice'] = data.get('lmtPrice', data.get('limit_price', 0))
        elif order_type == 'STP':
            order_data['auxPrice'] = data.get('auxPrice', data.get('stop_price', 0))
        elif order_type == 'STP LMT':
            order_data['lmtPrice'] = data.get('lmtPrice', data.get('limit_price', 0))
            order_data['auxPrice'] = data.get('auxPrice', data.get('stop_price', 0))
        
        # Create bracket data if bracket order fields are present
        bracket_data = None
        if any(key in data for key in ['entry_price', 'take_profit_price', 'stop_loss_price']):
            bracket_data = {}
            if 'take_profit_price' in data:
                bracket_data['profit_taker_price'] = data['take_profit_price']
            if 'stop_loss_price' in data:
                bracket_data['stop_loss_price'] = data['stop_loss_price']
        
        return contract_data, order_data, bracket_data
    
    def _create_contract_from_data(self, contract_data: Dict) -> Optional[Contract]:
        """
        Create IB contract from dictionary data with comprehensive type support.
        
        OPTIMIZATION: This unified method replaces multiple contract creation patterns
        throughout the original codebase, eliminating duplication.
        
        Supported Contract Types:
        
        # Stock (STK)
        {'symbol': 'AAPL', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'}
        
        # Option (OPT) 
        {'symbol': 'SPY', 'secType': 'OPT', 'strike': 580, 'right': 'P', 
         'lastTradeDateOrContractMonth': '20241220', 'exchange': 'SMART'}
        
        # Forex (CASH)
        {'symbol': 'EURUSD', 'secType': 'CASH', 'exchange': 'IDEALPRO'}
        
        # Generic (any secType)
        {'symbol': 'ES', 'secType': 'FUT', 'exchange': 'GLOBEX', ...}
        
        Returns: IB Contract object or None if creation fails
        """
        try:
            sec_type = contract_data.get('secType', 'STK').upper()
            
            # Stock contracts
            if sec_type == 'STK':
                return Stock(
                    symbol=contract_data.get('symbol', ''),
                    exchange=contract_data.get('exchange', 'SMART'),
                    currency=contract_data.get('currency', 'USD')
                )
            # Option contracts
            elif sec_type == 'OPT':
                return Option(
                    symbol=contract_data.get('symbol', ''),
                    lastTradeDateOrContractMonth=contract_data.get('lastTradeDateOrContractMonth', ''),
                    strike=contract_data.get('strike', 0),
                    right=contract_data.get('right', 'C'),
                    exchange=contract_data.get('exchange', 'SMART'),
                    currency=contract_data.get('currency', 'USD')
                )
            # Forex contracts
            elif sec_type == 'CASH':
                return Forex(
                    pair=contract_data.get('symbol', ''), # Forex uses 'pair' in ib_async >= 1.0
                    exchange=contract_data.get('exchange', 'IDEALPRO')
                )
            # Generic contracts (futures, bonds, etc.)
            else:
                contract = Contract()
                for key, value in contract_data.items():
                    if hasattr(contract, key):
                        setattr(contract, key, value)
                return contract
                
        except Exception as e:
            logger.error(f"Error creating contract from data: {e}", exc_info=True)
            return None
    
    async def _cleanup_market_data_subscriptions(self):
        """Enhanced cleanup of all market data subscriptions with status tracking."""
        logger.info(f"Cleaning up {len(self._market_data_subscriptions)} market data subscriptions")
        
        cleanup_results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for con_id, subscription in list(self._market_data_subscriptions.items()):
            try:
                contract = subscription['contract']
                success = self.ib.cancelMktData(contract)
                
                if success:
                    logger.debug(f"Successfully cancelled market data for {contract.localSymbol}")
                    cleanup_results['successful'] += 1
                else:
                    logger.warning(f"Failed to cancel market data for {contract.localSymbol}")
                    cleanup_results['failed'] += 1
                    
            except Exception as e:
                error_msg = f"Error cancelling market data for con_id {con_id}: {e}"
                logger.warning(error_msg)
                cleanup_results['failed'] += 1
                cleanup_results['errors'].append(error_msg)
        
        self._market_data_subscriptions.clear()
        
        logger.info(f"Market data cleanup completed: {cleanup_results['successful']} successful, {cleanup_results['failed']} failed")
        
        if cleanup_results['errors']:
            logger.warning(f"Market data cleanup errors: {cleanup_results['errors']}")
        
        return cleanup_results
    
    async def _cleanup_account_subscriptions(self):
        """Clean up account data subscriptions."""
        if self._account_subscription_active:
            self._account_subscription_active = False
            logger.debug("Account summary subscription marked for cleanup")
        
        if self._pnl_subscription_active:
            account = self._connection_params.get('account', '')
            if account and self.ib.isConnected():
                try:
                    self.ib.cancelPnL(account, '')
                except Exception as e:
                    logger.warning(f"Error cancelling P&L subscription: {e}")
            self._pnl_subscription_active = False
            logger.debug("Cancelled P&L subscription")
    
    # === IB EVENT CALLBACKS ===
    
    def _on_connected(self):
        """Handle successful IB connection."""
        try:
            logger.info("✓ IB Connection established successfully")
            self._connected = True
            self.connection_attempts = 0
            
            # Emit connection success event
            connection_data = {
                'host': self.config.get('connection', 'host', '127.0.0.1'),
                'port': self.config.get('connection', 'port', 7497),
                'client_id': self.config.get('connection', 'client_id', 1),
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_bus.emit('ib.connected', connection_data, priority=EventPriority.HIGH)
            
            # Immediately request account data
            asyncio.create_task(self._request_account_data_immediately())
            
        except Exception as e:
            logger.error(f"Error in connection success handler: {e}")
    
    def _on_disconnected(self):
        """Handle IB disconnection."""
        try:
            logger.info("✗ IB Connection disconnected")
            self._connected = False
            
            # Emit disconnection event
            disconnection_data = {
                'host': self.config.get('connection', 'host', '127.0.0.1'),
                'port': self.config.get('connection', 'port', 7497),
                'client_id': self.config.get('connection', 'client_id', 1),
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_bus.emit('ib.disconnected', disconnection_data, priority=EventPriority.HIGH)
            
        except Exception as e:
            logger.error(f"Error in disconnection handler: {e}")
    
    async def _request_account_data_immediately(self):
        """Request account data immediately upon connection."""
        try:
            logger.info("Requesting account data immediately upon connection...")
            
            # Request account summary
            await self._handle_request_account_summary()
            
            # Request P&L data
            await self._handle_request_pnl()
            
            # Request positions
            await self._handle_get_positions()
            
            # Request open orders
            await self._handle_get_open_orders()
            
            logger.info("Account data requests completed")
            
        except Exception as e:
            logger.error(f"Error requesting account data: {e}")
    
    def _on_account_summary_update(self, account_value: AccountValue):
        """Enhanced account summary callback with improved timing."""
        try:
            summary_data = {
                'account': account_value.account,
                'tag': account_value.tag,
                'value': account_value.value,
                'currency': account_value.currency,
                'timestamp': datetime.now().isoformat()
            }
            
            # Store for tests
            self.account_summary.append(summary_data)
            
            # Emit with HIGH priority to ensure immediate processing
            self.event_bus.emit('account.summary_update', summary_data, priority=EventPriority.HIGH)
            logger.debug(f"IB CONNECTION: Emitted account.summary_update with data: {summary_data}")
            
        except Exception as e:
            logger.error(f"Error handling account summary update: {e}", exc_info=True)
    
    def _on_pnl_update(self, pnl: PnL):
        """Enhanced P&L callback."""
        try:
            pnl_data = {
                'account': pnl.account,
                'dailyPnL': pnl.dailyPnL,
                'unrealizedPnL': pnl.unrealizedPnL,
                'realizedPnL': pnl.realizedPnL,
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_bus.emit('account.pnl_update', pnl_data, priority=EventPriority.LOW)
            
        except Exception as e:
            logger.error(f"Error handling P&L update: {e}", exc_info=True)
    
    def _on_market_data_tick(self, ticker: Ticker):
        """Enhanced market data callback with comprehensive tick processing."""
        try:
            # Update active contracts with current prices
            if hasattr(ticker, 'contract') and ticker.contract:
                contract = ticker.contract
                last_price = ticker.last if ticker.last and not util.isNan(ticker.last) else ticker.close
                
                # Store current price for external access
                if contract.symbol == 'SPY' and last_price and last_price > 0:
                    self.current_spy_price = last_price
                
                for contract_key, active_contract in self._active_contracts.items():
                    if (getattr(active_contract.contract, 'conId', None) == getattr(contract, 'conId', None) and
                        last_price and last_price > 0):
                        
                        active_contract.current_price = last_price
            
            # Publish tick update with NORMAL priority (will be throttled if needed)
            tick_data = {
                'contract': util.tree(ticker.contract) if ticker.contract else None,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'volume': ticker.volume,
                'high': ticker.high,
                'low': ticker.low,
                'close': ticker.close,
                'timestamp': datetime.now().isoformat()
            }
            
            # Use the new market data sampling system
            self.event_bus.emit('market_data.tick_update', tick_data, priority=EventPriority.NORMAL)
            
        except Exception as e:
            logger.error(f"Error handling market data tick: {e}", exc_info=True)
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Enhanced IB API error handling with categorization and recovery strategies."""
        try:
            error_data = {
                'reqId': reqId,
                'errorCode': errorCode,
                'errorString': errorString,
                'advancedOrderRejectJson': advancedOrderRejectJson,
                'timestamp': datetime.now().isoformat(),
                'category': self._categorize_error(errorCode),
                'recovery_strategy': self._get_recovery_strategy(errorCode)
            }
            
            logger.error(f"IB Error {errorCode}: {errorString}")
            
            # Emit categorized error events based on error type
            if errorCode in [1100, 1101, 1102]:  # Connection errors
                self.event_bus.emit('ib.connection_error', error_data, priority=EventPriority.HIGH)
                self._handle_connection_error(errorCode, errorString)
            elif errorCode in [200, 201, 202]:  # Order errors
                self.event_bus.emit('ib.order_error', error_data, priority=EventPriority.CRITICAL)
                self._handle_order_error(errorCode, errorString)
            elif errorCode in [10167, 10168, 10169]:  # Market data errors
                self.event_bus.emit('ib.market_data_error', error_data, priority=EventPriority.NORMAL)
                self._handle_market_data_error(errorCode, errorString)
            else:
                # Generic error event
                self.event_bus.emit('ib.error', error_data, priority=EventPriority.HIGH)
            
        except Exception as e:
            logger.error(f"Error handling IB error: {e}", exc_info=True)
    
    def _categorize_error(self, error_code: int) -> str:
        """Categorize IB error codes for better handling."""
        if error_code in [1100, 1101, 1102]:
            return "connection"
        elif error_code in [200, 201, 202]:
            return "order"
        elif error_code in [10167, 10168, 10169]:
            return "market_data"
        elif error_code in [300, 301, 302]:
            return "account"
        else:
            return "general"
    
    def _get_recovery_strategy(self, error_code: int) -> str:
        """Get recovery strategy for specific error codes."""
        if error_code in [1100, 1101, 1102]:
            return "auto_reconnect"
        elif error_code in [200, 201, 202]:
            return "retry_order"
        elif error_code in [10167, 10168, 10169]:
            return "retry_subscription"
        else:
            return "log_only"
    
    def _handle_connection_error(self, error_code: int, error_string: str):
        """Handle connection-specific errors with recovery logic."""
        logger.warning(f"Connection error {error_code}: {error_string}")
        
        # Implement circuit breaker pattern
        if not hasattr(self, '_connection_failure_count'):
            self._connection_failure_count = 0
        if not hasattr(self, '_connection_circuit_breaker_activated'):
            self._connection_circuit_breaker_activated = False
        
        self._connection_failure_count += 1
        
        if self._connection_failure_count >= 3 and not self._connection_circuit_breaker_activated:
            logger.error("Connection failure threshold reached, implementing circuit breaker")
            self._connection_circuit_breaker_activated = True
            self.event_bus.emit('ib.circuit_breaker_activated', {
                'failure_count': self._connection_failure_count,
                'error_code': error_code,
                'timestamp': datetime.now().isoformat()
            }, priority=EventPriority.CRITICAL)
    
    def _handle_order_error(self, error_code: int, error_string: str):
        """Handle order-specific errors with recovery logic."""
        logger.warning(f"Order error {error_code}: {error_string}")
        
        # Track order failures for circuit breaker
        if not hasattr(self, '_order_failure_count'):
            self._order_failure_count = 0
        if not hasattr(self, '_order_circuit_breaker_activated'):
            self._order_circuit_breaker_activated = False
        
        self._order_failure_count += 1
        
        if self._order_failure_count >= 5 and not self._order_circuit_breaker_activated:
            logger.error("Order failure threshold reached, implementing circuit breaker")
            self._order_circuit_breaker_activated = True
            self.event_bus.emit('ib.order_circuit_breaker_activated', {
                'failure_count': self._order_failure_count,
                'error_code': error_code,
                'timestamp': datetime.now().isoformat()
            }, priority=EventPriority.CRITICAL)
    
    def _handle_market_data_error(self, error_code: int, error_string: str):
        """Handle market data-specific errors with recovery logic."""
        logger.warning(f"Market data error {error_code}: {error_string}")
        
        # Implement exponential backoff for market data errors
        if not hasattr(self, '_market_data_error_count'):
            self._market_data_error_count = 0
        if not hasattr(self, '_market_data_backoff_activated'):
            self._market_data_backoff_activated = False
        
        self._market_data_error_count += 1
        
        if self._market_data_error_count >= 10 and not self._market_data_backoff_activated:
            logger.error("Market data error threshold reached, implementing backoff")
            self._market_data_backoff_activated = True
            self.event_bus.emit('ib.market_data_backoff_activated', {
                'error_count': self._market_data_error_count,
                'error_code': error_code,
                'timestamp': datetime.now().isoformat()
            }, priority=EventPriority.NORMAL)
    
    def _on_order_status_update(self, order):
        """Handle order status updates."""
        try:
            order_data = {
                'orderId': order.orderId,
                'status': order.status,
                'filled': order.filled,
                'remaining': order.remaining,
                'avgFillPrice': order.avgFillPrice,
                'lastFillPrice': order.lastFillPrice,
                'whyHeld': order.whyHeld,
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_bus.emit('order.status_update', order_data, priority=EventPriority.NORMAL)
            
        except Exception as e:
            logger.error(f"Error handling order status update: {e}", exc_info=True)
    
    def _on_exec_details(self, reqId: int, contract, execution):
        """Handle execution details."""
        try:
            exec_data = {
                'reqId': reqId,
                'contract': util.tree(contract) if contract else None,
                'execution': util.tree(execution) if execution else None,
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_bus.emit('order.fill', exec_data, priority=EventPriority.NORMAL)
            
        except Exception as e:
            logger.error(f"Error handling execution details: {e}", exc_info=True)
    
    def _on_commission_report(self, commissionReport):
        """Handle commission reports."""
        try:
            commission_data = {
                'commissionReport': util.tree(commissionReport) if commissionReport else None,
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_bus.emit('order.commission_report', commission_data, priority=EventPriority.NORMAL)
            
        except Exception as e:
            logger.error(f"Error handling commission report: {e}", exc_info=True)

    # === FX RATE MANAGEMENT ===

    async def _handle_request_fx_rate(self, data: dict):
        """
        Handle FX rate subscription and calculation.
        If account base currency != underlying currency, subscribe to FX rate and calculate direct/reciprocal rates.
        Emits 'fx.rate_update' event with both rates.
        """
        # Determine base and quote currencies
        account_currency = self._connection_params.get('account_currency')
        underlying_symbol = data.get('underlying_symbol', self._underlying_symbol)
        underlying_currency = data.get('underlying_currency', 'USD')
        
        if not account_currency:
            # Try to get from config or IB
            account_currency = str(self.config_manager.get('connection', 'base_currency', 'USD') or 'USD')
        if not underlying_currency:
            underlying_currency = 'USD'
        
        if account_currency == underlying_currency:
            # No FX needed
            fx_rate = 1.0
            reciprocal_rate = 1.0
            self.event_bus.emit('fx.rate_update', {
                'pair': f'{account_currency}.{underlying_currency}',
                'rate': fx_rate,
                'reciprocal_rate': reciprocal_rate,
                'timestamp': datetime.now().isoformat(),
                'note': 'No FX conversion needed.'
            })
            return
        
        # Subscribe to FX rate (e.g., USD.CAD)
        pair = f'{account_currency}{underlying_currency}'
        reverse_pair = f'{underlying_currency}{account_currency}'
        fx_contract = self._create_contract_from_data({'symbol': pair, 'secType': 'CASH', 'exchange': 'IDEALPRO'})
        reverse_fx_contract = self._create_contract_from_data({'symbol': reverse_pair, 'secType': 'CASH', 'exchange': 'IDEALPRO'})
        
        # Subscribe to both directions for safety
        ticker = self.ib.reqMktData(fx_contract, '', False, False)
        reverse_ticker = self.ib.reqMktData(reverse_fx_contract, '', False, False)
        await asyncio.sleep(1)  # Wait for price update
        
        fx_rate = ticker.last if ticker.last and not util.isNan(ticker.last) else ticker.close
        reciprocal_rate = reverse_ticker.last if reverse_ticker.last and not util.isNan(reverse_ticker.last) else reverse_ticker.close
        
        # Calculate reciprocal if only one is available
        if fx_rate and not reciprocal_rate:
            reciprocal_rate = 1.0 / fx_rate if fx_rate else None
        elif reciprocal_rate and not fx_rate:
            fx_rate = 1.0 / reciprocal_rate if reciprocal_rate else None
        
        self.event_bus.emit('fx.rate_update', {
            'pair': pair,
            'rate': fx_rate,
            'reciprocal_pair': reverse_pair,
            'reciprocal_rate': reciprocal_rate,
            'timestamp': datetime.now().isoformat()
        })
        # Optionally cancel market data after fetch
        self.ib.cancelMktData(fx_contract)
        self.ib.cancelMktData(reverse_fx_contract)

    # === HISTORICAL DATA MANAGEMENT ===

    @require_connection('market_data.historical_error')
    @handle_errors('market_data.historical_update', 'market_data.historical_error')
    async def _handle_request_historical_data(self, data: dict):
        """
        Fetch historical 1-minute bar data for a contract.
        Emits 'market_data.historical_update' with the bar data.
        Example data: {'symbol': 'AAPL', 'secType': 'STK', 'duration': '1 D', 'barSize': '1 min'}
        """
        contract = self._create_contract_from_data(data.get('contract', data))
        if not contract:
            raise ValueError(f"Could not create contract from data: {data}")
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified or qualified[0] is None:
            raise ValueError(f"Could not qualify contract: {contract}")
        qualified_contract = qualified[0]
        duration = data.get('duration', '1 D')
        bar_size = data.get('barSize', '1 min')
        what_to_show = data.get('whatToShow', 'TRADES')
        use_rth = data.get('useRTH', 1)
        
        bars = await self.ib.reqHistoricalDataAsync(
            qualified_contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=use_rth,
            formatDate=1
        )
        # Convert bars to serializable format
        bar_data = [
            {
                'date': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars
        ]
        return {
            'symbol': qualified_contract.symbol,
            'secType': qualified_contract.secType,
            'conId': qualified_contract.conId,
            'bars': bar_data,
            'count': len(bar_data)
        }
