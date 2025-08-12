from PyQt5.QtCore import QObject, pyqtSignal
from utils.config_manager import AppConfig
from utils.ib_connection import IBDataCollector
import asyncio
import logging
import random

logger = logging.getLogger(__name__)

class DataCollectorWorker(QObject):
    """Worker class for data collection in a separate thread"""
    data_ready = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    price_updated = pyqtSignal(dict)  # Signal for real-time price updates
    fx_rate_updated = pyqtSignal(dict)  # Signal for real-time FX rate updates
    connection_success = pyqtSignal(dict)
    connection_disconnected = pyqtSignal(dict)
    puts_option_updated = pyqtSignal(dict)
    calls_option_updated = pyqtSignal(dict)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.collector = IBDataCollector(
            host=config.ib_host,
            port=config.ib_port,
            clientId=config.ib_client_id,
            trading_config=config.trading,
            account_config = config.account
        )
        # Pass reference to data worker for signal emission
        self.collector.data_worker = self
        self.is_running = False
        self.reconnect_attempts = 0
        self._last_saved_high_water_mark = (
            self.config.account.get('high_water_mark') if self.config and self.config.account else None
        )
        
    def start_collection(self):
        """Start the data collection loop"""
        self.is_running = True
        asyncio.run(self._collection_loop())
    
    def stop_collection(self):
        """Stop the data collection loop"""
        self.is_running = False
    
    def connect_to_ib(self):
        """Manually connect to IB (called from settings form)"""
        try:
            logger.info("Manual connection request from settings form")
            # Create a new event loop for this connection attempt
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def connect_async():
                try:
                    success = await self.collector.connect()
                    if success:
                        logger.info("Manual connection successful")
                        # Emit connection success signal
                        self.connection_success.emit({'status': 'Connected'})
                    else:
                        logger.error("Manual connection failed")
                        self.error_occurred.emit("Failed to connect to IB")
                except Exception as e:
                    logger.error(f"Error during manual connection: {e}")
                    self.error_occurred.emit(f"Connection error: {str(e)}")
                finally:
                    loop.close()
            
            # Run the connection in the new event loop
            loop.run_until_complete(connect_async())
            
        except Exception as e:
            logger.error(f"Error in connect_to_ib: {e}")
            self.error_occurred.emit(f"Connection setup error: {str(e)}")
    
    def disconnect_from_ib(self):
        """Manually disconnect from IB (called from settings form)"""
        try:
            logger.info("Manual disconnection request from settings form")
            # Disconnect the collector
            self.collector.disconnect()
            logger.info("Manual disconnection successful")
            # Emit disconnection signal
            self.connection_disconnected.emit({'status': 'Disconnected'})
            
        except Exception as e:
            logger.error(f"Error in disconnect_from_ib: {e}")
            self.error_occurred.emit(f"Disconnection error: {str(e)}")
    
    async def _collection_loop(self):
        """Main data collection loop"""
        while self.is_running:
            try:
                # Check connection status
                if not self.collector.ib.isConnected():
                    self.connection_status_changed.emit(False)
                    if await self._reconnect():
                        self.connection_status_changed.emit(True)
                        self.reconnect_attempts = 0
                    else:
                        await self._sleep_with_cancel(self.config.reconnect_delay)
                        continue
                
                # Collect data
                data = await self.collector.collect_all_data()
                if data:
                    self.data_ready.emit(data)
                    logger.info("Data collection completed successfully")

                    # Persist updated high water mark if it changed
                    try:
                        current_hwm = self.collector.account_config.get('high_water_mark') if self.collector.account_config else None
                        if current_hwm is not None and current_hwm != self._last_saved_high_water_mark:
                            # Reflect into AppConfig and persist
                            if self.config and self.config.account is not None:
                                self.config.account['high_water_mark'] = current_hwm
                                self.config.save_to_file()
                                self._last_saved_high_water_mark = current_hwm
                                logger.info(f"Persisted updated High Water Mark: {current_hwm}")
                    except Exception as persist_err:
                        logger.warning(f"Could not persist High Water Mark: {persist_err}")
                else:
                    logger.warning("Data collection returned None")
                
                # Wait for next collection cycle
                await self._sleep_with_cancel(self.config.data_collection_interval)
                
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                self.error_occurred.emit(str(e))
                await self._sleep_with_cancel(self.config.reconnect_delay)
    
    async def _reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff"""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False
        
        try:
            self.reconnect_attempts += 1
            max_delay = self.config.connection.get("max_reconnect_delay", 60)
            base_delay = self.config.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
            # Cap and add a small jitter to avoid thundering herd
            delay = min(base_delay, max_delay) + random.uniform(0, 1.0)
            logger.info(f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.config.max_reconnect_attempts})")
            
            # Allow prompt shutdown during backoff sleep
            await self._sleep_with_cancel(delay)
            if not self.is_running:
                return False
            success = await self.collector.connect()
            
            if success:
                logger.info("Reconnection successful")
                return True
            else:
                logger.warning(f"Reconnection attempt {self.reconnect_attempts} failed")
                return False
                
        except Exception as e:
            logger.error(f"Error during reconnection: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Ensure proper cleanup via collector's disconnect to cancel subscriptions
            self.collector.disconnect()
            logger.info("Disconnected from IB")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def _sleep_with_cancel(self, total_seconds: float):
        """Sleep in short intervals so we can react quickly to stop requests."""
        try:
            remaining = float(total_seconds)
            interval = 0.2
            while self.is_running and remaining > 0:
                await asyncio.sleep(min(interval, remaining))
                remaining -= interval
        except Exception as e:
            logger.debug(f"Sleep interrupted: {e}")

