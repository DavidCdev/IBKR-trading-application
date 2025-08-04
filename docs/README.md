# My Trader Documentation

## Overview

This directory contains comprehensive documentation for the My Trader application, a sophisticated trading system built with Python and the Interactive Brokers API.

## Current Source Files

The application consists of the following core modules in the `src/` directory:

### Core Application Files
- **`main.py`** - Application entry point and main orchestration
- **`gui.py`** - Trading interface and user interaction
- **`ib_connection.py`** - Interactive Brokers API integration
- **`event_bus.py`** - Multi-threaded, priority-based event processing system
- **`config_manager.py`** - Configuration management and settings
- **`logger.py`** - Logging system and error handling
- **`config.json`** - Application configuration file

## Documentation Structure

### Core Module Documentation
- **[event_bus.md](event_bus.md)** - Resilient Event Bus system documentation
- **[gui.md](gui.md)** - Trading interface documentation
- **[config_manager.md](config_manager.md)** - Configuration management documentation
- **[logger.md](logger.md)** - Logging system documentation

### Interactive Brokers Integration
- **[ib_connection_best_practices.md](ib_connection_best_practices.md)** - Best practices for IB API integration
- **[ib_connection.md](ib_connection.md)** - IBConnectionManager class documentation

### Legacy Documentation
- **[resilient_event_bus.md](resilient_event_bus.md)** - Legacy event bus documentation (superseded by event_bus.md)

## Testing

All test files have been moved to the `tests/` directory to keep the source code clean and organized.

## Architecture Overview

The My Trader application follows a modular, event-driven architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│      GUI        │    │   Event Bus     │    │ IB Connection   │
│   (tkinter)     │◄──►│  (Multi-thread) │◄──►│   (ib_async)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Config Manager  │    │     Logger      │    │     Main        │
│   (Settings)    │    │   (Logging)     │    │ (Orchestration) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Key Features

- **Priority-Based Event Processing**: Critical orders get dedicated thread processing
- **Intelligent Throttling**: Automatic throttling based on system load
- **Market Data Sampling**: Preserves current price accuracy while reducing noise
- **Robust Error Handling**: Comprehensive error categorization and recovery
- **Real-Time Monitoring**: Performance tracking and system health monitoring
- **Interactive Brokers Integration**: Production-ready IB API integration

## Getting Started

1. **Configuration**: Review and update `src/config.json` for your trading parameters
2. **TWS/Gateway Setup**: Ensure Interactive Brokers TWS or Gateway is running
3. **API Configuration**: Enable API access in TWS/Gateway settings
4. **Run Application**: Execute `python src/main.py`

## Documentation Updates

This documentation is maintained to match the current source code. When source files are updated, corresponding documentation should be updated to reflect the changes.

## Testing Strategy

- Test files are kept in the `tests/` directory
- Tests should be deleted after completion unless specifically requested to keep
- Each module has corresponding test files for validation
- Integration tests verify the complete system functionality 