import asyncio
from typing import Dict, Any, List
from ib_async import IB, Option, Order
from datetime import datetime, timedelta
import pytz
from threading import Thread, Event, Lock
import time
from .smart_logger import get_logger

logger = get_logger("TRADING_MANAGER")


class TradingManager:
    """
    Trading Manager for handling order placement, position management, and hotkey execution
    """
    
    def __init__(self, ib_connection: IB, trading_config: Dict[str, Any], account_config: Dict[str, Any]):
        self.ib = ib_connection
        self.trading_config = trading_config
        self.account_config = account_config
        self.underlying_symbol = trading_config.get('underlying_symbol', 'QQQ')
        self.trade_delta = trading_config.get('trade_delta', 0.05)
        self.max_trade_value = trading_config.get('max_trade_value', 475.0)
        self.runner = trading_config.get('runner', 1)
        self.risk_levels = trading_config.get('risk_levels', [])
        
        # Position tracking
        self._active_positions = {}  # {symbol: position_data}
        self._open_orders = {}  # {order_id: order_data}
        self._position_lock = Lock()
        self._order_lock = Lock()
        
        # Chase logic tracking
        self._chase_orders = {}  # {order_id: chase_data}
        self._chase_timer = None
        self._chase_thread = None
        self._stop_chase = Event()
        
        # PDT buffer calculation
        self._pdt_minimum_usd = 2000
        self._pdt_minimum_cad = 2500
        
        # Current market data
        self._current_call_option = None
        self._current_put_option = None
        self._underlying_price = 0
        self._account_value = 0
        self._daily_pnl_percent = 0
        
        # Est timezone for expiration calculations
        self._est_timezone = pytz.timezone('US/Eastern')
        
        logger.info("Trading Manager initialized")
    
    def update_market_data(self, call_option: Dict[str, Any] = None, 
                          put_option: Dict[str, Any] = None,
                          underlying_price: float = None,
                          account_value: float = None,
                          daily_pnl_percent: float = None):
        """Update current market data"""
        if call_option:
            self._current_call_option = call_option
        if put_option:
            self._current_put_option = put_option
        if underlying_price is not None:
            self._underlying_price = underlying_price
        if account_value is not None:
            self._account_value = account_value
        if daily_pnl_percent is not None:
            self._daily_pnl_percent = daily_pnl_percent
    
    def _calculate_order_quantity(self, option_price: float) -> int:
        """
        Calculate order quantity using three-step calculation:
        1. GUI Max Trade Value
        2. Tiered Risk Limit
        3. PDT Buffer
        """
        try:
            # Step 1: GUI Max Trade Value
            gui_max_value = self.max_trade_value
            
            # Step 2: Tiered Risk Limit
            tiered_max_value = self._calculate_tiered_risk_limit()
            
            # Step 3: PDT Buffer
            pdt_max_value = self._calculate_pdt_buffer()
            
            # Use minimum of the three
            max_trade_value = min(gui_max_value, tiered_max_value, pdt_max_value)
            
            # Calculate quantity
            if option_price > 0:
                quantity = int(max_trade_value / option_price)
                logger.info(f"Order quantity calculation: GUI={gui_max_value}, Tiered={tiered_max_value}, PDT={pdt_max_value}, Final={max_trade_value}, Qty={quantity}")
                return max(1, quantity)  # Minimum 1 contract
            else:
                logger.warning("Option price is zero or negative, cannot calculate quantity")
                return 1
                
        except Exception as e:
            logger.error(f"Error calculating order quantity: {e}")
            return 1
    
    def _calculate_tiered_risk_limit(self) -> float:
        """Calculate maximum trade value based on current daily P&L and risk levels"""
        try:
            current_pnl_percent = abs(self._daily_pnl_percent)
            
            for risk_level in self.risk_levels:
                loss_threshold = float(risk_level.get('loss_threshold', 0))
                account_trade_limit = float(risk_level.get('account_trade_limit', 100))
                
                if current_pnl_percent >= loss_threshold:
                    # Calculate trade limit as percentage of account value
                    max_trade_value = (account_trade_limit / 100) * self._account_value
                    logger.info(f"Tiered risk limit: PnL={current_pnl_percent}%, Threshold={loss_threshold}%, Limit={account_trade_limit}%, MaxValue=${max_trade_value:.2f}")
                    return max_trade_value
            
            # Default to GUI max trade value if no risk level matches
            return self.max_trade_value
            
        except Exception as e:
            logger.error(f"Error calculating tiered risk limit: {e}")
            return self.max_trade_value
    
    def _calculate_pdt_buffer(self) -> float:
        """Calculate buffer to stay above PDT minimum equity requirement"""
        try:
            # Determine currency and minimum requirement
            # For now, assume USD - this should be determined from account currency
            pdt_minimum = self._pdt_minimum_usd
            
            # Calculate available buffer
            available_buffer = self._account_value - pdt_minimum
            
            # Use 80% of available buffer as safety margin
            safe_buffer = available_buffer * 0.8
            
            logger.info(f"PDT buffer calculation: Account=${self._account_value:.2f}, Min=${pdt_minimum}, Available=${available_buffer:.2f}, Safe=${safe_buffer:.2f}")
            
            return max(0, safe_buffer)
            
        except Exception as e:
            logger.error(f"Error calculating PDT buffer: {e}")
            return self.max_trade_value
    
    def _get_contract_expiration(self) -> str:
        """Programmatically determine the correct contract expiration date with smart fallback to available expirations"""
        try:
            est_now = datetime.now(self._est_timezone)
            
            # First, try to get available expirations from the data collector if available
            available_expirations = self._get_available_expirations()
            
            if available_expirations:
                # Smart expiration selection based on available expirations
                return self._select_smart_expiration(est_now, available_expirations)
            else:
                # Fallback to original logic if no available expirations
                return self._get_fallback_expiration(est_now)
                
        except Exception as e:
            logger.error(f"Error calculating contract expiration: {e}")
            # Final fallback to next day
            tomorrow = datetime.now(self._est_timezone).date() + timedelta(days=1)
            return tomorrow.strftime("%Y%m%d")
    
    def update_available_expirations(self, expirations: List[str]):
        """Update available expirations in the trading manager"""
        try:
            if expirations:
                logger.info(f"Trading manager updated with {len(expirations)} available expirations")
                # Store locally for quick access
                self._local_available_expirations = expirations
            else:
                logger.warning("Trading manager: Received empty expirations list")
                
        except Exception as e:
            logger.error(f"Trading manager error updating available expirations: {e}")
    
    def _get_available_expirations(self) -> List[str]:
        """Get available expirations from the data collector if available"""
        try:
            # First try local cache
            if hasattr(self, '_local_available_expirations') and self._local_available_expirations:
                return self._local_available_expirations
            
            # Try to access available expirations from the data collector
            if hasattr(self, 'data_collector') and self.data_collector:
                if hasattr(self.data_collector, 'collector') and self.data_collector.collector:
                    if hasattr(self.data_collector.collector, '_available_expirations'):
                        expirations = self.data_collector.collector._available_expirations
                        if expirations:
                            logger.info(f"Found {len(expirations)} available expirations")
                            return expirations
            
            # Try alternative path through connection
            if hasattr(self, 'data_collector') and self.data_collector:
                if hasattr(self.data_collector, 'collector') and self.data_collector.collector:
                    if hasattr(self.data_collector.collector, 'ib_connection'):
                        if hasattr(self.data_collector.collector.ib_connection, '_available_expirations'):
                            expirations = self.data_collector.collector.ib_connection._available_expirations
                            if expirations:
                                logger.info(f"Found {len(expirations)} available expirations via IB connection")
                                return expirations
            
            logger.warning("No available expirations found, using fallback logic")
            return []
            
        except Exception as e:
            logger.error(f"Error getting available expirations: {e}")
            return []
    
    def _select_smart_expiration(self, est_now: datetime, available_expirations: List[str]) -> str:
        """Select the best available expiration based on time and availability"""
        try:
            current_date = est_now.date()
            current_time = est_now.time()
            
            # Convert available expirations to dates for comparison
            exp_dates = []
            for exp_str in available_expirations:
                try:
                    # Handle different expiration formats
                    if ' ' in exp_str:  # Format: "20241220 16:00:00"
                        exp_str = exp_str.split()[0]
                    exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
                    exp_dates.append((exp_str, exp_date))
                except Exception as e:
                    logger.warning(f"Could not parse expiration {exp_str}: {e}")
                    continue
            
            if not exp_dates:
                logger.warning("No valid expiration dates found")
                return self._get_fallback_expiration(est_now)
            
            # Sort by date
            exp_dates.sort(key=lambda x: x[1])
            
            # Determine target expiration type based on time
            if current_time.hour < 12:
                # Before 12:00 PM EST - prefer 0DTE (same day)
                target_type = "0DTE"
                target_date = current_date
            else:
                # After 12:00 PM EST - prefer 1DTE (next business day)
                target_type = "1DTE"
                target_date = current_date + timedelta(days=1)
                # Skip weekends
                while target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    target_date += timedelta(days=1)
            
            logger.info(f"Target expiration type: {target_type}, target date: {target_date}")
            
            # Strategy 1: Try to find exact target date
            for exp_str, exp_date in exp_dates:
                if exp_date == target_date:
                    logger.info(f"Found exact {target_type} expiration: {exp_str}")
                    return exp_str
            
            # Strategy 2: Find nearest available expiration to target date
            nearest_exp = None
            min_days_diff = float('inf')
            
            for exp_str, exp_date in exp_dates:
                days_diff = abs((exp_date - target_date).days)
                if days_diff < min_days_diff:
                    min_days_diff = days_diff
                    nearest_exp = exp_str
            
            if nearest_exp:
                logger.info(f"Selected nearest available expiration: {nearest_exp} (days diff: {min_days_diff})")
                return nearest_exp
            
            # Strategy 3: Fallback to first available expiration
            logger.warning("No suitable expiration found, using first available")
            return exp_dates[0][0]
            
        except Exception as e:
            logger.error(f"Error in smart expiration selection: {e}")
            return self._get_fallback_expiration(est_now)
    
    def _get_fallback_expiration(self, est_now: datetime) -> str:
        """Fallback expiration logic when no available expirations are known"""
        try:
            # Original logic as fallback
            if est_now.hour < 12:
                # Use same day expiration
                expiration_date = est_now.date()
            else:
                # Use next business day expiration
                expiration_date = est_now.date() + timedelta(days=1)
                # Skip weekends
                while expiration_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    expiration_date += timedelta(days=1)
            
            # Format as YYYYMMDD
            expiration_str = expiration_date.strftime("%Y%m%d")
            logger.info(f"Fallback expiration calculated: {expiration_str}")
            return expiration_str
            
        except Exception as e:
            logger.error(f"Error calculating fallback expiration: {e}")
            # Final fallback to next day
            tomorrow = est_now.date() + timedelta(days=1)
            return tomorrow.strftime("%Y%m%d")
    
    def _create_option_contract(self, option_type: str, strike: float) -> Option:
        """Create an option contract"""
        try:
            expiration = self._get_contract_expiration()
            
            contract = Option(
                symbol=self.underlying_symbol,
                exchange="SMART",
                currency="USD",
                lastTradingDay=expiration,
                strike=strike,
                right=option_type.upper(),  # "C" for call, "P" for put
                multiplier="100"
            )
            
            logger.info(f"Created {option_type} option contract: {self.underlying_symbol} {strike} {expiration}")
            return contract
            
        except Exception as e:
            logger.error(f"Error creating option contract: {e}")
            raise

    def _create_stock_contract(self, symbol: str):
        """Create a stock contract for the given symbol"""
        try:
            from ib_async import Stock
            contract = Stock(symbol, 'SMART', 'USD')
            logger.info(f"Created stock contract for {symbol}")
            return contract
        except Exception as e:
            logger.error(f"Error creating stock contract for {symbol}: {e}")
            return None
    
    def _create_adaptive_order(self, action: str, quantity: int, price: float = None) -> Order:
        """Create an order using Interactive Brokers' Adaptive Algo (IBALGO)"""
        try:
            if action.upper() == "BUY":
                order = Order(
                    action="BUY",
                    totalQuantity=quantity,
                    orderType="MKT"  # Market order for immediate execution
                )
            elif action.upper() == "SELL":
                if price:
                    # Limit order for sell
                    order = Order(
                        action="SELL",
                        totalQuantity=quantity,
                        orderType="LMT",
                        lmtPrice=price
                    )
                else:
                    # Market order for sell
                    order = Order(
                        action="SELL",
                        totalQuantity=quantity,
                        orderType="MKT"
                    )
            else:
                raise ValueError(f"Invalid action: {action}")
            
            logger.info(f"Created {action} order: {quantity} contracts at {price if price else 'market'}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating adaptive order: {e}")
            raise
    
    async def place_buy_order(self, option_type: str) -> bool:
        """Place a BUY order for the specified option type"""
        try:
            # Validate option type
            if option_type.upper() not in ["CALL", "PUT"]:
                logger.error(f"Invalid option type: {option_type}")
                return False
            
            # Check for existing positions (one active position rule)
            with self._position_lock:
                if self._active_positions:
                    logger.warning("One active position rule: Cannot place new order while position exists")
                    return False
            
            # Get current option data
            option_data = self._current_call_option if option_type.upper() == "CALL" else self._current_put_option
            if not option_data:
                logger.error(f"No {option_type} option data available")
                return False
            
            # Get option price and calculate quantity
            option_price = option_data.get("Ask", 0)
            if option_price <= 0:
                logger.error(f"Invalid {option_type} option price: {option_price}")
                return False
            
            quantity = self._calculate_order_quantity(option_price)
            
            # Create contract and order
            strike = option_data.get("Strike", self._underlying_price)
            contract = self._create_option_contract(option_type, strike)
            order = self._create_adaptive_order("BUY", quantity)
            
            # Submit order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait for order status
            await asyncio.sleep(1)
            
            if trade.orderStatus.status == "Submitted":
                logger.info(f"BUY {option_type} order submitted: {quantity} contracts at ${option_price:.2f}")
                
                # Track the order
                with self._order_lock:
                    self._open_orders[trade.order.orderId] = {
                        'trade': trade,
                        'contract': contract,
                        'order': order,
                        'type': 'BUY',
                        'option_type': option_type,
                        'quantity': quantity,
                        'price': option_price
                    }
                
                return True
            else:
                logger.error(f"BUY {option_type} order failed: {trade.orderStatus.status}")
                return False
                
        except Exception as e:
            logger.error(f"Error placing BUY {option_type} order: {e}")
            return False
    
    async def place_sell_order(self, use_chase_logic: bool = True) -> bool:
        """Place a SELL order for any open position using chase logic if specified"""
        try:
            # Get current positions
            with self._position_lock:
                if not self._active_positions:
                    logger.warning("No active positions to sell")
                    return False
                
                positions = list(self._active_positions.values())
            
            # For now, sell the first position (should be the only one due to one active position rule)
            position = positions[0]
            symbol = position['symbol']
            quantity = position.get('position_size', 0)  # Use position_size instead of quantity
            
            # Validate quantity
            if quantity <= 0:
                logger.error(f"Invalid position quantity: {quantity}")
                return False
            
            logger.info(f"Processing sell order for position: {symbol}, quantity: {quantity}, type: {position.get('position_type', 'UNKNOWN')}")
            
            # Apply runner logic if profitable
            if position.get('pnl_percent', 0) > 0 and self.runner > 0:
                sell_quantity = max(1, quantity - self.runner)
                logger.info(f"Runner logic: Selling {sell_quantity} of {quantity} contracts (keeping {self.runner} as runner)")
            else:
                sell_quantity = quantity
            
            # Get current pricing data for the position
            pricing_data = None
            if "CALL" in symbol.upper():
                pricing_data = self._current_call_option
            elif "PUT" in symbol.upper():
                pricing_data = self._current_put_option
            else:
                # For stock positions, use underlying price as reference
                pricing_data = {"Bid": self._underlying_price * 0.999, "Ask": self._underlying_price * 1.001}
            
            if not pricing_data:
                logger.error("No pricing data available for position")
                return False
            
            # Calculate sell price
            bid_price = pricing_data.get("Bid", 0)
            ask_price = pricing_data.get("Ask", 0)
            mid_price = (bid_price + ask_price) / 2
            
            if use_chase_logic:
                # Chase logic: Start with limit order at (midpoint - trade_delta)
                limit_price = mid_price - self.trade_delta
                order = self._create_adaptive_order("SELL", sell_quantity, limit_price)
                
                # Create contract (reuse from position if available)
                contract = position.get('contract')
                logger.info(f"Position contract: {contract}, type: {type(contract)}")
                
                # Validate contract object
                if not contract or not hasattr(contract, 'symbol'):
                    logger.warning("Invalid contract object from position, attempting to recreate")
                    if "CALL" in symbol.upper() or "PUT" in symbol.upper():
                        # Option contract
                        strike = pricing_data.get("Strike", self._underlying_price)
                        option_type = "CALL" if "CALL" in symbol.upper() else "PUT"
                        contract = self._create_option_contract(option_type, strike)
                    else:
                        # Stock contract - create stock contract
                        contract = self._create_stock_contract(symbol)
                        if not contract:
                            logger.error(f"Failed to create stock contract for {symbol}")
                            return False
                
                # Submit limit order
                logger.info(f"Submitting limit order: {sell_quantity} contracts at ${limit_price:.2f}")
                trade = self.ib.placeOrder(contract, order)
                
                # Track for chase logic
                with self._order_lock:
                    self._chase_orders[trade.order.orderId] = {
                        'trade': trade,
                        'contract': contract,
                        'original_quantity': sell_quantity,
                        'remaining_quantity': sell_quantity,
                        'start_time': time.time(),
                        'limit_price': limit_price
                    }
                
                # Start chase monitoring
                self._start_chase_monitoring()
                
                logger.info(f"SELL order submitted with chase logic: {sell_quantity} contracts at ${limit_price:.2f}")
                return True
            else:
                # Direct market order
                order = self._create_adaptive_order("SELL", sell_quantity)
                
                # Create contract
                contract = position.get('contract')
                logger.info(f"Position contract: {contract}, type: {type(contract)}")
                
                # Validate contract object
                if not contract or not hasattr(contract, 'symbol'):
                    logger.warning("Invalid contract object from position, attempting to recreate")
                    if "CALL" in symbol.upper() or "PUT" in symbol.upper():
                        # Option contract
                        strike = pricing_data.get("Strike", self._underlying_price)
                        option_type = "CALL" if "CALL" in symbol.upper() else "PUT"
                        contract = self._create_option_contract(option_type, strike)
                    else:
                        # Stock contract - create stock contract
                        contract = self._create_stock_contract(symbol)
                        if not contract:
                            logger.error(f"Failed to create stock contract for {symbol}")
                            return False
                
                # Submit market order
                logger.info(f"Submitting market order: {sell_quantity} contracts")
                trade = self.ib.placeOrder(contract, order)
                
                logger.info(f"SELL order submitted: {sell_quantity} contracts at market")
                return True
                
        except Exception as e:
            logger.error(f"Error placing SELL order: {e}")
            return False
    
    async def panic_button(self) -> bool:
        """Panic button: Flatten all risk for the underlying"""
        try:
            logger.warning("PANIC BUTTON ACTIVATED - Flattening all risk")
            
            # Step 1: Place Market Order to sell 100% of any open options position
            sell_success = await self.place_sell_order(use_chase_logic=False)
            
            # Step 2: Cancel all other open orders for the underlying
            await self._cancel_all_orders()
            
            logger.info("Panic button execution completed")
            return sell_success
            
        except Exception as e:
            logger.error(f"Error executing panic button: {e}")
            return False
    
    async def _cancel_all_orders(self):
        """Cancel all open orders for the underlying"""
        try:
            with self._order_lock:
                orders_to_cancel = list(self._open_orders.keys())
            
            for order_id in orders_to_cancel:
                try:
                    self.ib.cancelOrder(order_id)
                    logger.info(f"Cancelled order {order_id}")
                except Exception as e:
                    logger.error(f"Error cancelling order {order_id}: {e}")
            
            # Clear chase orders
            with self._order_lock:
                self._chase_orders.clear()
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
    
    def _start_chase_monitoring(self):
        """Start monitoring chase orders"""
        if self._chase_thread and self._chase_thread.is_alive():
            return
        
        self._stop_chase.clear()
        self._chase_thread = Thread(target=self._chase_monitor_loop, daemon=True)
        self._chase_thread.start()
    
    def _chase_monitor_loop(self):
        """Monitor chase orders and convert to market orders after 10 seconds"""
        while not self._stop_chase.is_set():
            try:
                current_time = time.time()
                orders_to_convert = []
                
                with self._order_lock:
                    for order_id, chase_data in self._chase_orders.items():
                        if current_time - chase_data['start_time'] >= 10:  # 10 seconds
                            orders_to_convert.append(order_id)
                
                # Convert orders to market orders
                for order_id in orders_to_convert:
                    asyncio.run(self._convert_to_market_order(order_id))
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in chase monitor loop: {e}")
                time.sleep(1)
    
    async def _convert_to_market_order(self, order_id: int):
        """Convert a limit order to a market order"""
        try:
            with self._order_lock:
                if order_id not in self._chase_orders:
                    return
                
                chase_data = self._chase_orders[order_id]
                remaining_quantity = chase_data['remaining_quantity']
            
            if remaining_quantity <= 0:
                return
            
            # Cancel the original limit order
            try:
                self.ib.cancelOrder(order_id)
                logger.info(f"Cancelled limit order {order_id} for chase logic")
            except Exception as e:
                logger.error(f"Error cancelling limit order {order_id}: {e}")
            
            # Create and submit market order
            market_order = self._create_adaptive_order("SELL", remaining_quantity)
            trade = self.ib.placeOrder(chase_data['contract'], market_order)
            
            logger.info(f"Converted to market order: {remaining_quantity} contracts")
            
            # Remove from chase orders
            with self._order_lock:
                self._chase_orders.pop(order_id, None)
            
        except Exception as e:
            logger.error(f"Error converting to market order: {e}")
    
    def update_position(self, position_data: Dict[str, Any]):
        """Update position information"""
        try:
            with self._position_lock:
                symbol = position_data.get('symbol')
                if symbol:
                    self._active_positions[symbol] = position_data
                    logger.info(f"Position updated: {symbol}")
                else:
                    logger.warning("Position data missing symbol")
        except Exception as e:
            logger.error(f"Error updating position: {e}")
    
    def clear_position(self, symbol: str):
        """Clear a position"""
        try:
            with self._position_lock:
                if symbol in self._active_positions:
                    del self._active_positions[symbol]
                    logger.info(f"Position cleared: {symbol}")
        except Exception as e:
            logger.error(f"Error clearing position: {e}")
    
    def get_active_positions(self) -> Dict[str, Any]:
        """Get current active positions"""
        with self._position_lock:
            return self._active_positions.copy()
    
    def get_open_orders(self) -> Dict[str, Any]:
        """Get current open orders"""
        with self._order_lock:
            return self._open_orders.copy()
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self._stop_chase.set()
            if self._chase_thread and self._chase_thread.is_alive():
                self._chase_thread.join(timeout=5)
            
            logger.info("Trading Manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during trading manager cleanup: {e}")

    def manual_expiration_switch(self, target_expiration: str = None) -> bool:
        """Manually trigger expiration switching to a specific expiration or best available"""
        try:
            if hasattr(self, 'data_collector') and self.data_collector:
                if hasattr(self.data_collector, 'collector') and self.data_collector.collector:
                    if hasattr(self.data_collector.collector, 'ib_connection'):
                        ib_connection = self.data_collector.collector.ib_connection
                        if hasattr(ib_connection, 'manual_expiration_switch'):
                            return ib_connection.manual_expiration_switch(target_expiration)
                        else:
                            logger.error("IB connection doesn't have manual_expiration_switch method")
                    else:
                        logger.error("No IB connection available")
                else:
                    logger.error("No collector available")
            else:
                logger.error("No data collector available")
            
            return False
            
        except Exception as e:
            logger.error(f"Error in trading manager manual expiration switch: {e}")
            return False
    
    def get_expiration_status(self) -> Dict[str, Any]:
        """Get detailed expiration status for monitoring"""
        try:
            if hasattr(self, 'data_collector') and self.data_collector:
                if hasattr(self.data_collector, 'collector') and self.data_collector.collector:
                    if hasattr(self.data_collector.collector, 'ib_connection'):
                        ib_connection = self.data_collector.collector.ib_connection
                        if hasattr(ib_connection, 'get_expiration_status'):
                            return ib_connection.get_expiration_status()
                        else:
                            logger.error("IB connection doesn't have get_expiration_status method")
                    else:
                        logger.error("No IB connection available")
                else:
                    logger.error("No collector available")
            else:
                logger.error("No data collector available")
            
            return {'error': 'No IB connection available'}
            
        except Exception as e:
            logger.error(f"Error in trading manager get_expiration_status: {e}")
            return {'error': str(e)}
