# Simple IB API Connection Test
import asyncio
from ib_async import IB

# Configuration - Modify these for your setup
HOST = "127.0.0.1"  # TWS/Gateway host
PORT = 4002  # TWS Paper: 7497, TWS Live: 7496, Gateway Paper: 4002, Gateway Live: 4001
CLIENT_ID = 1  # Unique ID for this connection (1-32)


async def test_ib_connection():
    """Test connection and basic API functionality"""
    ib = IB()

    try:
        print("Connecting to Interactive Brokers...")
        print(f"Host: {HOST}, Port: {PORT}, Client ID: {CLIENT_ID}")

        # Attempt connection
        await ib.connectAsync(HOST, PORT, clientId=CLIENT_ID, timeout=10)
        print("✓ Connected successfully!")

        # Test connection status
        print(f"Connection status: {ib.isConnected()}")

        # Get account summary
        try:
            print("\nGetting account information...")
            account_summary = ib.accountSummary()

            if account_summary:
                print("✓ Account data retrieved:")
                # Show key account metrics
                key_metrics = ['TotalCashValue', 'NetLiquidation', 'BuyingPower', 'ExcessLiquidity']
                for item in account_summary:
                    if item.tag in key_metrics:
                        print(f"  {item.tag}: {item.value} {item.currency}")
            else:
                print("⚠ No account data received")

        except Exception as e:
            print(f"⚠ Could not retrieve account info: {e}")

        # Get managed accounts
        try:
            accounts = ib.managedAccounts()
            print(f"\nManaged accounts: {accounts}")
        except Exception as e:
            print(f"⚠ Could not retrieve managed accounts: {e}")

        print("\n✓ All tests completed successfully!")

    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nTroubleshooting checklist:")
        print("1. Ensure TWS or IB Gateway is running")
        print("2. In TWS: File → Global Configuration → API → Settings")
        print("3. Check 'Enable ActiveX and Socket Clients'")
        print("4. Uncheck 'Read-Only API' (if placing orders)")
        print("5. Verify port number matches your setup:")
        print("   - TWS Paper Trading: 7497")
        print("   - TWS Live Trading: 7496")
        print("   - IB Gateway Paper: 4002")
        print("   - IB Gateway Live: 4001")
        print("6. Ensure client ID is not in use by another connection")

    finally:
        if ib.isConnected():
            ib.disconnect()
            print("\nDisconnected from IB API")


# Run the test
if __name__ == "__main__":
    asyncio.run(test_ib_connection())
