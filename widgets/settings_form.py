from PyQt6.QtWidgets import QDialog
from PyQt6 import QtWidgets
from utils.config_manager import AppConfig
from ui.settings_gui import Ui_PreferencesDialog
from utils.smart_logger import get_logger, log_error_with_context
from datetime import datetime

logger = get_logger("SETTINGS")

class Settings_Form(QDialog):
    def __init__(self, config: AppConfig = None, connection_status: str = None, data_worker=None):
        super().__init__()
        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)
        self.config = config
        self.connection_status = connection_status
        self.data_worker = data_worker
        if self.config:
            self.load_config_values()
        
        # Set connection status safely
        if hasattr(self.ui, 'connectionStatusLabel'):
            self.ui.connectionStatusLabel.setText("Connection: " + (self.connection_status or "Disconnected"))
            if self.connection_status == 'Connected':
                self.ui.connectionStatusLabel.setStyleSheet("color: green;")
            else:
                self.ui.connectionStatusLabel.setStyleSheet("color: red;")
        
        if hasattr(self.ui, 'connectButton'):
            if self.connection_status == 'Connected':
                self.ui.connectButton.setText("Disconnect")
            else:
                self.ui.connectButton.setText("Connect")
                
        self.ui.connectButton.clicked.connect(self.connect_button_clicked)
        
        # Add initial log message
        self.log_connection_event("Connection log initialized", "Info")
            
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
            
    def get_current_connection_settings(self):
        """Get current connection settings from the UI"""
        try:
            host = self.ui.hostEdit.text().strip()
            port = int(self.ui.portEdit.text().strip())
            client_id = int(self.ui.clientIdEdit.text().strip())
            
            # Validate settings
            if not host:
                logger.error("Host cannot be empty")
                return None
            
            if port <= 0 or port > 65535:
                logger.error(f"Invalid port number: {port}")
                return None
            
            if client_id < 0:
                logger.error(f"Invalid client ID: {client_id}")
                return None
            
            return {
                'host': host,
                'port': port,
                'client_id': client_id
            }
        except ValueError as e:
            logger.error(f"Error parsing connection settings from UI: {e}")
            # Return default values if parsing fails
            return {
                'host': '127.0.0.1',
                'port': 7497,
                'client_id': 1
            }
        except Exception as e:
            logger.error(f"Error getting connection settings from UI: {e}")
            return None
    
    def log_connection_event(self, message: str, level: str = "Info"):
        """Log a connection event to the connectionLogText widget"""
        try:
            if hasattr(self.ui, 'connectionLogText'):
                # Get current timestamp
                timestamp = datetime.now().strftime("%I:%M:%S %p")
                
                # Format the log message
                log_entry = f"[{timestamp}] {level}: {message}\n"
                
                # Append to the text widget
                self.ui.connectionLogText.append(log_entry)
                
                # Auto-scroll to the bottom
                cursor = self.ui.connectionLogText.textCursor()
                cursor.movePosition(cursor.End)
                self.ui.connectionLogText.setTextCursor(cursor)
                
                logger.info(f"Connection log: {message}")
            else:
                logger.warning("connectionLogText widget not found in UI")
        except Exception as e:
            logger.error(f"Error logging to connection log: {e}")
            
    def connect_button_clicked(self):
        """Handle connect button click"""
        if self.connection_status == 'Connected':
            # Disconnect from IB
            if self.data_worker and hasattr(self.data_worker, 'disconnect_from_ib'):
                try:
                    self.log_connection_event("Manual disconnect requested", "Info")
                    logger.info("Disconnecting from IB via DataCollectorWorker")
                    self.data_worker.disconnect_from_ib()
                    self.connection_status = 'Disconnecting...'
                    self.ui.connectionStatusLabel.setText("Connection: " + self.connection_status)
                    self.ui.connectionStatusLabel.setStyleSheet("color: orange;")
                    self.ui.connectButton.setText("Disconnecting...")
                    self.ui.connectButton.setEnabled(False)
                    
                    # Set up a timer to check if disconnect completed and update button state
                    from PyQt6.QtCore import QTimer
                    def check_disconnect_status():
                        if not self.data_worker.collector.ib.isConnected():
                            logger.info("Disconnect completed, updating button state")
                            self.log_connection_event("Disconnect completed successfully", "Info")
                            self.update_connection_status('Disconnected')
                        else:
                            # Still connected, try again in 1 second
                            QTimer.singleShot(1000, check_disconnect_status)
                    
                    # Check after 2 seconds
                    QTimer.singleShot(2000, check_disconnect_status)
                    
                except Exception as e:
                    logger.error(f"Error disconnecting from IB: {e}")
                    self.log_connection_event(f"Error disconnecting: {str(e)}", "Error")
                    self.ui.connectionStatusLabel.setText("Connection: Error disconnecting")
                    self.ui.connectionStatusLabel.setStyleSheet("color: red;")
                    # Re-enable button on error
                    self.ui.connectButton.setEnabled(True)
                    self.ui.connectButton.setText("Disconnect")
            else:
                logger.warning("No data worker available for disconnection")
                self.log_connection_event("No data worker available for disconnection", "Warning")
                self.ui.connectionStatusLabel.setText("Connection: No data worker")
                self.ui.connectionStatusLabel.setStyleSheet("color: red;")
        else:
            # Connect to IB
            if self.data_worker and hasattr(self.data_worker, 'connect_to_ib'):
                try:
                    logger.info("Connecting to IB via DataCollectorWorker")
                    
                    # Get current connection settings from UI
                    connection_settings = self.get_current_connection_settings()
                    if connection_settings:
                        self.log_connection_event(f"Manual connect requested to {connection_settings['host']}:{connection_settings['port']} (Client ID: {connection_settings['client_id']})", "Info")
                        logger.info(f"Using connection settings from UI: {connection_settings}")
                        self.data_worker.connect_to_ib(connection_settings)
                        
                        self.connection_status = 'Connecting...'
                        self.ui.connectionStatusLabel.setText("Connection: " + self.connection_status)
                        self.ui.connectionStatusLabel.setStyleSheet("color: orange;")
                        self.ui.connectButton.setText("Connecting...")
                        self.ui.connectButton.setEnabled(False)
                    else:
                        logger.warning("Invalid connection settings, cannot connect")
                        self.log_connection_event("Invalid connection settings, cannot connect", "Error")
                        self.ui.connectionStatusLabel.setText("Connection: Invalid settings")
                        self.ui.connectionStatusLabel.setStyleSheet("color: red;")
                        # Keep button enabled and show "Connect" text
                        self.ui.connectButton.setEnabled(True)
                        self.ui.connectButton.setText("Connect")
                        
                except Exception as e:
                    logger.error(f"Error connecting to IB: {e}")
                    self.log_connection_event(f"Error connecting: {str(e)}", "Error")
                    self.ui.connectionStatusLabel.setText("Connection: Error connecting")
                    self.ui.connectionStatusLabel.setStyleSheet("color: red;")
                    # Re-enable button on error
                    self.ui.connectButton.setEnabled(True)
                    self.ui.connectButton.setText("Connect")
            else:
                logger.warning("No data worker available for connection")
                self.log_connection_event("No data worker available for connection", "Warning")
                self.ui.connectionStatusLabel.setText("Connection: No data worker")
                self.ui.connectionStatusLabel.setStyleSheet("color: red;")
    
    def update_connection_status(self, status: str):
        """Update connection status from external source (e.g., signal handlers)"""
        logger.info(f"Settings form: Updating connection status to: {status}")
        self.connection_status = status
        
        if hasattr(self.ui, 'connectionStatusLabel'):
            self.ui.connectionStatusLabel.setText("Connection: " + status)
            if status == 'Connected':
                self.ui.connectionStatusLabel.setStyleSheet("color: green;")
                self.ui.connectButton.setText("Disconnect")
                self.log_connection_event("Connection established successfully", "Info")
                logger.info("Settings form: Button set to 'Disconnect'")
            elif status == 'Disconnected':
                self.ui.connectionStatusLabel.setStyleSheet("color: red;")
                self.ui.connectButton.setText("Connect")
                self.log_connection_event("Connection disconnected", "Info")
                logger.info("Settings form: Button set to 'Connect'")
            else:
                self.ui.connectionStatusLabel.setStyleSheet("color: orange;")
                self.ui.connectButton.setText("Connecting..." if "Connecting" in status else "Disconnecting...")
                if "Connecting" in status:
                    self.log_connection_event("Connection attempt in progress...", "Info")
                elif "Disconnecting" in status:
                    self.log_connection_event("Disconnection in progress...", "Info")
                logger.info(f"Settings form: Button set to '{self.ui.connectButton.text()}'")
            
            # Re-enable button
            self.ui.connectButton.setEnabled(True)
            logger.info(f"Settings form: Button enabled: {self.ui.connectButton.isEnabled()}")
        else:
            logger.warning("Settings form: connectionStatusLabel not found in UI")