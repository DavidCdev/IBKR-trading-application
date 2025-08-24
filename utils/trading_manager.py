import asyncio
from typing import Dict, Any, List
from ib_async import IB, Option, Order
from datetime import datetime, timedelta
import pytz
from threading import Thread, Event, Lock
import time
from .logger import get_logger

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
        self._config_lock = Lock()
        
        # Chase logic tracking
        self._chase_orders = {}  # {order_id: chase_data}
        self._chase_timer = None
        self._chase_thread = None
        self._stop_chase = Event()
        
        # Bracket order tracking for risk management
        self._bracket_orders = {}  # {parent_order_id: {stop_loss_id, take_profit_id, contract, quantity}}
        self._bracket_lock = Lock()
        
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
        
        # Last action message for UI notifications
        self._last_action_message = ""
        # Optional UI notify callback set by UI layer (callable: (message: str, success: bool) -> None)
        self.ui_notify = None
        
        logger.info("Trading Manager initialized")
    
    def update_trading_config(self, trading_config: Dict[str, Any]):
        """Update trading configuration at runtime so calculations reflect GUI changes immediately"""
        try:
            if not trading_config:
                return
            with self._config_lock:
                # Detect underlying symbol change before mutating config
                try:
                    incoming_symbol = None
                    if isinstance(trading_config, dict):
                        incoming_symbol = trading_config.get('underlying_symbol')
                    symbol_changed = (
                        incoming_symbol is not None and str(incoming_symbol) != str(getattr(self, 'underlying_symbol', ''))
                    )
                except Exception:
                    symbol_changed = False

                # Merge dict and refresh derived attributes
                if isinstance(self.trading_config, dict):
                    self.trading_config.update(trading_config)
                else:
                    self.trading_config = dict(trading_config)

                self.underlying_symbol = self.trading_config.get('underlying_symbol', self.underlying_symbol)
                self.trade_delta = self.trading_config.get('trade_delta', self.trade_delta)
                self.max_trade_value = self.trading_config.get('max_trade_value', self.max_trade_value)
                self.runner = self.trading_config.get('runner', self.runner)
                self.risk_levels = self.trading_config.get('risk_levels', self.risk_levels) or []

                # If the underlying symbol changed, clear cached market-data to avoid stale orders
                if symbol_changed:
                    try:
                        self._current_call_option = None
                        self._current_put_option = None
                        self._underlying_price = 0
                        # Clear any locally cached expirations so fresh ones are requested
                        if hasattr(self, '_local_available_expirations'):
                            self._local_available_expirations = []
                        # Drop any tracked positions that don't match the new underlying
                        try:
                            with self._position_lock:
                                symbols_to_remove = []
                                for pos_symbol, pos in self._active_positions.items():
                                    try:
                                        contract_obj = pos.get('contract') if isinstance(pos, dict) else None
                                        contract_symbol = getattr(contract_obj, 'symbol', None)
                                        # Match either by explicit contract symbol or by stored symbol prefix
                                        matches_new_underlying = (
                                            (contract_symbol == self.underlying_symbol) or
                                            (isinstance(pos_symbol, str) and (
                                                pos_symbol == self.underlying_symbol or pos_symbol.startswith(f"{self.underlying_symbol} ")
                                            ))
                                        )
                                        if not matches_new_underlying:
                                            symbols_to_remove.append(pos_symbol)
                                    except Exception:
                                        symbols_to_remove.append(pos_symbol)
                                for sym in symbols_to_remove:
                                    self._active_positions.pop(sym, None)
                                if symbols_to_remove:
                                    logger.info(f"Removed {len(symbols_to_remove)} positions not matching new underlying '{self.underlying_symbol}'")
                        except Exception as pos_err:
                            logger.warning(f"Error pruning positions on symbol change: {pos_err}")
                        logger.info(
                            f"Underlying symbol changed. Cleared cached market data to wait for fresh '{self.underlying_symbol}' updates"
                        )
                    except Exception as clear_err:
                        logger.warning(f"Error clearing cached market data on symbol change: {clear_err}")

            logger.info(
                f"Trading config updated: symbol={self.underlying_symbol}, symbol_price: {self._underlying_price}, trade_delta={self.trade_delta}, "
                f"max_trade_value={self.max_trade_value}, runner={self.runner}, tiers={len(self.risk_levels)}"
            )
        except Exception as e:
            logger.error(f"Error updating trading config: {e}")

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
            logger.info(f"Trading manager updating account value: {self._account_value} -> {account_value}")
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
            with self._config_lock:
                gui_max_value = self.max_trade_value
            logger.info(f"GUI Max Trade Value: {gui_max_value}")
            # Step 2: Tiered Risk Limit
            tiered_max_value = self._calculate_tiered_risk_limit()
            logger.info(f"Tiered Max Trade Value: {tiered_max_value}")
            # Step 3: PDT Buffer
            pdt_max_value = self._calculate_pdt_buffer()
            logger.info(f"PDT Max Trade Value: {pdt_max_value}")
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
            with self._config_lock:
                risk_levels_snapshot = list(self.risk_levels) if self.risk_levels else []

            for risk_level in risk_levels_snapshot:
                loss_threshold = float(risk_level.get('loss_threshold', 0))
                account_trade_limit = float(risk_level.get('account_trade_limit', 100))
                
                if current_pnl_percent >= loss_threshold:
                    # Calculate trade limit as percentage of account value
                    if self._account_value > 0:
                        max_trade_value = (account_trade_limit / 100) * self._account_value
                        logger.info(f"Tiered risk limit: PnL={current_pnl_percent}%, Threshold={loss_threshold}%, Limit={account_trade_limit}%, MaxValue=${max_trade_value:.2f}")
                        return max_trade_value
                    else:
                        logger.warning(f"Account value is {self._account_value}, cannot calculate tiered risk limit")
                        return 0.0
            
            # Default to GUI max trade value if no risk level matches
            with self._config_lock:
                return self.max_trade_value
            
        except Exception as e:
            logger.error(f"Error calculating tiered risk limit: {e}")
            return self.max_trade_value
    
    def _calculate_pdt_buffer(self) -> float:
        """Calculate buffer to stay above PDT minimum equity requirement"""
        try:
            # Determine currency and minimum requirement
            with self._config_lock:
                account_currency = (self.account_config or {}).get('currency', 'USD')
            currency_upper = str(account_currency).upper()
            pdt_minimum = self._pdt_minimum_cad if currency_upper == 'CAD' else self._pdt_minimum_usd
            
            # Check if account value is valid
            if self._account_value <= 0:
                logger.warning(f"Account value is {self._account_value}, cannot calculate PDT buffer")
                return 0.0
            
            # Calculate available buffer
            available_buffer = self._account_value - pdt_minimum
            
            # Use 80% of available buffer as safety margin
            safe_buffer = available_buffer * 0.8
            
            logger.info(f"PDT buffer calculation ({currency_upper}): Account=${self._account_value:.2f}, Min=${pdt_minimum}, Available=${available_buffer:.2f}, Safe=${safe_buffer:.2f}")
            
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
            # Validate strike price
            if not isinstance(strike, (int, float)) or strike <= 0:
                raise ValueError(f"Invalid strike price: {strike}. Strike must be a positive number.")
            
            # Ensure strike is a valid option strike (whole number for most liquid options)
            valid_strike = int(round(strike))
            if valid_strike != strike:
                logger.warning(f"Strike price adjusted from {strike} to {valid_strike} for valid option contract")
            
            expiration = self._get_contract_expiration()

            contract = Option(
                symbol=self.underlying_symbol,
                exchange="SMART",
                currency="USD",
                lastTradeDateOrContractMonth=expiration,  # e.g. '20250117'
                strike=valid_strike,
                right='C' if option_type.upper() == 'CALL' else 'P',
                multiplier="100"
            )
            
            logger.info(f"Created {option_type} option contract: {self.underlying_symbol} {valid_strike} {expiration}")
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
                # Apply IB Adaptive Algo (IBALGO) with "Normal" urgency for BUY orders
                try:
                    # Try IB API TagValue first
                    from ibapi.tag_value import TagValue  # type: ignore
                    setattr(order, 'algoStrategy', 'Adaptive')
                    setattr(order, 'algoParams', [TagValue("adaptivePriority", "Normal")])
                except Exception:
                    # Fallback to generic structure if TagValue is unavailable in this environment
                    try:
                        setattr(order, 'algoStrategy', 'Adaptive')
                        setattr(order, 'algoParams', [{"tag": "adaptivePriority", "value": "Normal"}])
                    except Exception as e2:
                        logger.warning(f"Could not set IB Adaptive Algo parameters: {e2}")
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
                self._last_action_message = f"Invalid option type: {option_type}"
                return False
            
            # Check for existing positions (one active position rule)
            with self._position_lock:
                if self._active_positions:
                    logger.warning("One active position rule: Cannot place new order while position exists")
                    self._last_action_message = "Cannot BUY: an active position already exists. Close or sell the current position first."
                    return False
            
            # Get current option data
            option_data = self._current_call_option if option_type.upper() == "CALL" else self._current_put_option
            if not option_data:
                logger.error(f"No {option_type} option data available")
                self._last_action_message = f"Cannot BUY {option_type}: option data unavailable."
                return False
            
            # Get option price and calculate quantity
            option_price = option_data.get("Ask", 0)
            if option_price <= 0:
                logger.error(f"Invalid {option_type} option price: {option_price}")
                self._last_action_message = f"Cannot BUY {option_type}: invalid ask price ({option_price})."
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
                self._last_action_message = f"BUY {option_type} submitted: {quantity} contracts at ${option_price:.2f}."
                
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
                
                # Place bracket orders for risk management
                await self._place_bracket_orders(trade.order.orderId, contract, quantity, option_price, option_type)
                
                return True
            else:
                logger.error(f"BUY {option_type} order failed: {trade.orderStatus.status}")
                try:
                    status_text = str(trade.orderStatus.status)
                except Exception:
                    status_text = "Unknown"
                self._last_action_message = f"BUY {option_type} failed: status={status_text}."
                return False
                
        except Exception as e:
            logger.error(f"Error placing BUY {option_type} order: {e}")
            self._last_action_message = f"BUY {option_type} error: {str(e)}"
            return False
    
    async def place_sell_order(self, use_chase_logic: bool = True) -> bool:
        """Place a SELL order for any open position using chase logic if specified"""
        try:
            # Get current positions
            with self._position_lock:
                if not self._active_positions:
                    logger.warning("No active positions to sell")
                    self._last_action_message = "Cannot SELL: no active positions."
                    return False
                
                # Filter positions to the current underlying symbol only
                filtered_positions = []
                for pos in self._active_positions.values():
                    try:
                        contract_obj = pos.get('contract') if isinstance(pos, dict) else None
                        contract_symbol = getattr(contract_obj, 'symbol', None)
                        pos_symbol_str = str(pos.get('symbol', '')) if isinstance(pos, dict) else ''
                        # Match by contract symbol when available, else by symbol string prefix
                        matches_underlying = False
                        if contract_symbol:
                            matches_underlying = (contract_symbol == self.underlying_symbol)
                        else:
                            # Accept exact match or prefix like "SPY CALL" / "SPY PUT"
                            matches_underlying = (
                                pos_symbol_str == self.underlying_symbol or pos_symbol_str.startswith(f"{self.underlying_symbol} ")
                            )
                        if matches_underlying:
                            filtered_positions.append(pos)
                    except Exception:
                        continue

                if not filtered_positions:
                    logger.warning(f"No active positions found for current underlying {self.underlying_symbol}")
                    self._last_action_message = f"Cannot SELL: no active positions for {self.underlying_symbol}."
                    return False
                
                positions = filtered_positions
            
            # For now, sell the first matching position (should typically be the only one)
            position = positions[0]
            symbol = position['symbol']
            quantity = position.get('position_size', 0)  # Use position_size instead of quantity
            
            # Validate quantity
            if quantity <= 0:
                logger.error(f"Invalid position quantity: {quantity}")
                self._last_action_message = f"Cannot SELL: invalid position quantity ({quantity})."
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
            try:
                contract_obj = position.get('contract')
                sec_type = getattr(contract_obj, 'secType', '').upper() if contract_obj else ''
                right = getattr(contract_obj, 'right', '').upper() if contract_obj else ''
                if sec_type == 'OPT':
                    if right == 'C':
                        pricing_data = self._current_call_option
                    elif right == 'P':
                        pricing_data = self._current_put_option
                # Fallbacks based on symbol string if contract info missing
                if pricing_data is None:
                    if "CALL" in symbol.upper():
                        pricing_data = self._current_call_option
                    elif "PUT" in symbol.upper():
                        pricing_data = self._current_put_option
                # Stock pricing fallback
                if pricing_data is None:
                    pricing_data = {"Bid": self._underlying_price * 0.999, "Ask": self._underlying_price * 1.001}
            except Exception:
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
                self._last_action_message = f"SELL submitted (chase): {sell_quantity} contracts at ${limit_price:.2f}."
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
                self._last_action_message = f"SELL submitted: {sell_quantity} contracts at market."
                return True
                
        except Exception as e:
            logger.error(f"Error placing SELL order: {e}")
            self._last_action_message = f"SELL error: {str(e)}"
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
            self._last_action_message = (
                "PANIC executed: submitted market sell for all positions and cancelled remaining orders."
                if sell_success else
                "PANIC attempted but no active positions were found. All open orders cancelled."
            )
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
                    # Retrieve the actual Order/Trade object for cancellation
                    with self._order_lock:
                        order_data = self._open_orders.get(order_id)
                        order_obj = None
                        if order_data:
                            if order_data.get('order'):
                                order_obj = order_data['order']
                            elif order_data.get('trade'):
                                order_obj = order_data['trade'].order

                    if order_obj:
                        self.ib.cancelOrder(order_obj)
                        logger.info(f"Cancelled order {order_id}")
                    else:
                        logger.warning(f"No order object found for order {order_id}; skipping cancel")
                    
                    # Cancel associated bracket orders
                    await self._cancel_bracket_orders(order_id)
                    
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
                self.ib.cancelOrder(chase_data['trade'].order)
                logger.info(f"Cancelled limit order {order_id} for chase logic")
            except Exception as e:
                logger.error(f"Error cancelling limit order {order_id}: {e}")
            
            # Create and submit market order
            market_order = self._create_adaptive_order("SELL", remaining_quantity)
            trade = self.ib.placeOrder(chase_data['contract'], market_order)
            
            logger.info(f"Converted to market order: {remaining_quantity} contracts")
            self._last_action_message = (
                f"SELL order converted to MARKET after 10s: {remaining_quantity} contracts (order {order_id})."
            )
            try:
                if callable(self.ui_notify):
                    self.ui_notify(self._last_action_message, True)
            except Exception as notify_err:
                logger.warning(f"UI notify callback error: {notify_err}")
            
            # Remove from chase orders
            with self._order_lock:
                self._chase_orders.pop(order_id, None)
            
        except Exception as e:
            logger.error(f"Error converting to market order: {e}")
    
    async def _place_bracket_orders(self, parent_order_id: int, contract, quantity: int, entry_price: float, option_type: str):
        """Place bracket orders (stop loss and take profit) for risk management"""
        try:
            # Get current risk level based on daily P&L
            current_risk_level = self._get_current_risk_level()
            if not current_risk_level:
                logger.warning("No risk level found, skipping bracket orders")
                return
            
            stop_loss_percent = current_risk_level.get('stop_loss')
            profit_gain_percent = current_risk_level.get('profit_gain')
            
            # If both are empty, no bracket orders needed
            if not stop_loss_percent and not profit_gain_percent:
                logger.info("No stop loss or profit gain configured, skipping bracket orders")
                return
            
            logger.info(f"Placing bracket orders for {option_type}: Stop Loss={stop_loss_percent}%, Profit Gain={profit_gain_percent}%")
            
            bracket_orders = {}
            stop_loss_order = None
            take_profit_order = None
            
            # Build orders (do not transmit yet) so we can set OCA if needed
            if stop_loss_percent:
                stop_loss_price = self._calculate_stop_loss_price(entry_price, float(stop_loss_percent), option_type)
                stop_loss_order = self._create_stop_loss_order(quantity, stop_loss_price)
            if profit_gain_percent:
                take_profit_price = self._calculate_take_profit_price(entry_price, float(profit_gain_percent), option_type)
                take_profit_order = self._create_take_profit_order(quantity, take_profit_price)
            
            # If both exist, set OCA group so that one cancels the other at broker side
            if stop_loss_order and take_profit_order:
                oca_group = f"OCA_{parent_order_id}"
                try:
                    setattr(stop_loss_order, 'ocaGroup', oca_group)
                    setattr(take_profit_order, 'ocaGroup', oca_group)
                    # 1 = Cancel with block (typical OCO behavior)
                    setattr(stop_loss_order, 'ocaType', 1)
                    setattr(take_profit_order, 'ocaType', 1)
                except Exception as e:
                    logger.warning(f"Could not set OCA group on bracket orders: {e}")
            
            # Place orders that are configured
            if stop_loss_order:
                stop_loss_trade = self.ib.placeOrder(contract, stop_loss_order)
                bracket_orders['stop_loss_id'] = stop_loss_trade.order.orderId
                bracket_orders['stop_loss_trade'] = stop_loss_trade
                logger.info(f"Stop loss order placed: {quantity} contracts at ${stop_loss_price:.2f}")
            if take_profit_order:
                take_profit_trade = self.ib.placeOrder(contract, take_profit_order)
                bracket_orders['take_profit_id'] = take_profit_trade.order.orderId
                bracket_orders['take_profit_trade'] = take_profit_trade
                logger.info(f"Take profit order placed: {quantity} contracts at ${take_profit_price:.2f}")
            
            # Store bracket order information
            if bracket_orders:
                with self._bracket_lock:
                    self._bracket_orders[parent_order_id] = {
                        **bracket_orders,
                        'contract': contract,
                        'quantity': quantity,
                        'entry_price': entry_price,
                        'option_type': option_type
                    }
                logger.info(f"Bracket orders created for parent order {parent_order_id}")
            
        except Exception as e:
            logger.error(f"Error placing bracket orders: {e}")
    
    def _get_current_risk_level(self) -> Dict[str, Any]:
        """Get the current risk level based on daily P&L"""
        try:
            current_pnl_percent = abs(self._daily_pnl_percent)
            with self._config_lock:
                risk_levels_snapshot = list(self.risk_levels) if self.risk_levels else []

            for risk_level in risk_levels_snapshot:
                loss_threshold = float(risk_level.get('loss_threshold', 0))
                
                if current_pnl_percent >= loss_threshold:
                    logger.info(f"Selected risk level: PnL={current_pnl_percent}%, Threshold={loss_threshold}%")
                    return risk_level
            
            # Return first risk level as default
            if risk_levels_snapshot:
                logger.info("Using default risk level")
                return risk_levels_snapshot[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current risk level: {e}")
            return None
    
    def _calculate_stop_loss_price(self, entry_price: float, stop_loss_percent: float, option_type: str) -> float:
        """Calculate stop loss price based on entry price and percentage"""
        try:
            # For options, stop loss is a percentage decrease from entry price
            stop_loss_price = entry_price * (1 - stop_loss_percent / 100)
            
            # Ensure minimum price
            stop_loss_price = max(0.01, stop_loss_price)
            
            logger.info(f"Stop loss calculation: Entry=${entry_price:.2f}, Loss={stop_loss_percent}%, Stop=${stop_loss_price:.2f}")
            return stop_loss_price
            
        except Exception as e:
            logger.error(f"Error calculating stop loss price: {e}")
            return entry_price * 0.8  # Default to 20% loss
    
    def _calculate_take_profit_price(self, entry_price: float, profit_gain_percent: float, option_type: str) -> float:
        """Calculate take profit price based on entry price and percentage"""
        try:
            # For options, take profit is a percentage increase from entry price
            take_profit_price = entry_price * (1 + profit_gain_percent / 100)
            
            logger.info(f"Take profit calculation: Entry=${entry_price:.2f}, Gain={profit_gain_percent}%, Target=${take_profit_price:.2f}")
            return take_profit_price
            
        except Exception as e:
            logger.error(f"Error calculating take profit price: {e}")
            return entry_price * 1.2  # Default to 20% gain
    
    def _create_stop_loss_order(self, quantity: int, stop_loss_price: float) -> Order:
        """Create a stop loss order"""
        try:
            order = Order(
                action="SELL",
                totalQuantity=quantity,
                orderType="STP",
                auxPrice=stop_loss_price,
                tif="GTC"
            )
            
            logger.info(f"Created stop loss order: {quantity} contracts at ${stop_loss_price:.2f}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating stop loss order: {e}")
            raise
    
    def _create_take_profit_order(self, quantity: int, take_profit_price: float) -> Order:
        """Create a take profit order"""
        try:
            order = Order(
                action="SELL",
                totalQuantity=quantity,
                orderType="LMT",
                lmtPrice=take_profit_price,
                tif="GTC"  # Good Till Cancelled
            )
            
            logger.info(f"Created take profit order: {quantity} contracts at ${take_profit_price:.2f}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating take profit order: {e}")
            raise
    
    async def _cancel_bracket_orders(self, parent_order_id: int):
        """Cancel bracket orders associated with a parent order"""
        try:
            with self._bracket_lock:
                if parent_order_id not in self._bracket_orders:
                    return
                
                bracket_data = self._bracket_orders[parent_order_id]
            
            # Cancel stop loss order
            if 'stop_loss_id' in bracket_data:
                try:
                    if 'stop_loss_trade' in bracket_data:
                        self.ib.cancelOrder(bracket_data['stop_loss_trade'].order)
                        logger.info(f"Cancelled stop loss order {bracket_data['stop_loss_id']}")
                    else:
                        logger.warning("Stop loss trade object not available; cannot cancel by id")
                except Exception as e:
                    logger.error(f"Error cancelling stop loss order: {e}")
            
            # Cancel take profit order
            if 'take_profit_id' in bracket_data:
                try:
                    if 'take_profit_trade' in bracket_data:
                        self.ib.cancelOrder(bracket_data['take_profit_trade'].order)
                        logger.info(f"Cancelled take profit order {bracket_data['take_profit_id']}")
                    else:
                        logger.warning("Take profit trade object not available; cannot cancel by id")
                except Exception as e:
                    logger.error(f"Error cancelling take profit order: {e}")
            
            # Remove from tracking
            with self._bracket_lock:
                self._bracket_orders.pop(parent_order_id, None)
            
            logger.info(f"Bracket orders cancelled for parent order {parent_order_id}")
            
        except Exception as e:
            logger.error(f"Error cancelling bracket orders: {e}")
    
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
    
    def get_bracket_orders(self) -> Dict[str, Any]:
        """Get current bracket orders"""
        with self._bracket_lock:
            return self._bracket_orders.copy()
    
    def get_risk_management_status(self) -> Dict[str, Any]:
        """Get current risk management status"""
        try:
            current_risk_level = self._get_current_risk_level()
            active_brackets = len(self._bracket_orders)
            
            return {
                'current_risk_level': current_risk_level,
                'active_bracket_orders': active_brackets,
                'daily_pnl_percent': self._daily_pnl_percent,
                'account_value': self._account_value
            }
            
        except Exception as e:
            logger.error(f"Error getting risk management status: {e}")
            return {'error': str(e)}
    
    def handle_order_fill(self, order_id: int, filled_quantity: int, fill_price: float):
        """Handle order fill events and manage bracket orders accordingly"""
        try:
            logger.info(f"Order fill event: Order {order_id}, Quantity {filled_quantity}, Price ${fill_price:.2f}")
            
            # Check if this is a bracket order fill
            with self._bracket_lock:
                for parent_id, bracket_data in self._bracket_orders.items():
                    if bracket_data.get('stop_loss_id') == order_id:
                        logger.info(f"Stop loss order {order_id} filled - cancelling take profit order")
                        self._cancel_remaining_bracket_order(parent_id, 'take_profit_id')
                        return
                    elif bracket_data.get('take_profit_id') == order_id:
                        logger.info(f"Take profit order {order_id} filled - cancelling stop loss order")
                        self._cancel_remaining_bracket_order(parent_id, 'stop_loss_id')
                        return
            
            # Check if this is a primary order fill
            with self._order_lock:
                if order_id in self._open_orders:
                    order_data = self._open_orders[order_id]
                    if order_data['type'] == 'BUY':
                        logger.info(f"Primary BUY order {order_id} filled - position opened")
                        # The bracket orders are already in place from when the order was submitted
                        # Just update the position tracking
                        self._update_position_from_fill(order_data, filled_quantity, fill_price)
                    elif order_data['type'] == 'SELL':
                        logger.info(f"Primary SELL order {order_id} filled - position closed")
                        # Cancel any remaining bracket orders
                        asyncio.run(self._cancel_bracket_orders(order_id))
                        # Clear any chase tracking for this order if present
                        if order_id in self._chase_orders:
                            self._chase_orders.pop(order_id, None)
            
        except Exception as e:
            logger.error(f"Error handling order fill: {e}")
    
    def _cancel_remaining_bracket_order(self, parent_id: int, order_type: str):
        """Cancel the remaining bracket order when one is filled"""
        try:
            with self._bracket_lock:
                if parent_id not in self._bracket_orders:
                    return
                
                bracket_data = self._bracket_orders[parent_id]
                order_id = bracket_data.get(order_type)
                
                if order_id:
                    try:
                        # Determine the matching trade key for the given order_type key
                        trade_key = 'stop_loss_trade' if order_type == 'stop_loss_id' else 'take_profit_trade'
                        if trade_key in bracket_data:
                            self.ib.cancelOrder(bracket_data[trade_key].order)
                            logger.info(f"Cancelled {order_type} order {order_id} due to other bracket order fill")
                        else:
                            logger.warning(f"Trade object for {order_type} not available; cannot cancel by id")
                    except Exception as e:
                        logger.error(f"Error cancelling {order_type} order: {e}")
                    
                    # Remove the cancelled order from tracking
                    bracket_data.pop(order_type, None)
                    if 'stop_loss_trade' in bracket_data and order_type == 'stop_loss_id':
                        bracket_data.pop('stop_loss_trade', None)
                    if 'take_profit_trade' in bracket_data and order_type == 'take_profit_id':
                        bracket_data.pop('take_profit_trade', None)
                    
                    # If no more bracket orders, remove the entire entry
                    if not bracket_data.get('stop_loss_id') and not bracket_data.get('take_profit_id'):
                        self._bracket_orders.pop(parent_id, None)
                        logger.info(f"All bracket orders for parent {parent_id} have been processed")
            
        except Exception as e:
            logger.error(f"Error cancelling remaining bracket order: {e}")
    
    def _update_position_from_fill(self, order_data: Dict[str, Any], filled_quantity: int, fill_price: float):
        """Update position tracking when a buy order is filled"""
        try:
            symbol = f"{self.underlying_symbol} {order_data['option_type']}"
            
            with self._position_lock:
                self._active_positions[symbol] = {
                    'symbol': symbol,
                    'position_type': order_data['option_type'],
                    'position_size': filled_quantity,
                    'entry_price': fill_price,
                    'contract': order_data['contract'],
                    'entry_time': datetime.now(),
                    'pnl_percent': 0.0
                }
            
            logger.info(f"Position updated: {symbol}, {filled_quantity} contracts at ${fill_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating position from fill: {e}")
    
    def handle_partial_fill(self, order_id: int, filled_quantity: int, remaining_quantity: int, fill_price: float):
        """Handle partial fill events and adjust bracket orders accordingly"""
        try:
            logger.info(f"Partial fill: Order {order_id}, Filled {filled_quantity}, Remaining {remaining_quantity}")
            
            # Check if this is a bracket order partial fill
            with self._bracket_lock:
                for parent_id, bracket_data in self._bracket_orders.items():
                    if bracket_data.get('stop_loss_id') == order_id or bracket_data.get('take_profit_id') == order_id:
                        # Adjust the remaining bracket order quantity
                        asyncio.run(self._adjust_bracket_order_quantity(parent_id, remaining_quantity))
                        return
            
            # For primary orders, update position tracking
            with self._order_lock:
                if order_id in self._open_orders:
                    order_data = self._open_orders[order_id]
                    if order_data['type'] == 'BUY':
                        self._update_position_from_fill(order_data, filled_quantity, fill_price)
                        # Adjust bracket orders for remaining quantity
                        asyncio.run(self._adjust_bracket_order_quantity(order_id, remaining_quantity))
                    elif order_data['type'] == 'SELL':
                        # Update chase remaining quantity if this SELL is being chased
                        if order_id in self._chase_orders:
                            self._chase_orders[order_id]['remaining_quantity'] = remaining_quantity
                            if remaining_quantity <= 0:
                                self._chase_orders.pop(order_id, None)
            
        except Exception as e:
            logger.error(f"Error handling partial fill: {e}")
    
    async def _adjust_bracket_order_quantity(self, parent_order_id: int, new_quantity: int):
        """Adjust bracket order quantities after partial fills"""
        try:
            with self._bracket_lock:
                if parent_order_id not in self._bracket_orders:
                    return
                
                bracket_data = self._bracket_orders[parent_order_id]
            
            # Cancel existing bracket orders
            await self._cancel_bracket_orders(parent_order_id)
            
            # If there's remaining quantity, create new bracket orders
            if new_quantity > 0:
                contract = bracket_data['contract']
                entry_price = bracket_data['entry_price']
                option_type = bracket_data['option_type']
                
                # Place new bracket orders with adjusted quantity
                await self._place_bracket_orders(parent_order_id, contract, new_quantity, entry_price, option_type)
                
                logger.info(f"Adjusted bracket orders for {new_quantity} remaining contracts")
            
        except Exception as e:
            logger.error(f"Error adjusting bracket order quantity: {e}")
    
    def handle_runner_logic(self, position_symbol: str, sell_quantity: int):
        """Handle runner logic when selling profitable positions"""
        try:
            with self._position_lock:
                if position_symbol not in self._active_positions:
                    return
                
                position = self._active_positions[position_symbol]
                current_quantity = position.get('position_size', 0)
                
                if current_quantity <= 0:
                    return
                
                # Calculate runner quantity
                runner_quantity = min(self.runner, current_quantity)
                sell_quantity = min(sell_quantity, current_quantity - runner_quantity)
                
                if sell_quantity > 0:
                    logger.info(f"Runner logic: Selling {sell_quantity} of {current_quantity} contracts, keeping {runner_quantity} as runner")
                    
                    # Update position size
                    position['position_size'] = current_quantity - sell_quantity
                    
                    # Adjust bracket orders for remaining quantity
                    asyncio.run(self._adjust_bracket_order_quantity_for_position(position_symbol, position['position_size']))
                    
                    return sell_quantity
                else:
                    logger.info("Runner logic: No contracts to sell, keeping all as runner")
                    return 0
            
        except Exception as e:
            logger.error(f"Error handling runner logic: {e}")
            return 0
    
    async def _adjust_bracket_order_quantity_for_position(self, position_symbol: str, new_quantity: int):
        """Adjust bracket orders for a specific position"""
        try:
            # Find the parent order for this position
            with self._order_lock:
                parent_order_id = None
                for order_id, order_data in self._open_orders.items():
                    if order_data['type'] == 'BUY' and order_data['option_type'] in position_symbol:
                        parent_order_id = order_id
                        break
            
            if parent_order_id:
                await self._adjust_bracket_order_quantity(parent_order_id, new_quantity)
            
        except Exception as e:
            logger.error(f"Error adjusting bracket orders for position: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self._stop_chase.set()
            if self._chase_thread and self._chase_thread.is_alive():
                self._chase_thread.join(timeout=5)
            
            logger.info("Trading Manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during trading manager cleanup: {e}")

    def get_last_action_message(self) -> str:
        """Return the last user-facing action message for UI notifications"""
        try:
            return str(self._last_action_message)
        except Exception:
            return ""

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
