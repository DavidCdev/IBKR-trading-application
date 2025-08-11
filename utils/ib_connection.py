import asyncio
import logging
from typing import Optional, Dict, Any
from ib_async import IB, Stock, Option, Forex
import pandas as pd
from datetime import datetime, timedelta
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

        self._register_ib_callbacks()


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
            logger.info("✓ IB Connection established successfully")
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
            logger.info("✗ IB Connection disconnected")
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
            # Ensure we have the latest price
            if self.underlying_symbol_price == 0:
                await self.get_underlying_symbol_price(self.underlying_symbol)
            if self.underlying_symbol_price == 0:
                logger.error("Unable to get current stock price for strike selection")
                return pd.DataFrame()
            # Calculate the nearest strike price by rounding to the nearest whole number
            self.option_strike = int(round(self.underlying_symbol_price))
            logger.info(f"Nearest strike price (rounded): {self.option_strike}")

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

            # Get current stock price for strike selection
            if self.underlying_symbol_price == 0:
                await self.get_underlying_symbol_price(self.underlying_symbol)

            if self.underlying_symbol_price == 0:
                logger.error("Unable to get current stock price for strike selection")
                return pd.DataFrame()

            # Select strikes around current price
            current_price = self.underlying_symbol_price

            # Get nearest expirations
            expirations = sorted(chain.expirations)[:3]  # Get first 3 expirations

            option_data = []

            for expiration in expirations:
                try:
                    # Create CALL option
                    call_option = Option(symbol, expiration, self.option_strike, 'C', 'SMART')
                    # Create PUT option
                    put_option = Option(symbol, expiration, self.option_strike, 'P', 'SMART')

                    # Qualify contracts
                    call_qualified = await self.ib.qualifyContractsAsync(call_option)
                    put_qualified = await self.ib.qualifyContractsAsync(put_option)

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
                logger.info(f"Retrieved {len(df)} option contracts")
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
            ticker = self.ib.reqMktData(contract)
            self._active_subscriptions.add(contract)
            
            # Wait for data
            await asyncio.sleep(1)
            
            # Extract data
            data = {
                'Symbol': contract.symbol,
                'Expiration': contract.lastTradingDay,
                'Strike': contract.strike,
                'Type': option_type,
                'Bid': ticker.bid if ticker.bid else 0,
                'Ask': ticker.ask if ticker.ask else 0,
                'Last': ticker.last if ticker.last else 0,
                'Volume': ticker.volume if ticker.volume else 0,
                'Open_Interest': ticker.openInterest if ticker.openInterest else 0,
                'Implied_Volatility': ticker.impliedVolatility if ticker.impliedVolatility else 0,
                'Delta': ticker.delta if ticker.delta else 0,
                'Gamma': ticker.gamma if ticker.gamma else 0,
                'Theta': ticker.theta if ticker.theta else 0,
                'Vega': ticker.vega if ticker.vega else 0
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
                high_water_mark = realized_pn_l_account_value
            else:
                try:
                    high_water_mark = float(high_water_mark)
                except Exception:
                    # If persisted as string previously, coerce to float
                    high_water_mark = realized_pn_l_account_value

            if realized_pn_l_account_value > high_water_mark:
                high_water_mark = realized_pn_l_account_value
                if self.account_config is not None:
                    self.account_config['high_water_mark'] = high_water_mark
                logger.info(f"High water mark updated to {high_water_mark}")

            # Create DataFrame with common metrics
            metrics = {
                'NetLiquidation': liquidation_account_value,
                'StartingValue':starting_value,
                'HighWaterMark': high_water_mark,
                'RealizedPnLPrice': realized_pn_l_account_value,
                'RealizedPnLPercent': realized_pn_l_account_percent,
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

            # # Get SPY price
            logger.info(f"Getting {self.underlying_symbol} price...")
            await self.get_underlying_symbol_price(self.underlying_symbol)

            # Get USD/CAD ratio
            logger.info("Getting USD/CAD ratio...")
            data["fx_ratio"] = await self.get_fx_ratio()

            # Get account metrics
            logger.info("Getting account metrics...")
            account_df = await self.get_account_metrics()
            data['account'] = account_df
            #
            # Get option chain
            logger.info("Getting option chain...")
            options_df = await self.get_option_chain()
            data['options'] = options_df
            #
            # Get active positions
            logger.info("Getting active positions...")
            positions_df = await self.get_active_positions(self.underlying_symbol)
            data['active_contract'] = positions_df
            #
            # # Get trade statistics
            # logger.info("Getting trade statistics...")
            # stats_df = await self.get_trade_statistics()
            # data['statistics'] = stats_df
            
            logger.info("Data collection completed successfully")
            return data
            
        except Exception as e:
            logger.error(f"Error during data collection: {e}")
            return None
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self.disconnect()
        except:
            pass
