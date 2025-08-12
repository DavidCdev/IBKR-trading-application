import time

from ib_async import *
import asyncio
import pandas as pd
import time
from datetime import datetime

# Connect to TWS
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2)  # Paper trading port

# Wait for connection to be established
print("Waiting for connection to be established...")
time.sleep(5)

# Check if connected
if not ib.isConnected():
    print("Failed to connect to TWS")
    exit(1)

print("Connected to TWS successfully")

# Create a more specific contract with expiration date
# Using the first expiration date from the error message: 20250815 (August 15, 2025)
call_contract = Option('SPY', 
                      strike=502, 
                      right='C', 
                      exchange='SMART',
                      lastTradeDateOrContractMonth='20250815')

print(f"Requesting contract qualification for: {call_contract}")
contracts = ib.qualifyContracts(call_contract)

# Wait a bit more for contract qualification
time.sleep(3)

print(f"Contracts returned: {contracts}")

# Check if contracts were qualified successfully
if not contracts or contracts[0] is None:
    print("Failed to qualify contracts. Please check:")
    print("1. TWS is running and accepting connections")
    print("2. Contract specifications are correct")
    print("3. You have market data permissions")
    exit(1)

print(f"Successfully qualified contract: {contracts[0]}")

# Check current time and market status
current_time = datetime.now()
print(f"Current time: {current_time}")
print("Note: Market data may not be available outside of market hours (9:30 AM - 4:00 PM ET, weekdays)")

# Request market data
ticker = ib.reqMktData(contracts[0],
    genericTickList='100,101,106',  # Volume, Open Interest, IV
    snapshot=False
)

# Wait for market data to arrive with progress updates
print("Waiting for market data...")
for i in range(20):  # Wait up to 20 seconds
    time.sleep(1)
    print(f"Waiting... {i+1}/20 seconds")
    
    # Check if we have any data
    if hasattr(ticker, 'last') and ticker.last is not None:
        print(f"Last price received: {ticker.last}")
        break
    if hasattr(ticker, 'bid') and ticker.bid is not None:
        print(f"Bid received: {ticker.bid}")
        break
    if hasattr(ticker, 'ask') and ticker.ask is not None:
        print(f"Ask received: {ticker.ask}")
        break

print("\n=== Market Data Summary ===")

# Basic price data
if hasattr(ticker, 'last') and ticker.last is not None:
    print(f"Last Price: {ticker.last}")
else:
    print("Last Price: Not available")

if hasattr(ticker, 'bid') and ticker.bid is not None:
    print(f"Bid: {ticker.bid}")
else:
    print("Bid: Not available")

if hasattr(ticker, 'ask') and ticker.ask is not None:
    print(f"Ask: {ticker.ask}")
else:
    print("Ask: Not available")

# Greeks
print("\n=== Greeks ===")
if hasattr(ticker, 'modelGreeks') and ticker.modelGreeks is not None:
    delta = ticker.modelGreeks.delta
    gamma = ticker.modelGreeks.gamma
    theta = ticker.modelGreeks.theta
    vega = ticker.modelGreeks.vega
    
    print(f"Delta: {delta}")
    print(f"Gamma: {gamma}")
    print(f"Theta: {theta}")
    print(f"Vega: {vega}")
else:
    print("Greeks not available (may need market to be open)")

# Open Interest and Volume
print("\n=== Volume & Open Interest ===")
if hasattr(ticker, 'callOpenInterest') and not pd.isna(ticker.callOpenInterest):
    open_interest = ticker.callOpenInterest
    print(f"Call Open Interest: {open_interest}")
else:
    print("Call Open Interest: Not available")

if hasattr(ticker, 'callVolume') and not pd.isna(ticker.callVolume):
    volume = ticker.callVolume
    print(f"Call Volume: {volume}")
else:
    print("Call Volume: Not available")

# Additional debugging info
print("\n=== Debug Info ===")
print(f"Ticker object type: {type(ticker)}")
print(f"Ticker attributes: {[attr for attr in dir(ticker) if not attr.startswith('_')]}")
print(f"Contract details: {contracts[0]}")

# Disconnect
ib.disconnect()
print("\nDisconnected from TWS")
