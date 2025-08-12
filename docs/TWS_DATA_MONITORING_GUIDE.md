# TWS Gateway Data Monitoring Guide

This guide explains how trading data is gathered from TWS Gateway and how to check and display the request results.

## Architecture Overview

The application uses an event-driven architecture to gather data from TWS Gateway:

```
TWS Gateway ←→ IBConnectionManager ←→ EventBus ←→ SubscriptionManager
                                    ↓
                              TWSDataMonitor ←→ GUI/Logging
```

### Key Components:

1. **IBConnectionManager** - Handles connection to TWS Gateway
2. **SubscriptionManager** - Manages data subscriptions and requests
3. **EventBus** - Coordinates communication between components
4. **TWSDataMonitor** - Tracks and monitors all data requests/responses
5. **GUI** - Displays data to users

## Data Flow

### 1. Connection Setup
```python
# In main.py - automatic connection
event_bus.emit("ib.connect", {}, priority=EventPriority.HIGH)
```

### 2. Data Requests
The system makes various types of requests to TWS Gateway:

- **Market Data**: Real-time price and volume data
- **Historical Data**: Past price data for analysis
- **Account Data**: Account balances and positions
- **Contract Data**: Instrument specifications
- **Order Status**: Order execution status

### 3. Data Processing
All data flows through the EventBus system:
- `ib.data` - Incoming market data
- `ib.account` - Account updates
- `ib.position` - Position changes
- `ib.error` - Error messages

## How to Check and Show Request Results

### Method 1: Using the TWS Data Monitor Script

The application includes a monitoring script that allows you to check data requests and responses:

```bash
# Show status of all requests
python src/check_tws_data.py status

# Show data for a specific request
python src/check_tws_data.py data <request_id>

# Track a new request
python src/check_tws_data.py track market_data AAPL

# Start real-time monitoring
python src/check_tws_data.py monitor
```

### Method 2: Using Python Code

You can also check data programmatically:

```python
from tws_data_monitor import get_monitor, show

# Get the monitor instance
monitor = get_monitor()

# Show all requests
monitor.show_results()

# Show specific request
monitor.show_results("market_data_1234567890")

# Get request status
status = monitor.get_status("market_data_1234567890")
print(f"Status: {status}")

# Get data for request
data = monitor.get_data("market_data_1234567890")
print(f"Data points: {len(data)}")
```

### Method 3: Using the GUI

The GUI displays real-time data in various panels:
- Market data panel shows live prices
- Account panel shows balances and positions
- Log panel shows all events and errors

## Common Data Request Types

### Market Data Requests
```python
# Request real-time market data
event_bus.emit("ib.reqMktData", {
    "request_id": "mkt_data_123",
    "symbol": "AAPL",
    "contract": {...}
})
```

### Historical Data Requests
```python
# Request historical data
event_bus.emit("ib.reqHistoricalData", {
    "request_id": "hist_123",
    "symbol": "AAPL",
    "duration": "1 D",
    "bar_size": "1 min"
})
```

### Account Data Requests
```python
# Request account updates
event_bus.emit("ib.reqAccountUpdates", {
    "request_id": "account_123",
    "subscribe": True
})
```

## Monitoring Request Status

### Request States
- **pending**: Request sent, waiting for response
- **success**: Request completed successfully
- **error**: Request failed with error
- **cancelled**: Request was cancelled

### Example Output
```
==================================================
REQUEST: market_data_1234567890
==================================================
Type: market_data
Symbol: AAPL
Status: success
Created: 2024-01-15 10:30:00
Responses: 150

Latest Data:
  2024-01-15 10:35:00: {'bid': 150.25, 'ask': 150.30, 'last': 150.28}
  2024-01-15 10:35:01: {'bid': 150.26, 'ask': 150.31, 'last': 150.29}
  2024-01-15 10:35:02: {'bid': 150.27, 'ask': 150.32, 'last': 150.30}
```

## Debugging Data Issues

### 1. Check Connection Status
```python
# Check if connected to TWS
monitor = get_monitor()
if monitor:
    print("TWS Monitor is active")
else:
    print("TWS Monitor not initialized")
```

### 2. Check for Errors
```python
# Look for error requests
requests = monitor.get_all_requests()
error_requests = [req for req in requests if req.status == 'error']
for req in error_requests:
    print(f"Error in {req.request_id}: {req.error_message}")
```

### 3. Check Data Flow
```python
# Monitor data flow in real-time
import time

while True:
    requests = monitor.get_all_requests()
    active_requests = [req for req in requests if req.status == 'pending']
    print(f"Active requests: {len(active_requests)}")
    
    for req in active_requests:
        data_count = len(monitor.get_data(req.request_id))
        print(f"  {req.request_id}: {data_count} data points")
    
    time.sleep(5)
```

## Logging and Troubleshooting

### Enable Debug Logging
The system uses structured logging. Check the logs for detailed information:

```python
# In your code
from logger import get_logger
logger = get_logger('TWS_MONITOR')

# Log data events
logger.info(f"Data received: {data}")
logger.error(f"Request failed: {error}")
```

### Common Issues and Solutions

1. **No Data Received**
   - Check TWS Gateway connection
   - Verify market data subscriptions
   - Check for error messages in logs

2. **Slow Data**
   - Check network connection
   - Verify TWS Gateway settings
   - Monitor system performance

3. **Missing Data**
   - Check request parameters
   - Verify symbol/contract details
   - Check for market hours

## Real-Time Monitoring Example

```python
#!/usr/bin/env python3
"""
Real-time TWS data monitoring example
"""

import time
from tws_data_monitor import get_monitor

def monitor_tws_data():
    monitor = get_monitor()
    if not monitor:
        print("TWS Monitor not available")
        return
    
    print("Starting real-time TWS data monitoring...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            # Clear screen
            print("\033[2J\033[H", end="")
            
            # Show current status
            requests = monitor.get_all_requests()
            active_requests = [req for req in requests if req.status == 'pending']
            
            print(f"TWS Data Monitor - {time.strftime('%H:%M:%S')}")
            print(f"Total Requests: {len(requests)}")
            print(f"Active Requests: {len(active_requests)}")
            print("=" * 50)
            
            # Show active requests
            for req in active_requests[-5:]:  # Show last 5
                data = monitor.get_data(req.request_id)
                print(f"{req.request_id}: {len(data)} data points")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    monitor_tws_data()
```

## Integration with Your Application

The TWS data monitor is automatically initialized when you start the application. You can access it from anywhere in your code:

```python
from tws_data_monitor import get_monitor

# In your trading logic
monitor = get_monitor()
if monitor:
    # Track your custom requests
    req_id = monitor.track_request("custom_analysis", "AAPL")
    
    # Check results later
    data = monitor.get_data(req_id)
    print(f"Analysis data: {data}")
```

This monitoring system provides comprehensive visibility into all TWS Gateway data requests and responses, making it easy to debug issues and verify data quality. 