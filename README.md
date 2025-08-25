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
- **Centralized Logging System**: Comprehensive logging with real-time configuration and module auto-discovery

### User Interface
- **Modern PyQt6 GUI**: Clean, responsive interface with real-time updates
- **Settings Panel**: Easy configuration management with per-module logging controls
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

### Logging Configuration
```json
{
    "debug": {
        "master_debug": true,
        "modules": {
            "MAIN": "INFO",
            "GUI": "DEBUG",
            "IB_CONNECTION": "TRACE",
            "DATA_COLLECTOR": "INFO",
            "TRADING_MANAGER": "INFO",
            "AI_ENGINE": "INFO"
        }
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

- **Settings Panel**: Access via the settings button to modify configuration and logging levels
- **AI Assistant**: Use the AI prompt interface for market analysis
- **Connection Management**: Monitor and control IBKR connection status

### Logging System

The application features a comprehensive centralized logging system:
- **Module Auto-Discovery**: Automatically discovers 47+ Python modules
- **Real-Time Configuration**: Change log levels without restarting the application
- **GUI Integration**: Control logging verbosity through the settings interface
- **Performance Monitoring**: Built-in performance and trade event logging
- **Log Rotation**: Automatic log file rotation with configurable limits

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
│   ├── ai_engine.py       # AI analysis engine
│   └── logger.py          # Centralized logging system
├── src/                   # Additional source files
│   ├── gui.py            # GUI components
│   ├── event_bus.py      # Event management
│   └── data_monitor.py   # Data monitoring
├── ui/                    # UI definition files
├── tests/                 # Test suite
├── docs/                  # Comprehensive documentation
│   ├── LOGGING_SYSTEM.md  # Logging system documentation
│   ├── Setting GUI.md     # Settings interface documentation
│   ├── Trading Manager.md # Trading system documentation
│   └── [other docs]      # Additional component documentation
└── logs/                  # Application logs (auto-generated)
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

### Logging System
- **Centralized management** of all application logging
- **Real-time configuration** via GUI without restarts
- **Module auto-discovery** for automatic logger setup
- **Performance monitoring** with built-in metrics collection

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

4. **Logging Issues**
   - Verify logging system is properly initialized
   - Check module configuration in debug settings
   - Ensure appropriate log levels are set

### Logging

The application generates detailed logs in the `logs/` directory:
- `trading_app.log` - Main application logs
- `errors.log` - Error-only logs
- `debug.log` - Debug information (if enabled)
- `performance.log` - Performance metrics

Enable debug logging in `config.json` for detailed troubleshooting. Use the Settings GUI to adjust log levels for individual modules in real-time.

## 📚 Documentation

Comprehensive documentation is available in the `docs/` folder:

- **Logging System**: `docs/LOGGING_SYSTEM.md` - Complete logging system guide
- **Settings GUI**: `docs/Setting GUI.md` - Configuration interface documentation
- **Trading Manager**: `docs/Trading Manager.md` - Trading system documentation
- **Data Collector**: `docs/Data Collector README.md` - Data collection system
- **IB Connection**: `docs/IB connection.md` - Connection management
- **AI Engine**: `docs/AI Engine README.md` - AI analysis system
- **Configuration**: `docs/Config Manager READEM.md` - Configuration management
- **Update Summary**: `docs/DOCUMENTATION_UPDATE_SUMMARY.md` - Recent changes overview

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
- Consult the comprehensive documentation in `docs/`
- Open an issue on the repository

---

**Note**: This application requires an active Interactive Brokers account and appropriate market data subscriptions. Ensure compliance with IBKR's terms of service and API usage guidelines.