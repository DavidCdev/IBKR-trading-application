from ib_async import IB, Stock
import time

def on_price_update(ticker):
    # This callback gets called when new market data updates occur
    print(f"SPY Price Update - Last: {ticker.last}, Bid: {ticker.bid}, Ask: {ticker.ask}")

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2)

# Define SPY contract
spy = Stock('SPY', 'SMART', 'USD')
spy_qualified = ib.qualifyContracts(spy)
if spy_qualified:
    ticker = ib.reqMktData(spy_qualified[0], snapshot=False, regulatorySnapshot=False)

# Register a callback handler for live updates
ticker.updateEvent += on_price_update

try:
    # Run the message loop to process events and callbacks, keep alive for 10 seconds
    ib.run(timeout=10)
finally:
    ib.disconnect()
