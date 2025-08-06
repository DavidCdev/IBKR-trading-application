from ib_async import *
import asyncio
import pandas as pd

# Connect to TWS
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading port
# ib.connect('127.0.0.1', 7496, clientId=1)  # Live trading port


# Create SPY contract
spy_stock = Stock('SPY', 'SMART', 'USD')
ib.qualifyContracts(spy_stock)

# Get market data
spy_ticker = ib.reqMktData(spy_stock)
ib.sleep(2)  # Wait for data

print(f"SPY Price: ${spy_ticker.marketPrice()}")


# Get option chain for SPY
chains = ib.reqSecDefOptParams('SPY', '', 'STK', 756733)  # SPY conId
print("Getting chains successfully")
# Filter for your expiration date (2025-08-05)
target_expiry = '20250805'
strikes = []
for chain in chains:
    if target_expiry in chain.expirations:
        strikes = chain.strikes
        break


print("Options")
# Create option contracts for $502 strike
call_502 = Option('SPY', target_expiry, 502, 'C', 'SMART')
put_502 = Option('SPY', target_expiry, 502, 'P', 'SMART')

ib.qualifyContracts(call_502, put_502)
print("reqMktData")
# Get option market data
call_ticker = ib.reqMktData(call_502, '', False, False)
put_ticker = ib.reqMktData(put_502, '', False, False)
ib.sleep(2)

print(f"Call Bid: ${call_ticker.bid}, Ask: ${call_ticker.ask}")
print(f"Put Bid: ${put_ticker.bid}, Ask: ${put_ticker.ask}")

# Greeks are available in the ticker object
print(f"Call Delta: {call_ticker.modelGreeks.delta if call_ticker.modelGreeks else 'N/A'}")
print(f"Call Gamma: {call_ticker.modelGreeks.gamma if call_ticker.modelGreeks else 'N/A'}")
print(f"Call Theta: {call_ticker.modelGreeks.theta if call_ticker.modelGreeks else 'N/A'}")
print(f"Call Vega: {call_ticker.modelGreeks.vega if call_ticker.modelGreeks else 'N/A'}")

# Volume and Open Interest are in the ticker
print(f"Call Volume: {call_ticker.volume}")
print(f"Call Open Interest: {call_ticker.openInterest}")
print(f"Put Volume: {put_ticker.volume}")
print(f"Put Open Interest: {put_ticker.openInterest}")


# Get account summary
account_summary = ib.accountSummary()

# Extract key metrics
account_metrics = {}
for item in account_summary:
    if item.tag == 'NetLiquidation':
        account_metrics['Account Value'] = float(item.value)
    elif item.tag == 'DayTradesRemaining':
        account_metrics['Day Trades Remaining'] = item.value
    elif item.tag == 'BuyingPower':
        account_metrics['Buying Power'] = float(item.value)

print(f"Account Value: ${account_metrics.get('Account Value', 0):,.2f}")


# Get current positions
positions = ib.positions()

for position in positions:
    if position.contract.symbol == 'SPY' and position.contract.secType == 'OPT':
        print(f"Symbol: {position.contract.symbol}")
        print(f"Strike: {position.contract.strike}")
        print(f"Right: {position.contract.right}")
        print(f"Quantity: {position.position}")
        print(f"Avg Cost: ${position.avgCost}")

# Get P&L for positions
pnl = ib.reqPnL('your_account_id')  # Replace with your account ID

# For single position P&L
for position in positions:
    if position.contract.symbol == 'SPY':
        pnl_single = ib.reqPnLSingle('your_account_id', '', position.contract.conId)
        print(f"Daily P&L: ${pnl_single.dailyPnL}")
        print(f"Unrealized P&L: ${pnl_single.unrealizedPnL}")


# You'll need to track this yourself or get from executions
executions = ib.reqExecutions()

# Calculate win rate and statistics
wins = 0
losses = 0
total_win_amount = 0
total_loss_amount = 0

# This requires processing your execution history
# and calculating realized P&L per trade

print(f"Total Trades: {len(executions)}")
print(f"Win Rate: {(wins/(wins+losses)*100):.1f}%" if (wins+losses) > 0 else "N/A")


# Get currency exchange rates
usd_cad = Forex('USD', 'CAD')
ib.qualifyContracts(usd_cad)

usd_cad_ticker = ib.reqMktData(usd_cad)
ib.sleep(2)

print(f"USD/CAD: {usd_cad_ticker.marketPrice()}")



