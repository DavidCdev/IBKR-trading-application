import asyncio
import logging
from typing import Optional, Dict, Any, List
from ib_async import IB, Stock, Option, util
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class IBDataCollectorImproved:
    """
    Improved IB Data Collector with better error handling and resource management
    """
    
    def __init__(self, host='127.0.0.1', port=7497, clientId=1, timeout=30):
        self.ib = IB()
        self.host = host
        self.port = port
        self.clientId = clientId
        self.timeout = timeout
        self.spy_price = 0
        self._active_subscriptions = set()  # Track active market data subscriptions
        
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
    
    async def get_spy_price(self) -> Optional[float]:
        """Get current SPY price with improved error handling"""
        try:
            spy = Stock('SPY', 'SMART', 'USD')
            
            # Qualify the contract
            spy_qualified = await self.ib.qualifyContractsAsync(spy)
            if not spy_qualified or spy_qualified[0] is None:
                logger.error("Could not qualify SPY contract")
                return None
            
            # Request market data
            spy_ticker = self.ib.reqMktData(spy_qualified[0])
            self._active_subscriptions.add(spy_qualified[0])
            
            # Wait for data with timeout
            await asyncio.sleep(2)
            
            price = spy_ticker.marketPrice()
            if price and price > 0:
                self.spy_price = price
                logger.info(f"SPY Price: ${price:.2f}")
                
                # Cancel market data subscription
                self.ib.cancelMktData(spy_qualified[0])
                self._active_subscriptions.discard(spy_qualified[0])
                
                return price
            else:
                logger.warning("Invalid SPY price received")
                return None
                
        except Exception as e:
            logger.error(f"Error getting SPY price: {e}")
            return None
    
    async def get_option_chain(self, symbol='SPY', num_strikes=10) -> pd.DataFrame:
        """Get option chain data with improved error handling and validation"""
        try:
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
            if self.spy_price == 0:
                await self.get_spy_price()

            if self.spy_price == 0:
                logger.error("Unable to get current stock price for strike selection")
                return pd.DataFrame()

            # Select strikes around current price
            current_price = self.spy_price
            strikes = sorted([float(s) for s in chain.strikes])

            # Find strikes around current price with better logic
            selected_strikes = []
            price_range = current_price * 0.1  # 10% range around current price
            
            for strike in strikes:
                if abs(strike - current_price) <= price_range:
                    selected_strikes.append(strike)

            # Take the closest strikes
            selected_strikes = sorted(selected_strikes, key=lambda x: abs(x - current_price))[:num_strikes]

            if not selected_strikes:
                logger.warning("No suitable strikes found around current price")
                return pd.DataFrame()

            # Get nearest expirations
            expirations = sorted(chain.expirations)[:3]  # Get first 3 expirations

            option_data = []

            for expiration in expirations:
                for strike in selected_strikes:
                    try:
                        # Create CALL option
                        call_option = Option(symbol, expiration, strike, 'C', 'SMART')
                        # Create PUT option
                        put_option = Option(symbol, expiration, strike, 'P', 'SMART')

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
                        logger.warning(f"Error processing option {symbol} {expiration} {strike}: {e}")
                        continue

            if option_data:
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
    
    async def get_active_positions(self) -> pd.DataFrame:
        """Get active positions with improved error handling"""
        try:
            positions = await self.ib.positionsAsync()
            
            if not positions:
                logger.info("No active positions found")
                return pd.DataFrame()
            
            position_data = []
            for position in positions:
                try:
                    data = {
                        'Symbol': position.contract.symbol,
                        'SecType': position.contract.secType,
                        'Exchange': position.contract.exchange,
                        'Currency': position.contract.currency,
                        'Position': position.position,
                        'AvgCost': position.avgCost,
                        'MarketValue': position.marketValue
                    }
                    position_data.append(data)
                except Exception as e:
                    logger.warning(f"Error processing position: {e}")
                    continue
            
            if position_data:
                df = pd.DataFrame(position_data)
                logger.info(f"Retrieved {len(df)} active positions")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return pd.DataFrame()
    
    async def get_account_metrics(self) -> pd.DataFrame:
        """Get account metrics with improved error handling"""
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
            
            # Create DataFrame with common metrics
            metrics = {
                'NetLiquidation': account_data.get('NetLiquidation', 0),
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
            
            # Get SPY price
            logger.info("Getting SPY price...")
            spy_price = await self.get_spy_price()
            data['spy_price'] = spy_price
            
            # Get account metrics
            logger.info("Getting account metrics...")
            account_df = await self.get_account_metrics()
            data['account'] = account_df
            
            # Get option chain
            logger.info("Getting option chain...")
            options_df = await self.get_option_chain()
            data['options'] = options_df
            
            # Get active positions
            logger.info("Getting active positions...")
            positions_df = await self.get_active_positions()
            data['positions'] = positions_df
            
            # Get trade statistics
            logger.info("Getting trade statistics...")
            stats_df = await self.get_trade_statistics()
            data['statistics'] = stats_df
            
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
