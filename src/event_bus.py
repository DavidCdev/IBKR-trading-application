import asyncio
import threading
import time
import random
from collections import defaultdict, deque
from typing import Callable, Any, Dict, Awaitable, Optional, List, Tuple
import concurrent.futures
from enum import Enum
from dataclasses import dataclass, field
from logger import get_logger
from enhanced_logging import log_event_flow, log_performance
from performance_optimizer import record_event_processing

logger = get_logger('EVENT_BUS')

class EventPriority(Enum):
    """Event priority levels for different types of operations."""
    CRITICAL = 0    # Buy/sell orders, order cancellations
    HIGH = 1        # Order status updates, fills
    NORMAL = 2      # Market data updates, price ticks
    LOW = 3         # Account updates, P&L updates
    BACKGROUND = 4  # Logging, cleanup operations

@dataclass
class ThrottleConfig:
    """Configuration for throttling different event types."""
    max_events_per_second: int = 100  # Reduced from 1250 to prevent CPU overload
    sample_window_ms: int = 100  # How often to sample current data
    throttle_threshold: float = 0.8  # Start throttling at 80% capacity
    max_order_delay_ms: int = 750  # Maximum acceptable order delay

@dataclass
class MarketDataSample:
    """Represents a sampled market data point with timestamp."""
    data: Dict[str, Any]
    timestamp: float
    source: str  # Which subscription this came from

@dataclass
class PriorityMetrics:
    """Metrics for priority event processing."""
    events_processed: int = 0
    events_failed: int = 0
    avg_processing_time_ms: float = 0.0
    queue_size: int = 0
    last_processed_time: float = 0.0
    timeout_count: int = 0
    fallback_used: int = 0

