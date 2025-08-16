import asyncio
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path so we can import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ib_connection import IBDataCollector


async def test_historical_data():
    """Test historical data retrieval using IBDataCollector with correct port"""
    
    # Create IBDataCollector with paper trading port (7498) and different client ID
    # This matches your test_historical_data.py configuration
    ib_collector = IBDataCollector(
        host='127.0.0.1',
        port=7498,  # Paper trading port (same as your test file)
        clientId=3,  # Different client ID to avoid conflicts
        timeout=30
    )
    
    try:
        # Connect to IB
        print("Connecting to IB...")
        connected = await ib_collector.connect()
        
        if not connected:
            print("Failed to connect to IB")
            return
        
        print("Successfully connected to IB")
        
        # Set up date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Get historical data for SPY
        print(f"Requesting historical data for SPY from {start_date} to {end_date}")
        historical_data = await ib_collector.get_historical_data("SPY", start_date, end_date)
        
        if historical_data:
            print(f"Successfully retrieved {len(historical_data)} historical data points")
            print("First 3 data points:")
            for i, data_point in enumerate(historical_data[:3]):
                print(f"  {i+1}. {data_point}")
        else:
            print("No historical data retrieved")
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Disconnect
        ib_collector.disconnect()
        print("Disconnected from IB")


if __name__ == "__main__":
    asyncio.run(test_historical_data())
