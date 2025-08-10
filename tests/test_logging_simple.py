import logging
import sys
from datetime import datetime

# Set up logging with more verbose configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_logging.log')
    ]
)
logger = logging.getLogger(__name__)

# Ensure we can see all logging output
logging.getLogger().setLevel(logging.INFO)

def test_logging():
    """Simple test function to demonstrate logging works"""
    logger.info("=== LOGGING TEST STARTED ===")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.debug("This is a DEBUG message (should not show with INFO level)")
    
    # Test with different logger names
    test_logger = logging.getLogger("test_module")
    test_logger.info("This is from test_module logger")
    
    # Test with data
    data = {"price": 100.50, "symbol": "SPY", "timestamp": datetime.now().isoformat()}
    logger.info(f"Market data received: {data}")
    
    logger.info("=== LOGGING TEST COMPLETED ===")

if __name__ == "__main__":
    print("Starting logging test...")
    test_logging()
    print("Logging test finished. Check the output above and the 'test_logging.log' file.")
