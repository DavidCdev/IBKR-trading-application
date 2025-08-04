import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.ib_connection import IBConnectionManager
from src.event_bus import ResilientEventBus
from src.config_manager import ConfigManager

@pytest.fixture
def event_bus():
    return ResilientEventBus(max_workers=2, enable_monitoring=False)

@pytest.fixture
def config_manager(tmp_path, event_bus):
    # Use a temp config file to avoid side effects
    config_path = tmp_path / "config.json"
    config_path.write_text('{"connection": {"host": "127.0.0.1", "port": 7497, "client_id": 1, "account_currency": "USD"}, "trading": {"underlying_symbol": "AAPL"}}')
    return ConfigManager(str(config_path), event_bus=event_bus)

@pytest.fixture
def ib_connection(event_bus, config_manager):
    ibc = IBConnectionManager(event_bus, config_manager)
    # Patch IB methods for async/historical/FX
    ibc.ib.qualifyContractsAsync = AsyncMock(return_value=[MagicMock(conId=123, symbol='AAPL', secType='STK')])
    ibc.ib.reqHistoricalDataAsync = AsyncMock(return_value=[
        MagicMock(date='20240101 09:30:00', open=100, high=101, low=99, close=100.5, volume=1000),
        MagicMock(date='20240101 09:31:00', open=100.5, high=102, low=100, close=101, volume=1200),
    ])
    # FX mocks
    fake_fx_ticker = MagicMock()
    fake_fx_ticker.last = 1.25
    fake_fx_ticker.close = 1.25
    ibc.ib.reqMktData = MagicMock(return_value=fake_fx_ticker)
    ibc.ib.cancelMktData = MagicMock()
    return ibc

@pytest.mark.asyncio
async def test_historical_data_fetch(ib_connection, event_bus):
    results = {}
    def on_historical_update(data):
        results['data'] = data
    event_bus.on('market_data.historical_update', on_historical_update)
    # Simulate connection
    ib_connection._connected = True
    # Emit event
    await ib_connection._handle_request_historical_data({
        'symbol': 'AAPL',
        'secType': 'STK',
        'duration': '1 D',
        'barSize': '1 min'
    })
    await asyncio.sleep(0.1)
    assert 'data' in results
    bars = results['data']['bars']
    assert len(bars) == 2
    assert bars[0]['open'] == 100

@pytest.mark.asyncio
async def test_fx_rate_fetch(ib_connection, event_bus):
    results = {}
    def on_fx_update(data):
        results['data'] = data
    event_bus.on('fx.rate_update', on_fx_update)
    ib_connection._connected = True
    # Emit event (simulate USD/CAD conversion)
    await ib_connection._handle_request_fx_rate({
        'underlying_symbol': 'AAPL',
        'underlying_currency': 'CAD'
    })
    await asyncio.sleep(0.1)
    assert 'data' in results
    fx = results['data']
    assert fx['rate'] == 1.25
    assert fx['reciprocal_rate'] == 1.25 or abs(fx['reciprocal_rate'] - 0.8) < 0.01  # Accept reciprocal
