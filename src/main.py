import threading
import time
import random
import os
import asyncio
import sys
from logger import get_logger, initialize_logger_manager
from enhanced_logging import initialize_enhanced_logging, get_enhanced_logging_manager
from performance_optimizer import initialize_performance_optimizer, start_performance_monitoring, stop_performance_monitoring

# Fix Windows asyncio issues
if sys.platform == 'win32':
    # Use the WindowsSelectorEventLoopPolicy on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# Ensure the paths are correct if these files are in a subdirectory, e.g., from src.gui import IBTradingGUI
from gui import IBTradingGUI
from config_manager import ConfigManager
from event_bus import EventBus, EventPriority
from event_monitor import create_monitored_event_bus
from ib_connection import IBConnectionManager
from subscription_manager import SubscriptionManager

logger = get_logger('MAIN')


def auto_connect_and_subscribe(event_bus, ib_connection):
    """
    Automatically connect to IB and subscribe to account updates.
    This runs in a separate thread to avoid blocking the GUI.
    """
    def connect_worker():
        try:
            logger.info("Starting automatic connection...")
            
            # Wait a moment for the GUI to fully initialize
            time.sleep(1)
            
            # Emit connect event - the GUI will handle subscriptions automatically
            logger.info("Emitting ib.connect event for automatic connection...")
            event_bus.emit("ib.connect", {}, priority=EventPriority.HIGH)
            
            logger.info("Automatic connection initiated successfully")
            
        except Exception as e:
            logger.error(f"Error during automatic connection: {e}")
    
    # Start the connection worker in a separate thread
    connection_thread = threading.Thread(target=connect_worker, daemon=True)
    connection_thread.start()
    logger.info("Automatic connection thread started")


