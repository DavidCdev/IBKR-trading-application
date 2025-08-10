from PyQt5.QtCore import QObject, pyqtSignal
from utils.config_manager import AppConfig
from utils.ib_connection import IBDataCollector
import asyncio
import logging

logger = logging.getLogger(__name__)

class DataCollectorWorker(QObject):
    """Worker class for data collection in a separate thread"""
    data_ready = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.collector = IBDataCollector(
            host=config.ib_host,
            port=config.ib_port,
            clientId=config.ib_client_id,
            trading_config=config.trading
        )
        self.is_running = False
        self.reconnect_attempts = 0
        
    def start_collection(self):
        """Start the data collection loop"""
        self.is_running = True
        asyncio.run(self._collection_loop())
    
    def stop_collection(self):
        """Stop the data collection loop"""
        self.is_running = False
    
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
                        await asyncio.sleep(self.config.reconnect_delay)
                        continue
                
                # Collect data
                data = await self.collector.collect_all_data()
                if data:
                    self.data_ready.emit(data)
                    logger.info("Data collection completed successfully")
                else:
                    logger.warning("Data collection returned None")
                
                # Wait for next collection cycle
                await asyncio.sleep(self.config.data_collection_interval)
                
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                self.error_occurred.emit(str(e))
                await asyncio.sleep(self.config.reconnect_delay)
    
    async def _reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff"""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False
        
        try:
            self.reconnect_attempts += 1
            delay = min(self.config.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
            logger.info(f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.config.max_reconnect_attempts})")
            
            await asyncio.sleep(delay)
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
            if self.collector.ib.isConnected():
                self.collector.ib.disconnect()
                logger.info("Disconnected from IB")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

