import asyncio
from ib_async import IB
from datetime import datetime, time
import time as time_module

async def main():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7499, clientId=2)
    print("Connected")

    account = (ib.managedAccounts())[0]  # Get first managed account
    print(f"Account: {account}")

    # Track daily starting value (reset at market open)
    daily_starting_value = None
    last_account_update = None

    # Subscribe to P&L updates for the account
    pnl = ib.reqPnL(account)
    
    # Subscribe to account summary updates
    ib.reqAccountSummaryAsync()
    
    # Define an event handler for P&L updates
    def on_pnl_update(pnl_obj):
        print(f"P&L Update: Unrealized: ${pnl_obj.unrealizedPnL:.2f}, Realized: ${pnl_obj.realizedPnL:.2f}, Daily: ${pnl_obj.dailyPnL:.2f}")
    
    # Define an event handler for account summary updates
    def on_account_summary_update(account_summary):
        nonlocal daily_starting_value, last_account_update
        
        # Extract NetLiquidation value
        net_liquidation = None
        for item in account_summary:
            if item.tag == 'NetLiquidation':
                net_liquidation = float(item.value)
                break
        
        if net_liquidation is not None:
            current_time = datetime.now()
            
            # Check if it's a new trading day (market open at 9:30 AM ET)
            # For simplicity, we'll use 9:30 AM local time
            market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
            
            # If it's a new day or first time, set the daily starting value
            if (daily_starting_value is None or 
                (last_account_update and last_account_update.date() < current_time.date()) or
                (current_time.time() >= time(9, 30) and 
                 (last_account_update is None or last_account_update.time() < time(9, 30)))):
                
                daily_starting_value = net_liquidation
                print(f"🆕 New trading day - Daily starting value set to: ${daily_starting_value:.2f}")
            
            # Calculate daily PnL and percentage
            if daily_starting_value is not None:
                daily_pnl = net_liquidation - daily_starting_value
                daily_pnl_percent = (daily_pnl / daily_starting_value) * 100 if daily_starting_value != 0 else 0
                
                # Color coding for console output
                pnl_color = "🟢" if daily_pnl >= 0 else "🔴"
                percent_color = "🟢" if daily_pnl_percent >= 0 else "🔴"
                
                print(f"📊 Account Update - {current_time.strftime('%H:%M:%S')}")
                print(f"   Net Liquidation: ${net_liquidation:.2f}")
                print(f"   Daily Starting Value: ${daily_starting_value:.2f}")
                print(f"   Daily P&L: {pnl_color} ${daily_pnl:.2f}")
                print(f"   Daily P&L %: {percent_color} {daily_pnl_percent:.2f}%")
                print(f"   Unrealized P&L: ${pnl_obj.unrealizedPnL:.2f}" if 'pnl_obj' in locals() else "   Unrealized P&L: N/A")
                print("-" * 50)
            
            last_account_update = current_time

    # Connect event handlers
    ib.pnlEvent += on_pnl_update
    ib.accountSummaryEvent += on_account_summary_update

    # Keep the program running to receive updates
    try:
        print("Monitoring account in real-time... Press Ctrl+C to stop")
        print("=" * 50)
        await asyncio.Future()  # Run forever
    except asyncio.CancelledError:
        pass
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
