# IBKR Trading Application

A comprehensive Python-based trading application for Interactive Brokers (IBKR) that provides real-time market data monitoring, dynamic option trading, and automated risk management with a modern PyQt6 GUI interface.

## 🚀 Features

### Core Trading Features
- **Real-time Market Data**: Live streaming of stock prices, options data, and FX rates
- **Dynamic Strike Price Monitoring**: Automatic adjustment of option strikes based on underlying price movements
- **Dynamic Expiration Management**: Seamless switching between 0DTE and 1DTE options at market open
- **Risk Management**: Multi-level risk controls with configurable stop-loss and profit targets
- **Account Monitoring**: Real-time P&L tracking and account summary updates

### Advanced Features
- **AI-Powered Analysis**: Integrated AI engine for market analysis and trading insights
- **Performance Optimization**: Memory management and API throttling for optimal performance
- **Event Monitoring**: Comprehensive event tracking and logging system
- **Configuration Management**: JSON-based configuration with runtime updates
- **Thread-Safe Architecture**: Non-blocking UI with separate data collection threads

### User Interface
- **Modern PyQt6 GUI**: Clean, responsive interface with real-time updates
- **Settings Panel**: Easy configuration management
- **AI Prompt Interface**: Interactive AI assistance
- **Connection Status**: Real-time connection monitoring
- **Data Visualization**: Live charts and data displays

## 📋 Prerequisites

- Python 3.8 or higher
- Interactive Brokers TWS (Trader Workstation) or IB Gateway
- Active IBKR account with market data subscriptions
- Windows 10/11 (primary platform)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd IBKR
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure IBKR Connection**
   - Start TWS or IB Gateway
   - Enable API connections in TWS settings
   - Note the port number (default: 7497 for TWS, 7499 for IB Gateway)

## ⚙️ Configuration

The application uses `config.json` for configuration. Key settings include:

### Connection Settings
```json
{
    "connection": {
        "host": "127.0.0.1",
        "port": 7499,
        "client_id": 1,
        "timeout": 30,
        "readonly": false
    }
}
```

### Trading Parameters
```json
{
    "trading": {
        "underlying_symbol": "SPY",
        "max_trade_value": 475.0,
        "trade_delta": 0.05,
        "risk_levels": [
            {
                "loss_threshold": "0",
                "account_trade_limit": "30",
                "stop_loss": "20"
            }
        ]
    }
}
```

### Performance Settings
```json
{
    "performance": {
        "memory_allocation_mb": 4096,
        "market_data_throttling": true,
        "order_validation": true
    }
}
```

## 🚀 Usage

### Starting the Application

1. **Ensure TWS/IB Gateway is running**
   - Start TWS or IB Gateway
   - Verify API connections are enabled
   - Check the correct port number

2. **Run the application**
   ```bash
   python main.py
   ```

3. **Connect to IBKR**
   - Click "Connect" in the main interface
   - Verify connection status shows "Connected"
   - Monitor real-time data updates

### Dynamic Monitoring Features

The application automatically:
- **Monitors underlying price changes** and adjusts option strikes
- **Switches expirations** at 12:00 PM EST (0DTE to 1DTE)
- **Manages risk levels** based on account performance
- **Updates market data** in real-time

### Manual Controls

- **Settings Panel**: Access via the settings button to modify configuration
- **AI Assistant**: Use the AI prompt interface for market analysis
- **Connection Management**: Monitor and control IBKR connection status

## 📁 Project Structure

```
IBKR/
├── main.py                 # Application entry point
├── config.json            # Main configuration file
├── requirements.txt       # Python dependencies
├── widgets/               # PyQt6 GUI components
│   ├── ib_trading_app.py  # Main application window
│   ├── settings_form.py   # Settings interface
│   └── ai_prompt_form.py  # AI assistant interface
├── utils/                 # Core utilities
│   ├── ib_connection.py   # IBKR API connection
│   ├── data_collector.py  # Market data collection
│   ├── config_manager.py  # Configuration management
│   └── ai_engine.py       # AI analysis engine
├── src/                   # Additional source files
│   ├── gui.py            # GUI components
│   ├── event_bus.py      # Event management
│   └── data_monitor.py   # Data monitoring
├── ui/                    # UI definition files
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## 🔧 Key Components

### Data Collection System
- **Thread-safe architecture** with separate worker threads
- **Real-time market data** streaming from IBKR
- **Dynamic subscription management** for options and stocks
- **Error handling** with automatic reconnection

### Risk Management
- **Multi-level risk controls** based on account performance
- **Automatic stop-loss** and profit target management
- **Trade limit enforcement** per risk level
- **Real-time P&L monitoring**

### Performance Optimization
- **Memory management** with configurable allocation
- **API throttling** to prevent rate limiting
- **Connection pooling** for efficient resource usage
- **Background processing** for non-blocking operations

## 🐛 Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify TWS/IB Gateway is running
   - Check port number in configuration
   - Ensure API connections are enabled in TWS

2. **Market Data Not Updating**
   - Verify market data subscriptions
   - Check account permissions
   - Review connection status

3. **Performance Issues**
   - Adjust memory allocation in config
   - Enable market data throttling
   - Monitor system resources

### Logging

The application generates detailed logs in:
- `trading_app.log` - Main application logs
- `ib_data_collector.log` - Data collection logs

Enable debug logging in `config.json` for detailed troubleshooting.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results. Always consult with a qualified financial advisor before making investment decisions.

## 📞 Support

For issues and questions:
- Check the troubleshooting section
- Review the logs for error details
- Open an issue on the repository

---

**Note**: This application requires an active Interactive Brokers account and appropriate market data subscriptions. Ensure compliance with IBKR's terms of service and API usage guidelines.