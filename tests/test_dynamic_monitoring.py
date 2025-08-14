#!/usr/bin/env python3
"""
Test script for dynamic strike price and expiration monitoring
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
import pytz

# Add the utils directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from ib_connection import IBDataCollector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_dynamic_monitoring():
    """Test the dynamic monitoring functionality"""
    
    # Configuration
    trading_config = {
        'underlying_symbol': 'SPY'
    }
    
    account_config = {
        'high_water_mark': 10000.0
    }
    
    # Create IB connection
    ib_collector = IBDataCollector(
        host='127.0.0.1',
        port=7497,
        clientId=999,
        trading_config=trading_config,
        account_config=account_config
    )
    
    try:
        logger.info("Testing Dynamic Strike Price and Expiration Monitoring")
        logger.info("=" * 60)
        
        # Connect to IB
        logger.info("Connecting to Interactive Brokers...")
        connected = await ib_collector.connect()
        
        if not connected:
            logger.error("Failed to connect to IB. Make sure TWS/IB Gateway is running.")
            return
        
        logger.info("Successfully connected to IB")
        
        # Wait a moment for connection to stabilize
        await asyncio.sleep(2)
        
        # Log initial status
        logger.info("\nInitial Status:")
        ib_collector.log_dynamic_monitoring_status()
        
        # Collect initial data to set up monitoring
        logger.info("\nCollecting initial data...")
        data = await ib_collector.collect_all_data()
        
        if data:
            logger.info("Initial data collection successful")
            logger.info(f"Options data shape: {data['options'].shape if 'options' in data else 'No options'}")
        else:
            logger.error("Initial data collection failed")
            return
        
        # Wait for dynamic monitoring to start
        await asyncio.sleep(3)
        
        # Log status after setup
        logger.info("\nStatus after setup:")
        ib_collector.log_dynamic_monitoring_status()
        
        # Test manual strike update
        logger.info("\nTesting manual strike update...")
        await ib_collector.manual_trigger_update('strike')
        await asyncio.sleep(2)
        
        # Test manual expiration update
        logger.info("\nTesting manual expiration update...")
        await ib_collector.manual_trigger_update('expiration')
        await asyncio.sleep(2)
        
        # Log final status
        logger.info("\nFinal Status:")
        ib_collector.log_dynamic_monitoring_status()
        
        # Keep running to observe dynamic changes
        logger.info("\nMonitoring for dynamic changes...")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                await asyncio.sleep(10)
                # Log status every 10 seconds
                current_time = datetime.now(pytz.timezone('US/Eastern'))
                logger.info(f"\nStatus at {current_time.strftime('%H:%M:%S')} EST:")
                ib_collector.log_dynamic_monitoring_status()
                
        except KeyboardInterrupt:
            logger.info("\nStopping monitoring...")
            
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        ib_collector.disconnect()
        logger.info("Test completed")

if __name__ == "__main__":
    try:
        asyncio.run(test_dynamic_monitoring())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
