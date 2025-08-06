import sys
import asyncio
import logging
from PyQt5.QtWidgets import QApplication

from widgets.ib_trading_app import IB_Trading_APP

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
