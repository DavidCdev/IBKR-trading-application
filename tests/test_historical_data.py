from ib_async import *
from datetime import datetime, timedelta
ib = IB()
ib.connect('127.0.0.1', 7498, clientId=3)


# Create a Stock contract for the symbol
stock = Stock("SPY", 'SMART', 'USD')

# Qualify the contract
qualified_contracts = ib.qualifyContracts(stock)

contract = qualified_contracts[0]

start_date = datetime.now() - timedelta(days=30)
end_date = datetime.now()

# Format dates for IB API (YYYYMMDD HH:mm:ss)
start_str = start_date.strftime('%Y%m%d %H:%M:%S')
end_str = end_date.strftime('%Y%m%d %H:%M:%S')

# Request historical data
# Using 1 day bars for daily data
bars = ib.reqHistoricalData(
    contract,
    end_str,
    f"{int((end_date - start_date).days)} D",  # Duration
    "1 day",  # Bar size
    "TRADES",  # What to show
    1,  # Use RTH
    1,  # Format date
    False,  # Keep up to date after bar
    []  # Chart options
)

if not bars:
    print(f"No historical data returned for {contract.symbol}")
    exit()

# Convert bars to list of dictionaries
historical_data = []
for bar in bars:
    historical_data.append({
        'timestamp': bar.date,
        'open': bar.open,
        'high': bar.high,
        'low': bar.low,
        'close': bar.close,
        'volume': bar.volume
    })

print(f"Retrieved {len(historical_data)} historical data points for {contract.symbol}")


for history_data_point in historical_data:
    print(f"Historical data: {history_data_point}")
