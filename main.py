import sys
import asyncio
from PyQt6.QtWidgets import QApplication

from widgets.ib_trading_app import IB_Trading_APP
from utils.config_manager import AppConfig
from utils.logger import initialize_logger_manager, get_logger

# Initialize configuration and logging system
config = AppConfig.load_from_file()
initialize_logger_manager(config)

# Get logger for main module
logger = get_logger("MAIN")



def main():
    """Main application entry point"""
    # Set up asyncio policy for Windows
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        logger.info("Starting IB Trading Application")
        
        app = QApplication(sys.argv)
        
        # Create and show main window
        main_window = IB_Trading_APP()
        main_window.show()
        
        logger.info("IB Trading Application GUI initialized successfully")
        
        # Run the application
        sys.exit(app.exec())
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error during application startup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
