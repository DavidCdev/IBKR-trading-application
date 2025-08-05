# options_data_fetcher.py
import asyncio
import sys
from ib_async import *
import time
from datetime import datetime, timedelta
import pandas as pd


class IBOptionsDataFetcher:
    def __init__(self):
        self.ib = IB()
        # Set up event handlers for debugging
        self.ib.connectedEvent += self.on_connected
        self.ib.disconnectedEvent += self.on_disconnected
        self.ib.errorEvent += self.on_error

    def on_connected(self):
        print("✅ Connected event triggered")

    def on_disconnected(self):
        print("📡 Disconnected event triggered")

    def on_error(self, reqId, errorCode, errorString, contract):
        print(f"⚠️ Error {errorCode}: {errorString}")

    async def connect_with_retry(self, host='127.0.0.1', port=4002, client_id=1, max_retries=3):
        """Connect with proper timeout and retry logic"""

        for attempt in range(max_retries):
            print(f"\n--- Connection Attempt {attempt + 1}/{max_retries} ---")
            print(f"Connecting to {host}:{port} with client ID {client_id}")

            try:
                await asyncio.wait_for(
                    self.ib.connectAsync(
                        host=host,
                        port=port,
                        clientId=client_id,
                        timeout=20
                    ),
                    timeout=25
                )

                print("⏳ Waiting for connection to stabilize...")
                await asyncio.sleep(3)

                if self.ib.isConnected():
                    print("✅ Connection established successfully!")

                    try:
                        current_time = await asyncio.wait_for(
                            self.ib.reqCurrentTimeAsync(),
                            timeout=10
                        )
                        print(f"🕐 IB Server time: {current_time}")
                        return True

                    except asyncio.TimeoutError:
                        print("⚠️ API call timed out, but connection seems stable")
                        return True
                    except Exception as e:
                        print(f"⚠️ API test failed: {e}")
                        return True

            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if self.ib.isConnected():
                    self.ib.disconnect()
                    await asyncio.sleep(2)

            if attempt < max_retries - 1:
                await asyncio.sleep(5)

        return False

    async def get_options_chain_data(self, symbol='SPY', exchange='SMART', currency='USD'):
        """Fetch comprehensive options chain data"""

        print(f"\n--- Fetching Options Data for {symbol} ---")

        try:
            # Create stock contract
            stock_contract = Stock(symbol, exchange, currency)

            # Qualify the contract
            qualified_contracts = await asyncio.wait_for(
                self.ib.qualifyContractsAsync(stock_contract),
                timeout=15
            )

            if not qualified_contracts:
                print("❌ Failed to qualify stock contract")
                return None

            stock = qualified_contracts[0]
            print(f"✅ Qualified contract: {stock}")

            # Get current stock price
            stock_ticker = self.ib.reqMktData(stock, '', False, False)
            await asyncio.sleep(3)  # Wait for market data

            current_price = stock_ticker.marketPrice() or stock_ticker.close
            print(f"📈 Current {symbol} price: ${current_price}")

            # Request option chain
            print("⏳ Requesting options chain...")
            chains = await asyncio.wait_for(
                self.ib.reqSecDefOptParamsAsync(
                    stock.symbol, '', stock.secType, stock.conId
                ),
                timeout=20
            )

            if not chains:
                print("❌ No options chains found")
                return None

            print(f"✅ Found {len(chains)} option chains")

            # Use the first chain (usually the most liquid)
            chain = chains[0]
            print(f"📊 Chain: {chain.exchange}, Multiplier: {chain.multiplier}")
            print(f"📅 Expirations: {len(chain.expirations)} available")
            print(f"🎯 Strikes: {len(chain.strikes)} available")

            # Get options data for multiple strikes and expirations
            options_data = []

            # Select a few expirations (next 3-4 monthly expirations)
            selected_expirations = sorted(chain.expirations)[:4]

            for expiration in selected_expirations:
                print(f"\n--- Processing expiration: {expiration} ---")

                # Find strikes around current price (±10%)
                price_range = current_price * 0.10
                relevant_strikes = [
                    s for s in chain.strikes
                    if current_price - price_range <= s <= current_price + price_range
                ]
                relevant_strikes = sorted(relevant_strikes)[:10]  # Limit to 10 strikes

                for strike in relevant_strikes:
                    print(f"⏳ Processing strike ${strike}...")

                    try:
                        # Create call and put contracts
                        call_contract = Option(
                            symbol, expiration, strike, 'C',
                            chain.exchange, multiplier=chain.multiplier, currency=currency
                        )

                        put_contract = Option(
                            symbol, expiration, strike, 'P',
                            chain.exchange, multiplier=chain.multiplier, currency=currency
                        )

                        # Qualify contracts
                        call_qualified = await self.ib.qualifyContractsAsync(call_contract)
                        put_qualified = await self.ib.qualifyContractsAsync(put_contract)

                        if not call_qualified or not put_qualified:
                            continue

                        call_contract = call_qualified[0]
                        put_contract = put_qualified[0]

                        # Get market data and Greeks
                        call_data = await self.get_option_details(call_contract, 'call')
                        put_data = await self.get_option_details(put_contract, 'put')

                        if call_data and put_data:
                            option_pair = {
                                "strike": strike,
                                "expiration": expiration,
                                "calls": call_data,
                                "puts": put_data
                            }
                            options_data.append(option_pair)

                            # Print formatted data
                            print(f"✅ Strike ${strike}:")
                            print(f"   📞 Call: ${call_data['mid']:.2f} (Δ{call_data['delta']:.2f})")
                            print(f"   📞 Put:  ${put_data['mid']:.2f} (Δ{put_data['delta']:.2f})")

                    except Exception as e:
                        print(f"⚠️ Error processing strike {strike}: {e}")
                        continue

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

            # Cancel market data subscriptions
            self.ib.cancelMktData(stock)

            return options_data

        except Exception as e:
            print(f"❌ Error fetching options data: {e}")
            return None

    async def get_option_details(self, contract, option_type):
        """Get detailed option data including Greeks"""

        try:
            # Request market data with Greeks
            ticker = self.ib.reqMktData(
                contract,
                '100,101,104,105,106,107,165,221,225',  # Greek snapshot + volume/OI
                False,
                False
            )

            # Wait for data to populate
            for i in range(10):  # Wait up to 5 seconds
                await asyncio.sleep(0.5)

                if (ticker.bid and ticker.ask and
                        hasattr(ticker, 'modelGreeks') and ticker.modelGreeks):
                    break

            # Extract data
            bid = ticker.bid or 0
            ask = ticker.ask or 0
            mid = (bid + ask) / 2 if (bid and ask) else (ticker.last or 0)

            # Get Greeks
            greeks = ticker.modelGreeks
            delta = greeks.delta if greeks else 0
            gamma = greeks.gamma if greeks else 0
            theta = greeks.theta if greeks else 0
            vega = greeks.vega if greeks else 0

            # Get volume and open interest
            volume = ticker.volume or 0

            # For open interest, we might need a separate request
            # IB doesn't always provide OI in real-time data

            option_data = {
                "mid": round(mid, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "delta": round(delta, 2),
                "gamma": round(gamma, 3),
                "theta": round(theta, 3),
                "vega": round(vega, 3),
                "volume": int(volume),
                "open_interest": 0  # Will need separate request for accurate OI
            }

            # Cancel this market data subscription
            self.ib.cancelMktData(contract)

            return option_data

        except Exception as e:
            print(f"⚠️ Error getting option details: {e}")
            return None

    async def get_open_interest(self, contract):
        """Get open interest data separately"""
        try:
            # Request fundamental data for open interest
            fundamental = await asyncio.wait_for(
                self.ib.reqFundamentalDataAsync(contract, 'ReportsFinSummary'),
                timeout=10
            )
            # Parse fundamental data for open interest
            # This is complex and may require XML parsing
            return 0
        except:
            return 0

    def format_options_data(self, options_data):
        """Format options data in the requested structure"""

        if not options_data:
            return None

        # Example: Return the first option pair in the requested format
        first_option = options_data[0]

        formatted_data = {
            "strike": first_option["strike"],
            "expiration": first_option["expiration"],
            "puts": first_option["puts"],
            "calls": first_option["calls"]
        }

        return formatted_data

    def disconnect(self):
        """Safely disconnect"""
        if self.ib.isConnected():
            self.ib.disconnect()
            print("📡 Disconnected from IB")


async def main():
    print("IB Options Data Fetcher")
    print("=" * 60)

    fetcher = IBOptionsDataFetcher()

    try:
        # Try to connect to IB Gateway (paper trading)
        success = await fetcher.connect_with_retry(
            host='127.0.0.1',
            port=7499,  # Paper trading port
            client_id=1
        )

        if not success:
            print("❌ Failed to connect to IB")
            return

        # Fetch options data
        symbol = 'SPY'  # Change this to your desired symbol
        options_data = await fetcher.get_options_chain_data(symbol)

        if options_data:
            print(f"\n🎉 Successfully fetched data for {len(options_data)} option pairs")

            # Display first option in requested format
            if options_data:
                sample_data = fetcher.format_options_data(options_data)
                print("\n📊 Sample Option Data (Requested Format):")
                print("-" * 50)

                import json
                print(json.dumps(sample_data, indent=2))

            # Save all data to file
            with open(f'{symbol}_options_data.json', 'w') as f:
                json.dump(options_data, f, indent=2)
            print(f"\n💾 All data saved to {symbol}_options_data.json")

        else:
            print("❌ No options data retrieved")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    # Set event loop policy for Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())