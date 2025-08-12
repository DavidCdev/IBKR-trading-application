import asyncio
from ib_async import IB

async def main():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7498, clientId=3)
    print("Connected")

    account = (ib.managedAccounts())[0]  # Get first managed account

    # Subscribe to P&L updates for the account
    pnl = ib.reqPnL(account)

    # Define an event handler for P&L updates
    def on_pnl_update(pnl_obj):
        print(f"P&L Update: Unrealized: ${pnl_obj.unrealizedPnL:.2f}, Realized: ${pnl_obj.realizedPnL:.2f}, Daily: ${pnl_obj.dailyPnL:.2f}")

    ib.pnlEvent += on_pnl_update

    # Keep the program running to receive updates
    try:
        await asyncio.Future()  # Run forever
    except asyncio.CancelledError:
        pass
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