def main():
    """
    The main entry point for the application.
    Initializes and wires together all the components.
    """
    logger.info("Application starting...")
    logger.debug(f"Main thread ID: {threading.current_thread().ident}")
    
    try:
        # 1. Initialize the core components.
        logger.debug("Initializing EventBus with monitoring...")
        event_bus_wrapper = create_monitored_event_bus(max_workers=8)  # Optimized for 24-core system
        event_bus = event_bus_wrapper.get_event_bus()  # Get the monitored event bus
        logger.debug("EventBus with monitoring initialized successfully")

        logger.debug("Initializing ConfigManager...")
        config_manager = ConfigManager(None, event_bus=event_bus)
        logger.debug("ConfigManager initialized successfully")

        logger.debug("Initializing logger manager with config...")
        initialize_logger_manager(config_manager)
        logger.debug("Logger manager initialized successfully")

        # Initialize enhanced logging system
        logger.debug("Initializing enhanced logging system...")
        initialize_enhanced_logging(config_manager, log_dir="logs")
        logger.debug("Enhanced logging system initialized successfully")

        # Initialize performance optimizer
        logger.debug("Initializing performance optimizer...")
        performance_optimizer = initialize_performance_optimizer()
        performance_optimizer.set_event_bus(event_bus)
        logger.debug("Performance optimizer initialized successfully")

        # Initialize TWS data monitor
        logger.debug("Initializing TWS data monitor...")
        logger.debug("TWS data monitor initialized successfully")

        # 2. Create the GUI, injecting the config and event bus.
        #    The GUI will automatically load its settings from the config manager.
        logger.debug("Creating GUI...")
        gui = IBTradingGUI(event_bus=event_bus, config_manager=config_manager)
        logger.debug("GUI created successfully")

        # 3. Create and initialize the subscription manager.
        #    This must be created before IB connection and will wait for ib.connected.
        logger.debug("Creating SubscriptionManager...")
        subscription_manager = SubscriptionManager(event_bus, config_manager)
        logger.info("Subscription manager initialized successfully")

        # 4. Create and initialize the IB connection manager.
        logger.debug("Creating IBConnectionManager...")
        ib_connection = IBConnectionManager(event_bus, config_manager)
        logger.info("IB connection manager initialized successfully")

        # 5. Start performance monitoring
        logger.info("Starting performance monitoring...")
        start_performance_monitoring()
        logger.info("Performance monitoring started successfully")

        # 6. Start automatic connection in background
        logger.info("Starting automatic connection...")
        auto_connect_and_subscribe(event_bus, ib_connection)

        # 7. Run the GUI's main loop. This is a blocking call and will run until
        #    the user closes the window.
        logger.info("Starting GUI main loop...")
        try:
            gui.run()
        except KeyboardInterrupt:
            logger.warning("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error in GUI main loop: {e}")
        finally:
            # 8. Cleanly shut down background processes after the GUI is closed.
            logger.info("GUI closed. Shutting down application...")
            
            # Clean up event bus wrapper and monitor
            logger.debug("Cleaning up event bus wrapper...")
            try:
                event_bus_wrapper.cleanup()
                logger.info("Event bus wrapper cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up event bus wrapper: {e}")
            
            # Stop performance monitoring
            logger.debug("Stopping performance monitoring...")
            try:
                stop_performance_monitoring()
                logger.info("Performance monitoring stopped successfully")
            except Exception as e:
                logger.warning(f"Error stopping performance monitoring: {e}")
            
            # Stop event bus first to prevent new events during shutdown
            logger.debug("Stopping event bus...")
            try:
                event_bus.stop()
            except Exception as e:
                logger.warning(f"Error stopping event bus: {e}")
            
            # Stop enhanced logging
            logger.debug("Stopping enhanced logging...")
            try:
                from enhanced_logging import get_enhanced_logging_manager
                enhanced_logging_manager = get_enhanced_logging_manager()
                enhanced_logging_manager.stop()
                logger.info("Enhanced logging stopped successfully")
            except Exception as e:
                logger.warning(f"Error stopping enhanced logging: {e}")
            
            # Force garbage collection
            logger.debug("Performing garbage collection...")
            try:
                import gc
                collected = gc.collect()
                if collected > 0:
                    logger.info(f"Garbage collection collected {collected} objects")
            except Exception as e:
                logger.warning(f"Error during garbage collection: {e}")
            
            # Then disconnect from IB with proper task cancellation
            logger.debug("Disconnecting from IB...")
            if ib_connection:
                try:
                    # Use the new shutdown method with timeout
                    import asyncio
                    import concurrent.futures
                    
                    # Run shutdown with timeout
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(ib_connection.shutdown)
                        try:
                            future.result(timeout=10)  # 10 second timeout
                            logger.info("IB disconnected successfully")
                        except concurrent.futures.TimeoutError:
                            logger.warning("IB shutdown timed out, forcing disconnect")
                            # Force disconnect as fallback
                            if hasattr(ib_connection, 'ib') and ib_connection.ib:
                                try:
                                    ib_connection.ib.disconnect()
                                except Exception:
                                    pass
                except Exception as e:
                    logger.warning(f"Error during IB disconnect: {e}")
            
            # Comprehensive async task cleanup
            logger.debug("Performing comprehensive async task cleanup...")
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    # Cancel all remaining asyncio tasks
                    tasks = asyncio.all_tasks(loop)
                    if tasks:
                        logger.info(f"Cancelling {len(tasks)} remaining asyncio tasks")
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        
                        # Wait for tasks to be cancelled
                        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                        logger.info("All asyncio tasks cancell ed successfully")
            except Exception as e:
                logger.warning(f"Error during async task cleanup: {e}")
            
            # Force cleanup of any remaining threads
            logger.debug("Performing final thread cleanup...")
            try:
                # Wait for daemon threads to finish
                time.sleep(1)
                
                # Log remaining threads for debugging
                remaining_threads = [t for t in threading.enumerate() if t.name != 'MainThread']
                if remaining_threads:
                    logger.warning(f"Remaining threads after shutdown: {len(remaining_threads)}")
                    for thread in remaining_threads:
                        logger.warning(f"  - {thread.name} (daemon: {thread.daemon}, alive: {thread.is_alive()})")
                else:
                    logger.info("All background threads stopped successfully")
                    
            except Exception as e:
                logger.warning(f"Error during thread cleanup: {e}")
            
            # Final verification
            logger.debug("Performing final shutdown verification...")
            try:
                # Check for remaining threads
                remaining_threads = [t for t in threading.enumerate() 
                                   if t.name != 'MainThread' and t.is_alive()]
                
                # Check for remaining asyncio tasks
                try:
                    loop = asyncio.get_event_loop()
                    remaining_tasks = asyncio.all_tasks(loop)
                except RuntimeError:
                    remaining_tasks = []
                
                if not remaining_threads and not remaining_tasks:
                    logger.info("✅ Final verification: All threads and tasks cleaned up")
                else:
                    logger.warning(f"⚠️ Final verification: {len(remaining_threads)} threads, {len(remaining_tasks)} tasks remaining")
                    
            except Exception as e:
                logger.warning(f"Error during final verification: {e}")
            
            logger.info("Application shutdown complete.")
            
            # Force exit if there are still hanging threads after a reasonable timeout
            # Wait up to 3 seconds for threads to finish (reduced from 5)
            start_time = time.time()
            while time.time() - start_time < 3:
                remaining_threads = [t for t in threading.enumerate() if t.name != 'MainThread' and t.is_alive()]
                if not remaining_threads:
                    logger.info("All threads stopped, exiting cleanly")
                    break
                time.sleep(0.2)  # Check more frequently
            else:
                logger.warning("Some threads still running after 3 seconds, forcing exit")
                # Force exit the process
                import os
                os._exit(0)

    except Exception as e:
        logger.fatal(f"Critical error during application startup: {e}")
        raise


if __name__ == "__main__":
    main()
