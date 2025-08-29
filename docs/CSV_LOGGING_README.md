# CSV Logging System

## Overview

The CSV Logging System provides comprehensive logging of trading activities and account summaries to CSV files. It automatically creates daily trade logs and maintains a persistent trading summary log.

## Features

### Statistics Filtering
- **Primary Symbol Only**: Only records trades involving calls or puts on the primary underlying symbol (e.g., QQQ, SPY)
- **Options Only**: Filters out non-options trades (stocks, futures, etc.)
- **Daily Filtering**: Only records trades from the current trading day

### Daily Trade Logs
- **File Naming**: `TradingLog-YYYY-MM-DD.csv` (e.g., `TradingLog-2025-01-04.csv`)
- **Location**: `csv/daily_logs/` directory
- **Automatic Creation**: New files are created automatically for each trading day
- **Real-time Updates**: Trades are logged immediately upon execution

### Trading Summary Log
- **File Name**: `trading-summary.csv`
- **Location**: `csv/` directory
- **Persistent**: Single file that accumulates data across all trading days
- **Daily Updates**: Updated whenever account summary or daily PnL changes

## CSV File Formats

### Daily Trade Log (`TradingLog-YYYY-MM-DD.csv`)

| Column | Description | Example |
|--------|-------------|---------|
| Timestamp | Trade execution time | `2025-01-04 12:42:13` |
| Trade Type | BUY or SELL | `BUY` |
| Right | C for call, P for put | `P` |
| ConId | Contract ID | `769189776` |
| Strike | Strike price | `559.0` |
| Expiry | Expiration date (YYYYMMDD) | `20250104` |
| Quantity | Number of contracts | `4.0` |
| Price | Execution price | `1.05` |
| PnL | Profit/Loss (0 for buys) | `0` or `8.99` |
| Outcome | Profit, Loss, or empty | `Profit`, `Loss`, or `` |
| OrderId | Order ID | `291` |

### Trading Summary (`trading-summary.csv`)

| Column | Description | Example |
|--------|-------------|---------|
| Date | Trading date | `2025-01-04` |
| Total Balance (CAD) | Account net liquidation | `4372.3` |
| Daily PnL | Daily profit/loss | `-395` |
| Starting Balance | Balance at start of day | `3977.3` |
| High water mark | Highest account value | `4372.3` |
| Profitable Trades | Number of winning trades | `0` |
| Profit Amount | Total profit from wins | `0` |
| Loss Trades | Number of losing trades | `1` |
| Loss Amount | Total loss from losses | `395` |

## Implementation Details

### Integration Points

The CSV logging system integrates with the IB connection at three key points:

1. **Trade Execution** (`on_exec_details`):
   - Logs every BUY/SELL trade immediately
   - Filters for options trades on primary underlying symbol
   - Records trade details with PnL initially set to 0

2. **Trade Closure** (when BUY + SELL match):
   - Updates corresponding BUY trade with calculated PnL
   - Sets outcome to "Profit" or "Loss"
   - Updates closed trades summary

3. **Account Updates** (`on_account_summary_update`, `on_pnl_update`):
   - Logs account balance changes
   - Updates daily PnL
   - Maintains high water mark tracking

### File Management

- **Daily Logs**: Automatically created in `csv/daily_logs/` directory
- **Summary File**: Single persistent file in `csv/` directory
- **Headers**: Automatically added to new files
- **Updates**: Existing entries are updated rather than duplicated

### Error Handling

- **Graceful Degradation**: CSV logging failures don't affect trading operations
- **Comprehensive Logging**: All errors are logged to the application log
- **File Validation**: Checks file existence before operations
- **Data Validation**: Validates trade data before logging

## Usage

### Automatic Operation

The CSV logging system operates automatically once integrated:

1. **Startup**: CSV logger initializes when IB connection is established
2. **Trade Logging**: Every options trade is automatically logged
3. **Account Updates**: Account changes automatically update summary
4. **Daily Rotation**: New daily log files are created automatically

### Manual Access

You can access the logged data programmatically:

```python
from utils.csv_logger import CSVTradeLogger

# Initialize logger
csv_logger = CSVTradeLogger()

# Get today's trades
today = date.today()
daily_trades = csv_logger.get_daily_trades(today)

# Get trading summary
summary = csv_logger.get_trading_summary()
```

### File Locations

```
csv/
├── trading-summary.csv              # Persistent summary log
└── daily_logs/
    ├── TradingLog-2025-01-04.csv   # Today's trades
    ├── TradingLog-2025-01-03.csv   # Yesterday's trades
    └── ...                         # Historical daily logs
```

## Configuration

### CSV Directory

The CSV logger uses the `csv/` directory by default. You can customize this:

```python
# Custom directory
csv_logger = CSVTradeLogger(csv_directory="custom/path")
```

### File Permissions

Ensure the application has write permissions to the CSV directory:
- **Windows**: Run as administrator or ensure user has write access
- **Linux/Mac**: Set appropriate directory permissions

## Data Flow

```
IB Trade Execution → Filter (Options + Primary Symbol) → CSV Daily Log
                                                           ↓
                                                    Update PnL/Outcome
                                                           ↓
                                                    CSV Trading Summary
```

## Benefits

1. **Comprehensive Record**: Complete audit trail of all trading activities
2. **Performance Analysis**: Easy import to Excel/Google Sheets for analysis
3. **Compliance**: Maintains records for regulatory requirements
4. **Debugging**: Detailed logs for troubleshooting trading issues
5. **Reporting**: Automated generation of daily and summary reports

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check file/directory write permissions
2. **File Not Found**: Ensure CSV directory exists and is accessible
3. **Import Errors**: Verify CSV file format and encoding (UTF-8)
4. **Missing Data**: Check application logs for CSV logging errors

### Debug Mode

Enable debug logging for the CSV_LOGGER module to see detailed operation:

```json
{
  "debug": {
    "modules": {
      "CSV_LOGGER": "DEBUG"
    }
  }
}
```

## Future Enhancements

- **Compression**: Automatic compression of old daily logs
- **Backup**: Automated backup of CSV files
- **Export Formats**: Support for additional export formats (JSON, XML)
- **Real-time Streaming**: WebSocket streaming of trade data
- **Analytics Integration**: Direct integration with trading analytics tools
