from ui.ib_trading_gui import Ui_MainWindow
from utils.config_manager import AppConfig
from widgets.settings_form import Settings_Form
from widgets.ai_prompt_form import AIPrompt_Form

from utils.data_collector import DataCollectorWorker
from utils.ai_engine import AI_Engine

from typing import Dict, Any, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
try:
    from PyQt5.QtWidgets import QMainWindow, QMessageBox
    from PyQt5.QtCore import QThread, QTimer
    logger.info("PyQt5 imports successful")
except ImportError as e:
    logger.error(f"PyQt5 import failed: {e}")
    raise


class IB_Trading_APP(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)


        # Load configuration
        try:
            logger.info("Loading configuration...")
            self.config = AppConfig.load_from_file()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            logger.info("Creating default configuration...")
            self.config = AppConfig()
            self.config.save_to_file()
            logger.info("Default configuration created and saved")
        
        self.connection_status = 'disconnected'
        # Initialize data collector worker
        try:
            logger.info("Initializing data collector worker...")
            self.data_worker = DataCollectorWorker(self.config)
            self.worker_thread = QThread()
            self.data_worker.moveToThread(self.worker_thread)
            logger.info("Data collector worker initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize data collector worker: {e}")
            self.data_worker = None
            self.worker_thread = None
        
        # Connect signals
        if self.data_worker and self.worker_thread:
            try:
                self.data_worker.data_ready.connect(self.update_ui_with_data)
                self.data_worker.connection_status_changed.connect(self.update_connection_status)
                self.data_worker.error_occurred.connect(self.handle_error)
                self.data_worker.price_updated.connect(self.update_real_time_price)
                self.data_worker.fx_rate_updated.connect(self.update_fx_rate)
                self.data_worker.connection_success.connect(self.update_connection_status)
                self.data_worker.connection_disconnected.connect(self.update_connection_status)
                self.data_worker.calls_option_updated.connect(self.update_calls_option)
                self.data_worker.puts_option_updated.connect(self.update_puts_option)
                
                # Connect thread signals
                self.worker_thread.started.connect(self.data_worker.start_collection)
                self.worker_thread.finished.connect(self.data_worker.cleanup)
                logger.info("Data worker signals connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect data worker signals: {e}")
        else:
            logger.warning("Data worker not available, skipping signal connections")
        
        # Setup UI
        self.setup_ui()
        
        # Initialize UI forms with error handling
        try:
            logger.info("Initializing Settings_Form...")
            # Check if required UI files exist
            import os
            ui_file_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'settings_gui.py')
            if not os.path.exists(ui_file_path):
                logger.error(f"UI file not found: {ui_file_path}")
                raise FileNotFoundError(f"UI file not found: {ui_file_path}")
            
            # Check if main UI file exists
            main_ui_file_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'ib_trading_gui.py')
            if not os.path.exists(main_ui_file_path):
                logger.error(f"Main UI file not found: {main_ui_file_path}")
                raise FileNotFoundError(f"Main UI file not found: {main_ui_file_path}")
            
            self.setting_ui = Settings_Form(self.config, self.connection_status, self.data_worker)
            logger.info("Settings_Form initialized successfully")
            
            logger.info("Initializing AIPrompt_Form...")
            # Check if required AI prompt UI file exists
            ai_ui_file_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'ai_prompt_gui.py')
            if not os.path.exists(ai_ui_file_path):
                logger.error(f"AI Prompt UI file not found: {ai_ui_file_path}")
                raise FileNotFoundError(f"AI Prompt UI file not found: {ai_ui_file_path}")
            
            self.ai_prompt_ui = AIPrompt_Form(self.config)
            logger.info("AIPrompt_Form initialized successfully")
            
            # Connect form signals
            if hasattr(self.setting_ui.ui, 'cancelButton'):
                self.setting_ui.ui.cancelButton.clicked.connect(self._close_setting_form)
            if hasattr(self.setting_ui.ui, 'saveButton'):
                self.setting_ui.ui.saveButton.clicked.connect(self._save_setting_form)
            
            # Connect settings form to data worker signals for connection status updates
            if self.setting_ui and self.data_worker:
                try:
                    self.data_worker.connection_success.connect(lambda data: self.setting_ui.update_connection_status(data.get('status', 'Connected')))
                    self.data_worker.connection_disconnected.connect(lambda data: self.setting_ui.update_connection_status(data.get('status', 'Disconnected')))
                    self.data_worker.error_occurred.connect(lambda msg: self.setting_ui.update_connection_status("Error"))
                    logger.info("Settings form signal connections established")
                except Exception as e:
                    logger.error(f"Failed to connect settings form signals: {e}")
                
        except Exception as e:
            logger.error(f"Error initializing UI forms: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Create minimal forms if there's an error
            self.setting_ui = None
            self.ai_prompt_ui = None
        
        # Start data collection
        if self.worker_thread and self.data_worker:
            try:
                self.worker_thread.start()
                logger.info("Data collection thread started successfully")
            except Exception as e:
                logger.error(f"Failed to start data collection thread: {e}")
        else:
            logger.warning("Data collection thread not available")

        try:
            logger.info("Initializing AI engine...")
            self.ai_engine = AI_Engine(self.config)
            logger.info("AI engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI engine: {e}")
            self.ai_engine = None
        
        self.refresh_ui_with_whitespace()
        
        # Ensure setting_ui attribute exists even if initialization failed
        if not hasattr(self, 'setting_ui'):
            self.setting_ui = None
        if not hasattr(self, 'ai_prompt_ui'):
            self.ai_prompt_ui = None

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("IB Trading Application")
        
        # Set initial connection status
        self.update_connection_status({'status': self.connection_status})
        
        # Initialize time label with current time
        if hasattr(self.ui, 'label_time'):
            current_time = datetime.now().strftime("%I:%M:%S %p")
            self.ui.label_time.setText(current_time)
        
        # Connect settings button
        if hasattr(self.ui, 'pushButton_settings'):
            try:
                self.ui.pushButton_settings.clicked.connect(self.show_setting_ui)
            except Exception as e:
                logger.error(f"Error connecting settings button: {e}")
        
        # Connect AI prompt button
        if hasattr(self.ui, 'button_ai_prompt'):
            try:
                self.ui.button_ai_prompt.clicked.connect(self.show_ai_prompt_ui)
            except Exception as e:
                logger.error(f"Error connecting AI prompt button: {e}")
        
        if hasattr(self.ui, 'button_refresh_ai'):
            try:
                self.ui.button_refresh_ai.clicked.connect(self.refresh_ai)
            except Exception as e:
                logger.error(f"Error connecting refresh AI button: {e}")
        
        # Setup refresh timer for UI updates
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_ui)
        self.refresh_timer.start(1000)  # Update every second
        
    def show_setting_ui(self):
        """Show the settings dialog"""
        if self.setting_ui is None:
            logger.error("Settings UI not available")
            return
            
        # Reload config values into UI before showing
        if hasattr(self.setting_ui, 'load_config_values'):
            self.setting_ui.load_config_values()
        self.setting_ui.exec_()

    def refresh_ai(self):
        """Refresh the AI engine"""
        if hasattr(self, 'ai_engine') and self.ai_engine:
            try:
                self.ai_engine.refresh()
            except Exception as e:
                logger.error(f"Failed to refresh AI engine: {e}")
        else:
            logger.warning("AI engine not available")

    def show_ai_prompt_ui(self):
        """Show the AI prompt dialog"""
        if not hasattr(self, 'ai_prompt_ui') or self.ai_prompt_ui is None:
            logger.error("AI Prompt UI not available - attempting to reinitialize...")
            try:
                self.ai_prompt_ui = AIPrompt_Form(self.config)
                logger.info("AIPrompt_Form reinitialized successfully")
            except Exception as e:
                logger.error(f"Failed to reinitialize AIPrompt_Form: {e}")
                return
        self.ai_prompt_ui.exec_()

    def _close_setting_form(self):
        if hasattr(self, 'setting_ui') and self.setting_ui:
            self.setting_ui.close()
        
    def _save_setting_form(self):
        """Save all settings from the preferences UI to the config file"""
        if not hasattr(self, 'setting_ui') or self.setting_ui is None:
            logger.error("Settings UI not available")
            return
            
        try:
            if not hasattr(self, 'config') or not self.config:
                logger.error("Configuration not available")
                return
                
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

    def update_calls_option(self, calls_data: Dict[str, Any]):
        try:
            print(f"UI Calls Data: {calls_data}")
            self.ui.label_call_price_value.setText(f'{calls_data.get("Last")}')
            self.ui.label_call_bid_value.setText(f'{calls_data.get("Bid")}')
            self.ui.label_call_ask_value.setText(f'{calls_data.get("Ask")}')
            self.ui.label_call_delta_value.setText(f'{calls_data.get("Delta"):.4f}')
            self.ui.label_call_gamma_value.setText(f'{calls_data.get("Gamma"):.4f}')
            self.ui.label_call_theta_value.setText(f'{calls_data.get("Theta"):.4f}')
            self.ui.label_call_vega_value.setText(f'{calls_data.get("Vega"):.4f}')
            self.ui.label_call_openint_value.setText(f'{calls_data.get("Call_Open_Interest")}')
            self.ui.label_call_volume_value.setText(f'{calls_data.get("Volume")}')

        except Exception as e:
            logger.error(f"Error updating UI with calls option data: {e}")


    def update_puts_option(self, puts_data: Dict[str, Any]):
        try:
            print(f"UI Puts Data: {puts_data}")
            self.ui.label_put_price_value.setText(f'{puts_data.get("Last")}')
            self.ui.label_put_bid_value.setText(f'{puts_data.get("Bid")}')
            self.ui.label_put_ask_value.setText(f'{puts_data.get("Ask")}')
            self.ui.label_put_delta_value.setText(f'{puts_data.get("Delta"):.4f}')
            self.ui.label_put_gamma_value.setText(f'{puts_data.get("Gamma"):.4f}')
            self.ui.label_put_theta_value.setText(f'{puts_data.get("Theta"):.4f}')
            self.ui.label_put_vega_value.setText(f'{puts_data.get("Vega"):.4f}')
            self.ui.label_put_openint_value.setText(f'{puts_data.get("Put_Open_Interest")}')
            self.ui.label_put_volume_value.setText(f'{puts_data.get("Volume")}')

        except Exception as e:
            logger.error(f"Error updating UI with puts option data: {e}")

    def update_ui_with_data(self, data: Dict[str, Any]):
        """Update UI with collected data"""
        try:
            if hasattr(self, 'config') and self.config and self.config.trading and self.config.trading.get('underlying_symbol') is not None:
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
                high_water_mark = account_data.get('HighWaterMark', '---')

                self.ui.label_account_value_value.setText(f"${account_value}")
                self.ui.label_starting_value_value.setText(f"${starting_value}")
                self.ui.label_daily_pl_value.setText(f"${pnl_value_price}")
                self.ui.label_daily_pl_percent_value.setText(f"{pnl_value_percent}%")
                self.ui.label_high_water_value.setText(f"${high_water_mark}")
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
                self.ui.label_pl_dollar_value.setText(f"{active_contract_data.get('pnl_dollar', '---')}$")
                self.ui.label_pl_percent_value.setText(f"{active_contract_data.get('pnl_percent', '---')}%")

            # Update option information data
            if data.get('options') is not None and not data['options'].empty:
                logger.info(f"Updating Option Information Data in UI: {data['options']}")

                option_primary_data = data['options']
                tmp_expiration = option_primary_data["Expiration"]
                # Convert string format "20250810" to datetime then format as "2025-08-10"
                if isinstance(tmp_expiration, str) and len(tmp_expiration) == 8:
                    tmp_expiration = datetime.strptime(tmp_expiration, "%Y%m%d").strftime("%Y-%m-%d")

                self.ui.label_strike_value.setText(f'{option_primary_data["Strike"]}')
                self.ui.label_expiration_value.setText(f'{tmp_expiration}')

            # # Update statistics
            # if data.get('statistics') and not data['statistics'].empty:
            #     stats = data['statistics'].iloc[0]
            #     win_rate = stats.get('Win_Rate', 0)
            #     logger.info(f"Win rate: {win_rate:.2f}%")
                
        except Exception as e:
            logger.error(f"Error updating UI with data: {e}")
    
    def update_connection_status(self, data: Union[Dict[str, Any], bool]):
        """Update connection status in UI"""
        # Handle both boolean and dictionary inputs
        if isinstance(data, bool):
            # Boolean input from connection_status_changed signal
            status = 'Connected' if data else 'Disconnected'
        else:
            # Dictionary input from connection_success/connection_disconnected signals
            status = data.get('status', 'Unknown')
        
        status_text = f"Connections Status: {status}"
        status_color = "green" if status == 'Connected' else "red"
        self.connection_status = status
        
        # Update status label if it exists in the UI
        if hasattr(self.ui, 'label_connection_status'):
            self.ui.label_connection_status.setText(status_text)
            self.ui.label_connection_status.setStyleSheet(f"color: {status_color}")
            
        if hasattr(self, 'setting_ui') and self.setting_ui and hasattr(self.setting_ui.ui, 'connectionStatusLabel'):
            try:
                self.setting_ui.ui.connectionStatusLabel.setText("Connection: " + self.connection_status)
                if self.connection_status == 'Connected':
                    self.setting_ui.ui.connectionStatusLabel.setStyleSheet("color: green;")
                    self.setting_ui.ui.connectButton.setText("Disconnect")
                else:
                    self.setting_ui.ui.connectionStatusLabel.setStyleSheet("color: red;")
                    self.setting_ui.ui.connectButton.setText("Connect")
            except Exception as e:
                logger.error(f"Error updating setting UI connection status: {e}")

        
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
    
    def update_real_time_price(self, price_data: Dict[str, Any]):
        """Handle real-time price updates from IB"""
        try:
            symbol = price_data.get('symbol', 'Unknown')
            price = price_data.get('price', 0)
            timestamp = price_data.get('timestamp', '')
            
            logger.info(f"Real-time price update: {symbol} = ${price:.2f} at {timestamp}")
            
            # Update the underlying symbol price in UI
            if hasattr(self, 'config') and self.config and self.config.trading and symbol == self.config.trading.get('underlying_symbol'):
                self.ui.label_spy_value.setText(f"${price:.2f}")
                    
        except Exception as e:
            logger.error(f"Error updating real-time price: {e}")
    
    def update_fx_rate(self, fx_rate_data: Dict[str, Any]):
        """Handle real-time FX rate updates from IB"""
        try:
            symbol = fx_rate_data.get('symbol', 'Unknown')
            rate = fx_rate_data.get('rate', 0)
            timestamp = fx_rate_data.get('timestamp', '')

            logger.info(f"Real-time FX rate update: {symbol} = {rate} at {timestamp}")

            # Update the FX rate in UI
            if symbol == 'USDCAD':
                self.ui.label_usd_cad_value.setText(f"{rate:.4f}")
                self.ui.label_cad_usd_value.setText(f"{1/rate:.4f}")
        except Exception as e:
            logger.error(f"Error updating FX rate: {e}")
    
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
            if hasattr(self, 'data_worker') and self.data_worker:
                try:
                    self.data_worker.stop_collection()
                except Exception as e:
                    logger.error(f"Error stopping data collection: {e}")
            
            # Wait for thread to finish
            if hasattr(self, 'worker_thread') and self.worker_thread and self.worker_thread.isRunning():
                try:
                    self.worker_thread.quit()
                    self.worker_thread.wait(5000)  # Wait up to 5 seconds
                except Exception as e:
                    logger.error(f"Error stopping worker thread: {e}")
            
            # Save configuration
            if hasattr(self, 'config') and self.config:
                try:
                    self.config.save_to_file()
                except Exception as e:
                    logger.error(f"Error saving configuration: {e}")
            
            logger.info("Application shutdown completed")
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            event.accept()

