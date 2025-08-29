import asyncio
from typing import Dict, Any, List
from ib_async import IB, Option, Order
from datetime import datetime, timedelta
import pytz
from threading import Thread, Event, Lock
import time
import math
from .logger import get_logger
from .tick_size_validator import validate_and_round_price, TickSizeValidator

logger = get_logger("TRADING_MANAGER")


class TradingManager:
    """
    Trading Manager for handling order placement, position management, and hotkey execution
    """
    
    def __init__(self, ib_connection: IB, trading_config: Dict[str, Any], account_config: Dict[str, Any]):
        self._local_available_expirations = None
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
        
        # Reference to hotkey manager for submission state coordination
        self.hotkey_manager = None
        
        logger.info("Trading Manager initialized")
    
    def set_hotkey_manager(self, hotkey_manager):
        """Set reference to hotkey manager for submission state coordination"""
        try:
            self.hotkey_manager = hotkey_manager
            logger.info("Hotkey manager reference set in trading manager")
        except Exception as e:
            logger.error(f"Error setting hotkey manager reference: {e}")
    
    def _notify_hotkey_manager(self, submission_state: bool):
        """Notify hotkey manager about order submission state changes"""
        try:
            if self.hotkey_manager and hasattr(self.hotkey_manager, 'set_submission_state'):
                self.hotkey_manager.set_submission_state(submission_state)
                if submission_state:
                    logger.info("Notified hotkey manager: submission LOCKED")
                else:
                    logger.info("Notified hotkey manager: submission UNLOCKED")
        except Exception as e:
            logger.error(f"Error notifying hotkey manager: {e}")
    
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
        
        IMPORTANT: Options have a multiplier of 100, so the actual cost per contract is option_price * 100
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
            
            # Use minimum of the three to ensure strictest risk constraint
            max_trade_value = min(gui_max_value, tiered_max_value, pdt_max_value)
            
            # Validate that we have a valid maximum trade value
            if max_trade_value <= 0:
                logger.error(f"Invalid maximum trade value calculated: {max_trade_value}")
                return 0
            
            # Calculate quantity using floor to ensure we don't exceed the maximum trade value
            # CRITICAL FIX: Options have a multiplier of 100, so cost per contract = option_price * 100
            if option_price > 0:
                # Calculate the actual cost per contract (option_price * 100)
                cost_per_contract = option_price * 100
                logger.info(f"Option price: ${option_price:.2f}, Cost per contract: ${cost_per_contract:.2f}")
                
                # Calculate max quantity: max_trade_value / cost_per_contract
                quantity = math.floor(max_trade_value / cost_per_contract)
                logger.info(f"Order quantity calculation: GUI={gui_max_value}, Tiered={tiered_max_value}, PDT={pdt_max_value}, Final={max_trade_value}, CostPerContract=${cost_per_contract:.2f}, Qty={quantity}")
                
                # Ensure quantity is at least 1 but doesn't exceed risk limits
                if quantity < 1:
                    logger.warning(f"Calculated quantity {quantity} is less than 1, cannot place order")
                    return 0
                
                # Double-check that the actual trade value doesn't exceed our calculated maximum
                # Actual trade value = quantity * cost_per_contract
                actual_trade_value = quantity * cost_per_contract
                if actual_trade_value > max_trade_value:
                    logger.error(f"Trade value validation failed: {actual_trade_value} > {max_trade_value}")
                    # Recalculate with one less contract to stay within limits
                    quantity = math.floor(max_trade_value / cost_per_contract)
                    if quantity < 1:
                        return 0
                    # Recalculate actual trade value
                    actual_trade_value = quantity * cost_per_contract
                
                logger.info(f"Final validated quantity: {quantity}, Trade value: ${actual_trade_value:.2f}")
                return quantity
            else:
                logger.warning("Option price is zero or negative, cannot calculate quantity")
                return 0
                
        except Exception as e:
            logger.error(f"Error calculating order quantity: {e}")
            return 0
    
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
            
            # If no risk level matches, use a conservative default
            # This ensures we don't bypass PDT buffer constraints
            logger.info(f"No risk level matches current PnL {current_pnl_percent}%, using conservative default")
            with self._config_lock:
                # Use 50% of GUI max trade value as conservative default when no risk level matches
                conservative_default = self.max_trade_value * 0.5
                logger.info(f"Conservative default tiered risk limit: ${conservative_default:.2f}")
                return conservative_default
            
        except Exception as e:
            logger.error(f"Error calculating tiered risk limit: {e}")
            # Return 0 to force PDT buffer to be the limiting factor
            return 0.0
    
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
    
    def update_active_contract_items(self, position):
        self._active_positions = {}
        symbol = getattr(position.contract, 'localSymbol', None)
        if position.position > 0:
            position_type = 'LONG'
        else:
            position_type = 'SHORT'
        
        if position.position != 0:
            self._active_positions[symbol] = {
                'symbol': symbol,
                'position_type': position_type,
                'position_size': abs(position.position),
                'entry_price': getattr(position, 'avgCost', 0),
                'contract': position.contract,
                'entry_time': datetime.now(),
            }

        logger.info(f"Active Contract Updated with {self._active_positions}")
    
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
    
    @staticmethod
    def _get_fallback_expiration(est_now: datetime) -> str:
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

    @staticmethod
    def _create_stock_contract(symbol: str):
        """Create a stock contract for the given symbol"""
        try:
            from ib_async import Stock
            contract = Stock(symbol, 'SMART', 'USD')
            logger.info(f"Created stock contract for {symbol}")
            return contract
        except Exception as e:
            logger.error(f"Error creating stock contract for {symbol}: {e}")
            return None
    
    @staticmethod
    def _create_adaptive_order(action: str, quantity: int, price: float = None) -> Order:
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
    
    @staticmethod
    def _ensure_contract_routable(contract):
        """Ensure contract has routing fields set (exchange/currency/multiplier) required by IB."""
        try:
            if not contract:
                return contract
            # Exchange
            try:
                exch = getattr(contract, 'exchange', None)
                if not exch:
                    setattr(contract, 'exchange', 'SMART')
            except Exception:
                try:
                    setattr(contract, 'exchange', 'SMART')
                except Exception:
                    pass
            # Currency
            try:
                curr = getattr(contract, 'currency', None)
                if not curr:
                    setattr(contract, 'currency', 'USD')
            except Exception:
                try:
                    setattr(contract, 'currency', 'USD')
                except Exception:
                    pass
            # Multiplier for options
            try:
                sec_type = getattr(contract, 'secType', '').upper()
                if sec_type == 'OPT':
                    mult = getattr(contract, 'multiplier', None)
                    if not mult:
                        setattr(contract, 'multiplier', '100')
            except Exception:
                pass
        except Exception as ensure_err:
            logger.warning(f"Could not ensure contract routability: {ensure_err}")
        return contract

    async def _cleanup_failed_order(self, order_id: int, symbol: str):
        """Clean up failed order and pending position"""
        try:
            # Remove from open orders
            with self._order_lock:
                self._open_orders.pop(order_id, None)
            
            # Remove pending position
            with self._position_lock:
                self._active_positions.pop(symbol, None)
            
            # Cancel any bracket orders that may have been placed
            await self._cancel_bracket_orders(order_id)
            
            logger.info(f"Cleaned up failed order {order_id} and pending position {symbol}")
            
        except Exception as e:
            logger.error(f"Error cleaning up failed order {order_id}: {e}")
    
    async def place_buy_order(self, option_type: str) -> bool:
        """Place a BUY order for the specified option type"""
        try:
            # Validate option type
            if option_type.upper() not in ["CALL", "PUT"]:
                logger.error(f"Invalid option type: {option_type}")
                self._last_action_message = f"Invalid option type: {option_type}"
                return False
            
            # Check for existing positions (one active position rule)
            # Clear any positions with size 0 (closed positions) first

            logger.info(f"_Active Position after clear: {self._active_positions}")
            with self._position_lock:
                # Now check if there are any active positions with size > 0
                if self._active_positions:
                    logger.warning("One active position rule: Cannot place new order while position exists")
                    self._last_action_message = "Cannot BUY: an active position already exists. Close or sell the current position first."
                    return False
            
            # Notify hotkey manager that submission is starting
            self._notify_hotkey_manager(True)
            
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
            
            # Calculate quantity with risk management constraints
            quantity = self._calculate_order_quantity(option_price)
            
            # CRITICAL: Validate quantity before proceeding
            if quantity <= 0:
                logger.error(f"Risk management constraints prevent order placement: calculated quantity = {quantity}")
                self._last_action_message = f"Cannot BUY {option_type}: risk management constraints prevent order placement."
                return False
            
            # Additional validation: ensure the trade value doesn't exceed any risk limits
            # CRITICAL FIX: Options have a multiplier of 100, so cost per contract = option_price * 100
            cost_per_contract = option_price * 100
            actual_trade_value = quantity * cost_per_contract
            gui_limit = self.max_trade_value
            tiered_limit = self._calculate_tiered_risk_limit()
            pdt_limit = self._calculate_pdt_buffer()
            
            if actual_trade_value > min(gui_limit, tiered_limit, pdt_limit):
                logger.error(f"Trade value validation failed: ${actual_trade_value:.2f} exceeds risk limits")
                self._last_action_message = f"Cannot BUY {option_type}: calculated trade value exceeds risk limits."
                return False
            
            logger.info(f"Risk validation passed: Quantity={quantity}, Trade Value=${actual_trade_value:.2f} (${cost_per_contract:.2f} per contract)")
            
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
                
                # IMMEDIATELY track the order and create pending position
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
                
                # IMMEDIATELY add to active positions as pending (will be confirmed on fill)
                symbol = f"{self.underlying_symbol} {option_type}"
                
                logger.info(f"Position immediately tracked as pending: {symbol}, {quantity} contracts")
                
                # Place bracket orders for risk management
                await self._place_bracket_orders(trade.order.orderId, contract, quantity, option_price, option_type)
                
                # Notify hotkey manager that submission is complete and successful
                self._notify_hotkey_manager(False)
                
                return True
            else:
                logger.error(f"BUY {option_type} order failed: {trade.orderStatus.status}")
                try:
                    status_text = str(trade.orderStatus.status)
                except Exception:
                    status_text = "Unknown"
                self._last_action_message = f"BUY {option_type} failed: status={status_text}."
                
                # Clean up any pending position that was created
                symbol = f"{self.underlying_symbol} {option_type}"
                await self._cleanup_failed_order(trade.order.orderId, symbol)
                
                # Notify hotkey manager that submission is complete (failed)
                self._notify_hotkey_manager(False)
                
                return False
                
        except Exception as e:
            logger.error(f"Error placing BUY {option_type} order: {e}")
            self._last_action_message = f"BUY {option_type} error: {str(e)}"
            # Ensure hotkey manager is notified of submission completion on error
            self._notify_hotkey_manager(False)
            return False
    
    async def place_sell_order(self, use_chase_logic: bool = True) -> bool:
        """Place a SELL order for any open position using chase logic if specified"""
        try:
            # Notify hotkey manager that submission is starting
            self._notify_hotkey_manager(True)
            
            logger.info(f"_Active Position after clear: {self._active_positions}")

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
                # CRITICAL FIX: Validate and round limit price to conform to IBKR tick size requirements
                raw_limit_price = mid_price - self.trade_delta
                limit_price = validate_and_round_price(raw_limit_price, f"SELL limit order for {symbol}")
                
                # Log the price adjustment for debugging
                if raw_limit_price != limit_price:
                    logger.info(f"Adjusted limit price from ${raw_limit_price:.4f} to ${limit_price:.2f} for tick size compliance")
                
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
                
                # Ensure routing fields are set and submit limit order
                contract = self._ensure_contract_routable(contract)
                logger.info(f"Submitting limit order: {sell_quantity} contracts at ${limit_price:.2f}")
                trade = self.ib.placeOrder(contract, order)
                
                # Track for chase logic
                with self._order_lock:
                    chase_order_data = {
                        'trade': trade,
                        'contract': contract,
                        'original_quantity': sell_quantity,
                        'remaining_quantity': sell_quantity,
                        'start_time': time.time(),
                        'limit_price': limit_price,
                        'order_id': trade.order.orderId,
                        'last_status_check': time.time()
                    }
                    self._chase_orders[trade.order.orderId] = chase_order_data
                    logger.info(f"Chase order {trade.order.orderId} initialized with contract: {getattr(contract, 'symbol', 'N/A')}, quantity: {sell_quantity}")
                    logger.debug(f"Full chase order data: {chase_order_data}")
                
                # Start chase monitoring
                self._start_chase_monitoring()
                
                logger.info(f"SELL order submitted with chase logic: {sell_quantity} contracts at ${limit_price:.2f}")
                self._last_action_message = f"SELL submitted (chase): {sell_quantity} contracts at ${limit_price:.2f}."
                
                # Notify hotkey manager that submission is complete and successful
                self._notify_hotkey_manager(False)
                
                return True
            else:
                # Create contract
                contract = position.get('contract')
                logger.info(f"Position contract: {contract}, type: {type(contract)}")
                
                # Validate contract object
                if not contract or not hasattr(contract, 'symbol'):
                    logger.warning("Invalid contract object from position, attempting to recreate")
                    if "CALL" in symbol.upper() or "PUT" in symbol.upper():
                        pass
                    else:
                        # Stock contract - create stock contract
                        contract = self._create_stock_contract(symbol)
                        if not contract:
                            logger.error(f"Failed to create stock contract for {symbol}")
                            return False
                
                # Ensure routing fields are set and submit market order
                contract = self._ensure_contract_routable(contract)
                
                # CRITICAL FIX: Actually submit the market order to IB
                market_order = self._create_adaptive_order("SELL", sell_quantity)
                try:
                    trade = self.ib.placeOrder(contract, market_order)
                    logger.info(f"Market order submitted to IB: {sell_quantity} contracts, order ID: {trade.order.orderId}")
                except Exception as submit_error:
                    logger.error(f"Failed to submit market order to IB: {submit_error}")
                    self._last_action_message = f"Failed to submit market order: {str(submit_error)}"
                    return False

                logger.info(f"SELL order submitted: {sell_quantity} contracts at market")
                self._last_action_message = f"SELL submitted: {sell_quantity} contracts at market."
                
                # Notify hotkey manager that submission is complete and successful
                self._notify_hotkey_manager(False)
                
                return True
                
        except Exception as e:
            logger.error(f"Error placing SELL order: {e}")
            self._last_action_message = f"SELL error: {str(e)}"
            # Ensure hotkey manager is notified of submission completion on error
            self._notify_hotkey_manager(False)
            return False
    
    async def panic_button(self) -> bool:
        """Panic button: Flatten all risk for the underlying"""
        try:
            # Notify hotkey manager that submission is starting
            self._notify_hotkey_manager(True)
            
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
            
            # Notify hotkey manager that submission is complete
            self._notify_hotkey_manager(False)
            
            return sell_success
            
        except Exception as e:
            logger.error(f"Error executing panic button: {e}")
            # Ensure hotkey manager is notified of submission completion on error
            self._notify_hotkey_manager(False)
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
                chase_count = len(self._chase_orders)
                if chase_count > 0:
                    logger.info(f"Clearing {chase_count} chase orders during panic button execution")
                    for order_id, chase_data in self._chase_orders.items():
                        logger.debug(f"Clearing chase order {order_id}: {chase_data}")
                    self._chase_orders.clear()
                else:
                    logger.debug("No chase orders to clear")
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
    
    def cancel_chase_order(self, order_id: int):
        """Cancel a specific chase order and remove it from monitoring"""
        try:
            with self._order_lock:
                if order_id in self._chase_orders:
                    chase_data = self._chase_orders[order_id]
                    trade = chase_data.get('trade')
                    
                    if trade and hasattr(trade, 'order'):
                        try:
                            self.ib.cancelOrder(trade.order)
                            logger.info(f"Cancelled chase order {order_id}")
                        except Exception as e:
                            logger.error(f"Error cancelling chase order {order_id}: {e}")
                    
                    # Remove from chase monitoring
                    removed_data = self._chase_orders.pop(order_id)
                    logger.info(f"Removed cancelled chase order {order_id} from monitoring: {removed_data}")
                else:
                    logger.warning(f"Chase order {order_id} not found for cancellation")
            
        except Exception as e:
            logger.error(f"Error cancelling chase order {order_id}: {e}")
    
    def _start_chase_monitoring(self):
        """Start monitoring chase orders"""
        if self._chase_thread and self._chase_thread.is_alive():
            logger.debug("Chase monitoring already active")
            return
        
        logger.info("Starting chase monitoring thread")
        self._stop_chase.clear()
        self._chase_thread = Thread(target=self._chase_monitor_loop, daemon=True)
        self._chase_thread.start()
        logger.info("Chase monitoring thread started successfully")
    
    def _check_chase_order_status(self, order_id: int, chase_data: Dict[str, Any]) -> bool:
        """Check if a chase order is still active (not filled/cancelled)"""
        try:
            trade = chase_data.get('trade')
            if not trade or not hasattr(trade, 'orderStatus'):
                return False
            
            order_status = trade.orderStatus
            status = order_status.status.upper()
            
            # Order is no longer active if it's filled, cancelled, or in error state
            if status in ['FILLED', 'CANCELLED', 'INACTIVE', 'ERROR']:
                logger.info(f"Chase order {order_id} no longer active: {status}")
                return False
            
            # Update last status check time
            chase_data['last_status_check'] = time.time()
            return True
            
        except Exception as e:
            logger.error(f"Error checking chase order {order_id} status: {e}")
            return False
    
    def handle_order_status_update(self, order_id: int, status: str, filled: float = 0, remaining: float = 0, avg_fill_price: float = 0):
        """Handle order status updates from IB callbacks and clean up chase monitoring"""
        try:
            logger.info(f"Order status update: Order {order_id}, Status: {status}, Filled: {filled}, Remaining: {remaining}")
            
            # Check if this is a chase order
            with self._order_lock:
                if order_id in self._chase_orders:
                    chase_data = self._chase_orders[order_id]
                    
                    # If order is filled, remove from chase monitoring immediately
                    if status.upper() == 'FILLED':
                        removed_data = self._chase_orders.pop(order_id)
                        logger.info(f"Chase order {order_id} filled, removed from monitoring: {removed_data}")
                        
                        # Update position tracking if this was a sell order
                        if filled > 0 and avg_fill_price > 0:
                            self._update_position_from_sell_fill({
                                'option_type': 'CALL' if 'CALL' in str(chase_data.get('contract', '')) else 'PUT'
                            }, filled, avg_fill_price)
                    
                    # If order is cancelled or in error state, remove from chase monitoring
                    elif status.upper() in ['CANCELLED', 'INACTIVE', 'ERROR']:
                        removed_data = self._chase_orders.pop(order_id)
                        logger.info(f"Chase order {order_id} {status.lower()}, removed from monitoring: {removed_data}")
            
        except Exception as e:
            logger.error(f"Error handling order status update for order {order_id}: {e}")
    
    def _chase_monitor_loop(self):
        """Monitor chase orders and convert to market orders after 10 seconds"""
        logger.info("Chase monitor loop started")
        while not self._stop_chase.is_set():
            try:
                current_time = time.time()
                orders_to_convert = []
                
                with self._order_lock:
                    chase_count = len(self._chase_orders)
                    if chase_count > 0:
                        logger.debug(f"Monitoring {chase_count} active chase orders")
                    
                    for order_id, chase_data in list(self._chase_orders.items()):
                        # Check if order is still active (not filled/cancelled)
                        if not self._check_chase_order_status(order_id, chase_data):
                            logger.info(f"Chase order {order_id} no longer active, removing from monitoring")
                            self._chase_orders.pop(order_id, None)
                            continue
                        
                        time_elapsed = current_time - chase_data['start_time']
                        logger.debug(f"Chase order {order_id}: {time_elapsed:.1f}s elapsed, threshold: 10s")
                        if time_elapsed >= 10:  # 10 seconds
                            orders_to_convert.append(order_id)
                            logger.info(f"Chase order {order_id} ready for conversion to market: {time_elapsed:.1f}s elapsed")
                
                # Convert orders to market orders
                for order_id in orders_to_convert:
                    logger.info(f"Converting chase order {order_id} to market order after 10 seconds")
                    asyncio.run(self._convert_to_market_order(order_id))
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in chase monitor loop: {e}")
                time.sleep(1)
        
        logger.info("Chase monitor loop stopped")
    
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
                # Continue with market order conversion even if cancellation fails
            
            # Create and submit market order
            market_order = self._create_adaptive_order("SELL", remaining_quantity)
            
            # CRITICAL FIX: Actually submit the market order to IB
            contract = chase_data.get('contract')
            if not contract:
                logger.error(f"No contract available for market order conversion of order {order_id}")
                logger.error(f"Chase data keys: {list(chase_data.keys())}")
                logger.error(f"Chase data: {chase_data}")
                return
            
            # Ensure contract is routable
            contract = self._ensure_contract_routable(contract)
            logger.info(f"Contract for market order conversion: {contract}, symbol: {getattr(contract, 'symbol', 'N/A')}")
            
            # Submit the market order to IB
            try:
                trade = self.ib.placeOrder(contract, market_order)
                logger.info(f"Market order submitted to IB: {remaining_quantity} contracts, order ID: {trade.order.orderId}")
            except Exception as submit_error:
                logger.error(f"Failed to submit market order to IB: {submit_error}")
                self._last_action_message = f"Failed to submit market order: {str(submit_error)}"
                return

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
                if order_id in self._chase_orders:
                    removed_data = self._chase_orders.pop(order_id)
                    logger.info(f"Chase order {order_id} removed after market conversion: {removed_data}")
                else:
                    logger.warning(f"Chase order {order_id} not found during cleanup")
            
            logger.info(f"Successfully converted chase order {order_id} to market order")
            
        except Exception as e:
            logger.error(f"Error converting to market order: {e}")
            # Try to clean up chase order even on error
            try:
                with self._order_lock:
                    if order_id in self._chase_orders:
                        self._chase_orders.pop(order_id)
                        logger.info(f"Cleaned up chase order {order_id} after error")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up chase order {order_id} after conversion error: {cleanup_error}")
    
    async def _place_bracket_orders(self, parent_order_id: int, contract, quantity: int, entry_price: float, option_type: str):
        """Place bracket orders (stop loss and take profit) for risk management"""
        global stop_loss_price, take_profit_price
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
                raw_stop_loss_price = self._calculate_stop_loss_price(entry_price, float(stop_loss_percent))
                # CRITICAL FIX: Validate and round stop loss price to conform to IBKR tick size requirements
                stop_loss_price = validate_and_round_price(raw_stop_loss_price, f"Stop loss order for {option_type}")
                if raw_stop_loss_price != stop_loss_price:
                    logger.info(f"Adjusted stop loss price from ${raw_stop_loss_price:.4f} to ${stop_loss_price:.2f} for tick size compliance")
                stop_loss_order = self._create_stop_loss_order(quantity, stop_loss_price)
            if profit_gain_percent:
                raw_take_profit_price = self._calculate_take_profit_price(entry_price, float(profit_gain_percent))
                # CRITICAL FIX: Validate and round take profit price to conform to IBKR tick size requirements
                take_profit_price = validate_and_round_price(raw_take_profit_price, f"Take profit order for {option_type}")
                if raw_take_profit_price != take_profit_price:
                    logger.info(f"Adjusted take profit price from ${raw_take_profit_price:.4f} to ${take_profit_price:.2f} for tick size compliance")
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
    
    def _get_current_risk_level(self) -> Any | None:
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
    
    @staticmethod
    def _calculate_stop_loss_price(entry_price: float, stop_loss_percent: float) -> float:
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
    
    @staticmethod
    def _calculate_take_profit_price(entry_price: float, profit_gain_percent: float) -> float:
        """Calculate take profit price based on entry price and percentage"""
        try:
            # For options, take profit is a percentage increase from entry price
            take_profit_price = entry_price * (1 + profit_gain_percent / 100)
            
            logger.info(f"Take profit calculation: Entry=${entry_price:.2f}, Gain={profit_gain_percent}%, Target=${take_profit_price:.2f}")
            return take_profit_price
            
        except Exception as e:
            logger.error(f"Error calculating take profit price: {e}")
            return entry_price * 1.2  # Default to 20% gain
    
    @staticmethod
    def _create_stop_loss_order(quantity: int, stop_loss_price: float) -> Order:
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
    
    @staticmethod
    def _create_take_profit_order(quantity: int, take_profit_price: float) -> Order:
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
                if not symbol:
                    logger.warning("Position data missing symbol")
                    return
                
                # Check if position quantity is 0 (closed position)
                position_size = position_data.get('position_size', 0)
                if position_size == 0:
                    # Remove closed position from active positions
                    if symbol in self._active_positions:
                        del self._active_positions[symbol]
                        logger.info(f"Closed position removed: {symbol}")
                    return
                
        except Exception as e:
            logger.error(f"Error updating position: {e}")


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
                if symbol in self._active_positions:
                    # Update existing pending position with fill confirmation
                    position = self._active_positions[symbol]
                    position.update({
                        'position_size': filled_quantity,
                        'entry_price': fill_price,
                        'status': 'active',  # Mark as active (filled)
                        'fill_time': datetime.now(),
                        'pnl_percent': 0.0
                    })
                    logger.info(f"Position confirmed as filled: {symbol}, {filled_quantity} contracts at ${fill_price:.2f}")
                else:
                    # Create new position if somehow not tracked (fallback)
                    self._active_positions[symbol] = {
                        'symbol': symbol,
                        'position_type': order_data['option_type'],
                        'position_size': filled_quantity,
                        'entry_price': fill_price,
                        'contract': order_data['contract'],
                        'entry_time': datetime.now(),
                        'fill_time': datetime.now(),
                        'pnl_percent': 0.0,
                        'status': 'active'
                    }
                    logger.info(f"Position created from fill (fallback): {symbol}, {filled_quantity} contracts at ${fill_price:.2f}")
            
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
                            old_quantity = self._chase_orders[order_id]['remaining_quantity']
                            self._chase_orders[order_id]['remaining_quantity'] = remaining_quantity
                            logger.info(f"Updated chase order {order_id} remaining quantity: {old_quantity} -> {remaining_quantity}")
                            if remaining_quantity <= 0:
                                removed_data = self._chase_orders.pop(order_id)
                                logger.info(f"Chase order {order_id} removed due to complete fill: {removed_data}")
            
        except Exception as e:
            logger.error(f"Error handling partial fill: {e}")
    
    def handle_order_fill(self, order_id: int, filled_quantity: int, fill_price: float):
        """Handle complete order fill events and clean up chase monitoring"""
        try:
            logger.info(f"Order filled: Order {order_id}, Filled {filled_quantity} at ${fill_price:.2f}")
            
            # Immediately remove from chase monitoring if this was a chase order
            with self._order_lock:
                if order_id in self._chase_orders:
                    removed_data = self._chase_orders.pop(order_id)
                    logger.info(f"Chase order {order_id} removed from monitoring due to fill: {removed_data}")
            
            # Handle position updates for BUY orders
            with self._order_lock:
                if order_id in self._open_orders:
                    order_data = self._open_orders[order_id]
                    if order_data['type'] == 'BUY':
                        self._update_position_from_fill(order_data, filled_quantity, fill_price)
                    elif order_data['type'] == 'SELL':
                        # For SELL orders, update position tracking
                        self._update_position_from_sell_fill(order_data, filled_quantity, fill_price)
            
        except Exception as e:
            logger.error(f"Error handling order fill: {e}")
    
    def _update_position_from_sell_fill(self, order_data: Dict[str, Any], filled_quantity: int, fill_price: float):
        """Update position tracking when a sell order is filled"""
        try:
            symbol = f"{self.underlying_symbol} {order_data['option_type']}"
            
            with self._position_lock:
                if symbol in self._active_positions:
                    position = self._active_positions[symbol]
                    current_size = position.get('position_size', 0)
                    new_size = current_size - filled_quantity
                    
                    if new_size <= 0:
                        # Position fully closed
                        removed_position = self._active_positions.pop(symbol)
                        logger.info(f"Position fully closed: {symbol}, {filled_quantity} contracts sold at ${fill_price:.2f}")
                    else:
                        # Partial position closed
                        position['position_size'] = new_size
                        logger.info(f"Partial position closed: {symbol}, {filled_quantity} contracts sold at ${fill_price:.2f}, remaining: {new_size}")
                else:
                    logger.warning(f"No active position found for sell fill: {symbol}")
            
        except Exception as e:
            logger.error(f"Error updating position from sell fill: {e}")
    
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


    def calculate_max_affordable_quantity(self, option_price: float) -> Dict[str, Any]:
        """
        Calculate the maximum number of contracts that can be purchased at the given price
        while respecting all risk management constraints.
        
        This method is designed for GUI display and user feedback before order placement.
        """
        try:
            if option_price <= 0:
                return {
                    'max_quantity': 0,
                    'max_trade_value': 0,
                    'can_afford': False,
                    'error': 'Invalid option price'
                }
            
            # Get all risk limits
            gui_limit = self.max_trade_value
            tiered_limit = self._calculate_tiered_risk_limit()
            pdt_limit = self._calculate_pdt_buffer()
            
            # Determine the limiting factor (strictest constraint)
            limiting_factor = min(gui_limit, tiered_limit, pdt_limit)
            
            if limiting_factor <= 0:
                return {
                    'max_quantity': 0,
                    'max_trade_value': 0,
                    'can_afford': False,
                    'error': 'No available risk capacity'
                }
            
            # Calculate maximum quantity using floor to stay within limits
            # CRITICAL FIX: Options have a multiplier of 100, so cost per contract = option_price * 100
            cost_per_contract = option_price * 100
            max_quantity = math.floor(limiting_factor / cost_per_contract)
            
            # Calculate the actual trade value for this quantity
            actual_trade_value = max_quantity * cost_per_contract
            
            # Determine which constraint is limiting
            limiting_constraint = 'unknown'
            if limiting_factor == gui_limit:
                limiting_constraint = 'GUI Max Trade Value'
            elif limiting_factor == tiered_limit:
                limiting_constraint = 'Tiered Risk Limit'
            elif limiting_factor == pdt_limit:
                limiting_constraint = 'PDT Buffer'
            
            # Calculate available margin
            available_margin = limiting_factor - actual_trade_value
            
            result = {
                'max_quantity': max_quantity,
                'max_trade_value': limiting_factor,
                'actual_trade_value': actual_trade_value,
                'option_price': option_price,
                'can_afford': max_quantity > 0,
                'limiting_constraint': limiting_constraint,
                'available_margin': available_margin,
                'risk_limits': {
                    'gui_max_trade_value': gui_limit,
                    'tiered_risk_limit': tiered_limit,
                    'pdt_buffer_limit': pdt_limit
                },
                'user_friendly_message': self._generate_user_friendly_message(
                    max_quantity, option_price, limiting_constraint, available_margin
                )
            }
            
            logger.info(f"Max affordable quantity calculation: {max_quantity} contracts at ${option_price:.2f} (limited by {limiting_constraint})")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating max affordable quantity: {e}")
            return {
                'max_quantity': 0,
                'max_trade_value': 0,
                'can_afford': False,
                'error': str(e)
            }
    
    @staticmethod
    def _generate_user_friendly_message(max_quantity: int, option_price: float,
                                        limiting_constraint: str, available_margin: float) -> str:
        """Generate a user-friendly message about the trading capacity"""
        try:
            if max_quantity <= 0:
                return f"Cannot afford any contracts at ${option_price:.2f}. Limited by {limiting_constraint}."
            
            if max_quantity == 1:
                quantity_text = "1 contract"
            else:
                quantity_text = f"{max_quantity} contracts"
            
            # CRITICAL FIX: Options have a multiplier of 100, so cost per contract = option_price * 100
            cost_per_contract = option_price * 100
            trade_value = max_quantity * cost_per_contract
            
            if available_margin < 1.0:
                margin_text = " (at maximum capacity)"
            else:
                margin_text = f" (${available_margin:.2f} remaining capacity)"
            
            return f"You can afford {quantity_text} at ${option_price:.2f} (${trade_value:.2f} total){margin_text}. Limited by {limiting_constraint}."
            
        except Exception as e:
            logger.error(f"Error generating user friendly message: {e}")
            return "Unable to calculate trading capacity."
    
    def get_last_action_message(self) -> str:
        """Return the last user-facing action message for UI notifications"""
        try:
            return str(self._last_action_message)
        except Exception:
            return ""
    
    def get_chase_order_status(self) -> Dict[str, Any]:
        """Get current status of all chase orders for debugging and monitoring"""
        try:
            with self._order_lock:
                chase_status = {}
                for order_id, chase_data in self._chase_orders.items():
                    trade = chase_data.get('trade')
                    order_status = None
                    if trade and hasattr(trade, 'orderStatus'):
                        order_status = trade.orderStatus.status
                    
                    chase_status[order_id] = {
                        'symbol': getattr(chase_data.get('contract'), 'symbol', 'N/A'),
                        'quantity': chase_data.get('remaining_quantity', 0),
                        'limit_price': chase_data.get('limit_price', 0),
                        'start_time': chase_data.get('start_time', 0),
                        'elapsed_time': time.time() - chase_data.get('start_time', time.time()),
                        'order_status': order_status,
                        'last_status_check': chase_data.get('last_status_check', 0)
                    }
                
                return {
                    'total_chase_orders': len(self._chase_orders),
                    'chase_orders': chase_status
                }
            
        except Exception as e:
            logger.error(f"Error getting chase order status: {e}")
            return {'error': str(e)}

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
    
    def validate_option_price_for_ib(self, price: float, context: str = "") -> Dict[str, Any]:
        """
        Validate an option price for IBKR compliance and provide detailed feedback.
        
        Args:
            price: The option price to validate
            context: Context for the validation (e.g., "SELL order", "Stop loss")
            
        Returns:
            Dictionary with validation results and suggestions
        """
        try:
            from .tick_size_validator import get_tick_size_info
            
            # Get detailed tick size information
            tick_info = get_tick_size_info(price)
            
            # Add context and recommendations
            result = {
                'context': context,
                'original_price': price,
                'is_valid': tick_info.get('is_valid', False),
                'tick_size': tick_info.get('tick_size', 0),
                'validation_message': tick_info.get('validation_message', ''),
                'rounded_price': tick_info.get('rounded_price', price),
                'price_adjusted': price != tick_info.get('rounded_price', price),
                'recommendations': []
            }
            
            # Add specific recommendations based on validation results
            if not result['is_valid']:
                result['recommendations'].append(f"Use ${result['rounded_price']:.2f} instead of ${price:.4f}")
                result['recommendations'].append(f"Tick size for this price range is ${result['tick_size']:.2f}")
                
                if price < 3.00:
                    result['recommendations'].append("Prices below $3.00 must be multiples of $0.05")
                else:
                    result['recommendations'].append("Prices $3.00 and above must be multiples of $0.10")
            
            # Add IBKR compliance note
            result['ibkr_compliance'] = {
                'error_110_prevention': result['is_valid'],
                'tick_size_requirement': f"${result['tick_size']:.2f}",
                'price_threshold': "$3.00"
            }
            
            logger.info(f"Price validation for {context}: ${price:.4f} -> {'VALID' if result['is_valid'] else 'INVALID'} (tick size: ${result['tick_size']:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Error validating option price {price} for IBKR compliance: {e}")
            return {
                'context': context,
                'original_price': price,
                'is_valid': False,
                'error': str(e),
                'recommendations': ['Contact support for price validation assistance']
            }
    
    def analyze_tick_size_compliance(self, prices: List[float], context: str = "") -> Dict[str, Any]:
        """
        Analyze multiple prices for IBKR tick size compliance.
        
        Args:
            prices: List of prices to analyze
            context: Context for the analysis
            
        Returns:
            Dictionary with comprehensive compliance analysis
        """
        try:
            from .tick_size_validator import TickSizeValidator
            
            analysis = {
                'context': context,
                'total_prices': len(prices),
                'compliant_prices': 0,
                'non_compliant_prices': 0,
                'price_details': [],
                'summary': {},
                'recommendations': []
            }
            
            validator = TickSizeValidator()
            
            for i, price in enumerate(prices):
                if price <= 0:
                    continue
                    
                tick_size = validator.get_tick_size(price)
                is_valid, message = validator.validate_price(price)
                rounded_price = validator.round_to_valid_tick(price)
                
                price_detail = {
                    'index': i,
                    'original_price': price,
                    'tick_size': tick_size,
                    'is_valid': is_valid,
                    'validation_message': message,
                    'rounded_price': rounded_price,
                    'price_adjusted': price != rounded_price,
                    'adjustment_amount': abs(price - rounded_price)
                }
                
                analysis['price_details'].append(price_detail)
                
                if is_valid:
                    analysis['compliant_prices'] += 1
                else:
                    analysis['non_compliant_prices'] += 1
            
            # Generate summary statistics
            analysis['summary'] = {
                'compliance_rate': (analysis['compliant_prices'] / len(prices)) * 100 if prices else 0,
                'total_adjustments_needed': analysis['non_compliant_prices'],
                'max_adjustment_amount': max([p['adjustment_amount'] for p in analysis['price_details']]) if analysis['price_details'] else 0,
                'avg_adjustment_amount': sum([p['adjustment_amount'] for p in analysis['price_details']]) / len(analysis['price_details']) if analysis['price_details'] else 0
            }
            
            # Generate recommendations
            if analysis['non_compliant_prices'] > 0:
                analysis['recommendations'].append(f"Fix {analysis['non_compliant_prices']} non-compliant prices to prevent IBKR Error 110")
                analysis['recommendations'].append("Use the rounded prices provided in price_details")
                analysis['recommendations'].append("Consider implementing automatic tick size validation in order placement")
            
            if analysis['summary']['max_adjustment_amount'] > 0.05:
                analysis['recommendations'].append("Large price adjustments detected - review pricing logic")
            
            logger.info(f"Tick size compliance analysis for {context}: {analysis['compliant_prices']}/{len(prices)} prices compliant")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing tick size compliance for {context}: {e}")
            return {
                'context': context,
                'error': str(e),
                'recommendations': ['Contact support for compliance analysis assistance']
            }
    
