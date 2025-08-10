from ib_async import *
from math import isnan
from ib_async import IB, Contract, Order, Trade, Ticker, Stock, Option, Forex
from typing import Dict, List, Optional, Any, Union, Callable
import asyncio
from datetime import datetime
import logging
import sys

# Set up logging with more verbose configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ib_data_collector.log')
    ]
)
logger = logging.getLogger(__name__)

# Ensure we can see all logging output
logging.getLogger().setLevel(logging.INFO)

# 1. Connect to TWS or IB Gateway
# Note: Connection will be handled asynchronously in the IBDataCollector class


class IBDataCollector:
    """
    Improved IB Data Collector with better error handling and resource management
    """

    def __init__(self, host='127.0.0.1', port=7497, clientId=3, timeout=30):
        self.ib = IB()
        self.host = host
        self.port = port
        self.clientId = clientId
        self.timeout = timeout
        self.spy_price = 0
        self.current_spy_price = 0  # Added missing variable
        self.fx_ratio = 0.0
        self._active_subscriptions = set()  # Track active market data subscriptions
        self._active_contracts = {}  # Added missing variable
        self.event_bus = None  # Added missing variable - you'll need to implement this
        self.underlying_symbol = 'IBKR'  # Added missing config
        self.underlying_price = 0  # Added missing variable
        self.options_chain: List[Dict[str, Any]] = []
        self.initial_data = {
            'contract': {
                'symbol': 'SPY',
                'secType': 'OPT',
                'exchange': 'SMART',
                'currency': 'USD'
            }
        }
        self._market_data_subscriptions: Dict[int, Dict[str, Any]] = {}

        # Don't call async method from __init__
        # Instead, provide a separate initialization method
        self._initialized = False

        # Add logging to show the class is being instantiated
        logger.info("IBDataCollector instance created")

    async def initialize(self):
        """Async initialization method to set up market data subscriptions"""
        try:
            logger.info("Starting IBDataCollector initialization...")

            # Connect to IB if not already connected
            if not self.ib.isConnected():
                logger.info(f"Connecting to IB at {self.host}:{self.port}...")
                try:
                    await self.ib.connectAsync(self.host, self.port, self.clientId, timeout=self.timeout)
                    logger.info("Connected to IB successfully")
                except Exception as conn_error:
                    logger.error(f"Failed to connect to IB: {conn_error}")
                    raise ConnectionError(f"Cannot connect to IB TWS/Gateway at {self.host}:{self.port}. "
                                        f"Make sure TWS or IB Gateway is running and API connections are enabled. "
                                        f"Error: {conn_error}")
            else:
                logger.info("Already connected to IB")

            # Subscribe to initial market data
            logger.info("Subscribing to initial market data...")
            await self._handle_subscribe_market_data(self.initial_data)
            self._initialized = True
            logger.info("IBDataCollector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize IBDataCollector: {e}")
            raise

    async def _handle_subscribe_market_data(self, data: Dict):

        if not isinstance(data, dict):
            data = {}
        contract = self._create_contract_from_data(data.get('contract', data))
        if not contract:
            raise ValueError(f"Could not create contract from data: {data}")

        # Qualify with IB to get complete contract details
        logger.info("Qualifying contract with IB...")
        qualified_contracts = await self.ib.qualifyContractsAsync(contract)
        if not qualified_contracts or qualified_contracts[0] is None:
            raise ValueError(f"Could not qualify contract: {contract}")

        qualified_contract = qualified_contracts[0]
        con_id = qualified_contract.conId
        logger.info(f"Contract qualified successfully. ConId: {con_id}")

        # Check for existing subscription (deduplication)
        if con_id in self._market_data_subscriptions:
            logger.info(f"Already subscribed to market data for {qualified_contract.localSymbol}")
            return

        # Subscribe to market data stream
        logger.info("Requesting market data...")
        ticker = self.ib.reqMktData(qualified_contract, '', False, False)

        # Store subscription details for management
        self._market_data_subscriptions[con_id] = {
            'contract': qualified_contract,
            'ticker': ticker,
            'subscription_time': datetime.now()
        }
        self._on_market_data_tick(ticker)
        # Connect tick event handler for real-time updates
        # ticker.updateEvent.connect(lambda t=ticker: self._on_market_data_tick(t))

        logger.info(f"Subscribed to market data for {qualified_contract.localSymbol}")
        return {
            'contract': self._contract_to_dict(qualified_contract),  # Fixed util.tree
            'con_id': con_id
        }

    def _contract_to_dict(self, contract):
        """Convert contract to dictionary representation"""
        return {
            'symbol': getattr(contract, 'symbol', ''),
            'secType': getattr(contract, 'secType', ''),
            'exchange': getattr(contract, 'exchange', ''),
            'currency': getattr(contract, 'currency', ''),
            'conId': getattr(contract, 'conId', ''),
            'localSymbol': getattr(contract, 'localSymbol', '')
        }

    def _create_contract_from_data(self, contract_data: Dict) -> Optional[Contract]:
        """
        Create IB contract from dictionary data with comprehensive type support.

        OPTIMIZATION: This unified method replaces multiple contract creation patterns
        throughout the original codebase, eliminating duplication.

        Supported Contract Types:

        # Stock (STK)
        {'symbol': 'AAPL', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'}

        # Option (OPT)
        {'symbol': 'SPY', 'secType': 'OPT', 'strike': 580, 'right': 'P',
         'lastTradeDateOrContractMonth': '20241220', 'exchange': 'SMART'}

        # Forex (CASH)
        {'symbol': 'EURUSD', 'secType': 'CASH', 'exchange': 'IDEALPRO'}

        # Generic (any secType)
        {'symbol': 'ES', 'secType': 'FUT', 'exchange': 'GLOBEX', ...}

        Returns: IB Contract object or None if creation fails
        """
        try:
            sec_type = contract_data.get('secType', 'STK').upper()

            # Stock contracts
            if sec_type == 'STK':
                logger.info("Section Type is STK")
                return Stock(
                    symbol=contract_data.get('symbol', ''),
                    exchange=contract_data.get('exchange', 'SMART'),
                    currency=contract_data.get('currency', 'USD')
                )
            # Option contracts
            elif sec_type == 'OPT':
                logger.info("Section Type is OPT")
                return Option(
                    symbol=contract_data.get('symbol', ''),
                    lastTradeDateOrContractMonth=contract_data.get('lastTradeDateOrContractMonth', ''),
                    strike=contract_data.get('strike', 0),
                    right=contract_data.get('right', 'C'),
                    exchange=contract_data.get('exchange', 'SMART'),
                    currency=contract_data.get('currency', 'USD')
                )
            # Forex contracts
            elif sec_type == 'CASH':
                logger.info("Section Type is CASH")
                return Forex(
                    pair=contract_data.get('symbol', ''),  # Forex uses 'pair' in ib_async >= 1.0
                    exchange=contract_data.get('exchange', 'IDEALPRO')
                )
            # Generic contracts (futures, bonds, etc.)
            else:
                contract = Contract()
                for key, value in contract_data.items():
                    if hasattr(contract, key):
                        setattr(contract, key, value)
                return contract

        except Exception as e:
            logger.error(f"Error creating contract from data: {e}", exc_info=True)
            return None

    def _on_market_data_tick(self, ticker: Ticker):
        """Enhanced market data callback with comprehensive tick processing."""
        try:
            logging.info("Start market data tick")
            # Update active contracts with current prices
            if hasattr(ticker, 'contract') and ticker.contract:
                contract = ticker.contract
                # Fixed util.isNan to use math.isnan
                last_price = ticker.last if ticker.last and not isnan(ticker.last) else ticker.close
                logging.info(f"last price: {last_price}")
                # Store current price for external access
                if contract.symbol == 'SPY' and last_price and last_price > 0:
                    self.current_spy_price = last_price
                    logger.info(f"SPY price updated: {last_price}")

                for contract_key, active_contract in self._active_contracts.items():
                    if (getattr(active_contract.contract, 'conId', None) == getattr(contract, 'conId', None) and
                            last_price and last_price > 0):
                        active_contract.current_price = last_price

            # Log tick data for debugging
            tick_data = {
                'contract': self._contract_to_dict(ticker.contract) if ticker.contract else None,  # Fixed util.tree
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'volume': ticker.volume,
                'high': ticker.high,
                'low': ticker.low,
                'close': ticker.close,
                'timestamp': datetime.now().isoformat()
            }
            logger.debug(f"Market data tick: {tick_data}")

            # Use the new market data sampling system
            # self.event_bus.emit('market_data.tick_update', tick_data, priority=EventPriority.NORMAL)
            self._on_market_data_tick1(tick_data)
            # Log the tick data (you can replace this with your event system later)

        except Exception as e:
            logger.error(f"Error handling market data tick: {e}", exc_info=True)

    def _on_market_data_tick1(self, data: Dict[str, Any]):
        """Handle market data ticks with improved underlying price tracking."""
        try:
            contract = data.get('contract', {})
            print("contract:", contract)
            symbol = contract.get('symbol', '')
            sec_type = contract.get('secType', '')

            # Update underlying price for the configured symbol
            if symbol == self.underlying_symbol and sec_type == 'STK':  # Fixed self.config.underlying_symbol
                last_price = data.get('last')
                if last_price and last_price > 0:
                    self.underlying_price = last_price
                    logging.info("Underlying Symbol price: ", self.underlying_price)

                    logger.debug(f"Underlying price update: ${last_price}")

                    # Check if we need to reselect options
                    self._check_options_reselection()

            # Handle forex data for currency conversion
            elif sec_type == 'CASH' and symbol in ['USD', 'CAD']:
                last_price = data.get('last')
                if last_price and last_price > 0:
                    # Emit forex update for GUI
                    #     forex_data = {
                    #         'from_currency': 'USD',
                    #         'to_currency': 'CAD',
                    #         'rate': last_price,
                    #         'reciprocal_rate': 1.0 / last_price if last_price > 0 else 0,
                    #         'timestamp': datetime.now().isoformat()
                    #     }

                    logger.debug(f"Forex update: USD/CAD = {last_price}")

            # Handle options data
            elif sec_type == 'OPT':
                # Update options chain with current prices
                logger.info("Section Type is : OPT")
                self._update_options_chain(data)

        except Exception as e:
            logger.error(f"Error handling market data tick: {e}")

    def _check_options_reselection(self):
        """Placeholder for options reselection logic"""
        logger.debug("Checking options reselection...")

    def _update_options_chain(self, tick_data: Dict[str, Any]):
        """Update options chain with current market data."""
        try:
            contract = tick_data.get('contract', {})
            symbol = contract.get('symbol', '')

            if symbol != self.config.underlying_symbol:
                return

            # Find the option in our chain and update its data
            for option in self.options_chain:
                if (option.get('expiration') == contract.get('expiration') and
                        option.get('strike') == contract.get('strike') and
                        option.get('right') == contract.get('right')):
                    # Update option data
                    option.update({
                        'last': tick_data.get('last'),
                        'bid': tick_data.get('bid'),
                        'ask': tick_data.get('ask'),
                        'volume': tick_data.get('volume'),
                        'openInterest': tick_data.get('openInterest'),
                        'delta': tick_data.get('delta'),
                        'gamma': tick_data.get('gamma'),
                        'theta': tick_data.get('theta'),
                        'vega': tick_data.get('vega'),
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.info(f"Option INformation: {option}")



                    break

        except Exception as e:
            logger.error(f"Error updating options chain: {e}")

# Create the data collector instance
data_collector = IBDataCollector()

# Example of how to properly initialize it (uncomment when you want to use it)
async def main():
    logger.info("Starting main function...")
    try:
        await data_collector.initialize()
        logger.info("Data collector initialized successfully!")

        # Keep the connection alive for a few seconds to see market data
        logger.info("Waiting for market data...")
        await asyncio.sleep(5)

        logger.info("Test completed successfully!")
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")

    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Disconnect from IB
        if data_collector.ib.isConnected():
            data_collector.ib.disconnect()
            logger.info("Disconnected from IB")
        logger.info("Finally from IB")

# Run the async initialization
if __name__ == "__main__":
    logger.info("Script started - you should see this message!")
    asyncio.run(main())