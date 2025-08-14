from PyQt5.QtCore import QObject, pyqtSignal
from utils.config_manager import AppConfig
from utils.ib_connection import IBDataCollector
import asyncio
import random
from .smart_logger import get_logger, log_error_with_context
from .performance_monitor import monitor_function

logger = get_logger("DATA_COLLECTOR")

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
    daily_pnl_update = pyqtSignal(dict)
    account_summary_update = pyqtSignal(dict)
    trading_config_updated = pyqtSignal(dict)  # Signal for trading configuration updates
    active_contracts_pnl_refreshed = pyqtSignal(dict)
    closed_trades_update = pyqtSignal(list)

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
        self._manual_disconnect_requested = False  # Flag to track manual disconnect requests
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
    
    def connect_to_ib(self, connection_settings=None):
        """Manually connect to IB (called from settings form)"""
        try:
            logger.info("Manual connection request from settings form")
            
            # Update connection settings if provided
            if connection_settings:
                logger.info(f"Updating connection settings: {connection_settings}")
                self._update_connection_settings(connection_settings)
            
            # Reset manual disconnect flag to allow reconnection
            self._manual_disconnect_requested = False
            logger.info(f"Manual disconnect flag reset to: {self._manual_disconnect_requested}")
            # Reset reconnect attempts to allow fresh connection
            self.reconnect_attempts = 0
            # The connection will be handled by the collection loop
            logger.info("Manual connection request processed")
            
            # Emit connection attempt signal for logging
            self.connection_success.emit({'status': 'Connecting...', 'message': 'Manual connection attempt started'})
            
        except Exception as e:
            logger.error(f"Error in connect_to_ib: {e}")
            self.error_occurred.emit(f"Connection setup error: {str(e)}")
    
    def _update_connection_settings(self, connection_settings):
        """Update the collector's connection settings"""
        try:
            # Update the collector's connection parameters
            self.collector.host = connection_settings.get('host', self.collector.host)
            self.collector.port = connection_settings.get('port', self.collector.port)
            self.collector.clientId = connection_settings.get('client_id', self.collector.clientId)
            
            # Update the config object as well
            if self.config and self.config.connection:
                self.config.connection['host'] = self.collector.host
                self.config.connection['port'] = self.collector.port
                self.config.connection['client_id'] = self.collector.clientId
                
                # Save the updated config to file
                try:
                    self.config.save_to_file()
                    logger.info("Connection settings saved to config file")
                except Exception as save_error:
                    logger.warning(f"Could not save connection settings to config file: {save_error}")
            
            logger.info(f"Connection settings updated - Host: {self.collector.host}, Port: {self.collector.port}, Client ID: {self.collector.clientId}")
            
        except Exception as e:
            logger.error(f"Error updating connection settings: {e}")
            raise
    
    def update_trading_config(self, trading_config):
        """Update the collector's trading configuration"""
        try:
            logger.info(f"Updating trading configuration: {trading_config}")
            
            # Update the collector's trading configuration
            self.collector.trading_config = trading_config
            self.collector.underlying_symbol = trading_config.get('underlying_symbol', self.collector.underlying_symbol)
            
            # Update the config object as well
            if self.config and self.config.trading:
                self.config.trading.update(trading_config)
                
                # Save the updated config to file
                try:
                    self.config.save_to_file()
                    logger.info("Trading configuration saved to config file")
                except Exception as save_error:
                    logger.warning(f"Could not save trading configuration to config file: {save_error}")
            
            logger.info(f"Trading configuration updated - Underlying Symbol: {self.collector.underlying_symbol}")
            
            # Emit signal to notify other components of the configuration change
            self.trading_config_updated.emit({
                'underlying_symbol': self.collector.underlying_symbol,
                'trading_config': trading_config
            })
            
            # If connected, restart data collection with new configuration
            if self.collector.ib.isConnected():
                logger.info("Restarting data collection with new trading configuration")
                # This will trigger a reconnection with the new configuration
                self._manual_disconnect_requested = False
                self.reconnect_attempts = 0
            
        except Exception as e:
            logger.error(f"Error updating trading configuration: {e}")
            raise
    
    def reset_manual_disconnect_flag(self):
        """Reset the manual disconnect flag to allow automatic reconnection"""
        self._manual_disconnect_requested = False
        logger.info("Manual disconnect flag reset - automatic reconnection enabled")
    
    def disconnect_from_ib(self):
        """Manually disconnect from IB (called from settings form)"""
        try:
            logger.info("Manual disconnection request from settings form")
            # Set flag to prevent automatic reconnection
            self._manual_disconnect_requested = True
            logger.info(f"Manual disconnect flag set to: {self._manual_disconnect_requested}")
            # Disconnect the collector
            self.collector.disconnect()
            logger.info("Manual disconnection successful")
            # Emit disconnection signal with proper status
            self.connection_disconnected.emit({'status': 'Disconnected'})
            # Also emit connection status changed signal
            self.connection_status_changed.emit(False)
            
        except Exception as e:
            logger.error(f"Error in disconnect_from_ib: {e}")
            self.error_occurred.emit(f"Disconnection error: {str(e)}")
    
    async def _collection_loop(self):
        """Main data collection loop"""
        while self.is_running:
            try:
                # Check connection status
                if not self.collector.ib.isConnected():
                    logger.info(f"IB not connected. Manual disconnect flag: {self._manual_disconnect_requested}")
                    self.connection_status_changed.emit(False)
                    # Only attempt reconnection if manual disconnect was not requested
                    if not self._manual_disconnect_requested:
                        logger.info("Attempting automatic reconnection...")
                        # Emit reconnection attempt signal for logging
                        self.connection_success.emit({'status': 'Reconnecting...', 'message': f'Automatic reconnection attempt {self.reconnect_attempts + 1}'})
                        if await self._reconnect():
                            self.connection_status_changed.emit(True)
                            self.reconnect_attempts = 0
                        else:
                            await self._sleep_with_cancel(self.config.reconnect_delay)
                            continue
                    else:
                        # Manual disconnect was requested, don't reconnect automatically
                        logger.info("Manual disconnect requested, skipping automatic reconnection")
                        await self._sleep_with_cancel(self.config.data_collection_interval)
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
            logger.info(f"Using connection settings - Host: {self.collector.host}, Port: {self.collector.port}, Client ID: {self.collector.clientId}")
            
            # Allow prompt shutdown during backoff sleep
            await self._sleep_with_cancel(delay)
            if not self.is_running:
                return False
            success = await self.collector.connect()
            
            if success:
                logger.info("Reconnection successful")
                # Reset manual disconnect flag since we're now connected
                self._manual_disconnect_requested = False
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
            # Cleanup trading manager if available
            if hasattr(self.collector, 'trading_manager'):
                self.collector.trading_manager.cleanup()
                logger.info("Trading manager cleanup completed")
            
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

