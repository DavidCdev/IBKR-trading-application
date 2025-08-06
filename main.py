import sys
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject

from ui.ib_trading_gui import Ui_MainWindow
from utils.ib_connection import IBDataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    """Application configuration"""
    ib_host: str = '127.0.0.1'
    ib_port: int = 7497
    ib_client_id: int = 1
    data_collection_interval: int = 60  # seconds
    max_reconnect_attempts: int = 5
    reconnect_delay: int = 5  # seconds
    
    @classmethod
    def load_from_file(cls, config_path: str = 'config.json') -> 'AppConfig':
        """Load configuration from JSON file"""
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                return cls(**config_data)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return cls()
    
    def save_to_file(self, config_path: str = 'config.json'):
        """Save configuration to JSON file"""
        try:
            with open(config_path, 'w') as f:
                json.dump(self.__dict__, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")


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
            clientId=config.ib_client_id
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


class IB_Trading_APP(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Load configuration
        self.config = AppConfig.load_from_file()
        
        # Initialize data collector worker
        self.data_worker = DataCollectorWorker(self.config)
        self.worker_thread = QThread()
        self.data_worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.data_worker.data_ready.connect(self.update_ui_with_data)
        self.data_worker.connection_status_changed.connect(self.update_connection_status)
        self.data_worker.error_occurred.connect(self.handle_error)
        
        # Connect thread signals
        self.worker_thread.started.connect(self.data_worker.start_collection)
        self.worker_thread.finished.connect(self.data_worker.cleanup)
        
        # Setup UI
        self.setup_ui()
        
        # Start data collection
        self.worker_thread.start()
    
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("IB Trading Application")
        
        # Set initial connection status
        self.update_connection_status(False)
        
        # Setup refresh timer for UI updates
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_ui)
        self.refresh_timer.start(1000)  # Update every second
    
    def update_ui_with_data(self, data: Dict[str, Any]):
        """Update UI with collected data"""
        try:
            # Update SPY price
            if data.get('spy_price'):
                self.ui.label_spy_value.setText(f"${data['spy_price']:.2f}")
            
            # Update account metrics
            if data.get('account') and not data['account'].empty:
                account_data = data['account'].iloc[0]
                # Update account-related UI elements here
                logger.info(f"Account Net Liquidation: ${account_data.get('NetLiquidation', 'N/A')}")
            
            # Update positions
            if data.get('positions') and not data['positions'].empty:
                positions_count = len(data['positions'])
                logger.info(f"Active positions: {positions_count}")
            
            # Update statistics
            if data.get('statistics') and not data['statistics'].empty:
                stats = data['statistics'].iloc[0]
                win_rate = stats.get('Win_Rate', 0)
                logger.info(f"Win rate: {win_rate:.2f}%")
                
        except Exception as e:
            logger.error(f"Error updating UI with data: {e}")
    
    def update_connection_status(self, connected: bool):
        """Update connection status in UI"""
        status_text = "Connected" if connected else "Disconnected"
        status_color = "green" if connected else "red"
        
        # Update status label if it exists in the UI
        if hasattr(self.ui, 'label_connection_status'):
            self.ui.label_connection_status.setText(status_text)
            self.ui.label_connection_status.setStyleSheet(f"color: {status_color}")
        
        logger.info(f"Connection status: {status_text}")
    
    def handle_error(self, error_message: str):
        """Handle errors from data collection"""
        logger.error(f"Data collection error: {error_message}")
        
        # Show error dialog for critical errors
        if "connection" in error_message.lower() or "timeout" in error_message.lower():
            QMessageBox.warning(
                self,
                "Connection Error",
                f"Connection issue detected: {error_message}\nPlease check your IB Gateway/TWS connection."
            )
    
    def refresh_ui(self):
        """Refresh UI elements that need frequent updates"""
        # Add any UI elements that need real-time updates here
        pass
    
    def closeEvent(self, event):
        """Handle application shutdown"""
        try:
            # Stop data collection
            self.data_worker.stop_collection()
            
            # Wait for thread to finish
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(5000)  # Wait up to 5 seconds
            
            # Save configuration
            self.config.save_to_file()
            
            logger.info("Application shutdown completed")
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            event.accept()


def main():
    """Main application entry point"""
    # Set up asyncio policy for Windows
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        app = QApplication(sys.argv)
        
        # Create and show main window
        main_window = IB_Trading_APP()
        main_window.show()
        
        logger.info("IB Trading Application started")
        
        # Run the application
        sys.exit(app.exec_())
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
