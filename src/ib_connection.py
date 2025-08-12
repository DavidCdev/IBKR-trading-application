import asyncio
from ib_async import IB, Stock, Option, util
import pandas as pd
from datetime import datetime, timedelta
import numpy as np


class IBDataCollector:
    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        self.ib = IB()
        self.host = host
        self.port = port
        self.clientId = clientId
        self.spy_price = 0

    async def connect(self):
        """Connect to TWS/IB Gateway"""
        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.clientId)
            print("Connected to Interactive Brokers")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def get_spy_price(self):
        """Get current SPY price"""
        try:
            spy = Stock('SPY', 'SMART', 'USD')
            spy_qualified = await self.ib.qualifyContractsAsync(spy)
            if spy_qualified:
                spy_ticker = self.ib.reqMktData(spy_qualified[0])
                await asyncio.sleep(2)  # Wait for data
                self.spy_price = spy_ticker.marketPrice()
                self.ib.cancelMktData(spy_qualified[0])
                return self.spy_price
        except Exception as e:
            print(f"Error getting SPY price: {e}")
            return None

    async def get_option_chain(self, symbol='SPY', num_strikes=10):
        """Get option chain data with Greeks"""
        try:
            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            stock_qualified = await self.ib.qualifyContractsAsync(stock)

            if not stock_qualified or stock_qualified[0] is None:
                print(f"Could not qualify {symbol} contract")
                return pd.DataFrame()

            # Get option chain
            chains = await self.ib.reqSecDefOptParamsAsync(
                stock_qualified[0].symbol,
                '',
                stock_qualified[0].secType,
                stock_qualified[0].conId
            )

            if not chains:
                print("No option chains found")
                return pd.DataFrame()

            # Get the first chain (usually the most liquid exchange)
            chain = chains[0]

            # Get current stock price for strike selection
            if self.spy_price == 0:
                await self.get_spy_price()

            # Select strikes around current price
            current_price = self.spy_price
            strikes = sorted([float(s) for s in chain.strikes])

            # Find strikes around current price
            selected_strikes = []
            for strike in strikes:
                if abs(strike - current_price) <= (num_strikes * 5):  # Adjust range as needed
                    selected_strikes.append(strike)

            selected_strikes = sorted(selected_strikes)[:num_strikes]

            # Get nearest expiration
            expirations = sorted(chain.expirations)[:3]  # Get first 3 expirations

            option_data = []

            for expiration in expirations:
                for strike in selected_strikes:
                    # Create CALL option
                    call_option = Option(symbol, expiration, strike, 'C', 'SMART')
                    # Create PUT option
                    put_option = Option(symbol, expiration, strike, 'P', 'SMART')

                    # Qualify contracts
                    call_qualified = await self.ib.qualifyContractsAsync(call_option)
                    put_qualified = await self.ib.qualifyContractsAsync(put_option)

                    # Skip if contract is not valid or not found
                    if not call_qualified or call_qualified[0] is None:
                        continue
                    if not put_qualified or put_qualified[0] is None:
                        continue

                    # Get market data and Greeks for CALL
                    call_ticker = self.ib.reqMktData(call_qualified[0], '', False, False)
                    await asyncio.sleep(1)

                    # Safely extract Greeks data
                    call_greeks = {}
                    if hasattr(call_ticker, 'modelGreeks') and call_ticker.modelGreeks:
                        if hasattr(call_ticker.modelGreeks, 'get'):
                            call_greeks = call_ticker.modelGreeks
                        else:
                            # Handle OptionComputation object
                            call_greeks = {
                                'delta': getattr(call_ticker.modelGreeks, 'delta', 0),
                                'gamma': getattr(call_ticker.modelGreeks, 'gamma', 0),
                                'theta': getattr(call_ticker.modelGreeks, 'theta', 0),
                                'vega': getattr(call_ticker.modelGreeks, 'vega', 0)
                            }

                    option_data.append({
                        'Type': 'CALL',
                        'Strike': strike,
                        'Expiration': expiration,
                        'Bid': call_ticker.bid if call_ticker.bid == call_ticker.bid else 0,
                        'Ask': call_ticker.ask if call_ticker.ask == call_ticker.ask else 0,
                        'Delta': call_greeks.get('delta', 0),
                        'Gamma': call_greeks.get('gamma', 0),
                        'Theta': call_greeks.get('theta', 0),
                        'Vega': call_greeks.get('vega', 0),
                        'Volume': call_ticker.volume if call_ticker.volume == call_ticker.volume else 0,
                        'OpenInt': getattr(call_ticker, 'openInterest', 0)
                    })
                    self.ib.cancelMktData(call_qualified[0])

                    # Get market data and Greeks for PUT
                    put_ticker = self.ib.reqMktData(put_qualified[0], '', False, False)
                    await asyncio.sleep(1)

                    # Safely extract Greeks data
                    put_greeks = {}
                    if hasattr(put_ticker, 'modelGreeks') and put_ticker.modelGreeks:
                        if hasattr(put_ticker.modelGreeks, 'get'):
                            put_greeks = put_ticker.modelGreeks
                        else:
                            # Handle OptionComputation object
                            put_greeks = {
                                'delta': getattr(put_ticker.modelGreeks, 'delta', 0),
                                'gamma': getattr(put_ticker.modelGreeks, 'gamma', 0),
                                'theta': getattr(put_ticker.modelGreeks, 'theta', 0),
                                'vega': getattr(put_ticker.modelGreeks, 'vega', 0)
                            }

                    option_data.append({
                        'Type': 'PUT',
                        'Strike': strike,
                        'Expiration': expiration,
                        'Bid': put_ticker.bid if put_ticker.bid == put_ticker.bid else 0,
                        'Ask': put_ticker.ask if put_ticker.ask == put_ticker.ask else 0,
                        'Delta': put_greeks.get('delta', 0),
                        'Gamma': put_greeks.get('gamma', 0),
                        'Theta': put_greeks.get('theta', 0),
                        'Vega': put_greeks.get('vega', 0),
                        'Volume': put_ticker.volume if put_ticker.volume == put_ticker.volume else 0,
                        'OpenInt': getattr(put_ticker, 'openInterest', 0)
                    })
                    self.ib.cancelMktData(put_qualified[0])

            return pd.DataFrame(option_data)

        except Exception as e:
            print(f"Error getting option chain: {e}")
            return pd.DataFrame()

    async def get_active_positions(self):
        """Get active positions"""
        try:
            positions = await self.ib.reqPositionsAsync()
            position_data = []

            for pos in positions:
                if pos.position != 0:  # Only active positions
                    # Get current market price
                    ticker = self.ib.reqMktData(pos.contract)
                    await asyncio.sleep(1)

                    current_price = ticker.marketPrice()
                    avg_cost = pos.avgCost
                    quantity = pos.position

                    # Calculate P&L
                    if current_price and avg_cost:
                        unrealized_pnl = (current_price - avg_cost) * quantity
                        unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
                    else:
                        unrealized_pnl = 0
                        unrealized_pnl_pct = 0

                    position_data.append({
                        'Symbol': pos.contract.symbol,
                        'Quantity': quantity,
                        'P/L($)': unrealized_pnl,
                        'P/L(%)': unrealized_pnl_pct,
                        'Avg_Cost': avg_cost,
                        'Current_Price': current_price
                    })

                    self.ib.cancelMktData(pos.contract)

            return pd.DataFrame(position_data)

        except Exception as e:
            print(f"Error getting positions: {e}")
            return pd.DataFrame()

    async def get_account_metrics(self):
        """Get account information and metrics"""
        try:
            # Get account summary using async method
            account_values = await self.ib.reqAccountSummaryAsync()
            print(account_values)
            metrics = {}
            for item in account_values:
                metrics[item.tag] = float(item.value) if item.value.replace('.', '').replace('-',
                                                                                             '').isdigit() else item.value

            # Get managed accounts (synchronous method, but we're already in async context)
            try:
                managed_accounts = self.ib.managedAccounts()
                account_id = managed_accounts[0] if managed_accounts else 'N/A'
            except Exception:
                account_id = 'N/A'

            # Calculate additional metrics
            account_data = {
                'Account': account_id,
                'Value': metrics.get('NetLiquidation', 0),
                'Starting_Value': metrics.get('NetLiquidation', 0),  # You might want to store this separately
                'High_Water_Mark': metrics.get('NetLiquidation', 0),  # You might want to track this over time
                'Daily_PnL': metrics.get('DailyPnL', 0),
                'Daily_PnL_Pct': (metrics.get('DailyPnL', 0) / metrics.get('NetLiquidation', 1)) * 100 if metrics.get(
                    'NetLiquidation', 0) != 0 else 0
            }

            return pd.DataFrame([account_data])

        except Exception as e:
            print(f"Error getting account metrics: {e}")
            return pd.DataFrame()

    async def get_trade_statistics(self, days_back=30):
        """Get trade statistics"""
        try:
            # Get executions for the specified period
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            executions = await self.ib.reqExecutionsAsync()

            if not executions:
                return pd.DataFrame([{
                    'Win_Rate': 0,
                    'Total_Wins_Count': 0,
                    'Total_Wins_Sum': 0,
                    'Total_Losses_Count': 0,
                    'Total_Losses_Sum': 0,
                    'Total_Trades': 0
                }])

            # Process trades
            trades = {}
            for execution in executions:
                symbol = execution.contract.symbol
                if symbol not in trades:
                    trades[symbol] = []
                trades[symbol].append(execution)

            wins = []
            losses = []

            for symbol, symbol_executions in trades.items():
                # Simple P&L calculation (you might want to make this more sophisticated)
                for exec in symbol_executions:
                    # This is a simplified calculation - you might want to group by order ID
                    # and calculate proper P&L per complete trade
                    try:
                        # Handle Fill object structure
                        if hasattr(exec, 'execution'):
                            # Execution object structure
                            pnl = exec.execution.price * exec.execution.shares
                        elif hasattr(exec, 'price') and hasattr(exec, 'shares'):
                            # Direct Fill object structure
                            pnl = exec.price * exec.shares
                        else:
                            # Skip if we can't determine the structure
                            continue

                        if pnl > 0:
                            wins.append(pnl)
                        else:
                            losses.append(abs(pnl))
                    except Exception:
                        # Skip this execution if we can't calculate P&L
                        continue

            total_trades = len(wins) + len(losses)
            win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

            stats = {
                'Win_Rate': win_rate,
                'Total_Wins_Count': len(wins),
                'Total_Wins_Sum': sum(wins),
                'Total_Losses_Count': len(losses),
                'Total_Losses_Sum': sum(losses),
                'Total_Trades': total_trades
            }

            return pd.DataFrame([stats])

        except Exception as e:
            print(f"Error getting trade statistics: {e}")
            return pd.DataFrame([{
                'Win_Rate': 0,
                'Total_Wins_Count': 0,
                'Total_Wins_Sum': 0,
                'Total_Losses_Count': 0,
                'Total_Losses_Sum': 0,
                'Total_Trades': 0
            }])

    async def collect_all_data(self):
        """Collect all requested data"""
        print("Starting data collection...")

        # Connect to IB
        if not await self.connect():
            return None

        try:
            # Get SPY price
            print("Getting SPY price...")
            spy_price = await self.get_spy_price()
            print(f"SPY Price: ${spy_price}")

            # # Get account metrics
            # print("Getting account metrics...")
            # account_df = await self.get_account_metrics()
            #
            # # Get option chain
            # print("Getting option chain...")
            # options_df = await self.get_option_chain()
            # print(f"Retrieved {len(options_df)} option contracts")
            #
            # # Get active positions
            # print("Getting active positions...")
            # positions_df = await self.get_active_positions()
            # print(f"Retrieved {len(positions_df)} active positions")
            #
            # # Get trade statistics
            # print("Getting trade statistics...")
            # stats_df = await self.get_trade_statistics()

            return {
                'spy_price': spy_price,
                # 'options': options_df,
                # 'positions': positions_df,
                # 'account': account_df,
                # 'statistics': stats_df
            }

        except Exception as e:
            print(f"Error collecting data: {e}")
            return None

