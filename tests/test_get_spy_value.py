import asyncio
from ib_async import *


async def get_spy_price():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=3)

    try:
        # Request delayed market data (free)
        ib.reqMarketDataType(3)  # 1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen

        # Create SPY contract
        spy = Stock('AAPL', 'SMART', 'USD')
        qualified_contracts = await ib.qualifyContractsAsync(spy)
        spy_contract = qualified_contracts[0]
        print(f"Contract: {spy_contract}")

        # Request market data
        ticker = ib.reqMktData(spy_contract, '', False, False)
        print(f"TTTTTTTTTTTTTiker price: {ticker.marketPrice()}")
        # Wait longer for data and check periodically
        for i in range(10):  # Wait up to 10 seconds
            await asyncio.sleep(1)
            if ticker.bid > 0 or ticker.last > 0:
                break
            print(f"Waiting for data... attempt {i + 1}")

        print(f"Ticker after wait: {ticker}")

        # Check all possible price fields
        if ticker.last and ticker.last > 0:
            print(f"SPY Last Price: ${ticker.last}")
        elif ticker.bid > 0 and ticker.ask > 0:
            mid_price = (ticker.bid + ticker.ask) / 2
            print(f"SPY Mid Price: ${mid_price:.2f} (Bid: ${ticker.bid}, Ask: ${ticker.ask})")
        elif ticker.close and ticker.close > 0:
            print(f"SPY Previous Close: ${ticker.close}")
        else:
            print("No price data available")
            print(f"Last: {ticker.last}, Bid: {ticker.bid}, Ask: {ticker.ask}")
            print(f"Close: {ticker.close}, Open: {ticker.open}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(get_spy_price())