from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QCheckBox, QGroupBox, QTextEdit, QPushButton, QMessageBox, QSpacerItem, QSizePolicy
from PyQt6.QtCore import Qt, QTimer
from PyQt6 import QtWidgets
from utils.config_manager import AppConfig
from ui.ai_prompt_gui import Ui_AiPromptPanel
from utils.smart_logger import get_logger

logger = get_logger("AI_PROMPT")

class AIPrompt_Form(QDialog):
    def __init__(self, config: AppConfig = None):
        super().__init__()
        self.ui = Ui_AiPromptPanel()
        self.ui.setupUi(self)
        self.config = config
        if self.config:
            self.load_config_values()
        else:
            # Create a default config if none provided
            from utils.config_manager import AppConfig
            self.config = AppConfig()
            self.config.save_to_file()
        
        # Initialize polling timer
        self.polling_timer = QTimer()
        self.polling_timer.timeout.connect(self.execute_auto_polling)
        
        # Create additional UI elements for new configuration options
        self._create_advanced_ui()
        
        self.ui.outputArea.textChanged.connect(self.on_prompt_input_changed)
        self.ui.submitBtn.clicked.connect(self.save_config_values)
        
        # Connect polling checkbox to start/stop polling
        if hasattr(self, 'enable_polling_checkbox'):
            self.enable_polling_checkbox.toggled.connect(self.on_polling_toggled)
            self.interval_spinbox.valueChanged.connect(self.on_interval_changed)
        
        # Start polling if it was enabled in config
        self.start_polling_if_enabled()
    
    def start_polling_if_enabled(self):
        """Start polling if it was enabled in the configuration"""
        try:
            if hasattr(self, 'enable_polling_checkbox') and self.enable_polling_checkbox.isChecked():
                self.start_polling()
        except Exception as e:
            logger.error(f"Error starting polling: {e}")
    
    def on_polling_toggled(self, checked):
        """Handle polling checkbox toggle"""
        try:
            if checked:
                self.start_polling()
                logger.info("Auto polling started")
            else:
                self.stop_polling()
                logger.info("Auto polling stopped")
        except Exception as e:
            logger.error(f"Error toggling polling: {e}")
    
    def on_interval_changed(self, value):
        """Handle polling interval change"""
        try:
            if self.polling_timer.isActive():
                self.start_polling()  # Restart with new interval
                logger.info(f"Polling interval updated to {value} minutes")
        except Exception as e:
            logger.error(f"Error updating polling interval: {e}")
    
    def start_polling(self):
        """Start the polling timer"""
        try:
            if hasattr(self, 'interval_spinbox'):
                interval_minutes = self.interval_spinbox.value()
                interval_ms = interval_minutes * 60 * 1000  # Convert to milliseconds
                
                self.polling_timer.stop()
                self.polling_timer.start(interval_ms)
                logger.info(f"Polling timer started with {interval_minutes} minute interval")
        except Exception as e:
            logger.error(f"Error starting polling timer: {e}")
    
    def stop_polling(self):
        """Stop the polling timer"""
        try:
            self.polling_timer.stop()
            logger.info("Polling timer stopped")
        except Exception as e:
            logger.error(f"Error stopping polling timer: {e}")
    
    def execute_auto_polling(self):
        """Execute the automatic polling when timer triggers"""
        try:
            logger.info("Executing auto polling...")
            
            # Get the current prompt from the UI
            current_prompt = self.ui.outputArea.toPlainText()
            if not current_prompt.strip():
                logger.warning("No prompt configured for auto polling")
                return
            
            # Create AI engine and execute the prompt
            from utils.ai_engine import AI_Engine
            ai_engine = AI_Engine(self.config)
            
            # Execute the prompt (you may need to adjust this based on your AI engine implementation)
            if hasattr(ai_engine, 'execute_prompt'):
                result = ai_engine.execute_prompt(current_prompt)
                logger.info(f"Auto polling executed successfully: {result}")
            else:
                logger.warning("AI engine does not have execute_prompt method")
                
        except Exception as e:
            logger.error(f"Error executing auto polling: {e}")
    
    def closeEvent(self, event):
        """Handle dialog close event to stop polling"""
        try:
            self.stop_polling()
            event.accept()
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
            event.accept()
    
    def _create_advanced_ui(self):
        """Create additional UI elements for advanced AI configuration"""
        try:
            logger.info("Creating advanced UI...")
            # Create a scroll area or additional widgets for advanced settings
            # For now, we'll add them to the existing layout
            main_layout = self.ui.verticalLayout
            logger.info(f"Main layout: {main_layout}")
            
            # Add some spacing before advanced UI
            spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            main_layout.addItem(spacer)
            logger.info("Added spacer")
            
            # API Configuration Group
            api_group = QGroupBox("Gemini API Configuration")
            api_layout = QVBoxLayout()
            
            # API Key input
            api_key_layout = QHBoxLayout()
            api_key_label = QLabel("API Key:")
            self.api_key_input = QLineEdit()
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            api_key_layout.addWidget(api_key_label)
            api_key_layout.addWidget(self.api_key_input)
            api_layout.addLayout(api_key_layout)
            
            api_group.setLayout(api_layout)
            main_layout.addWidget(api_group)
            logger.info("Added API configuration group")
            
            # Polling Configuration Group
            polling_group = QGroupBox("Polling Configuration")
            polling_layout = QVBoxLayout()
            
            # Enable auto polling
            self.enable_polling_checkbox = QCheckBox("Enable Auto Polling")
            polling_layout.addWidget(self.enable_polling_checkbox)
            
            # Polling interval
            interval_layout = QHBoxLayout()
            interval_label = QLabel("Polling Interval (minutes):")
            self.interval_spinbox = QSpinBox()
            self.interval_spinbox.setRange(1, 60)
            self.interval_spinbox.setValue(10)
            interval_layout.addWidget(interval_label)
            interval_layout.addWidget(self.interval_spinbox)
            polling_layout.addLayout(interval_layout)
            
            # Enable price-triggered polling
            self.enable_price_trigger_checkbox = QCheckBox("Enable Price-Triggered Polling")
            polling_layout.addWidget(self.enable_price_trigger_checkbox)
            
            # Cache duration
            cache_layout = QHBoxLayout()
            cache_label = QLabel("Cache Duration (minutes):")
            self.cache_spinbox = QSpinBox()
            self.cache_spinbox.setRange(1, 120)
            self.cache_spinbox.setValue(15)
            cache_layout.addWidget(cache_label)
            cache_layout.addWidget(self.cache_spinbox)
            polling_layout.addLayout(cache_layout)
            
            # Historical data days
            history_layout = QHBoxLayout()
            history_label = QLabel("Historical Data Days:")
            self.history_spinbox = QSpinBox()
            self.history_spinbox.setRange(1, 90)
            self.history_spinbox.setValue(30)
            history_layout.addWidget(history_label)
            history_layout.addWidget(self.history_spinbox)
            polling_layout.addLayout(history_layout)
            
            polling_group.setLayout(polling_layout)
            main_layout.addWidget(polling_group)
            logger.info("Added polling configuration group")
            
            # Test AI Connection Button
            test_button = QPushButton("Test AI Connection")
            test_button.clicked.connect(self.test_ai_connection)
            main_layout.addWidget(test_button)
            logger.info("Added test button")
            
            # Resize the dialog to accommodate all widgets
            self.resize(500, 600)
            logger.info("Advanced UI creation completed successfully")
            
            # Verify widgets were created
            self._verify_advanced_ui()
            
        except Exception as e:
            logger.error(f"Error creating advanced UI: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _verify_advanced_ui(self):
        """Verify that advanced UI widgets were created and are visible"""
        try:
            widgets_to_check = [
                ('api_key_input', 'API Key Input'),
                ('enable_polling_checkbox', 'Enable Polling Checkbox'),
                ('interval_spinbox', 'Interval Spinbox'),
                ('enable_price_trigger_checkbox', 'Price Trigger Checkbox'),
                ('cache_spinbox', 'Cache Spinbox'),
                ('history_spinbox', 'History Spinbox')
            ]
            
            for attr_name, display_name in widgets_to_check:
                if hasattr(self, attr_name):
                    widget = getattr(self, attr_name)
                    logger.info(f"{display_name}: {widget} - Visible: {widget.isVisible()}")
                else:
                    logger.warning(f"{display_name}: Not found")
                    
        except Exception as e:
            logger.error(f"Error verifying advanced UI: {e}")
    
    def test_ai_connection(self):
        """Test the AI connection with current settings"""
        try:
            from utils.ai_engine import AI_Engine
            
            # Create a temporary AI engine to test connection
            temp_engine = AI_Engine(self.config)
            
            if temp_engine.gemini_client:
                QMessageBox.information(self, "Connection Test", "Gemini API connection successful!")
            else:
                QMessageBox.warning(self, "Connection Test", "Gemini API not configured. Please enter a valid API key.")
                
        except Exception as e:
            logger.error(f"Error testing AI connection: {e}")
            QMessageBox.critical(self, "Connection Test", f"Connection test failed: {str(e)}")
    
    def load_config_values(self):
        """Load configuration values into the UI"""
        try:
            # Load basic prompt
            self.ui.outputArea.setPlainText(self.config.ai_prompt.get("prompt", "You are a helpful assistant that can answer questions and help with tasks."))
            
            # Load advanced settings
            if hasattr(self, 'api_key_input'):
                self.api_key_input.setText(self.config.ai_prompt.get("gemini_api_key", ""))
            
            if hasattr(self, 'enable_polling_checkbox'):
                self.enable_polling_checkbox.setChecked(self.config.ai_prompt.get("enable_auto_polling", True))
            
            if hasattr(self, 'interval_spinbox'):
                self.interval_spinbox.setValue(self.config.ai_prompt.get("polling_interval_minutes", 10))
            
            if hasattr(self, 'enable_price_trigger_checkbox'):
                self.enable_price_trigger_checkbox.setChecked(self.config.ai_prompt.get("enable_price_triggered_polling", True))
            
            if hasattr(self, 'cache_spinbox'):
                self.cache_spinbox.setValue(self.config.ai_prompt.get("cache_duration_minutes", 15))
            
            if hasattr(self, 'history_spinbox'):
                self.history_spinbox.setValue(self.config.ai_prompt.get("max_historical_days", 30))
                
        except Exception as e:
            logger.error(f"Error loading configuration values: {e}")
    
    def save_config_values(self):
        """Save configuration values from the UI"""
        try:
            # Save basic prompt
            self.config.ai_prompt["prompt"] = self.ui.outputArea.toPlainText()
            
            # Save advanced settings
            if hasattr(self, 'api_key_input'):
                self.config.ai_prompt["gemini_api_key"] = self.api_key_input.text()
            
            if hasattr(self, 'enable_polling_checkbox'):
                self.config.ai_prompt["enable_auto_polling"] = self.enable_polling_checkbox.isChecked()
            
            if hasattr(self, 'interval_spinbox'):
                self.config.ai_prompt["polling_interval_minutes"] = self.interval_spinbox.value()
            
            if hasattr(self, 'enable_price_trigger_checkbox'):
                self.config.ai_prompt["enable_price_triggered_polling"] = self.enable_price_trigger_checkbox.isChecked()
            
            if hasattr(self, 'cache_spinbox'):
                self.config.ai_prompt["cache_duration_minutes"] = self.cache_spinbox.value()
            
            if hasattr(self, 'history_spinbox'):
                self.config.ai_prompt["max_historical_days"] = self.history_spinbox.value()
            
            self.config.save_to_file()
            logger.info("AI prompt configuration saved successfully")
            
            # Update polling based on saved configuration
            if hasattr(self, 'enable_polling_checkbox'):
                if self.enable_polling_checkbox.isChecked():
                    self.start_polling()
                else:
                    self.stop_polling()
            
        except Exception as e:
            logger.error(f"Error saving configuration values: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
        
        self.close()
    
    def on_prompt_input_changed(self):
        """Handle prompt input changes"""
        self.config.ai_prompt["prompt"] = self.ui.outputArea.toPlainText()
        self.config.save_to_file()