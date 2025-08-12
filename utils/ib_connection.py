import asyncio
import logging
from typing import Optional, Dict, Any
from ib_async import IB, Stock, Option, Forex
import pandas as pd
from datetime import datetime, timedelta
import pytz
from threading import Thread, Event
import time
logger = logging.getLogger(__name__)


class IBDataCollector:
    """
    Improved IB Data Collector with better error handling and resource management
    """
    
    def __init__(self, host='127.0.0.1', port=7497, clientId=1, timeout=30, trading_config=None, account_config=None):
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
        self.fx_ratio = 0
        self.option_strike = 0
        self._active_subscriptions = set()  # Track active market data subscriptions
        
        # Dynamic strike price and expiration monitoring
        self._previous_strike = 0
        self._current_expiration = None
        self._monitoring_active = False
        self._monitor_thread = None
        self._stop_monitoring = Event()
        self._est_timezone = pytz.timezone('US/Eastern')
        
        # Option contracts cache for quick resubscription
        self._cached_option_contracts = {}  # {strike: {expiration: {call: contract, put: contract}}}

        self._register_ib_callbacks()

    def _calculate_nearest_strike(self, price: float) -> int:
        """Calculate the nearest strike price by rounding to the nearest whole number"""
        return int(round(price))

    def _should_update_strike(self, new_strike: int) -> bool:
        """Check if the strike price has changed and needs updating"""
        return new_strike != self._previous_strike and new_strike > 0

    def _should_switch_to_next_expiration(self) -> bool:
        """Check if it's time to switch from 0DTE to 1DTE contracts (12:00 PM EST)"""
        try:
            est_now = datetime.now(self._est_timezone)
            return est_now.hour == 12 and est_now.minute == 0 and est_now.second == 0
        except Exception as e:
            logger.warning(f"Error checking expiration switch time: {e}")
            return False

    def _get_next_expiration(self, current_expiration: str) -> Optional[str]:
        """Get the next available expiration after the current one"""
        try:
            if not hasattr(self, '_available_expirations') or not self._available_expirations:
                return None
            
            # Find current expiration index and get next one
            expirations = sorted(self._available_expirations)
            try:
                current_index = expirations.index(current_expiration)
                if current_index + 1 < len(expirations):
                    return expirations[current_index + 1]
            except ValueError:
                # Current expiration not found, return first available
                return expirations[0] if expirations else None
                
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
        # self.ib.accountSummaryEvent += self._on_account_summary_update
        # self.ib.pnlEvent += self._on_pnl_update

        logger.debug("IB event callbacks registered")

    async def _on_connected(self):
        """Handle successful IB connection."""
        try:
            logger.info("IB Connection established successfully")
            self._connected = True
            self.connection_attempts = 0
            
            # Emit connection success event
            connection_data = {
                'host': self.host,
                'port': self.port,
                'client_id': self.clientId,
                'timestamp': datetime.now().isoformat()
            }
            logger.info(f"Connection data: {connection_data}")
            
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'connection_success'):
                self.data_worker.connection_success.emit({'status': 'Connected'})
        except Exception as e:
            logger.error(f"Error in connection success handler: {e}")
    
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
                self.data_worker.connection_disconnected.emit({'status': 'Disconnected'})
            
        except Exception as e:
            logger.error(f"Error in disconnection handler: {e}")
    
    async def connect(self) -> bool:
        """Connect to TWS/IB Gateway with timeout and retry logic"""
        try:
            logger.info(f"Attempting to connect to IB at {self.host}:{self.port}")
            
            # Set connection timeout
            await asyncio.wait_for(
                self.ib.connectAsync(self.host, self.port, clientId=self.clientId),
                timeout=self.timeout
            )
            
            logger.info("Successfully connected to Interactive Brokers")
            
            # Start dynamic monitoring after successful connection
            self.start_dynamic_monitoring()
            
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout after {self.timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Safely disconnect from IB and cleanup resources"""
        try:
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
                logger.info("Disconnected from Interactive Brokers")
                
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def get_underlying_symbol_price(self, symbol: str) -> Optional[float]:
        """Get current underlying symbol price with improved error handling.
        Returns the best available price as a float, or None on failure.
        """
        try:
            underlying_symbol = Stock(symbol, 'SMART', 'USD')
            
            # Qualify the contract
            underlying_symbol_qualified = await self.ib.qualifyContractsAsync(underlying_symbol)
            if not underlying_symbol_qualified or underlying_symbol_qualified[0] is None:
                logger.error(f"Could not qualify {symbol} contract")
                return None
            
            # Request market data and set up real-time updates
            underlying_symbol_ticker = self.ib.reqMktData(underlying_symbol_qualified[0])
            self._active_subscriptions.add(underlying_symbol_qualified[0])
            
            # Set up callback for real-time updates
            underlying_symbol_ticker.updateEvent += self._on_underlying_price_update

        except Exception as e:
            logger.error(f"Error getting {symbol} price: {e}")

    def _on_underlying_price_update(self, ticker):
        """Callback handler for real-time underlying symbol price updates"""
        try:
            old_price = self.underlying_symbol_price
            
            if ticker.last and ticker.last > 0:
                self.underlying_symbol_price = float(ticker.last)
                logger.info(f"Real-time {self.underlying_symbol} Last Price: ${self.underlying_symbol_price}")
            elif ticker.close and ticker.close > 0:
                self.underlying_symbol_price = float(ticker.close)
                logger.info(f"Real-time {self.underlying_symbol} Previous Close: ${self.underlying_symbol_price}")
            elif ticker.bid and ticker.ask:
                self.underlying_symbol_price = float((ticker.bid + ticker.ask) / 2)
                logger.info(f"Real-time {self.underlying_symbol} Mid Price: ${self.underlying_symbol_price:.2f} (Bid: ${ticker.bid}, Ask: ${ticker.ask})")
            else:
                logger.debug("No real-time price data available")
                logger.debug(f"Last: {ticker.last}, Bid: {ticker.bid}, Ask: {ticker.ask}")
                logger.debug(f"Close: {ticker.close}, Open: {ticker.open}")
                return
            
            # Check if strike price needs updating
            if old_price != self.underlying_symbol_price and self.underlying_symbol_price > 0:
                new_strike = self._calculate_nearest_strike(self.underlying_symbol_price)
                if self._should_update_strike(new_strike):
                    logger.info(f"Underlying price changed from ${old_price:.2f} to ${self.underlying_symbol_price:.2f}, new strike: {new_strike}")
                    # Schedule strike update
                    asyncio.create_task(self._switch_option_subscriptions(new_strike=new_strike))
            
            # Emit signal for UI update if we have a data worker
            if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'price_updated'):
                self.data_worker.price_updated.emit({
                    'symbol': self.underlying_symbol,
                    'price': self.underlying_symbol_price,
                    'timestamp': datetime.now().isoformat()
                })
                
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
            self.fx_ratio = ticker.last
            logger.info(f"USD/CAD Ratio (last): {self.fx_ratio}")
        elif ticker.close and ticker.close > 0:
            self.fx_ratio = ticker.close
            logger.info(f"USD/CAD Ratio (close): {self.fx_ratio}")
            
        elif ticker.bid and ticker.ask:
            self.fx_ratio = (ticker.bid + ticker.ask) / 2
            logger.info(f"USD/CAD Ratio (mid): {self.fx_ratio}")
            
        else:
            self.fx_ratio = 0
            logger.info(f"USD/CAD Ratio (no data): {self.fx_ratio}")
            
        if hasattr(self, 'data_worker') and hasattr(self.data_worker, 'fx_ratio_updated'):
            self.data_worker.fx_ratio_updated.emit({
                'symbol': 'USDCAD',
                'price': self.fx_ratio,
                'timestamp': datetime.now().isoformat()
            })
    
    async def get_option_chain(self, symbol='SPY') -> pd.DataFrame:
        """Get option chain data with improved error handling and validation"""
        try:
            # Calculate and update strike price
            if self.underlying_symbol_price > 0:
                new_strike = int(round(self.underlying_symbol_price))
                if new_strike != self.option_strike:
                    self.option_strike = new_strike
                    self._previous_strike = new_strike
                    logger.info(f"Updated strike price to: {self.option_strike}")
            else:
                self.option_strike = int(round(self.underlying_symbol_price)) if self.underlying_symbol_price > 0 else 0
                self.under_option_strike = self.option_strike
            
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
            chains = await self.ib.reqSecDefOptParamsAsync(
                stock_qualified[0].symbol,
                '',
                stock_qualified[0].secType,
                stock_qualified[0].conId
            )

            if not chains:
                logger.warning("No option chains found")
                return pd.DataFrame()

            # Get the first chain (usually the most liquid exchange)
            chain = chains[0]
            
            # Store available expirations for dynamic switching
            self._available_expirations = sorted(chain.expirations)
            
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

            option_data = []
            contracts_cache = {}

            for expiration in expirations:
                try:
                    # Create CALL option
                    call_option = Option(symbol, expiration, self.option_strike, 'C', 'SMART')
                    # Create PUT option
                    put_option = Option(symbol, expiration, self.option_strike, 'P', 'SMART')

                    # Qualify contracts
                    call_qualified = await self.ib.qualifyContractsAsync(call_option)
                    put_qualified = await self.ib.qualifyContractsAsync(put_option)

                    # Cache contracts for quick resubscription
                    cache_key = f"{self.option_strike}_{expiration}"
                    contracts_cache[cache_key] = {
                        'call': call_qualified[0] if call_qualified and call_qualified[0] else None,
                        'put': put_qualified[0] if put_qualified and put_qualified[0] else None
                    }
                    self._cached_option_contracts[cache_key] = contracts_cache[cache_key]

                    print(f"Call qualified: {call_qualified}")
                    # Process CALL option
                    if call_qualified and call_qualified[0]:
                        call_data = await self._get_option_data(call_qualified[0], 'CALL')
                        if call_data:
                            option_data.append(call_data)

                    # Process PUT option
                    if put_qualified and put_qualified[0]:
                        put_data = await self._get_option_data(put_qualified[0], 'PUT')
                        if put_data:
                            option_data.append(put_data)

                except Exception as e:
                    logger.warning(f"Error processing option {symbol} {expiration} {self.option_strike}: {e}")
                    continue

            if option_data:
                print(option_data)
                df = pd.DataFrame(option_data)
                logger.info(f"Retrieved {len(df)} option contracts for strike {self.option_strike}, expiration {self._current_expiration}")
                return df
            else:
                logger.warning("No option data retrieved")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return pd.DataFrame()
    
    async def _get_option_data(self, contract, option_type: str) -> Optional[Dict[str, Any]]:
        """Get market data for a specific option contract"""
        try:
            # Request market data
            option_ticker = self.ib.reqMktData(contract)
            self._active_subscriptions.add(contract)
            
            # Wait for data
            await asyncio.sleep(1)
            print(f"Contract: {contract}")
            # Extract data
            data = {
                'Symbol': contract.symbol,
                'Expiration': contract.lastTradeDateOrContractMonth,
                'Strike': contract.strike,
                'Type': option_type,
                'Bid': option_ticker.bid if option_ticker.bid else 0,
                'Ask': option_ticker.ask if option_ticker.ask else 0,
                'Last': option_ticker.last if option_ticker.last else 0,
                'Volume': option_ticker.volume if option_ticker.volume else 0,
                'Call_Open_Interest': getattr(option_ticker, 'callOpenInterest', 0),
                'Put_Open_Interest': getattr(option_ticker, 'putOpenInterest', 0),
                'Delta': getattr(option_ticker.modelGreeks, 'delta', 0),
                'Gamma': getattr(option_ticker.modelGreeks, 'gamma', 0),
                'Theta': getattr(option_ticker.modelGreeks, 'theta', 0),
                'Vega': getattr(option_ticker.modelGreeks, 'vega', 0),
                'Implied_Volatility': getattr(option_ticker.modelGreeks, 'impliedVol', 0) * 100
            }
            
            # Cancel market data subscription
            self.ib.cancelMktData(contract)
            self._active_subscriptions.discard(contract)
            
            return data
            
        except Exception as e:
            logger.warning(f"Error getting data for {option_type} option: {e}")
            return None
    
    async def calculate_pnl_detailed(self, pos, underlying_symbol_price):
        results = []
        pnl_dollar = 0
        pnl_percent = 0
        currency = ''
        current_price = underlying_symbol_price
        if 'USDCAD' in str(pos.contract):
            current_price = self.fx_ratio
            # Forex
            pnl_dollar = pos.position * (current_price - pos.avgCost)
            pnl_percent = ((current_price - pos.avgCost) / pos.avgCost) * 100
            currency = 'CAD'

        elif pos.contract.symbol == 'IBKR':
            # Option
            # current_price = await self.get_symbol_price(pos.contract.symbol)
            if current_price is None:
                logger.warning(f"Could not get price for {pos.contract.symbol}, skipping position")
                return results
            pnl_dollar = pos.position * (current_price - pos.avgCost)
            pnl_percent = ((current_price - pos.avgCost) / pos.avgCost) * 100
            currency = 'USD'

        elif pos.contract.symbol == 'SPY':
            # Stock (Short)
            # current_price = await self.get_symbol_price(pos.contract.symbol)
            if current_price is None:
                logger.warning(f"Could not get price for {pos.contract.symbol}, skipping position")
                return results
            pnl_dollar = pos.position * (current_price - pos.avgCost)
            pnl_percent = -((current_price - pos.avgCost) / pos.avgCost) * 100 * (-1 if pos.position < 0 else 1)
            currency = 'USD'

        results.append({
            'symbol': pos.contract.localSymbol if hasattr(pos.contract, 'localSymbol') else 'USDCAD',
            'position_size': pos.position,
            'avg_cost': pos.avgCost,
            'pnl_dollar': round(pnl_dollar, 2),
            'pnl_percent': round(pnl_percent, 2),
            'currency': currency
        })

        return results

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
                        pnl_detailed = await self.calculate_pnl_detailed(position, self.underlying_symbol_price)

                    except Exception as e:
                        logger.warning(f"Error processing position: {e}")
                        continue
            
            df = pd.DataFrame(pnl_detailed)

            return df
                
        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return pd.DataFrame()
    
    async def get_account_metrics(self) -> pd.DataFrame:
        """Get account metrics with improved error handling.
        High water mark is tracked consistently as a realized PnL value (currency units).
        """
        try:
            # Get account summary
            account_values = await self.ib.accountSummaryAsync()
            
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
            liquidation_account_value = float(account_data.get('NetLiquidation', 0) or 0)
            realized_pn_l_account_value = float(account_data.get('RealizedPnL', 0) or 0)
            starting_value = liquidation_account_value - realized_pn_l_account_value
            realized_pn_l_account_percent = (realized_pn_l_account_value / starting_value) * 100 if starting_value else 0

            # Treat high_water_mark as a value in currency units consistently
            high_water_mark = self.account_config.get('high_water_mark') if self.account_config else None
            logger.info(f"High water mark: {high_water_mark}")
            
            if high_water_mark is None:
                high_water_mark = liquidation_account_value
            else:
                try:
                    high_water_mark = float(high_water_mark)
                except Exception:
                    # If persisted as string previously, coerce to float
                    high_water_mark = liquidation_account_value

            if liquidation_account_value > high_water_mark:
                high_water_mark = liquidation_account_value
                if self.account_config is not None:
                    self.account_config['high_water_mark'] = high_water_mark
                logger.info(f"High water mark updated to {high_water_mark}")

            # Create DataFrame with common metrics
            metrics = {
                'NetLiquidation': liquidation_account_value,
                'StartingValue':starting_value,
                'HighWaterMark': high_water_mark,
                'RealizedPnLPrice': round(realized_pn_l_account_value, 2),
                'RealizedPnLPercent': round(realized_pn_l_account_percent, 2),
                'TotalCashValue': account_data.get('TotalCashValue', 0),
                'GrossPositionValue': account_data.get('GrossPositionValue', 0),
                'BuyingPower': account_data.get('BuyingPower', 0),
                'AvailableFunds': account_data.get('AvailableFunds', 0),
                'ExcessLiquidity': account_data.get('ExcessLiquidity', 0),
                'Cushion': account_data.get('Cushion', 0),
                'FullInitMarginReq': account_data.get('FullInitMarginReq', 0),
                'FullMaintMarginReq': account_data.get('FullMaintMarginReq', 0),
                'FullAvailableFunds': account_data.get('FullAvailableFunds', 0),
                'Currency': account_data.get('Currency', 'USD')
            }
            
            df = pd.DataFrame([metrics])
            logger.info("Account metrics retrieved successfully")
            return df
            
        except Exception as e:
            logger.error(f"Error getting account metrics: {e}")
            return pd.DataFrame()
    
    async def get_trade_statistics(self, days_back=30) -> pd.DataFrame:
        """Get trade statistics with improved error handling"""
        try:
            # Get completed orders
            trades = await self.ib.tradesAsync()
            
            if not trades:
                logger.info("No trades found")
                return self._create_empty_stats()
            
            # Filter trades by date
            cutoff_date = datetime.now() - timedelta(days=days_back)
            recent_trades = []
            
            for trade in trades:
                try:
                    if trade.orderStatus.status == 'Filled':
                        # Parse fill time
                        fill_time = datetime.strptime(
                            trade.orderStatus.filledTime, 
                            '%Y%m%d %H:%M:%S'
                        )
                        if fill_time >= cutoff_date:
                            recent_trades.append(trade)
                except Exception as e:
                    logger.warning(f"Error processing trade: {e}")
                    continue
            
            if not recent_trades:
                logger.info(f"No trades found in the last {days_back} days")
                return self._create_empty_stats()
            
            # Calculate statistics
            wins = []
            losses = []
            
            for trade in recent_trades:
                try:
                    # Calculate P&L (simplified calculation)
                    if hasattr(trade, 'realizedPNL'):
                        pnl = trade.realizedPNL
                    else:
                        # Estimate P&L from order details
                        pnl = 0  # This would need more complex calculation
                    
                    if pnl > 0:
                        wins.append(pnl)
                    elif pnl < 0:
                        losses.append(abs(pnl))
                        
                except Exception as e:
                    logger.warning(f"Error calculating P&L for trade: {e}")
                    continue
            
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
            await self.get_underlying_symbol_price(self.underlying_symbol)

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
            print(f"options_df is: {options_df}")
            data['options'] = options_df

            # Get active positions
            logger.info("Getting active positions...")
            positions_df = await self.get_active_positions(self.underlying_symbol)
            data['active_contract'] = positions_df

            # # Get trade statistics
            # logger.info("Getting trade statistics...")
            # stats_df = await self.get_trade_statistics()
            # data['statistics'] = stats_df
            
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
            
            # Check if we have cached contracts for this strike/expiration
            cache_key = f"{self.option_strike}_{self._current_expiration}"
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
            
            # Cache the contracts
            cache_key = f"{strike}_{expiration}"
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
                        asyncio.run_coroutine_threadsafe(
                            self._switch_option_subscriptions(new_strike=new_strike),
                            asyncio.get_event_loop()
                        )
                
                # Check if it's time to switch expiration (12:00 PM EST)
                if self._should_switch_to_next_expiration():
                    current_exp_type = self._get_expiration_type(self._current_expiration)
                    if current_exp_type == "0DTE":
                        next_expiration = self._get_next_expiration(self._current_expiration)
                        if next_expiration:
                            next_exp_type = self._get_expiration_type(next_expiration)
                            logger.info(f"Switching from {current_exp_type} ({self._current_expiration}) to {next_exp_type} ({next_expiration}) at 12:00 PM EST")
                            # Schedule expiration update in main thread
                            asyncio.run_coroutine_threadsafe(
                                self._switch_option_subscriptions(new_expiration=next_expiration),
                                asyncio.get_event_loop()
                            )
                
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

    async def manual_trigger_update(self, update_type: str, value: Any = None):
        """Manually trigger a dynamic update for testing purposes"""
        try:
            if update_type.lower() == 'strike':
                if value is None:
                    # Use current underlying price to calculate new strike
                    if self.underlying_symbol_price > 0:
                        new_strike = self._calculate_nearest_strike(self.underlying_symbol_price)
                        logger.info(f"Manually triggering strike update to {new_strike}")
                        await self._switch_option_subscriptions(new_strike=new_strike)
                    else:
                        logger.warning("Cannot calculate strike: no underlying price available")
                else:
                    # Use provided strike value
                    new_strike = int(value)
                    logger.info(f"Manually triggering strike update to {new_strike}")
                    await self._switch_option_subscriptions(new_strike=new_strike)
                    
            elif update_type.lower() == 'expiration':
                if value is None:
                    # Switch to next available expiration
                    next_expiration = self._get_next_expiration(self._current_expiration)
                    if next_expiration:
                        logger.info(f"Manually triggering expiration update to {next_expiration}")
                        await self._switch_option_subscriptions(new_expiration=next_expiration)
                    else:
                        logger.warning("No next expiration available")
                else:
                    # Use provided expiration value
                    if value in getattr(self, '_available_expirations', []):
                        logger.info(f"Manually triggering expiration update to {value}")
                        await self._switch_option_subscriptions(new_expiration=value)
                    else:
                        logger.warning(f"Expiration {value} not in available expirations")
                        
            elif update_type.lower() == 'status':
                self.log_dynamic_monitoring_status()
                
            else:
                logger.warning(f"Unknown update type: {update_type}. Use 'strike', 'expiration', or 'status'")
                
        except Exception as e:
            logger.error(f"Error in manual trigger update: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self.disconnect()
        except:
            pass
