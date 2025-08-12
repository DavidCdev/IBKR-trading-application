import asyncio
from ib_async import *


async def get_usd_cad_ratio():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=2)  # Connect to TWS or Gateway

    # Create Forex contract for USD/CAD
    contract = Forex('USDCAD', 'IDEALPRO')
    await ib.qualifyContractsAsync(contract)
    # Request market data
    ticker = ib.reqMktData(contract, '', False, False)

    # Allow some time to receive market data updates
    await asyncio.sleep(2)

    # Get the last price as the USD/CAD exchange rate
    print(f"ticker: {ticker}")
    # usd_cad_ratio = ticker.last
    print(f"Ratio is :{ticker.close}")

    ib.disconnect()  # Disconnect when done
    return ticker



# Run the async function to get the USD/CAD rate
usd_cad_rate = asyncio.run(get_usd_cad_ratio())
print(f"USD/CAD Exchange Rate: {usd_cad_rate}")
