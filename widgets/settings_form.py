from PyQt5.QtWidgets import QDialog
from PyQt5 import QtWidgets
from utils.config_manager import AppConfig
from ui.settings_gui import Ui_PreferencesDialog
import logging

logger = logging.getLogger(__name__)

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