class ResilientEventBus:
    """
    Multi-threaded, priority-based event bus with intelligent throttling and monitoring.
    
    Features:
    - Priority-based event processing with separate threads
    - Intelligent throttling to maintain order responsiveness
    - Market data sampling to preserve current price accuracy
    - Real-time monitoring of system performance
    - Automatic circuit breakers for extreme conditions
    - Enhanced priority processing with timeouts and fallbacks
    """
    
    def __init__(self, max_workers: int = 8, enable_monitoring: bool = True):
        """
        Initialize the resilient event bus.
        
        Args:
            max_workers: Maximum number of worker threads for normal priority events
            enable_monitoring: Whether to enable performance monitoring (default: True)
        """
        logger.debug("Initializing ResilientEventBus")
        
        # Priority-based event loops and threads
        self._priority_loops: Dict[EventPriority, asyncio.AbstractEventLoop] = {}
        self._priority_threads: Dict[EventPriority, threading.Thread] = {}
        self._priority_queues: Dict[EventPriority, deque] = {}
        
        # Enhanced priority monitoring
        self._priority_metrics: Dict[EventPriority, PriorityMetrics] = {}
        self._priority_timeouts: Dict[EventPriority, float] = {
            EventPriority.CRITICAL: 0.1,   # 100ms timeout for critical
            EventPriority.HIGH: 0.5,        # 500ms timeout for high
            EventPriority.NORMAL: 1.0,      # 1s timeout for normal
            EventPriority.LOW: 2.0,         # 2s timeout for low
            EventPriority.BACKGROUND: 5.0   # 5s timeout for background
        }
        
        # Priority processing health checks
        self._priority_health_checks: Dict[EventPriority, bool] = {}
        self._priority_circuit_breakers: Dict[EventPriority, bool] = {}
        
        # Throttling and monitoring
        self._throttle_config = ThrottleConfig()
        self._event_counters: Dict[str, int] = defaultdict(int)
        self._performance_metrics = {
            'total_events': 0,
            'throttled_events': 0,
            'avg_order_delay_ms': 0,
            'peak_events_per_second': 0,
            'priority_processing_stats': {}
        }
        
        # Event tracking for throttling
        self._event_timestamps = deque(maxlen=1000)  # Keep last 1000 events
        
        # Market data sampling
        self._market_data_samples: Dict[str, MarketDataSample] = {}
        
        # Order delay monitoring
        self._order_delay_monitor = OrderDelayMonitor()
        
        # Event handlers with thread safety
        self._handlers: Dict[str, List[Tuple[Callable, EventPriority]]] = defaultdict(list)
        self._handlers_lock = threading.RLock()  # Add thread safety
        self._request_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        
        # Worker pool for normal/lower priority events
        self._worker_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        
        # Stop flag for monitoring thread
        self._stop_flag = threading.Event()
        
        # Initialize priority system
        self._initialize_priority_system()
        
        # Start monitoring thread if enabled
        if enable_monitoring:
            self._start_monitoring_thread()
        
        logger.info("ResilientEventBus initialized successfully")
    
    def _initialize_priority_system(self):
        """Initialize separate event loops and threads for each priority level."""
        for priority in EventPriority:
            # Create event loop for this priority
            loop = asyncio.new_event_loop()
            self._priority_loops[priority] = loop
            self._priority_queues[priority] = deque(maxlen=1000)
            
            # Initialize priority metrics
            self._priority_metrics[priority] = PriorityMetrics()
            self._priority_health_checks[priority] = True
            self._priority_circuit_breakers[priority] = False
            
            # Create dedicated thread for critical and high priority
            if priority in [EventPriority.CRITICAL, EventPriority.HIGH]:
                thread = threading.Thread(
                    target=self._run_priority_loop,
                    args=(priority,),
                    name=f"EventBus-{priority.name}",
                    daemon=True
                )
                self._priority_threads[priority] = thread
                thread.start()
                logger.debug(f"Started dedicated thread for {priority.name} priority")
            
            # Normal and lower priorities share worker pool
            elif priority in [EventPriority.NORMAL, EventPriority.LOW, EventPriority.BACKGROUND]:
                # These will be processed by worker pool
                pass
    
    def _run_priority_loop(self, priority: EventPriority):
        """Run the event loop for a specific priority level."""
        loop = self._priority_loops[priority]
        asyncio.set_event_loop(loop)
        
        logger.info(f"Priority loop started for {priority.name}")
        
        try:
            # Use run_until_complete with a stop event instead of run_forever
            stop_event = asyncio.Event()
            
            def stop_loop():
                stop_event.set()
            
            # Schedule the stop event to be set when _stop_flag is set
            def check_stop():
                if self._stop_flag.is_set():
                    stop_event.set()
                else:
                    loop.call_later(0.1, check_stop)
            
            loop.call_soon(check_stop)
            loop.run_until_complete(stop_event.wait())
            
        except asyncio.CancelledError:
            # This is expected when the loop is being stopped
            logger.debug(f"Priority loop {priority.name} cancelled during shutdown")
        except Exception as e:
            logger.error(f"Priority loop {priority.name} failed: {e}")
            self._priority_health_checks[priority] = False
        finally:
            # Cancel all pending tasks before closing the loop
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    logger.debug(f"Cancelling {len(pending)} pending tasks in {priority.name} loop")
                    for task in pending:
                        task.cancel()
                    
                    # Wait for tasks to be cancelled
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.debug(f"Error cancelling tasks in {priority.name} loop: {e}")
            
            loop.close()
    
    def _start_monitoring_thread(self):
        """Start background monitoring thread for performance metrics."""
        def monitor_performance():
            while not self._stop_flag.is_set():
                try:
                    self._update_performance_metrics()
                    self._check_priority_health()
                    # Use wait instead of sleep to allow for graceful shutdown
                    if self._stop_flag.wait(timeout=5):  # Reduced frequency to every 5 seconds
                        break
                except Exception as e:
                    logger.error(f"Performance monitoring error: {e}")
        
        monitor_thread = threading.Thread(
            target=monitor_performance,
            name="EventBus-Monitor",
            daemon=True
        )
        monitor_thread.start()
        logger.debug("Performance monitoring thread started")
    
    def _check_priority_health(self):
        """Check health of priority processing systems."""
        for priority in EventPriority:
            metrics = self._priority_metrics[priority]
            current_time = time.time()
            
            # Check if priority system is responsive
            if metrics.last_processed_time > 0:
                time_since_last = current_time - metrics.last_processed_time
                timeout_threshold = self._priority_timeouts[priority]
                
                if time_since_last > timeout_threshold * 2:  # Double the timeout
                    logger.warning(f"Priority {priority.name} system appears unresponsive")
                    self._priority_health_checks[priority] = False
                else:
                    self._priority_health_checks[priority] = True
            
            # Check circuit breaker conditions
            if metrics.events_failed > 10 and metrics.events_processed > 0:
                failure_rate = metrics.events_failed / metrics.events_processed
                if failure_rate > 0.5:  # 50% failure rate
                    logger.error(f"Circuit breaker activated for {priority.name} priority")
                    self._priority_circuit_breakers[priority] = True
    
    def _update_performance_metrics(self):
        """Update performance metrics and adjust throttling if needed."""
        current_time = time.time()
        
        # Calculate events per second for each priority
        for priority in EventPriority:
            queue_size = len(self._priority_queues[priority])
            metrics = self._priority_metrics[priority]
            metrics.queue_size = queue_size
            
            if queue_size > 0:
                logger.debug(f"{priority.name} queue size: {queue_size}")
        
        # Update priority processing stats
        priority_stats = {}
        for priority in EventPriority:
            metrics = self._priority_metrics[priority]
            priority_stats[priority.name] = {
                'events_processed': metrics.events_processed,
                'events_failed': metrics.events_failed,
                'avg_processing_time_ms': metrics.avg_processing_time_ms,
                'queue_size': metrics.queue_size,
                'timeout_count': metrics.timeout_count,
                'fallback_used': metrics.fallback_used,
                'health_status': self._priority_health_checks[priority],
                'circuit_breaker_active': self._priority_circuit_breakers[priority]
            }
        
        self._performance_metrics['priority_processing_stats'] = priority_stats
        
        # Check order delay
        avg_delay = self._order_delay_monitor.get_average_delay()
        self._performance_metrics['avg_order_delay_ms'] = avg_delay
        
        # Adjust throttling if order delay is too high (only if we have order data)
        if avg_delay > 0:  # Only adjust if we have order delay data
            if avg_delay > self._throttle_config.max_order_delay_ms * 0.8:
                self._increase_throttling()
            elif avg_delay < self._throttle_config.max_order_delay_ms * 0.3:
                self._decrease_throttling()
    
    def _increase_throttling(self):
        """Increase throttling when system is under pressure."""
        old_limit = self._throttle_config.max_events_per_second
        self._throttle_config.max_events_per_second = max(10, old_limit - 5)
        logger.warning(f"Increased throttling: {old_limit} -> {self._throttle_config.max_events_per_second} events/sec")
    
    def _decrease_throttling(self):
        """Decrease throttling when system has capacity."""
        old_limit = self._throttle_config.max_events_per_second
        # Be more conservative - only decrease by 1 instead of 2
        self._throttle_config.max_events_per_second = min(50, old_limit + 1)
        logger.info(f"Decreased throttling: {old_limit} -> {self._throttle_config.max_events_per_second} events/sec")
    
    def emit(self, event_name: str, *args, priority: EventPriority = EventPriority.NORMAL, **kwargs):
        """
        Emit an event with priority-based processing.
        
        Args:
            event_name: Name of the event
            *args: Event arguments
            priority: Priority level for this event
            **kwargs: Event keyword arguments
        """
        current_time = time.time()
        
        # Update event counters
        self._event_counters[event_name] += 1
        self._performance_metrics['total_events'] += 1
        
        # Debug logging for first occurrence of each event type
        if self._event_counters[event_name] == 1:
            data = args[0] if args else kwargs
            logger.debug(f"FIRST EVENT: {event_name} - Priority: {priority} - Data: {data}")
        
        # Log event flow for comprehensive tracking
        source_module = "EVENT_BUS"
        target_module = "UNKNOWN"  # Will be determined during processing
        
        # Check circuit breaker for this priority
        if self._priority_circuit_breakers[priority]:
            logger.warning(f"Circuit breaker active for {priority.name} priority, skipping event {event_name}")
            # Log failed event due to circuit breaker
            log_event_flow(event_name, priority.name, source_module, target_module, 
                          success=False, error_message="Circuit breaker active")
            return
        
        # Check if we need to throttle this event
        if self._should_throttle_event(event_name, current_time):
            self._performance_metrics['throttled_events'] += 1
            logger.debug(f"Throttled event: {event_name}")
            # Log throttled event
            log_event_flow(event_name, priority.name, source_module, target_module, 
                          success=False, error_message="Event throttled")
            return
        
        # Handle market data events specially
        if event_name == 'market_data.tick_update':
            self._handle_market_data_tick(*args, **kwargs)
            return
        
        # Route to appropriate priority queue with enhanced processing
        # CRITICAL events get immediate processing in dedicated thread
        if priority == EventPriority.CRITICAL:
            # Critical events get immediate processing
            self._schedule_priority_event_with_timeout(priority, event_name, *args, **kwargs)
        elif priority == EventPriority.HIGH:
            # High priority events get dedicated thread with timeout
            self._schedule_priority_event_with_timeout(priority, event_name, *args, **kwargs)
        else:
            # Use worker pool for normal/lower priority
            self._schedule_worker_event(priority, event_name, *args, **kwargs)
    
    def _schedule_priority_event_with_timeout(self, priority: EventPriority, event_name: str, *args, **kwargs):
        """Schedule an event for processing in a dedicated priority thread with timeout and fallback."""
        loop = self._priority_loops[priority]
        metrics = self._priority_metrics[priority]
        
        async def process_event():
            start_time = time.time()
            target_modules = []
            success = True
            error_message = None
            
            try:
                if event_name in self._handlers:
                    for callback, _priority in self._handlers[event_name]:
                        # Determine target module from callback
                        target_module = getattr(callback, '__module__', 'UNKNOWN')
                        if target_module == '__main__':
                            target_module = 'MAIN'
                        target_modules.append(target_module)
                        
                        if asyncio.iscoroutinefunction(callback):
                            await callback(*args, **kwargs)
                        else:
                            callback(*args, **kwargs)
                
                # Update metrics
                end_time = time.time()
                processing_time = (end_time - start_time) * 1000
                metrics.events_processed += 1
                metrics.last_processed_time = end_time
                
                # Record performance metrics
                record_event_processing(event_name, processing_time, priority.name)
                
                # Update average processing time
                if metrics.avg_processing_time_ms == 0:
                    metrics.avg_processing_time_ms = processing_time
                else:
                    metrics.avg_processing_time_ms = (metrics.avg_processing_time_ms + processing_time) / 2
                
                # Update queue size metric
                metrics.queue_size = len(self._priority_queues[priority])
                
                logger.debug(f"Priority {priority.name} event {event_name} processed in {processing_time:.2f}ms")
                
                # Log successful event flow
                for target_module in target_modules:
                    log_event_flow(event_name, priority.name, "EVENT_BUS", target_module, 
                                  processing_time, success=True)
                
                # Log performance metrics
                log_performance("EVENT_BUS", f"priority_{priority.name.lower()}_processing", 
                              processing_time, queue_size=len(self._priority_queues[priority]))
                
            except asyncio.TimeoutError:
                metrics.timeout_count += 1
                metrics.events_failed += 1
                success = False
                error_message = "Timeout processing event"
                logger.error(f"Timeout processing {priority.name} event {event_name}")
                
                # Log failed event flow
                for target_module in target_modules:
                    log_event_flow(event_name, priority.name, "EVENT_BUS", target_module, 
                                  processing_time, success=False, error_message=error_message)
                
                self._handle_priority_fallback(priority, event_name, *args, **kwargs)
            except Exception as e:
                metrics.events_failed += 1
                success = False
                error_message = str(e)
                logger.error(f"Error processing {priority.name} event {event_name}: {e}")
                
                # Log failed event flow
                for target_module in target_modules:
                    log_event_flow(event_name, priority.name, "EVENT_BUS", target_module, 
                                  processing_time, success=False, error_message=error_message)
                
                self._handle_priority_fallback(priority, event_name, *args, **kwargs)
        
        # Schedule with timeout
        timeout = self._priority_timeouts[priority]
        try:
            # Use asyncio.wait_for to implement actual timeout
            async def timeout_wrapper():
                return await asyncio.wait_for(process_event(), timeout=timeout)
            
            future = asyncio.run_coroutine_threadsafe(timeout_wrapper(), loop)
        except Exception as e:
            logger.error(f"Failed to schedule {priority.name} event {event_name}: {e}")
            # Log scheduling failure
            log_event_flow(event_name, priority.name, "EVENT_BUS", "UNKNOWN", 
                          success=False, error_message=f"Failed to schedule: {e}")
            self._handle_priority_fallback(priority, event_name, *args, **kwargs)
    
    def _handle_priority_fallback(self, priority: EventPriority, event_name: str, *args, **kwargs):
        """Handle fallback processing when priority event fails."""
        metrics = self._priority_metrics[priority]
        metrics.fallback_used += 1
        
        logger.warning(f"Using fallback processing for {priority.name} event {event_name}")
        
        # Fallback to worker pool processing
        try:
            self._schedule_worker_event(priority, event_name, *args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback processing also failed for {event_name}: {e}")
    
    def _should_throttle_event(self, event_name: str, current_time: float) -> bool:
        """Determine if an event should be throttled based on current load."""
        # Never throttle critical events
        if event_name in ['order.place', 'order.cancel', 'sell_active_position']:
            return False
        
        # Track this event's timestamp
        self._event_timestamps.append(current_time)
        
        # Count events in the last second
        events_last_second = sum(
            1 for timestamp in self._event_timestamps
            if current_time - timestamp < 1.0
        )
        
        # Check if we're at capacity
        if events_last_second >= self._throttle_config.max_events_per_second:
            logger.debug(f"Throttling event {event_name}: {events_last_second} events in last second >= {self._throttle_config.max_events_per_second}")
            return True
        
        # Only log throttling decisions at debug level to reduce noise
        logger.debug(f"Not throttling event {event_name}: {events_last_second} events in last second < {self._throttle_config.max_events_per_second}")
        return False
    
    def _handle_market_data_tick(self, *args, **kwargs):
        """Special handling for market data ticks with intelligent sampling."""
        data = args[0] if args else kwargs
        
        # Extract contract identifier
        contract_info = data.get('contract', {})
        contract_id = self._get_contract_id(contract_info)
        
        if not contract_id:
            return
        
        current_time = time.time()
        
        # Check if we should sample this tick
        last_sample = self._market_data_samples.get(contract_id)
        if last_sample and (current_time - last_sample.timestamp) < (self._throttle_config.sample_window_ms / 1000.0):
            # Skip this tick but update the sample if it's more recent
            if current_time > last_sample.timestamp:
                self._market_data_samples[contract_id] = MarketDataSample(
                    data=data,
                    timestamp=current_time,
                    source=contract_id
                )
            return
        
        # Create new sample
        self._market_data_samples[contract_id] = MarketDataSample(
            data=data,
            timestamp=current_time,
            source=contract_id
        )
        
        # Process the tick through normal event system
        self._schedule_worker_event(EventPriority.NORMAL, 'market_data.tick_update', data)
    
    def _get_contract_id(self, contract_info: Dict) -> Optional[str]:
        """Extract a unique contract identifier from contract info."""
        if isinstance(contract_info, dict):
            symbol = contract_info.get('symbol', '')
            sec_type = contract_info.get('secType', '')
            if sec_type == 'OPT':
                strike = contract_info.get('strike', '')
                right = contract_info.get('right', '')
                expiry = contract_info.get('lastTradeDateOrContractMonth', '')
                return f"{symbol}_{strike}_{right}_{expiry}"
            else:
                return f"{symbol}_{sec_type}"
        return None
    
    def _schedule_priority_event(self, priority: EventPriority, event_name: str, *args, **kwargs):
        """Schedule an event for processing in a dedicated priority thread."""
        loop = self._priority_loops[priority]
        
        async def process_event():
            try:
                if event_name in self._handlers:
                    for callback, _priority in self._handlers[event_name]:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(*args, **kwargs)
                        else:
                            callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error processing {priority.name} event {event_name}: {e}")
        
        # Schedule in the appropriate event loop
        asyncio.run_coroutine_threadsafe(process_event(), loop)
    
    def _schedule_worker_event(self, priority: EventPriority, event_name: str, *args, **kwargs):
        """Schedule an event for processing in the worker pool."""
        def process_event():
            start_time = time.time()
            metrics = self._priority_metrics[priority]
            target_modules = []
            success = True
            error_message = None
            
            try:
                # Use thread safety when accessing handlers
                handlers_copy = []
                with self._handlers_lock:
                    if event_name in self._handlers:
                        # Create a copy of handlers to avoid modification during iteration
                        handlers_copy = self._handlers[event_name].copy()
                
                # Process handlers outside the lock to avoid deadlocks
                for callback, _priority in handlers_copy:
                    # Determine target module from callback
                    target_module = getattr(callback, '__module__', 'UNKNOWN')
                    if target_module == '__main__':
                        target_module = 'MAIN'
                    target_modules.append(target_module)
                    
                    # Check if callback is async and handle accordingly
                    if asyncio.iscoroutinefunction(callback):
                        # Create new event loop for async callback
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(callback(*args, **kwargs))
                        finally:
                            loop.close()
                    else:
                        # Regular synchronous callback
                        callback(*args, **kwargs)
                
                # Update metrics
                end_time = time.time()
                processing_time = (end_time - start_time) * 1000
                metrics.events_processed += 1
                metrics.last_processed_time = end_time
                
                # Record performance metrics
                record_event_processing(event_name, processing_time, priority.name)
                
                # Update average processing time
                if metrics.avg_processing_time_ms == 0:
                    metrics.avg_processing_time_ms = processing_time
                else:
                    metrics.avg_processing_time_ms = (metrics.avg_processing_time_ms + processing_time) / 2
                
                # Log successful event flow
                for target_module in target_modules:
                    log_event_flow(event_name, priority.name, "EVENT_BUS", target_module, 
                                  processing_time, success=True)
                
                # Log performance metrics
                log_performance("EVENT_BUS", f"worker_{priority.name.lower()}_processing", 
                              processing_time, queue_size=len(self._priority_queues[priority]))
                
            except Exception as e:
                metrics.events_failed += 1
                success = False
                error_message = str(e)
                logger.error(f"Error processing {priority.name} event {event_name}: {e}")
                
                # Log failed event flow
                for target_module in target_modules:
                    log_event_flow(event_name, priority.name, "EVENT_BUS", target_module, 
                                  processing_time, success=False, error_message=error_message)
                
                # Don't call fallback again if we're already in fallback mode
                if not hasattr(process_event, '_is_fallback'):
                    process_event._is_fallback = True
                    self._handle_priority_fallback(priority, event_name, *args, **kwargs)
        
        # Submit to worker pool
        self._worker_pool.submit(process_event)
    
    def on(self, event_name: str, callback: Callable, priority: EventPriority = EventPriority.NORMAL):
        """
        Subscribe to an event with priority level.
        
        Args:
            event_name: Name of the event to listen for
            callback: Function to call when event occurs
            priority: Priority level for this subscription
        """
        with self._handlers_lock:
            self._handlers[event_name].append((callback, priority))
        logger.debug(f"Listener registered for '{event_name}' with {priority.name} priority")
    
    def request(self, request_name: str, *args, **kwargs) -> concurrent.futures.Future[Any]:
        """
        Make an asynchronous request (always high priority).
        
        Args:
            request_name: Name of the request
            *args: Request arguments
            **kwargs: Request keyword arguments
            
        Returns:
            Future that will resolve with the result
        """
        logger.debug(f"Making request '{request_name}'")
        
        # Always use critical priority for requests
        loop = self._priority_loops[EventPriority.CRITICAL]
        
        async def handle_request():
            if request_name in self._request_handlers:
                handler = self._request_handlers[request_name]
                return await handler(*args, **kwargs)
            else:
                raise ValueError(f"No handler registered for request '{request_name}'")
        
        future = asyncio.run_coroutine_threadsafe(handle_request(), loop)
        return future
    
    def register_request_handler(self, request_name: str, handler: Callable[..., Awaitable[Any]]):
        """Register a request handler."""
        self._request_handlers[request_name] = handler
        logger.debug(f"Request handler registered for '{request_name}'")
    
    def get_market_data_sample(self, contract_id: str) -> Optional[MarketDataSample]:
        """Get the most recent market data sample for a contract."""
        return self._market_data_samples.get(contract_id)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self._performance_metrics.copy()
    
    def get_priority_health_status(self) -> Dict[str, bool]:
        """Get health status of all priority systems."""
        return self._priority_health_checks.copy()
    
    def get_priority_circuit_breaker_status(self) -> Dict[str, bool]:
        """Get circuit breaker status for all priority systems."""
        return self._priority_circuit_breakers.copy()
    
    def reset_priority_circuit_breaker(self, priority: EventPriority):
        """Reset circuit breaker for a specific priority level."""
        self._priority_circuit_breakers[priority] = False
        metrics = self._priority_metrics[priority]
        metrics.events_failed = 0
        logger.info(f"Circuit breaker reset for {priority.name} priority")
    
    def stop(self):
        """Stop the event bus and clean up resources."""
        logger.info("Stopping ResilientEventBus...")
        
        # Set stop flag to signal monitoring thread to stop
        self._stop_flag.set()
        
        # Stop all priority loops gracefully
        for priority, loop in self._priority_loops.items():
            try:
                # Cancel all pending tasks first
                pending = asyncio.all_tasks(loop)
                if pending:
                    logger.debug(f"Cancelling {len(pending)} pending tasks in {priority.name} loop")
                    for task in pending:
                        task.cancel()
                
                # Stop the loop
                loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                logger.warning(f"Error stopping priority loop {priority}: {e}")
        
        # Stop worker pool
        try:
            self._worker_pool.shutdown(wait=True)
        except Exception as e:
            logger.warning(f"Error shutting down worker pool: {e}")
        
        # Wait for threads to finish with shorter timeout
        for priority, thread in self._priority_threads.items():
            try:
                thread.join(timeout=1)  # Reduced timeout to 1 second
                if thread.is_alive():
                    logger.warning(f"Thread {priority} did not stop gracefully")
            except Exception as e:
                logger.warning(f"Error joining thread {priority}: {e}")
        
        # Wait for monitoring thread
        if hasattr(self, '_monitoring_thread') and self._monitoring_thread:
            try:
                self._monitoring_thread.join(timeout=1)
                if self._monitoring_thread.is_alive():
                    logger.warning("Monitoring thread did not stop gracefully")
            except Exception as e:
                logger.warning(f"Error joining monitoring thread: {e}")
        
        # Force stop any remaining threads
        for priority, thread in self._priority_threads.items():
            if thread.is_alive():
                logger.warning(f"Force stopping thread {priority}")
                # Note: We can't force kill threads in Python, but we can log it
        
        logger.info("ResilientEventBus stopped")

class OrderDelayMonitor:
    """Monitors order processing delays to adjust throttling."""
    
    def __init__(self, window_size: int = 100):
        self._order_times: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()
    
    def record_order_start(self, order_id: str):
        """Record when an order processing starts."""
        with self._lock:
            self._order_times.append(('start', order_id, time.time()))
    
    def record_order_complete(self, order_id: str):
        """Record when an order processing completes."""
        with self._lock:
            self._order_times.append(('complete', order_id, time.time()))
    
    def get_average_delay(self) -> float:
        """Calculate average order processing delay in milliseconds."""
        with self._lock:
            if len(self._order_times) < 2:
                return 0.0
            
            delays = []
            start_times = {}
            
            for event_type, order_id, timestamp in self._order_times:
                if event_type == 'start':
                    start_times[order_id] = timestamp
                elif event_type == 'complete' and order_id in start_times:
                    delay_ms = (timestamp - start_times[order_id]) * 1000
                    delays.append(delay_ms)
            
            if delays:
                return sum(delays) / len(delays)
            return 0.0

# Backward compatibility - alias for existing code
EventBus = ResilientEventBus