from PyQt5.QtWidgets import QDialog
from PyQt5 import QtWidgets
from utils.config_manager import AppConfig
from ui.ai_prompt_gui import Ui_AiPromptPanel
import logging

logger = logging.getLogger(__name__)

class AIPrompt_Form(QDialog):
    def __init__(self, config: AppConfig = None):
        super().__init__()
        self.ui = Ui_AiPromptPanel()
        self.ui.setupUi(self)
        self.config = config
        if self.config:
            self.load_config_values()
        else:
            self.config.ai_prompt["prompt"] = "You are a helpful assistant that can answer questions and help with tasks."
            self.config.save_to_file()
            
        self.ui.outputArea.textChanged.connect(self.on_prompt_input_changed)
        self.ui.submitBtn.clicked.connect(self.save_config_values)
    
    def load_config_values(self):
        """Load configuration values into the UI"""
        try:
            self.ui.outputArea.setPlainText(self.config.ai_prompt.get("prompt", "You are a helpful assistant that can answer questions and help with tasks."))
        except Exception as e:
            logger.error(f"Error loading configuration values: {e}")
    
    def save_config_values(self):
        """Save configuration values from the UI"""
        try:
            self.config.ai_prompt["prompt"] = self.ui.outputArea.toPlainText()
            self.config.save_to_file()
        except Exception as e:
            logger.error(f"Error saving configuration values: {e}")
        
        self.close()
    
    def on_prompt_input_changed(self):
        """Handle prompt input changes"""
        self.config.ai_prompt["prompt"] = self.ui.outputArea.toPlainText()
        self.config.save_to_file()