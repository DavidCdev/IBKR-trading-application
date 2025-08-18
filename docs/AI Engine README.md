## AI Engine

### Overview
The AI Engine (`utils/ai_engine.py`) integrates Google Gemini with your trading app to analyze market data and produce structured insights for options trading. It:
- Collects recent historical prices from your data layer
- Summarizes price action and key inflection points
- Builds a constrained prompt
- Calls Gemini and parses a strict JSON response
- Emits PyQt6 signals with the analysis, status, and errors

### Features
- **Gemini integration**: Uses `google.generativeai` with the `gemini-1.5-flash` model.
- **Structured output**: Ensures a predictable JSON schema for downstream consumers.
- **Intelligent polling**: Optional background polling via `QTimer` with safe threading.
- **Smart caching**: Reuses the last analysis unless the prompt changes, price exits the last valid range, or cache expires.
- **Historical context**: Pulls price history and computes simple high/low inflection points.
- **PyQt6 signals**: UI-friendly updates via `analysis_ready`, `analysis_error`, `polling_status`, `cache_status`.

### Installation
Install the required packages (minimal for the AI Engine itself):
```bash
pip install google-generativeai PyQt6
```
If you are using the provided IB data pipeline, you will also need its dependencies (see `utils/ib_connection.py`).

### Configuration
The engine reads settings from `config.json` via `utils/config_manager.AppConfig`.

- **Path**: `config.json` in the project root by default
- **Section**: `ai_prompt`

Example:
```json
{
  "ai_prompt": {
    "prompt": "Analyze the current market conditions and provide trading insights for options trading.",
    "context": "Additional context if needed.",
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "polling_interval_minutes": 10,
    "enable_auto_polling": true,
    "enable_price_triggered_polling": false,
    "max_historical_days": 30,
    "cache_duration_minutes": 15
  },
  "trading": {
    "underlying_symbol": "QQQ"
  }
}
```

Notes:
- **Do not commit secrets**: Keep `gemini_api_key` private.
- `underlying_symbol` controls which symbol is analyzed for history; defaults to `SPY` inside the engine if not provided.

### Signals
`AI_Engine` is a `QObject` and emits:
- `analysis_ready(dict)`: Dict representation of the analysis result
- `analysis_error(str)`: Error message
- `polling_status(str)`: Human-readable status for polling lifecycle
- `cache_status(str)`: Cache decisions/updates

### Data requirements
The engine expects a data layer with this minimal interface, passed in as `data_collector`:
- `data_collector.collector.underlying_symbol_price: float` — current price of the configured underlying
- `await data_collector.collector.get_historical_data(symbol: str, start_date: datetime, end_date: datetime) -> List[Dict]`
  - Each item should contain at least: `{"timestamp": datetime, "close": float, "volume": Optional[float]}`

The provided implementation is `utils/ib_connection.IBDataCollector`, typically wrapped by `utils/data_collector.DataCollectorWorker`.

### Usage
Basic setup inside a PyQt6 app (simplified):
```python
from utils.config_manager import AppConfig
from utils.ai_engine import AI_Engine
from utils.data_collector import DataCollectorWorker

config = AppConfig.load_from_file()
data_worker = DataCollectorWorker(config)
ai = AI_Engine(config, data_worker)

def on_ready(result: dict):
    print("AI analysis:", result)

def on_error(msg: str):
    print("AI error:", msg)

ai.analysis_ready.connect(on_ready)
ai.analysis_error.connect(on_error)

# Trigger an analysis (bypassing cache)
ai.force_refresh()

# Or run once (async) without forcing
# await ai.analyze_market_data()
```

Testing without IB (stub the minimal data interface):
```python
import asyncio
from datetime import datetime, timedelta

class StubCollector:
    def __init__(self):
        self.underlying_symbol_price = 100.0
    async def get_historical_data(self, symbol, start_date, end_date):
        now = datetime.now()
        return [{"timestamp": now - timedelta(days=i), "close": 100 + i * 0.1} for i in range(30)]

class StubWorker:
    def __init__(self):
        self.collector = StubCollector()

# ... create AppConfig with a valid gemini_api_key ...
# config = AppConfig.load_from_file()
# config.ai_prompt["gemini_api_key"] = "YOUR_GEMINI_API_KEY"

# ai = AI_Engine(config, StubWorker())
# asyncio.run(ai.analyze_market_data(force_refresh=True))
```

### Output format
The engine requests a strict JSON response and exposes it as:
```json
{
  "valid_price_range": { "low": 0.0, "high": 0.0 },
  "analysis_summary": "string",
  "confidence_level": 0.0,
  "key_insights": ["string"],
  "risk_assessment": "string"
}
```

You can also access the raw parsed response via the `raw_response` field in the emitted dict.

### Caching and polling
- **Cache is reused** unless any of the following is true:
  - User prompt changed
  - Current price is outside the last `valid_price_range`
  - Cache age exceeds `cache_duration_minutes`
- **Auto polling**: If `enable_auto_polling` is true, a `QTimer` triggers analyses every `polling_interval_minutes`.
- **Force refresh**: Call `force_refresh()` to bypass cache immediately.

### Key methods
- `analyze_market_data(force_refresh: bool = False)` — Main coroutine to produce an analysis
- `force_refresh()` — Run analysis in a background thread, bypassing cache
- `update_config(new_config: AppConfig)` — Apply new settings and restart polling if needed
- `reinitialize_api()` — Rebuild the Gemini client using the current key
- `is_ai_available()` — Whether Gemini is configured and ready
- `get_ai_status()` / `get_config_status()` / `get_cache_status()` — Diagnostic snapshots
- `get_last_analysis()` — Last successful analysis as a dict
- `cleanup()` — Stop polling and clean up

### Error handling and troubleshooting
- Ensure `ai_prompt.gemini_api_key` is set and non-empty.
- Ensure the app provides a valid current price; otherwise the engine will fail with "No valid current price available".
- If Gemini returns non-JSON or markdown-wrapped JSON, the engine auto-strips code fences and logs parse errors.
- Use `get_ai_status()` and `get_config_status()` for quick diagnostics.
- Logs are emitted via `utils.smart_logger.get_logger("AI_ENGINE")`.

### Security
- Keep your `gemini_api_key` secure and out of version control.
- Consider using environment injection or a secrets manager to populate `config.json` at runtime.
