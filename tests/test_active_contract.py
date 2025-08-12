from statistics import quantiles
from ib_async import *
from ib_async import IB, Contract, Order, Trade, Ticker, Stock, Option, Forex
from ib_async import MarketOrder, LimitOrder, StopOrder, util, ExecutionFilter
from ib_async.objects import Fill, CommissionReport, PnL, AccountValue
from math import isnan
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import date, timedelta, datetime
import time
import asyncio
import logging
#
# class DataCollector:
#     def __init__(self, host='127.0.0.1', port=7497, clientId=3):
#         self.ib = IB()
#         self.host = host
#         self.port = port
#         self.clientId = clientId
#         self.spy_price = 0
#
#     async def initialzation(self):
#         self.connectflag = await self.connect()
#         data = {
#             'symbol': "SPY",
#             'secType': 'OPT',
#             'exchange': 'SMART',
#             'currency': 'USD'
#         }
#         _underlying_symbol = "SPY"
#         symbol = data.get('underlying_symbol', _underlying_symbol)
#         option_type = data.get('option_type', 'BOTH').upper()
#
#         underlying = Stock(symbol, 'SMART', 'USD')
#         await self.ib.qualifyContractsAsync(underlying)
#
#         if not underlying.conId:
#             raise ValueError(f"Could not qualify underlying contract for {symbol}")
#
#         # Request option chain parameters
#         chains = await self.ib.reqSecDefOptParamsAsync(
#             underlyingSymbol=underlying.symbol,
#             futFopExchange='',
#             underlyingSecType=underlying.secType,
#             underlyingConId=underlying.conId
#         )
#
#         if not chains:
#             raise ValueError(f"No option chains found for {symbol}")
#
#         # Find target expiration with fallback logic
#         today_str = date.today().strftime('%Y%m%d')
#         tomorrow_str = (date.today() + timedelta(days=1)).strftime('%Y%m%d')
#
#         all_expirations = set()
#         for chain in chains:
#             all_expirations.update(chain.expirations)
#         sorted_expirations = sorted(all_expirations)
#
#         # Try multiple expiration strategies
#         target_expiration = None
#         expiration_type = None
#
#         # Strategy 1: Try 1DTE first (more reliable than 0DTE)
#         if tomorrow_str in sorted_expirations:
#             target_expiration = tomorrow_str
#             expiration_type = "1DTE"
#         # Strategy 2: Try 0DTE if 1DTE not available
#         elif today_str in sorted_expirations:
#             target_expiration = today_str
#             expiration_type = "0DTE"
#         # Strategy 3: Find nearest available expiration
#         else:
#             target_expiration = next((exp for exp in sorted_expirations if exp > today_str), None)
#             expiration_type = "NEAREST"
#
#         if not target_expiration:
#             # Final fallback: use the first available expiration
#             if sorted_expirations:
#                 target_expiration = sorted_expirations[0]
#                 expiration_type = "FALLBACK"
#             else:
#                 raise ValueError(f"No suitable expiration found for {symbol}")
#
#         print(f"Using {expiration_type} expiration: {target_expiration}")
#
#         # Collect strikes and create contracts
#         strikes = set()
#         for chain in chains:
#             if target_expiration in chain.expirations:
#                 strikes.update(chain.strikes)
#
#         # Limit strikes to avoid overwhelming the system
#         sorted_strikes = sorted(strikes)
#         if len(sorted_strikes) > 20:  # Limit to 20 strikes max
#             # Take strikes around current price (if available)
#             current_price = None
#             try:
#                 # Try to get current price for strike selection
#                 ticker = self.ib.reqMktData(underlying, '', False, False)
#                 await asyncio.sleep(1)  # Wait for price
#                 current_price = ticker.last if ticker.last and not util.isNan(ticker.last) else ticker.close
#                 self.ib.cancelMktData(underlying)
#             except:
#                 pass
#
#             if current_price:
#                 # Select strikes around current price
#                 mid_index = len(sorted_strikes) // 2
#                 start_index = max(0, mid_index - 10)
#                 end_index = min(len(sorted_strikes), mid_index + 10)
#                 selected_strikes = sorted_strikes[start_index:end_index]
#             else:
#                 # Take first 20 strikes
#                 selected_strikes = sorted_strikes[:20]
#         else:
#             selected_strikes = sorted_strikes
#
#         rights = []
#         if option_type in ['C', 'BOTH']:
#             rights.append('C')
#         if option_type in ['P', 'BOTH']:
#             rights.append('P')
#
#         contracts = []
#         for strike in selected_strikes:
#             for right in rights:
#                 contract = Option(
#                     symbol=symbol,
#                     lastTradeDateOrContractMonth=target_expiration,
#                     strike=strike,
#                     right=right,
#                     exchange='SMART',
#                     currency='USD'
#                 )
#                 contracts.append(contract)
#
#         # Qualify in smaller batches with better error handling
#         qualified_contracts = []
#         batch_size = 25  # Smaller batches
#         for i in range(0, len(contracts), batch_size):
#             batch = contracts[i:i + batch_size]
#             try:
#                 qualified_batch = await self.ib.qualifyContractsAsync(*batch)
#                 # Filter out None results from failed qualifications
#                 qualified_batch = [c for c in qualified_batch if c is not None]
#                 qualified_contracts.extend(qualified_batch)
#                 await asyncio.sleep(0.2)  # Longer delay between batches
#             except Exception as e:
#                 logger.warning(f"Error qualifying batch {i // batch_size}: {e}")
#                 # Continue with next batch instead of failing completely
#
#         # Convert to response format
#         contract_data = []
#         for contract in qualified_contracts:
#             if contract.conId:
#                 contract_info = {
#                     'symbol': contract.symbol,
#                     'strike': contract.strike,
#                     'right': contract.right,
#                     'expiry': contract.lastTradeDateOrContractMonth,
#                     'local_symbol': contract.localSymbol,
#                     'con_id': contract.conId,
#                     'exchange': contract.exchange,
#                     'currency': contract.currency
#                 }
#                 contract_data.append(contract_info)
#
#         print(f"Retrieved {len(contract_data)} qualified option contracts for {symbol}")
#
#         # Store for tests
#         self.option_contracts = contract_data
#
#         self.ib.disconnect()
#
#         result =  {
#             'underlying_symbol': symbol,
#             'expiration': target_expiration,
#             'expiration_type': expiration_type,
#             'option_type': option_type,
#             'contracts': contract_data,
#             'count': len(contract_data)
#         }
#         return result
#
#
#     async def connect(self):
#         """Connect to TWS/IB Gateway"""
#         try:
#             await self.ib.connectAsync(self.host, self.port, clientId=self.clientId)
#             print("Connected to Interactive Brokers")
#             return True
#         except Exception as e:
#             print(f"Connection failed: {e}")
#             return False
#

