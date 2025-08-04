# IBKR


1. Historical 1-Minute Bar Data Fetching

- Handler: `_handle_request_historical_data`
- Event: Listens for `'market_data.request_historical'` on the event bus.
- Function: Fetches historical 1-minute bar data for a given contract (stock, option, etc.) and emits the result as `'market_data.historical_update'`.
- Usage:
Emit an event like:

```python
# Fetch historical 1-minute bars for AAPL
event_bus.emit('market_data.request_historical', {
    'symbol': 'AAPL',
    'secType': 'STK',
    'duration': '1 D',
    'barSize': '1 min'
})
```

2. FX Rate Auto-Subscription & Calculation
- Handler: `_handle_request_fx_rate`
- Event: Listens for `'fx.request_rate'` on the event bus.
- Function:
Checks if the account base currency is different from the underlying's currency.
If so, subscribes to the relevant FX rate (e.g., USD.CAD and CAD.USD).
- Calculates and emits both the direct and reciprocal rates as `'fx.rate_update'`.
- Usage:
Emit an event like:

```python
# Request FX rate between account and underlying currency
event_bus.emit('fx.request_rate', {
    'underlying_symbol': 'AAPL',
    'underlying_currency': 'USD'
})
```

3. Event Bus Registration
Both handlers are registered in the event bus and handler map, so they are available for event-driven use.