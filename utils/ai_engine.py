from utils.config_manager import AppConfig
import logging

logger = logging.getLogger(__name__)

class AI_Engine:
    def __init__(self, config: AppConfig):
        self.config = config
    
    def refresh(self):
        """Refresh the AI engine"""
        self.config = AppConfig.load_from_file()

    def get_ai_prompt(self):
        return self.config.ai_prompt["prompt"]
    
    def get_ai_context(self):
        return self.config.ai_prompt["context"]
    
    def set_ai_prompt(self, prompt: str):
        self.config.ai_prompt["prompt"] = prompt
    
    def set_ai_context(self, context: str):
        self.config.ai_prompt["context"] = context
    
    def get_ai_response(self, prompt: str):
        return self.get_ai_prompt() + prompt
    
    def get_ai_response_with_context(self, prompt: str):
        return self.get_ai_prompt() + self.get_ai_context() + prompt
    
    def get_ai_response_with_context_and_prompt(self, prompt: str):
        return self.config.ai_prompt["prompt"] + self.config.ai_prompt["context"] + prompt