#!/usr/bin/env python3
"""
Example script demonstrating the Smart Logging System for IB Trading Application

This script shows how to use:
1. Basic logging with different levels
2. Performance monitoring
3. Structured logging for trading events
4. Connection event logging
5. Error logging with context
"""

import sys
import os
import time
import asyncio
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.smart_logger import (
    get_logger, 
    log_performance, 
    log_trade_event, 
    log_connection_event, 
    log_error_with_context
)
from utils.performance_monitor import (
    monitor_function, 
    monitor_async_function, 
    start_monitor, 
    stop_monitor
)


def example_basic_logging():
    """Demonstrate basic logging with different levels"""
    logger = get_logger("EXAMPLE")
    
    logger.debug("This is a debug message - only visible when debug is enabled")
    logger.info("This is an info message - general application flow")
    logger.warning("This is a warning message - something to be aware of")
    logger.error("This is an error message - something went wrong")
    
    # Log with context
    logger.info("Processing trade data", extra={
        'symbol': 'SPY',
        'price': 450.25,
        'quantity': 100
    })


@monitor_function("example_performance_function", threshold_ms=100)
def example_performance_function(sleep_time: float = 0.1):
    """Demonstrate performance monitoring with decorator"""
    logger = get_logger("PERFORMANCE_EXAMPLE")
    logger.info(f"Starting performance test with {sleep_time}s sleep")
    
    time.sleep(sleep_time)
    
    logger.info("Performance test completed")
    return f"Completed in {sleep_time}s"


@monitor_async_function("example_async_performance", threshold_ms=50)
async def example_async_performance(sleep_time: float = 0.05):
    """Demonstrate async performance monitoring"""
    logger = get_logger("ASYNC_PERFORMANCE")
    logger.info(f"Starting async performance test with {sleep_time}s sleep")
    
    await asyncio.sleep(sleep_time)
    
    logger.info("Async performance test completed")
    return f"Async completed in {sleep_time}s"


def example_manual_performance_monitoring():
    """Demonstrate manual performance monitoring"""
    logger = get_logger("MANUAL_PERFORMANCE")
    
    # Start monitoring
    monitor_id = start_monitor("manual_operation")
    
    logger.info("Starting manual performance monitoring")
    
    # Simulate some work
    time.sleep(0.2)
    
    # Stop monitoring with context
    duration = stop_monitor(monitor_id, operation_type="data_processing", records_processed=1000)
    
    logger.info(f"Manual monitoring completed in {duration:.3f}s")


def example_trading_events():
    """Demonstrate structured trading event logging"""
    logger = get_logger("TRADING_EXAMPLE")
    
    # Log different types of trading events
    log_trade_event(
        event_type="ORDER_PLACED",
        symbol="SPY",
        quantity=100,
        price=450.25,
        order_type="LIMIT",
        side="BUY",
        account="U123456"
    )
    
    log_trade_event(
        event_type="ORDER_FILLED",
        symbol="SPY",
        quantity=100,
        price=450.20,
        fill_time=datetime.now().isoformat(),
        commission=1.25
    )
    
    log_trade_event(
        event_type="STOP_LOSS_TRIGGERED",
        symbol="QQQ",
        quantity=50,
        price=380.15,
        stop_price=380.00,
        loss_amount=7.50
    )


def example_connection_events():
    """Demonstrate connection event logging"""
    logger = get_logger("CONNECTION_EXAMPLE")
    
    # Log connection attempts
    log_connection_event(
        event_type="CONNECT_ATTEMPT",
        host="127.0.0.1",
        port=7497,
        status="Connecting",
        client_id=1
    )
    
    # Log successful connection
    log_connection_event(
        event_type="CONNECT_SUCCESS",
        host="127.0.0.1",
        port=7497,
        status="Connected",
        connection_time_ms=1250
    )
    
    # Log disconnection
    log_connection_event(
        event_type="DISCONNECT",
        host="127.0.0.1",
        port=7497,
        status="Disconnected",
        session_duration_minutes=45
    )


def example_error_logging():
    """Demonstrate error logging with context"""
    logger = get_logger("ERROR_EXAMPLE")
    
    try:
        # Simulate an error
        raise ValueError("Invalid market data received")
    except Exception as e:
        log_error_with_context(
            error=e,
            context="Processing market data",
            symbol="SPY",
            timestamp=datetime.now().isoformat(),
            data_source="IB_API"
        )
    
    try:
        # Simulate another error
        raise ConnectionError("Failed to connect to IB Gateway")
    except Exception as e:
        log_error_with_context(
            error=e,
            context="Connection attempt",
            host="127.0.0.1",
            port=7497,
            retry_attempt=3
        )


async def example_async_operations():
    """Demonstrate async operations with logging"""
    logger = get_logger("ASYNC_EXAMPLE")
    
    logger.info("Starting async operations")
    
    # Run multiple async operations
    tasks = [
        example_async_performance(0.1),
        example_async_performance(0.05),
        example_async_performance(0.15)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info(f"Async operations completed: {results}")


def main():
    """Main function to run all examples"""
    logger = get_logger("EXAMPLE_MAIN")
    
    logger.info("Starting Smart Logging System Examples")
    
    try:
        # Basic logging examples
        logger.info("=== Basic Logging Examples ===")
        example_basic_logging()
        
        # Performance monitoring examples
        logger.info("=== Performance Monitoring Examples ===")
        example_performance_function(0.05)  # Fast operation (won't be logged due to threshold)
        example_performance_function(0.15)  # Slow operation (will be logged)
        example_manual_performance_monitoring()
        
        # Trading events examples
        logger.info("=== Trading Events Examples ===")
        example_trading_events()
        
        # Connection events examples
        logger.info("=== Connection Events Examples ===")
        example_connection_events()
        
        # Error logging examples
        logger.info("=== Error Logging Examples ===")
        example_error_logging()
        
        # Async operations examples
        logger.info("=== Async Operations Examples ===")
        asyncio.run(example_async_operations())
        
        logger.info("All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    main()
