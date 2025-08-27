import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import google.generativeai as genai
from utils.config_manager import AppConfig
from utils.logger import get_logger
from utils.performance_monitor import monitor_function

logger = get_logger("AI_ENGINE")

@dataclass
class PricePoint:
    """Represents a price point with timestamp"""
    timestamp: datetime
    price: float
    volume: Optional[float] = None

@dataclass
class InflectionPoint:
    """Represents a key inflection point in price action"""
    timestamp: datetime
    price: float
    type: str  # 'high', 'low', 'breakout', 'breakdown'
    significance: float  # 0.0 to 1.0

@dataclass
class AIAnalysisResult:
    """Structured result from AI analysis"""
    valid_price_range: Dict[str, float]  # {'low': float, 'high': float}
    analysis_summary: str
    confidence_level: float
    key_insights: List[str]
    risk_assessment: str
    timestamp: datetime
    raw_response: Dict[str, Any]
    alerts: List[str]

class AI_Engine(QObject):
    """AI Prompt Manager with Gemini API integration"""
    
    # Signals for GUI updates
    analysis_ready = pyqtSignal(dict)  # Emits AIAnalysisResult as dict
    analysis_error = pyqtSignal(str)   # Emits error message
    polling_status = pyqtSignal(str)   # Emits polling status updates
    cache_status = pyqtSignal(str)     # Emits cache status updates
    
    def __init__(self, config: AppConfig, data_collector=None):
        super().__init__()
        self.config = config
        self.data_collector = data_collector
        
        # Initialize Gemini API
        self._setup_gemini_api()
        
        # Historical price data storage
        self.historical_prices: List[PricePoint] = []
        self.inflection_points: List[InflectionPoint] = []
        
        # Caching and polling state
        self.last_analysis: Optional[AIAnalysisResult] = None
        self.last_prompt_hash: Optional[str] = None
        self.last_poll_time: Optional[datetime] = None
        self.is_polling = False
        
        # Timers for intelligent polling
        self.polling_timer = QTimer()
        self.polling_timer.timeout.connect(self._scheduled_poll)
        
        # Start polling if enabled
        if self.config.ai_prompt.get("enable_auto_polling", True):
            self._start_polling()
    
    def _setup_gemini_api(self):
        """Initialize Gemini API client"""
        try:
            api_key = self.config.ai_prompt.get("gemini_api_key", "")
            logger.info(f"Setting up Gemini API with key: {api_key[:10]}..." if api_key else "No API key found")
            
            if not api_key:
                logger.warning("No Gemini API key configured. AI analysis will be disabled.")
                logger.info("To enable AI analysis, please add your Gemini API key to the configuration.")
                self.gemini_client = None
                return
            
            if not api_key.strip():
                logger.warning("Gemini API key is empty. AI analysis will be disabled.")
                logger.info("To enable AI analysis, please add your Gemini API key to the configuration.")
                self.gemini_client = None
                return
            
            genai.configure(api_key=api_key)
            self.gemini_client = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini API client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            logger.info("AI analysis will be disabled until a valid API key is configured.")
            self.gemini_client = None
    
    def _start_polling(self):
        """Start the intelligent polling timer"""
        if not self.config.ai_prompt.get("enable_auto_polling", True):
            return
        
        interval_minutes = self.config.ai_prompt.get("polling_interval_minutes", 10)
        interval_ms = interval_minutes * 60 * 1000
        
        self.polling_timer.start(interval_ms)
        logger.info(f"AI polling started with {interval_minutes}-minute interval")
        self.polling_status.emit(f"Polling started - {interval_minutes} minute intervals")
    
    def _stop_polling(self):
        """Stop the intelligent polling timer"""
        self.polling_timer.stop()
        self.is_polling = False
        logger.info("AI polling stopped")
        self.polling_status.emit("Polling stopped")
    
    def _scheduled_poll(self):
        """Handle scheduled polling events"""
        if self.is_polling:
            logger.debug("Skipping scheduled poll - another poll in progress")
            return
        
        logger.info("Executing scheduled AI poll")
        
        # Run the analysis in a separate thread to avoid blocking the UI
        def run_scheduled_analysis():
            try:
                # Create a new event loop for this async operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.analyze_market_data())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error in scheduled poll: {e}")
                self.analysis_error.emit(f"Scheduled poll failed: {e}")
        
        # Start the analysis in a background thread
        analysis_thread = threading.Thread(target=run_scheduled_analysis, daemon=True)
        analysis_thread.start()
    
    @monitor_function("AI_ENGINE.collect_historical_data", threshold_ms=5000)
    async def collect_historical_data(self, days: int = None) -> List[PricePoint]:
        """Collect historical price data for analysis"""
        try:
            if days is None:
                days = self.config.ai_prompt.get("max_historical_days", 30)
            
            if not self.data_collector or not self.data_collector.collector:
                logger.warning("Data collector not available for historical data")
                return []
            
            # Get historical data from IB
            symbol = self.config.trading.get("underlying_symbol", "SPY")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get historical data from IB
            logger.info(f"Collecting {days} days of historical data for {symbol}")
            
            try:
                # Get historical data from IB
                historical_data = await self.data_collector.collector.get_historical_data(
                    symbol, start_date, end_date
                )
                
                if not historical_data:
                    logger.warning(f"No historical data returned for {symbol}")
                    return []
                
                # Convert to PricePoint objects
                price_points = []
                for data_point in historical_data:
                    # Use close price as the main price
                    price_point = PricePoint(
                        timestamp=data_point['timestamp'],
                        price=data_point['close'],
                        volume=data_point.get('volume')
                    )
                    price_points.append(price_point)
                
                logger.info(f"Successfully collected {len(price_points)} price points for {symbol}")
                return price_points
                
            except Exception as e:
                logger.error(f"Error fetching historical data from IB: {e}")
                return []
            
        except Exception as e:
            logger.error(f"Error collecting historical data: {e}")
            return []
    
    @staticmethod
    def _identify_inflection_points(prices: List[PricePoint]) -> List[InflectionPoint]:
        """Identify key inflection points in price action"""
        if len(prices) < 3:
            return []
        
        inflection_points = []
        
        # Simple inflection point detection
        for i in range(1, len(prices) - 1):
            prev_price = prices[i-1].price
            curr_price = prices[i].price
            next_price = prices[i+1].price
            
            # Local high
            if curr_price > prev_price and curr_price > next_price:
                significance = (curr_price - min(prev_price, next_price)) / curr_price
                inflection_points.append(InflectionPoint(
                    timestamp=prices[i].timestamp,
                    price=curr_price,
                    type='high',
                    significance=min(significance, 1.0)
                ))
            
            # Local low
            elif curr_price < prev_price and curr_price < next_price:
                significance = (max(prev_price, next_price) - curr_price) / curr_price
                inflection_points.append(InflectionPoint(
                    timestamp=prices[i].timestamp,
                    price=curr_price,
                    type='low',
                    significance=min(significance, 1.0)
                ))
        
        # Sort by significance and return top points
        inflection_points.sort(key=lambda x: x.significance, reverse=True)
        return inflection_points[:10]  # Return top 10 most significant points
    
    @staticmethod
    def _generate_price_summary(prices: List[PricePoint], inflection_points: List[InflectionPoint]) -> str:
        """Generate a token-efficient summary of historical price action"""
        if not prices:
            return "No historical price data available."
        
        # Calculate basic statistics
        price_values = [p.price for p in prices]
        current_price = price_values[-1]
        min_price = min(price_values)
        max_price = max(price_values)
        avg_price = sum(price_values) / len(price_values)
        
        # Calculate price change
        if len(price_values) > 1:
            price_change = current_price - price_values[0]
            price_change_pct = (price_change / price_values[0]) * 100
        else:
            price_change = 0
            price_change_pct = 0
        
        # Generate summary
        summary = f"""
Historical Price Summary ({len(prices)} data points):
- Current Price: ${current_price:.2f}
- Range: ${min_price:.2f} - ${max_price:.2f}
- Average: ${avg_price:.2f}
- Total Change: ${price_change:.2f} ({price_change_pct:+.2f}%)
"""
        
        # Add inflection points
        if inflection_points:
            summary += "\nKey Inflection Points:\n"
            for i, point in enumerate(inflection_points[:5], 1):  # Top 5 points
                summary += f"{i}. {point.type.upper()}: ${point.price:.2f} at {point.timestamp.strftime('%Y-%m-%d %H:%M')} (significance: {point.significance:.2f})\n"
        
        return summary.strip()

    @staticmethod
    def _construct_final_prompt(price_summary: str, current_price: float, user_prompt: str, price_window: List) -> str:
        """Construct the final prompt for Gemini API"""
        system_prompt = """You are a senior quantitative analyst and options strategist. You will receive:

A token-efficient summary of historical price action (from AI processor)
Today's real-time price of the instrument (e.g., SPY, IBKR, QQQ, etc.)
A user-defined market plan (e.g., directional bias, planned strategy, timeframes)
Your task: Analyze the current market situation and return a JSON object with both strategic context and real-time actionable insights. ONLY generate alerts if current conditions justify it.

In particular:

Actionable alerts must be filtered to the current valid_price_range, OR a narrow buffer zone around the current price (e.g., ±1%).
Do NOT output alerts based on support/resistance zones well above or below the current range unless the price is approaching them.
If no alert-worthy signals appear at the moment, state clearly: "No actionable trade setup at this time."
Insights and strategies may include signals like approaching technical levels, volatility-based setups, or breakout/breakdown confirmations.

📤 Return your response in this exact JSON format:

{
    "valid_price_range": {
        "low": <float>, ← AI-estimated actionable lower range (e.g., support from price structure or volatility)
        "high": <float> ← upper actionable range
    },
    "analysis_summary": "<string>", ← Succinct summary of what market is doing
    "confidence_level": <float>, ← 0.0–1.0 representing your confidence in the current thesis
    "key_insights": ["<string>", ...], ← General observations on trend, setups forming, option behavior
    "alerts": ["<string>", ...], ← Clearly actionable ideas valid NOW, e.g.:
        → "Approaching resistance zone – consider call spread entry"
        → "Price confirmed breakout above key level"
        → "Neutral chop – no action advised"
    "risk_assessment": "<string>" ← Summary of risk conditions: Low / Medium / Elevated / High
}
"""

        final_prompt = f"""
{system_prompt}

MARKET DATA:
{price_summary}

REAL-TIME CURRENT PRICE: ${current_price:.2f}

USER PLAN:
{user_prompt}

Special Instructions:

Limit alerts to conditions detectable or likely within the current actionable range: {price_window}
Exclude any long-range observations that are not near current price
Do not manufacture alerts if no valid signals based on price location / range volatility
Thank you.

Please provide your analysis in the specified JSON format.
"""

        return final_prompt.strip()

    def _should_skip_cache(self, user_prompt: str, current_price: float) -> bool:
        """Determine if we should skip cache and make a new API call"""
        # Check if prompt has changed
        prompt_hash = hash(user_prompt)
        if prompt_hash != self.last_prompt_hash:
            logger.info("User prompt changed - bypassing cache")
            return True
        
        # Check if price is outside valid range
        if self.last_analysis and self.last_analysis.valid_price_range:
            low = self.last_analysis.valid_price_range.get('low', 0)
            high = self.last_analysis.valid_price_range.get('high', float('inf'))
            
            if current_price < low or current_price > high:
                logger.info(f"Price ${current_price:.2f} outside valid range [${low:.2f}, ${high:.2f}] - bypassing cache")
                return True
        
        # Check cache duration
        cache_duration = self.config.ai_prompt.get("cache_duration_minutes", 15)
        if self.last_poll_time:
            time_since_last = datetime.now() - self.last_poll_time
            if time_since_last.total_seconds() > (cache_duration * 60):
                logger.info(f"Cache expired ({cache_duration} minutes) - bypassing cache")
                return True
        
        logger.info("Using cached analysis")
        self.cache_status.emit("Using cached analysis")
        return False
    
    @monitor_function("AI_ENGINE.call_gemini_api", threshold_ms=10000)
    async def _call_gemini_api(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Make API call to Gemini"""
        if not self.gemini_client:
            raise Exception("Gemini API client not initialized. Please configure a valid Gemini API key in the settings.")
        
        try:
            logger.info("Making Gemini API call...")
            response = await asyncio.to_thread(
                self.gemini_client.generate_content,
                prompt
            )
            
            if not response.text:
                raise Exception("Empty response from Gemini API")
            
            # Clean the response text to handle markdown-wrapped JSON
            cleaned_text = self._extract_json_from_response(response.text)
            
            # Parse JSON response
            try:
                result = json.loads(cleaned_text)
                logger.info("Successfully parsed Gemini API response")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {response.text}")
                logger.error(f"Cleaned text: {cleaned_text}")
                raise Exception(f"Invalid JSON response from Gemini API: {e}")
                
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    
    @staticmethod
    def _extract_json_from_response(response_text: str) -> str:
        """Extract JSON from response, handling markdown code blocks"""
        text = response_text.strip()
        
        # Remove markdown code block markers
        if text.startswith('```json'):
            text = text[7:]  # Remove ```json
        elif text.startswith('```'):
            text = text[3:]  # Remove ```
        
        if text.endswith('```'):
            text = text[:-3]  # Remove trailing ```
        
        return text.strip()
    
    @staticmethod
    def _parse_ai_response(response: Dict[str, Any]) -> AIAnalysisResult:
        """Parse and validate AI response"""
        try:
            # Validate required fields
            if 'valid_price_range' not in response:
                raise ValueError("Missing 'valid_price_range' in AI response")
            
            price_range = response['valid_price_range']
            if 'low' not in price_range or 'high' not in price_range:
                raise ValueError("Invalid 'valid_price_range' format")
            
            # Create analysis result
            result = AIAnalysisResult(
                valid_price_range=price_range,
                analysis_summary=response.get('analysis_summary', ''),
                confidence_level=float(response.get('confidence_level', 0.5)),
                key_insights=response.get('key_insights', []),
                risk_assessment=response.get('risk_assessment', ''),
                alerts=response.get('alerts', []),
                timestamp=datetime.now(),
                raw_response=response
            )
            
            logger.info(f"Parsed AI analysis: price range [${price_range['low']:.2f}, ${price_range['high']:.2f}]")
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise
    
    @monitor_function("AI_ENGINE.analyze_market_data", threshold_ms=15000)
    async def analyze_market_data(self, force_refresh: bool = False) -> Optional[AIAnalysisResult]:
        """Main method to analyze market data with AI"""
        try:
            if self.is_polling and not force_refresh:
                logger.debug("Analysis already in progress, skipping")
                return None
            
            self.is_polling = True
            self.polling_status.emit("Analysis in progress...")
            
            # Check if AI is available
            if not self.is_ai_available():
                error_msg = "AI analysis is not available. Please configure a valid Gemini API key in the settings."
                logger.warning(error_msg)
                self.analysis_error.emit(error_msg)
                self.polling_status.emit("AI not configured")
                return None
            
            # Get current data
            current_price = self._get_current_price()
            if current_price <= 0:
                raise Exception("No valid current price available")
            
            user_prompt = self.config.ai_prompt.get("prompt", "")
            if not user_prompt.strip():
                raise Exception("No user prompt configured")
            
            # Check cache
            if not force_refresh and not self._should_skip_cache(user_prompt, current_price):
                if self.last_analysis:
                    self.analysis_ready.emit(self._analysis_result_to_dict(self.last_analysis))
                    return self.last_analysis
            
            # Collect historical data
            historical_prices = await self.collect_historical_data()
            inflection_points = self._identify_inflection_points(historical_prices)
            
            # Generate price summary
            price_summary = self._generate_price_summary(historical_prices, inflection_points)

            buffer_pct = 0.015

            buffer_amount = current_price * buffer_pct
            price_window_low = round(current_price - buffer_amount, 2)
            price_window_high = round(current_price + buffer_amount, 2)

            price_window = [price_window_low, price_window_high]

            # Construct final prompt
            final_prompt = self._construct_final_prompt(price_summary, current_price, user_prompt, price_window)
            
            # Make API call
            logger.info("Initiating AI analysis...")
            logger.info(f"Final prompt: {final_prompt}")
            response = await self._call_gemini_api(final_prompt)
            
            # Parse response
            analysis_result = self._parse_ai_response(response)
            
            # Update cache
            self.last_analysis = analysis_result
            self.last_prompt_hash = hash(user_prompt)
            self.last_poll_time = datetime.now()
            
            # Emit result
            result_dict = self._analysis_result_to_dict(analysis_result)
            logger.info(f"Result dict: {result_dict}")
            self.analysis_ready.emit(result_dict)
            
            logger.info("AI analysis completed successfully")
            self.polling_status.emit("Analysis completed")
            self.cache_status.emit("Analysis cached")
            
            return analysis_result
            
        except Exception as e:
            error_msg = f"AI analysis failed: {e}"
            logger.error(error_msg)
            self.analysis_error.emit(error_msg)
            self.polling_status.emit("Analysis failed")
            return None
        
        finally:
            self.is_polling = False
    
    def _get_current_price(self) -> float:
        """Get current price from data collector"""
        try:
            if self.data_collector and self.data_collector.collector:
                return self.data_collector.collector.underlying_symbol_price or 0
            return 0
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 0
    
    @staticmethod
    def _analysis_result_to_dict(result: AIAnalysisResult) -> Dict[str, Any]:
        """Convert AIAnalysisResult to dictionary for signal emission"""
        return {
            'valid_price_range': result.valid_price_range,
            'analysis_summary': result.analysis_summary,
            'confidence_level': result.confidence_level,
            'key_insights': result.key_insights,
            'risk_assessment': result.risk_assessment,
            'alerts': result.alerts,
            'timestamp': result.timestamp.isoformat(),
            'raw_response': result.raw_response
        }
    
    def is_ai_available(self) -> bool:
        """Check if AI analysis is available (API key configured)"""
        return self.gemini_client is not None
    
    def force_refresh(self):
        """Force a refresh of AI analysis, bypassing cache"""
        logger.info("Force refresh requested")
        
        # Run the analysis in a separate thread to avoid blocking the UI
        def run_analysis():
            try:
                # Create a new event loop for this async operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.analyze_market_data(force_refresh=True))
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error in force refresh: {e}")
                self.analysis_error.emit(f"Force refresh failed: {e}")
        
        # Start the analysis in a background thread
        analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        analysis_thread.start()
    
    def get_config_status(self) -> Dict[str, Any]:
        """Get detailed configuration status for debugging"""
        return {
            'api_key_configured': bool(self.config.ai_prompt.get("gemini_api_key", "").strip()),
            'api_key_length': len(self.config.ai_prompt.get("gemini_api_key", "")),
            'api_key_preview': self.config.ai_prompt.get("gemini_api_key", "")[:10] + "..." if self.config.ai_prompt.get("gemini_api_key", "") else "None",
            'ai_available': self.is_ai_available(),
            'gemini_client_initialized': self.gemini_client is not None,
            'polling_enabled': self.config.ai_prompt.get("enable_auto_polling", True),
            'polling_interval': self.config.ai_prompt.get("polling_interval_minutes", 10)
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self._stop_polling()
        logger.info("AI Engine cleanup completed")
    
    # Backward compatibility methods
    def refresh(self):
        """Refresh the AI engine (backward compatibility)"""
        logger.info("Refreshing AI engine configuration...")
        self.config = AppConfig.load_from_file()
        self._setup_gemini_api()
        if self.is_ai_available():
            logger.info("AI engine refreshed successfully")
        else:
            logger.warning("AI engine refresh completed but API is not available")
    
