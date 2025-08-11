from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import QThread, QTimer
from ui.ib_trading_gui import Ui_MainWindow
from utils.config_manager import AppConfig
from widgets.settings_form import Settings_Form
from widgets.ai_prompt_form import AIPrompt_Form

from utils.data_collector import DataCollectorWorker
from utils.ai_engine import AI_Engine

from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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
        self.ai_prompt_ui = AIPrompt_Form(self.config)
        # Start data collection
        self.worker_thread.start()

        self.setting_ui.ui.cancelButton.clicked.connect(self._close_setting_form)
        self.setting_ui.ui.saveButton.clicked.connect(self._save_setting_form)

        self.ai_engine = AI_Engine(self.config)
        self.refresh_ui_with_whitespace()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("IB Trading Application")
        
        # Set initial connection status
        self.update_connection_status(False)
        
        # Initialize time label with current time
        if hasattr(self.ui, 'label_time'):
            current_time = datetime.now().strftime("%I:%M:%S %p")
            self.ui.label_time.setText(current_time)
        
        # Connect settings button
        if hasattr(self.ui, 'pushButton_settings'):
            self.ui.pushButton_settings.clicked.connect(self.show_setting_ui)
        
        # Connect AI prompt button
        if hasattr(self.ui, 'button_ai_prompt'):
            self.ui.button_ai_prompt.clicked.connect(self.show_ai_prompt_ui)
        
        self.ui.button_refresh_ai.clicked.connect(self.refresh_ai)
        
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

    def refresh_ai(self):
        """Refresh the AI engine"""
        self.ai_engine.refresh()

    def show_ai_prompt_ui(self):
        """Show the AI prompt dialog"""
        self.ai_prompt_ui.exec_()

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
        
    def refresh_ui_with_whitespace(self):
        """Refresh UI with whitespace"""
        self.ui.label_spy_name.setText(f"---")
        self.ui.label_spy_value.setText(f"---")
        self.ui.label_usd_cad_value.setText(f"---")
        self.ui.label_cad_usd_value.setText(f"---")
        self.ui.label_account_value_value.setText(f"---")
        self.ui.label_symbol_value.setText(f"---")
        self.ui.label_quantity_value.setText(f"---")
        self.ui.label_pl_dollar_value.setText(f"---")
        self.ui.label_pl_percent_value.setText(f"---")
        # self.ui.label_win_rate_value.setText(f"---")
        # self.ui.label_total_trades_value.setText(f"---")
        # self.ui.label_total_wins_value.setText(f"---")

    def update_ui_with_data(self, data: Dict[str, Any]):
        """Update UI with collected data"""
        try:
            if self.config.trading.get('underlying_symbol') is not None:
                self.ui.label_spy_name.setText(f"{self.config.trading.get('underlying_symbol')}")
            else:
                self.ui.label_spy_name.setText(f"---")

            # Update SPY price
            if data.get('underlying_symbol_price') is not None and data['underlying_symbol_price'] > 0:
                self.ui.label_spy_value.setText(f"${data['underlying_symbol_price']:.2f}")

            if data.get('fx_ratio') is not None and data['fx_ratio'] > 0:
                self.ui.label_usd_cad_value.setText(f"{data['fx_ratio']:.4f}")
                self.ui.label_cad_usd_value.setText(f"{1/data['fx_ratio']:.4f}")

            # Update account metrics
            if data.get('account') is not None and not data['account'].empty:
                logger.info("Updating Account Data in UI")
                account_data = data['account'].iloc[0]
                account_value = account_data.get('NetLiquidation', 'N/A')
                starting_value = account_data.get('StartingValue','---')
                pnl_value_price = account_data.get('RealizedPnLPrice', 0)
                pnl_value_percent = account_data.get('RealizedPnLPercent', 0)

                self.ui.label_account_value_value.setText(f"${account_value}")
                self.ui.label_starting_value_value.setText(f"${starting_value}")
                self.ui.label_daily_pl_value.setText(f"${pnl_value_price}")
                self.ui.label_daily_pl_percent_value.setText(f"${pnl_value_percent}")
                logger.info(f"Account Net Liquidation: ${account_value}")
                # Update account-related UI elements here
            #
            # # Update positions
            # if data.get('positions') and not data['positions'].empty:
            #     positions_count = len(data['positions'])
            #     logger.info(f"Active positions: {positions_count}")
            
            # Update active contract data
            if data.get('active_contract') is not None and not data['active_contract'].empty:
                logger.info("Updating Active Contract Data in UI")
                active_contract_data = data['active_contract'].iloc[0]
                logger.info(f"Active contract data: {active_contract_data}")
                self.ui.label_symbol_value.setText(f"{active_contract_data.get('symbol', '---')}")
                self.ui.label_quantity_value.setText(f"{active_contract_data.get('position_size', '---')}")
                self.ui.label_pl_dollar_value.setText(f"${active_contract_data.get('pnl_dollar', '---')}")
                self.ui.label_pl_percent_value.setText(f"{active_contract_data.get('pnl_percent', '---')}%")


            
            
            # # Update statistics
            # if data.get('statistics') and not data['statistics'].empty:
            #     stats = data['statistics'].iloc[0]
            #     win_rate = stats.get('Win_Rate', 0)
            #     logger.info(f"Win rate: {win_rate:.2f}%")
                
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
        # Update the time label with current time
        current_time = datetime.now().strftime("%I:%M:%S %p")
        if hasattr(self.ui, 'label_time'):
            self.ui.label_time.setText(current_time)
    
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