###################################################################################
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=3)


# account_values = ib.accountValues()
# print(account_values)

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
        if current_price is not None and entry_price is not None:
            price_diff = current_price - entry_price
            multiplier = 100 if contract.secType == 'OPT' else 1
            return price_diff * quantity * multiplier
        return 0.0
####################################################################################
def get_last_spy():
    spy = Stock('IBKR', 'SMART', 'USD')
    qualified_contract = ib.qualifyContracts(spy)[0]
    tickers = ib.reqTickers(qualified_contract)
    ticker = tickers[0]
    last_spy = ticker.close
    print(ticker)
    print(f"SPY Last Price: {ticker.close}")
    print(f"SPY Bid: {ticker.bid}")
    print(f"SPY Ask: {ticker.ask}")
    return last_spy

last_spy_value = get_last_spy()
####################################################################################
positions = ib.positions()
print(positions)
current_prices = {
    "SPY": last_spy_value,
    "USDCAD": last_spy_value,
    "IBKR_OPTION": last_spy_value,
}

def calculate_pnl_detailed(positions, current_prices):
    results = []
    for pos in positions:
        if 'USDCAD' in str(pos.contract):
            # Forex
            pnl_dollar = pos.position * (current_prices['USDCAD'] - pos.avgCost)
            pnl_percent = ((current_prices['USDCAD'] - pos.avgCost) / pos.avgCost) * 100
            currency = 'CAD'

        elif pos.contract.symbol == 'IBKR':
            # Option
            pnl_dollar = pos.position * (current_prices['IBKR_OPTION'] - pos.avgCost)
            pnl_percent = ((current_prices['IBKR_OPTION'] - pos.avgCost) / pos.avgCost) * 100
            currency = 'USD'

        elif pos.contract.symbol == 'SPY':
            # Stock (Short)
            pnl_dollar = pos.position * (current_prices['SPY'] - pos.avgCost)
            pnl_percent = -((current_prices['SPY'] - pos.avgCost) / pos.avgCost) * 100 * (-1 if pos.position < 0 else 1)
            currency = 'USD'

        results.append({
            'symbol': pos.contract.symbol if hasattr(pos.contract, 'symbol') else 'USDCAD',
            'position_size': pos.position,
            'avg_cost': pos.avgCost,
            'pnl_dollar': round(pnl_dollar, 2),
            'pnl_percent': round(pnl_percent, 2),
            'currency': currency
        })

    return results

active_contract = calculate_pnl_detailed(positions, current_prices)
print(f"Active Contract is : {active_contract}")

_active_contracts: Dict[str, ActiveContract] = {}
for position in positions:
    if position.contract.symbol == "IBKR":
        quantity = position.position
        avg_cost = position.avgCost
        Pnl_price = quantity * (last_spy_value - avg_cost)
        Pnl_percent = ((last_spy_value - avg_cost) / avg_cost) * 100
        print(position)
        print(f"SPY active contract: {position.contract.symbol}")
        print(f"SPY active contract Quantity: {position.position}")
        print(f"SPY active contract Symbol: {position.contract.symbol}")
        print(f"SPY active contract's PnL price: {Pnl_price}")
        print(f"SPY active contract's PnL %: {Pnl_percent}")

    else:
        print("There wasn't SPY active contract")
###################################################################################
# 2. Define the Forex contract for USD/CAD
# contract = Forex('USDCAD', 'IDEALPRO') # Use 'IDEALPRO' for true forex trading
# ib.qualifyContracts(contract)
# ticker = ib.reqMktData(contract, '', False, False)
# print(ticker)
###################################################################################

#
#
# async def main():
#     data_collector_ = DataCollector()
#     dataflag = await data_collector_.initialzation()
#     print(f"Connection status: {dataflag}")
# if __name__ == "__main__":
#     asyncio.run(main())