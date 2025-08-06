import sys
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog, QTableWidgetItem
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt5 import QtWidgets

from ui.ib_trading_gui import Ui_MainWindow
from ui.settings_gui import Ui_PreferencesDialog

from utils.ib_connection import IBDataCollector
from utils.config_manager import AppConfig

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

class Settings_Form(QDialog):
    def __init__(self, config: AppConfig = None):
        super().__init__()
        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)
        self.config = config
        if self.config:
            self.load_config_values()
    
    def load_config_values(self):
        """Load configuration values into the UI"""
        try:
            # Load connection settings
            if self.config.connection:
                self.ui.hostEdit.setText(str(self.config.connection.get("host", "127.0.0.1")))
                self.ui.portEdit.setText(str(self.config.connection.get("port", 7497)))
                self.ui.clientIdEdit.setText(str(self.config.connection.get("client_id", 1)))
            
            # Load trading settings
            if self.config.trading:
                self.ui.underlyingSymbolEdit.setText(str(self.config.trading.get("underlying_symbol", "QQQ")))
                self.ui.tradeDeltaEdit.setText(str(self.config.trading.get("trade_delta", 0.05)))
                self.ui.maxTradeValueEdit.setText(str(self.config.trading.get("max_trade_value", 475.0)))
                self.ui.runnerEdit.setText(str(self.config.trading.get("runner", 1)))
                
                # Load risk levels into table
                risk_levels = self.config.trading.get("risk_levels", [])
                table = self.ui.riskLevelsTable
                
                # Set table row count to match risk levels
                if len(risk_levels) > table.rowCount():
                    table.setRowCount(len(risk_levels))
                
                for row, risk_level in enumerate(risk_levels):
                    # Ensure items exist in table cells
                    for col in range(4):
                        if not table.item(row, col):
                            table.setItem(row, col, QtWidgets.QTableWidgetItem())
                    
                    # Set values
                    table.item(row, 0).setText(str(risk_level.get("loss_threshold", "")))
                    table.item(row, 1).setText(str(risk_level.get("account_trade_limit", "")))
                    table.item(row, 2).setText(str(risk_level.get("stop_loss", "")))
                    table.item(row, 3).setText(str(risk_level.get("profit_gain", "")))
            
            # Load debug settings
            if self.config.debug:
                self.ui.masterDebugCheckBox.setChecked(self.config.debug.get("master_debug", True))
                
                # Load module log levels
                modules = self.config.debug.get("modules", {})
                
                # Set combo box values
                if "MAIN" in modules:
                    self._set_combo_text(self.ui.mainLogLevelCombo, modules["MAIN"])
                if "GUI" in modules:
                    self._set_combo_text(self.ui.guiLogLevelCombo, modules["GUI"])
                if "EVENT_BUS" in modules:
                    self._set_combo_text(self.ui.eventBusLogLevelCombo, modules["EVENT_BUS"])
                if "SUBSCRIPTION_MANAGER" in modules:
                    self._set_combo_text(self.ui.subscriptionManagerLogLevelCombo, modules["SUBSCRIPTION_MANAGER"])
                    
        except Exception as e:
            logger.error(f"Error loading config values into UI: {e}")
    
    def _set_combo_text(self, combo, text):
        """Helper method to set combo box text"""
        try:
            # Map common log level names
            level_mapping = {
                "Trace": "DEBUG",
                "Info": "INFO", 
                "Debug": "DEBUG",
                "Warning": "WARNING",
                "Error": "ERROR",
                "Critical": "CRITICAL"
            }
            
            # Use mapping if available, otherwise use text as-is
            mapped_text = level_mapping.get(text, text.upper())
            
            index = combo.findText(mapped_text)
            if index >= 0:
                combo.setCurrentIndex(index)
        except Exception as e:
            logger.warning(f"Could not set combo text '{text}': {e}")

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
        self.setting_ui = Settings_Form(self.config)

        # Start data collection
        self.worker_thread.start()

        self.setting_ui.ui.cancelButton.clicked.connect(self._close_setting_form)
        self.setting_ui.ui.saveButton.clicked.connect(self._save_setting_form)

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("IB Trading Application")
        
        # Set initial connection status
        self.update_connection_status(False)
        
        # Connect settings button
        if hasattr(self.ui, 'pushButton_settings'):
            self.ui.pushButton_settings.clicked.connect(self.show_setting_ui)
        
        # Setup refresh timer for UI updates
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_ui)
        self.refresh_timer.start(1000)  # Update every second
        
    def show_setting_ui(self):
        """Show the settings dialog"""
        # Reload config values into UI before showing
        if hasattr(self.setting_ui, 'load_config_values'):
            self.setting_ui.load_config_values()
        self.setting_ui.exec_()

    def _close_setting_form(self):
        self.setting_ui.close()
        
    def _save_setting_form(self):
        """Save all settings from the preferences UI to the config file"""
        try:
            # Get connection settings
            self.config.connection.update({
                "host": self.setting_ui.ui.hostEdit.text(),
                "port": int(self.setting_ui.ui.portEdit.text()),
                "client_id": int(self.setting_ui.ui.clientIdEdit.text())
            })
            
            # Get trading settings
            self.config.trading.update({
                "underlying_symbol": self.setting_ui.ui.underlyingSymbolEdit.text(),
                "trade_delta": float(self.setting_ui.ui.tradeDeltaEdit.text()),
                "max_trade_value": float(self.setting_ui.ui.maxTradeValueEdit.text()),
                "runner": int(self.setting_ui.ui.runnerEdit.text())
            })
            
            # Get risk levels from table
            risk_levels = []
            table = self.setting_ui.ui.riskLevelsTable
            for row in range(table.rowCount()):
                risk_level = {}
                # Check if cells exist and have text
                loss_threshold_item = table.item(row, 0)
                account_trade_limit_item = table.item(row, 1)
                stop_loss_item = table.item(row, 2)
                profit_gain_item = table.item(row, 3)
                
                risk_level["loss_threshold"] = loss_threshold_item.text() if loss_threshold_item and loss_threshold_item.text() != "-" else ""
                risk_level["account_trade_limit"] = account_trade_limit_item.text() if account_trade_limit_item and account_trade_limit_item.text() != "-" else ""
                risk_level["stop_loss"] = stop_loss_item.text() if stop_loss_item and stop_loss_item.text() != "-" else ""
                risk_level["profit_gain"] = profit_gain_item.text() if profit_gain_item and profit_gain_item.text() != "-" else ""
                
                risk_levels.append(risk_level)
            
            self.config.trading["risk_levels"] = risk_levels
            
            # Get debug settings
            self.config.debug.update({
                "master_debug": self.setting_ui.ui.masterDebugCheckBox.isChecked()
            })
            
            # Get module log levels
            module_levels = {}
            if hasattr(self.setting_ui.ui, 'mainLogLevelCombo'):
                module_levels["MAIN"] = self.setting_ui.ui.mainLogLevelCombo.currentText()
            if hasattr(self.setting_ui.ui, 'guiLogLevelCombo'):
                module_levels["GUI"] = self.setting_ui.ui.guiLogLevelCombo.currentText()
            if hasattr(self.setting_ui.ui, 'eventBusLogLevelCombo'):
                module_levels["EVENT_BUS"] = self.setting_ui.ui.eventBusLogLevelCombo.currentText()
            if hasattr(self.setting_ui.ui, 'subscriptionManagerLogLevelCombo'):
                module_levels["SUBSCRIPTION_MANAGER"] = self.setting_ui.ui.subscriptionManagerLogLevelCombo.currentText()
            
            self.config.debug["modules"].update(module_levels)
            
            # Save to file
            self.config.save_to_file()
            
            # Close the settings dialog
            self.setting_ui.close()
            
            logger.info("Settings saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(
                self.setting_ui,
                "Error",
                f"Failed to save settings: {str(e)}"
            )
        

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
        status_text = "Connections Status: Connected" if connected else "Connections Status: Disconnected"
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
