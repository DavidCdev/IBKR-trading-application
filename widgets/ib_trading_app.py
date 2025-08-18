from ui.ib_trading_gui import Ui_MainWindow
from utils.config_manager import AppConfig
from widgets.settings_form import Settings_Form
from widgets.ai_prompt_form import AI_Prompt_Form

from utils.data_collector import DataCollectorWorker
from utils.ai_engine import AI_Engine
from utils.hotkey_manager import HotkeyManager

from typing import Dict, Any, Union, List
from datetime import datetime
from utils.smart_logger import get_logger

logger = get_logger("GUI")
try:
    from PyQt6.QtWidgets import QMainWindow, QMessageBox
    from PyQt6.QtCore import QThread, QTimer
    logger.info("PyQt6 imports successful")
except ImportError as e:
    logger.error(f"PyQt6 import failed: {e}")
    raise


class IB_Trading_APP(QMainWindow):
    def __init__(self):
        super().__init__()
        self.refresh_timer = None
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)


        # Load configuration
        try:
            logger.info("Loading configuration...")
            self.config = AppConfig.load_from_file()
            logger.info("Configuration loaded successfully")
        except Exception as e1:
            logger.error(f"Failed to load configuration: {e1}")
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
        except Exception as e2:
            logger.error(f"Failed to initialize data collector worker: {e2}")
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
                self.data_worker.daily_pnl_update.connect(self.update_daily_pnl_updated)
                self.data_worker.account_summary_update.connect(self.update_account_summary)
                self.data_worker.trading_config_updated.connect(self.on_trading_config_updated)
                self.data_worker.active_contracts_pnl_refreshed.connect(self.update_active_contracts_pnl)
                self.data_worker.closed_trades_update.connect(self.update_closed_trades)
                # Connect thread signals
                self.worker_thread.started.connect(self.data_worker.start_collection)
                self.worker_thread.finished.connect(self.data_worker.cleanup)
                logger.info("Data worker signals connected successfully")
            except Exception as e3:
                logger.error(f"Failed to connect data worker signals: {e3}")
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
            
            self.ai_prompt_ui = AI_Prompt_Form(self.config, self.refresh_ai)
            logger.info("AIPrompt_Form initialized successfully")
            
            # Connect form signals
            if hasattr(self.setting_ui.ui, 'cancelButton'):
                self.setting_ui.ui.cancelButton.clicked.connect(self._close_setting_form)
            if hasattr(self.setting_ui.ui, 'saveButton'):
                self.setting_ui.ui.saveButton.clicked.connect(self._save_setting_form)
            
            # Connect settings form to data worker signals for connection status updates
            if self.setting_ui and self.data_worker:
                try:
                    def on_connection_success(data):
                        status = data.get('status', 'Connected')
                        message = data.get('message', '')
                        logger.info(f"Main app: Connection success signal received: {status}")
                        self.setting_ui.update_connection_status(status)
                        if message and hasattr(self.setting_ui, 'log_connection_event'):
                            self.setting_ui.log_connection_event(message, "Info")
                    
                    def on_connection_disconnected(data):
                        status = data.get('status', 'Disconnected')
                        message = data.get('message', '')
                        logger.info(f"Main app: Connection disconnected signal received: {status}")
                        self.setting_ui.update_connection_status(status)
                        if message and hasattr(self.setting_ui, 'log_connection_event'):
                            self.setting_ui.log_connection_event(message, "Info")
                    
                    def on_error(msg):
                        logger.info(f"Main app: Error signal received: {msg}")
                        self.setting_ui.update_connection_status("Error")
                        if hasattr(self.setting_ui, 'log_connection_event'):
                            self.setting_ui.log_connection_event(msg, "Error")
                    
                    self.data_worker.connection_success.connect(on_connection_success)
                    self.data_worker.connection_disconnected.connect(on_connection_disconnected)
                    self.data_worker.error_occurred.connect(on_error)
                    logger.info("Settings form signal connections established")
                except Exception as e3:
                    logger.error(f"Failed to connect settings form signals: {e3}")
                
        except Exception as e3:
            logger.error(f"Error initializing UI forms: {e3}")
            logger.error(f"Exception type: {type(e3).__name__}")
            logger.error(f"Exception details: {str(e3)}")
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
            except Exception as e3:
                logger.error(f"Failed to start data collection thread: {e3}")
        else:
            logger.warning("Data collection thread not available")

        try:
            logger.info("Initializing AI engine...")
            self.ai_engine = AI_Engine(self.config, self.data_worker)
            logger.info("AI engine initialized successfully")
            
            # Connect AI engine signals
            if self.ai_engine:
                self.ai_engine.analysis_ready.connect(self.on_ai_analysis_ready)
                self.ai_engine.analysis_error.connect(self.on_ai_analysis_error)
                self.ai_engine.polling_status.connect(self.on_ai_polling_status)
                self.ai_engine.cache_status.connect(self.on_ai_cache_status)
                logger.info("AI engine signals connected successfully")
        except Exception as e3:
            logger.error(f"Failed to initialize AI engine: {e3}")
            self.ai_engine = None
        
        # Initialize hotkey manager
        try:
            logger.info("Initializing hotkey manager...")
            if self.data_worker and self.data_worker.collector:
                self.hotkey_manager = HotkeyManager(self.data_worker.collector.trading_manager)
                self.hotkey_manager.start()
                logger.info("Hotkey manager initialized and started successfully")
            else:
                logger.warning("Data worker not available, skipping hotkey manager initialization")
                self.hotkey_manager = None
        except Exception as e3:
            logger.error(f"Failed to initialize hotkey manager: {e3}")
            self.hotkey_manager = None
        
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
            except Exception as e4:
                logger.error(f"Error connecting settings button: {e4}")
        
        # Connect AI prompt button
        if hasattr(self.ui, 'button_ai_prompt'):
            try:
                self.ui.button_ai_prompt.clicked.connect(self.show_ai_prompt_ui)
            except Exception as e5:
                logger.error(f"Error connecting AI prompt button: {e5}")
        
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
        self.setting_ui.exec()

    def refresh_ai(self):
        """Refresh the AI engine"""
        if hasattr(self, 'ai_engine') and self.ai_engine:
            try:
                logger.info("Refreshing AI engine configuration and analysis...")
                # First refresh the configuration
                self.ai_engine.refresh()
                # Then force refresh the analysis
                self.ai_engine.force_refresh()
            except Exception as e:
                logger.error(f"Failed to refresh AI engine: {e}")
        else:
            logger.warning("AI engine not available")
    
    def check_ai_status(self):
        """Check and log AI engine status for debugging"""
        if hasattr(self, 'ai_engine') and self.ai_engine:
            try:
                status = self.ai_engine.get_config_status()
                logger.info("AI Engine Status:")
                for key, value in status.items():
                    logger.info(f"  {key}: {value}")
            except Exception as e:
                logger.error(f"Failed to get AI engine status: {e}")
        else:
            logger.warning("AI engine not available for status check")
    
    def on_ai_analysis_ready(self, analysis_data: Dict[str, Any]):
        """Handle AI analysis results"""
        try:
            logger.info("AI analysis ready received")
            
            # Extract key data
            price_range = analysis_data.get('valid_price_range', {})
            analysis_summary = analysis_data.get('analysis_summary', '')
            confidence_level = analysis_data.get('confidence_level', 0.0)
            key_insights = analysis_data.get('key_insights', [])
            risk_assessment = analysis_data.get('risk_assessment', '')
            
            # Update UI with analysis results
            logger.info(f"AI Analysis - Price Range: ${price_range.get('low', 0):.2f} - ${price_range.get('high', 0):.2f}")
            logger.info(f"AI Analysis - Confidence: {confidence_level:.2f}")
            logger.info(f"AI Analysis - Summary: {analysis_summary[:100]}...")
            
            # Update AI Insights UI elements
            self._update_ai_insights_ui(analysis_data)
            
            # Store analysis for potential use by trading logic
            self.last_ai_analysis = analysis_data
            
        except Exception as e:
            logger.error(f"Error handling AI analysis: {e}")
    
    def _update_ai_insights_ui(self, analysis_data: Dict[str, Any]):
        """Update the AI insights UI with analysis results"""
        try:
            # Extract data
            price_range = analysis_data.get('valid_price_range', {})
            analysis_summary = analysis_data.get('analysis_summary', '')
            confidence_level = analysis_data.get('confidence_level', 0.0)
            key_insights = analysis_data.get('key_insights', [])
            risk_assessment = analysis_data.get('risk_assessment', '')
            
            # Determine AI bias based on analysis
            ai_bias = self._determine_ai_bias(price_range, analysis_summary, key_insights)
            
            # Format key levels
            key_levels = self._format_key_levels(price_range)
            
            # Format strategy text
            strategy_text = self._format_strategy_text(analysis_summary, key_insights, confidence_level)
            
            # Format alert text
            alert_text = self._format_alert_text(risk_assessment, key_insights)
            
            # Update UI elements
            if hasattr(self.ui, 'label_ai_bias_value'):
                self.ui.label_ai_bias_value.setText(ai_bias)
            
            if hasattr(self.ui, 'label_ai_keylevel_value'):
                self.ui.label_ai_keylevel_value.setText(key_levels)
            
            if hasattr(self.ui, 'textbrowser_ai_strategy_value'):
                self.ui.textbrowser_ai_strategy_value.setPlainText(strategy_text)
            
            if hasattr(self.ui, 'textbrowser_ai_alert_value'):
                self.ui.textbrowser_ai_alert_value.setPlainText(alert_text)
            
            logger.info("AI insights UI updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating AI insights UI: {e}")
    
    def _determine_ai_bias(self, price_range: Dict[str, float], analysis_summary: str, key_insights: List[str]) -> str:
        """Determine AI bias (Bullish/Bearish/Neutral) based on analysis"""
        try:
            # Get current price
            current_price = 0
            if hasattr(self, 'data_worker') and self.data_worker and self.data_worker.collector:
                current_price = self.data_worker.collector.underlying_symbol_price or 0
            
            if current_price <= 0:
                return "Neutral"
            
            low_price = price_range.get('low', 0)
            high_price = price_range.get('high', 0)
            
            if low_price <= 0 or high_price <= 0:
                return "Neutral"
            
            # Calculate price position relative to range
            range_mid = (low_price + high_price) / 2
            range_size = high_price - low_price
            
            if range_size <= 0:
                return "Neutral"
            
            # Determine bias based on current price position and analysis content
            price_position = (current_price - low_price) / range_size
            
            # Check analysis content for bias indicators
            summary_lower = analysis_summary.lower()
            insights_text = ' '.join(key_insights).lower()
            
            bullish_indicators = ['bullish', 'bull', 'upward', 'higher', 'support', 'buy', 'long']
            bearish_indicators = ['bearish', 'bear', 'downward', 'lower', 'resistance', 'sell', 'short']
            
            bullish_count = sum(1 for indicator in bullish_indicators if indicator in summary_lower or indicator in insights_text)
            bearish_count = sum(1 for indicator in bearish_indicators if indicator in summary_lower or indicator in insights_text)
            
            # Combine price position and text analysis
            if price_position > 0.6 and bullish_count > bearish_count:
                return "Bullish"
            elif price_position < 0.4 and bearish_count > bullish_count:
                return "Bearish"
            else:
                return "Neutral"
                
        except Exception as e:
            logger.error(f"Error determining AI bias: {e}")
            return "Neutral"
    
    def _format_key_levels(self, price_range: Dict[str, float]) -> str:
        """Format key price levels for display"""
        try:
            low_price = price_range.get('low', 0)
            high_price = price_range.get('high', 0)
            
            if low_price <= 0 or high_price <= 0:
                return "N/A"
            
            return f"${low_price:.2f} - ${high_price:.2f}"
            
        except Exception as e:
            logger.error(f"Error formatting key levels: {e}")
            return "N/A"
    
    def _format_strategy_text(self, analysis_summary: str, key_insights: List[str], confidence_level: float) -> str:
        """Format strategy text for display"""
        try:
            strategy_parts = []
            
            # Add confidence level
            confidence_text = f"Confidence: {confidence_level:.1%}"
            strategy_parts.append(confidence_text)
            
            # Add analysis summary (truncated if too long)
            if analysis_summary:
                summary_text = analysis_summary[:200] + "..." if len(analysis_summary) > 200 else analysis_summary
                strategy_parts.append(f"Analysis: {summary_text}")
            
            # Add key insights
            if key_insights:
                insights_text = "\n".join([f"• {insight}" for insight in key_insights[:3]])  # Limit to 3 insights
                strategy_parts.append(f"Key Insights:\n{insights_text}")
            
            return "\n\n".join(strategy_parts)
            
        except Exception as e:
            logger.error(f"Error formatting strategy text: {e}")
            return "Strategy analysis unavailable"
    
    def _format_alert_text(self, risk_assessment: str, key_insights: List[str]) -> str:
        """Format alert text for display"""
        try:
            alert_parts = []
            
            # Add risk assessment
            if risk_assessment:
                alert_parts.append(f"Risk Assessment:\n{risk_assessment}")
            
            # Add any high-priority insights as alerts
            high_priority_keywords = ['warning', 'caution', 'risk', 'danger', 'alert', 'critical']
            high_priority_insights = []
            
            for insight in key_insights:
                insight_lower = insight.lower()
                if any(keyword in insight_lower for keyword in high_priority_keywords):
                    high_priority_insights.append(f"⚠️ {insight}")
            
            if high_priority_insights:
                alert_parts.append("Alerts:\n" + "\n".join(high_priority_insights[:2]))  # Limit to 2 alerts
            
            if not alert_parts:
                alert_parts.append("No immediate alerts")
            
            return "\n\n".join(alert_parts)
            
        except Exception as e:
            logger.error(f"Error formatting alert text: {e}")
            return "Alert information unavailable"
    
    def on_ai_analysis_error(self, error_message: str):
        """Handle AI analysis errors"""
        logger.error(f"AI analysis error: {error_message}")
        # You can add UI notification here
    
    def on_ai_polling_status(self, status: str):
        """Handle AI polling status updates"""
        logger.info(f"AI polling status: {status}")
        # You can add UI status updates here
    
    def on_ai_cache_status(self, status: str):
        """Handle AI cache status updates"""
        logger.info(f"AI cache status: {status}")
        # You can add UI cache status updates here

    def show_ai_prompt_ui(self):
        """Show the AI prompt dialog"""
        if not hasattr(self, 'ai_prompt_ui') or self.ai_prompt_ui is None:
            logger.error("AI Prompt UI not available - attempting to reinitialize...")
            try:
                self.ai_prompt_ui = AI_Prompt_Form(self.config, self.refresh_ai)
                logger.info("AIPrompt_Form reinitialized successfully")
            except Exception as e:
                logger.error(f"Failed to reinitialize AIPrompt_Form: {e}")
                return
        self.ai_prompt_ui.exec()

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
            
            # Update data worker with new trading configuration
            if hasattr(self, 'data_worker') and self.data_worker:
                try:
                    # Get the updated trading configuration
                    updated_trading_config = {
                        "underlying_symbol": self.config.trading.get("underlying_symbol"),
                        "trade_delta": self.config.trading.get("trade_delta"),
                        "max_trade_value": self.config.trading.get("max_trade_value"),
                        "runner": self.config.trading.get("runner"),
                        "risk_levels": self.config.trading.get("risk_levels", [])
                    }
                    
                    # Update the data worker's trading configuration
                    self.data_worker.update_trading_config(updated_trading_config)
                    logger.info("Data worker trading configuration updated")
                except Exception as e:
                    logger.error(f"Error updating data worker trading configuration: {e}")
            
            # Close the settings dialog
            self.setting_ui.close()
            
            # Refresh main GUI with updated configuration
            self.refresh_main_gui_with_config()
            
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
        
        # Clear option information fields
        self.ui.label_strike_value.setText(f"---")
        self.ui.label_expiration_value.setText(f"---")
        self.ui.label_call_price_value.setText(f"---")
        self.ui.label_call_bid_value.setText(f"---")
        self.ui.label_call_ask_value.setText(f"---")
        self.ui.label_call_delta_value.setText(f"---")
        self.ui.label_call_gamma_value.setText(f"---")
        self.ui.label_call_theta_value.setText(f"---")
        self.ui.label_call_vega_value.setText(f"---")
        self.ui.label_call_openint_value.setText(f"---")
        self.ui.label_call_volume_value.setText(f"---")
        self.ui.label_put_price_value.setText(f"---")
        self.ui.label_put_bid_value.setText(f"---")
        self.ui.label_put_ask_value.setText(f"---")
        self.ui.label_put_delta_value.setText(f"---")
        self.ui.label_put_gamma_value.setText(f"---")
        self.ui.label_put_theta_value.setText(f"---")
        self.ui.label_put_vega_value.setText(f"---")
        self.ui.label_put_openint_value.setText(f"---")
        self.ui.label_put_volume_value.setText(f"---")
        self.ui.label_account_value_value.setText(f"---")
        self.ui.label_starting_value_value.setText(f"---")
        self.ui.label_high_water_value.setText(f"---")
        self.ui.label_daily_pl_value.setText(f"---")
        self.ui.label_daily_pl_percent_value.setText(f"---")
        
        
        self.ui.label_win_rate_value.setText(f"---")
        self.ui.label_total_trades_value.setText(f"---")
        self.ui.label_total_wins_count_value.setText(f"---")
        self.ui.label_total_losses_count_value.setText(f"---")
        self.ui.label_total_losses_sum_value.setText(f"---")
        self.ui.label_total_trades_value.setText(f"---")
        self.ui.label_total_wins_sum_value.setText(f"---")

    def refresh_main_gui_with_config(self):
        """Refresh the main GUI with current configuration values"""
        try:
            logger.info("Refreshing main GUI with updated configuration")
            
            # Update underlying symbol display
            if hasattr(self, 'config') and self.config and self.config.trading:
                underlying_symbol = self.config.trading.get('underlying_symbol', '---')
                self.ui.label_spy_name.setText(f"{underlying_symbol}")
                logger.info(f"Updated underlying symbol display to: {underlying_symbol}")
            
            # Clear other values that might be affected by symbol change
            self.ui.label_spy_value.setText(f"---")
            self.ui.label_symbol_value.setText(f"---")
            self.ui.label_quantity_value.setText(f"---")
            self.ui.label_pl_dollar_value.setText(f"---")
            self.ui.label_pl_percent_value.setText(f"---")
            
            # Clear option information fields that are affected by symbol change
            self.ui.label_strike_value.setText(f"---")
            self.ui.label_expiration_value.setText(f"---")
            self.ui.label_call_price_value.setText(f"---")
            self.ui.label_call_bid_value.setText(f"---")
            self.ui.label_call_ask_value.setText(f"---")
            self.ui.label_call_delta_value.setText(f"---")
            self.ui.label_call_gamma_value.setText(f"---")
            self.ui.label_call_theta_value.setText(f"---")
            self.ui.label_call_vega_value.setText(f"---")
            self.ui.label_call_openint_value.setText(f"---")
            self.ui.label_call_volume_value.setText(f"---")
            self.ui.label_put_price_value.setText(f"---")
            self.ui.label_put_bid_value.setText(f"---")
            self.ui.label_put_ask_value.setText(f"---")
            self.ui.label_put_delta_value.setText(f"---")
            self.ui.label_put_gamma_value.setText(f"---")
            self.ui.label_put_theta_value.setText(f"---")
            self.ui.label_put_vega_value.setText(f"---")
            self.ui.label_put_openint_value.setText(f"---")
            self.ui.label_put_volume_value.setText(f"---")
                        
            logger.info("Main GUI refreshed successfully")
            
        except Exception as e:
            logger.error(f"Error refreshing main GUI: {e}")

    def on_trading_config_updated(self, config_data: dict):
        """Handle trading configuration updates from data worker"""
        try:
            logger.info(f"Trading configuration update received: {config_data}")
            
            # Update the underlying symbol display
            underlying_symbol = config_data.get('underlying_symbol', '---')
            self.ui.label_spy_name.setText(f"{underlying_symbol}")
            
            # Clear values that are affected by symbol change
            self.ui.label_spy_value.setText(f"---")
            self.ui.label_symbol_value.setText(f"---")
            self.ui.label_quantity_value.setText(f"---")
            self.ui.label_pl_dollar_value.setText(f"---")
            self.ui.label_pl_percent_value.setText(f"---")
            
            # Clear option information fields that are affected by symbol change
            self.ui.label_strike_value.setText(f"---")
            self.ui.label_expiration_value.setText(f"---")
            
            logger.info(f"Main GUI updated with new underlying symbol: {underlying_symbol}")
            
        except Exception as e:
            logger.error(f"Error handling trading configuration update: {e}")

    def reload_configuration(self):
        """Reload configuration from file and update data worker"""
        try:
            logger.info("Reloading configuration from file")
            
            # Reload configuration from file
            self.config = AppConfig.load_from_file()
            
            # Update data worker with new configuration
            if hasattr(self, 'data_worker') and self.data_worker:
                # Update trading configuration
                if self.config and self.config.trading:
                    self.data_worker.update_trading_config(self.config.trading)
                    logger.info("Data worker updated with reloaded configuration")
            
            # Refresh main GUI
            self.refresh_main_gui_with_config()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")


    def update_calls_option(self, calls_data: Dict[str, Any]):
        try:
            # print(f"UI Calls Data: {calls_data}")
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
            # print(f"UI Puts Data: {puts_data}")
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
                high_water_mark = account_data.get('HighWaterMark', '---')

                self.ui.label_account_value_value.setText(f"${account_value}")
                self.ui.label_starting_value_value.setText(f"${starting_value}")
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
                tmp_expiration = option_primary_data["Expiration"][0]
                # Convert string format "20250810" to datetime then format as "2025-08-10"
                if isinstance(tmp_expiration, str) and len(tmp_expiration) == 8:
                    tmp_expiration = datetime.strptime(tmp_expiration, "%Y%m%d").strftime("%Y-%m-%d")

                self.ui.label_strike_value.setText(f'{option_primary_data["Strike"][0]}')
                self.ui.label_expiration_value.setText(f'{tmp_expiration}')

            # Update statistics
            statistics = data.get('statistics')
            if statistics is not None and not statistics.empty:
                stats = statistics.iloc[0]
                win_rate = stats.get('Win_Rate', 0)
                self.ui.label_win_rate_value.setText(f"{win_rate:.2f}%")
                self.ui.label_total_trades_value.setText(f"{stats.get('Total_Trades', 0)}")
                self.ui.label_total_wins_count_value.setText(f"{stats.get('Total_Wins_Count', 0)}")
                self.ui.label_total_losses_count_value.setText(f"{stats.get('Total_Losses_Count', 0)}")
                self.ui.label_total_losses_sum_value.setText(f"-${stats.get('Total_Losses_Sum', 0):.2f}")
                self.ui.label_total_wins_sum_value.setText(f"${stats.get('Total_Wins_Sum', 0):.2f}")
                logger.info(f"Win rate: {win_rate:.2f}%")
                
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
                
                # Check if price-triggered AI analysis should be performed
                if (hasattr(self, 'ai_engine') and self.ai_engine and 
                    self.config.ai_prompt.get("enable_price_triggered_polling", True)):
                    self._check_price_triggered_analysis(price)
                    
        except Exception as e:
            logger.error(f"Error updating real-time price: {e}")
    
    def _check_price_triggered_analysis(self, current_price: float):
        """Check if price movement warrants AI analysis"""
        try:
            if not hasattr(self, 'last_ai_analysis') or not self.last_ai_analysis:
                return
            
            price_range = self.last_ai_analysis.get('valid_price_range', {})
            low = price_range.get('low', 0)
            high = price_range.get('high', float('inf'))
            
            # If price is outside the valid range, trigger analysis
            if current_price < low or current_price > high:
                logger.info(f"Price ${current_price:.2f} outside AI range [${low:.2f}, ${high:.2f}] - triggering analysis")
                if self.ai_engine:
                    import asyncio
                    asyncio.create_task(self.ai_engine.analyze_market_data())
                    
        except Exception as e:
            logger.error(f"Error checking price-triggered analysis: {e}")
    
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

    def update_daily_pnl_updated(self, daily_pnl_data: Dict[str, Any]):
        try:
            # logger.info(f"Updating daily PNL update: {daily_pnl_data}")
            daily_pnl_price = daily_pnl_data.get('daily_pnl_price', 0)
            daily_pnl_percent = daily_pnl_data.get('daily_pnl_percent', 0)
            self.ui.label_daily_pl_value.setText(f"${daily_pnl_price:.2f}")
            self.ui.label_daily_pl_percent_value.setText(f"{daily_pnl_percent:.4f}%")
            logger.info(f"GUI updated Daily pnl price : {daily_pnl_price}   Percent: {daily_pnl_percent}%")

        except Exception as e:
            logger.error(f"Error updating Daily Pnl rate: {e}")

    def update_account_summary(self, account_summary: Dict[str, Any]):
        try:
            self.ui.label_account_value_value.setText(f"${account_summary['NetLiquidation']:.2f}")
            self.ui.label_starting_value_value.setText(f"${account_summary['StartingValue']:.2f}")
            self.ui.label_high_water_value.setText(f"${account_summary['HighWaterMark']:.2f}")

        except Exception as e:
            logger.error(f"Error updating Daily Pnl rate: {e}")
            
    def update_active_contracts_pnl(self, active_contracts_pnl: Dict[str, Any]):
        try:
            logger.info(f"Updating active contracts PNL: {active_contracts_pnl}")
            self.ui.label_pl_percent_value.setText(f"{active_contracts_pnl['pnl_percent']:.2f}%")
            self.ui.label_pl_dollar_value.setText(f"{active_contracts_pnl['pnl_dollar']:.2f}$")
        except Exception as e:
            logger.error(f"Error updating active contracts PNL: {e}")

    def update_closed_trades(self, stats: Dict[str, Any]):
        try:
            logger.info(f"Updating closed trades: {stats}")
            self.ui.label_total_trades_value.setText(f"{stats['Total_Trades']}")
            self.ui.label_total_wins_count_value.setText(f"{stats['Total_Wins_Count']}")
            self.ui.label_total_losses_count_value.setText(f"{stats['Total_Losses_Count']}")
            self.ui.label_total_losses_sum_value.setText(f"-${stats['Total_Losses_Sum']:.2f}")
            self.ui.label_total_wins_sum_value.setText(f"${stats['Total_Wins_Sum']:.2f}")
        except Exception as e:
            logger.error(f"Error updating closed trades: {e}")

    def refresh_ui(self):
        """Refresh UI elements that need frequent updates"""
        # Update the time label with current time
        current_time = datetime.now().strftime("%I:%M:%S %p")
        if hasattr(self.ui, 'label_time'):
            self.ui.label_time.setText(current_time)
    
    def keyPressEvent(self, event):
        """Handle key press events for hotkey detection"""
        try:
            # Forward key events to hotkey manager if available
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
                self.hotkey_manager.keyPressEvent(event)
                if event.isAccepted():
                    return
            
            # Let other key events pass through
            event.ignore()
            
        except Exception as e:
            logger.error(f"Error in keyPressEvent: {e}")
            event.ignore()
    
    def closeEvent(self, event):
        """Handle application shutdown"""
        try:
            # Stop AI engine
            if hasattr(self, 'ai_engine') and self.ai_engine:
                try:
                    self.ai_engine.cleanup()
                except Exception as e:
                    logger.error(f"Error stopping AI engine: {e}")
            
            # Stop hotkey manager
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
                try:
                    self.hotkey_manager.stop()
                except Exception as e:
                    logger.error(f"Error stopping hotkey manager: {e}")
            
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

    def show_expiration_status(self):
        """Show the current expiration status and available expirations"""
        try:
            if hasattr(self, 'data_worker') and self.data_worker:
                if hasattr(self.data_worker, 'collector') and self.data_worker.collector:
                    if hasattr(self.data_worker.collector, 'trading_manager'):
                        trading_manager = self.data_worker.collector.trading_manager
                        if hasattr(trading_manager, 'get_expiration_status'):
                            status = trading_manager.get_expiration_status()
                            
                            if 'error' in status:
                                QMessageBox.warning(
                                    self,
                                    "Expiration Status Error",
                                    f"Could not retrieve expiration status: {status['error']}"
                                )
                                return
                            
                            # Format status message
                            message = f"""Expiration Status:
                            
Current Expiration: {status.get('current_expiration', 'N/A')}
Type: {status.get('current_expiration_type', 'N/A')}
Available Expirations: {status.get('available_expirations_count', 0)}
Next Recommended: {status.get('next_recommended_expiration', 'N/A')}
Should Switch: {status.get('should_switch', False)}
Current Time (EST): {status.get('current_time_est', 'N/A')}"""
                            
                            # Add expiration analysis if available
                            if 'expiration_analysis' in status:
                                message += "\n\nExpiration Analysis:"
                                for exp in status['expiration_analysis'][:5]:  # Show first 5
                                    current_marker = " (CURRENT)" if exp.get('is_current', False) else ""
                                    message += f"\n• {exp.get('expiration', 'N/A')} - {exp.get('type', 'N/A')} - {exp.get('days_diff', 'N/A')} days{current_marker}"
                            
                            QMessageBox.information(
                                self,
                                "Expiration Status",
                                message
                            )
                        else:
                            QMessageBox.warning(
                                self,
                                "Expiration Status",
                                "Trading manager doesn't support expiration status retrieval"
                            )
                    else:
                        QMessageBox.warning(
                            self,
                            "Expiration Status",
                            "No trading manager available"
                        )
                else:
                    QMessageBox.warning(
                        self,
                        "Expiration Status",
                        "No collector available"
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Expiration Status",
                    "No data worker available"
                )
                
        except Exception as e:
            logger.error(f"Error showing expiration status: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to show expiration status: {str(e)}"
            )
    
    def manual_expiration_switch(self):
        """Manually trigger expiration switching"""
        try:
            if hasattr(self, 'data_worker') and self.data_worker:
                if hasattr(self.data_worker, 'collector') and self.data_worker.collector:
                    if hasattr(self.data_worker.collector, 'trading_manager'):
                        trading_manager = self.data_worker.collector.trading_manager
                        if hasattr(trading_manager, 'manual_expiration_switch'):
                            # Get current status first
                            status = trading_manager.get_expiration_status()
                            if 'error' in status:
                                QMessageBox.warning(
                                    self,
                                    "Manual Switch Error",
                                    f"Could not get current status: {status['error']}"
                                )
                                return
                            
                            # Show current status and ask for confirmation
                            current_exp = status.get('current_expiration', 'N/A')
                            next_exp = status.get('next_recommended_expiration', 'N/A')
                            
                            if next_exp and next_exp != current_exp:
                                reply = QMessageBox.question(
                                    self,
                                    "Manual Expiration Switch",
                                    f"Current expiration: {current_exp}\n"
                                    f"Recommended next: {next_exp}\n\n"
                                    f"Switch to recommended expiration?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                )
                                
                                if reply == QMessageBox.StandardButton.Yes:
                                    success = trading_manager.manual_expiration_switch(next_exp)
                                    if success:
                                        QMessageBox.information(
                                            self,
                                            "Switch Successful",
                                            f"Successfully switched to {next_exp}"
                                        )
                                        # Refresh the display
                                        self.refresh_ui()
                                    else:
                                        QMessageBox.warning(
                                            self,
                                            "Switch Failed",
                                            "Failed to switch expiration. Check logs for details."
                                        )
                            else:
                                QMessageBox.information(
                                    self,
                                    "No Switch Needed",
                                    f"Current expiration {current_exp} is already optimal or no better expiration available."
                                )
                        else:
                            QMessageBox.warning(
                                self,
                                "Manual Switch",
                                "Trading manager doesn't support manual expiration switching"
                            )
                    else:
                        QMessageBox.warning(
                            self,
                            "Manual Switch",
                            "No trading manager available"
                        )
                else:
                    QMessageBox.warning(
                        self,
                        "Manual Switch",
                        "No collector available"
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Manual Switch",
                    "No data worker available"
                )
                
        except Exception as e:
            logger.error(f"Error in manual expiration switch: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to perform manual expiration switch: {str(e)}"
            )

