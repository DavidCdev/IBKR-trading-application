import logging
import json
import time
import threading
import os
import glob
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import queue
from logger import get_logger

logger = get_logger('ENHANCED_LOGGING')

class LogCategory(Enum):
    """Categories for structured logging."""
    EVENT_FLOW = "event_flow"
    PERFORMANCE = "performance"
    CONNECTION = "connection"
    ERROR = "error"
    SECURITY = "security"
    BUSINESS = "business"

@dataclass
class EventFlowLog:
    """Structured log entry for event flow tracking."""
    timestamp: float
    event_name: str
    priority: str
    source_module: str
    target_module: str
    event_id: str
    processing_time_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class PerformanceLog:
    """Structured log entry for performance monitoring."""
    timestamp: float
    module: str
    operation: str
    duration_ms: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    queue_size: Optional[int] = None
    throughput_events_per_sec: Optional[float] = None

@dataclass
class ConnectionStateLog:
    """Structured log entry for connection state tracking."""
    timestamp: float
    connection_id: str
    state: str  # connecting, connected, disconnected, error
    host: str
    port: int
    latency_ms: Optional[float] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0

class EnhancedLoggingManager:
    """
    Enhanced logging manager with comprehensive tracking capabilities.
    
    Features:
    - Event flow tracking with unique IDs
    - Performance monitoring with metrics
    - Connection state tracking
    - Structured JSON logging
    - Log rotation and management
    - Real-time monitoring
    """
    
    def __init__(self, config_manager=None, log_dir: str = "logs"):
        """
        Initialize the enhanced logging manager.
        
        Args:
            config_manager: Configuration manager instance
            log_dir: Directory for log files
        """
        self.config_manager = config_manager
        self.log_dir = log_dir
        self._setup_log_directory()
        
        # Event flow tracking
        self._event_flow_logs: deque = deque(maxlen=10000)
        self._event_counter = 0
        self._event_lock = threading.Lock()
        
        # Performance tracking
        self._performance_logs: deque = deque(maxlen=5000)
        self._performance_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._performance_lock = threading.Lock()
        
        # Connection state tracking
        self._connection_logs: deque = deque(maxlen=1000)
        self._connection_states: Dict[str, str] = {}
        self._connection_lock = threading.Lock()
        
        # Structured logging
        self._structured_logs: queue.Queue = queue.Queue(maxsize=10000)
        self._log_worker_thread = None
        self._stop_logging = threading.Event()
        
        # Start log worker thread
        self._start_log_worker()
        
        logger.info("EnhancedLoggingManager initialized successfully")
    
    def _setup_log_directory(self):
        """Create log directory and set up file handlers."""
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create separate log files for different categories
        self._setup_file_handlers()
    
    def _setup_file_handlers(self):
        """Set up file handlers for different log categories."""
        # Event flow log file
        event_flow_handler = logging.FileHandler(
            os.path.join(self.log_dir, "event_flow.log"),
            mode='a',
            encoding='utf-8'
        )
        event_flow_handler.setLevel(logging.DEBUG)
        event_flow_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        event_flow_handler.setFormatter(event_flow_formatter)
        
        # Performance log file
        performance_handler = logging.FileHandler(
            os.path.join(self.log_dir, "performance.log"),
            mode='a',
            encoding='utf-8'
        )
        performance_handler.setLevel(logging.DEBUG)
        performance_handler.setFormatter(event_flow_formatter)
        
        # Connection state log file
        connection_handler = logging.FileHandler(
            os.path.join(self.log_dir, "connection.log"),
            mode='a',
            encoding='utf-8'
        )
        connection_handler.setLevel(logging.DEBUG)
        connection_handler.setFormatter(event_flow_formatter)
        
        # Add handlers to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(event_flow_handler)
        root_logger.addHandler(performance_handler)
        root_logger.addHandler(connection_handler)
    
    def _start_log_worker(self):
        """Start background thread for processing structured logs."""
        def log_worker():
            while not self._stop_logging.is_set():
                try:
                    # Process structured logs with timeout
                    log_entry = self._structured_logs.get(timeout=1.0)
                    self._process_structured_log(log_entry)
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in log worker: {e}")
        
        self._log_worker_thread = threading.Thread(
            target=log_worker,
            name="EnhancedLogging-Worker",
            daemon=True
        )
        self._log_worker_thread.start()
        logger.debug("Log worker thread started")
    
    def _process_structured_log(self, log_entry: Dict[str, Any]):
        """Process a structured log entry."""
        try:
            category = log_entry.get('category')
            if category == LogCategory.EVENT_FLOW.value:
                self._log_event_flow(log_entry)
            elif category == LogCategory.PERFORMANCE.value:
                self._log_performance(log_entry)
            elif category == LogCategory.CONNECTION.value:
                self._log_connection_state(log_entry)
            else:
                # Write to general log
                logger.info(json.dumps(log_entry))
        except Exception as e:
            logger.error(f"Error processing structured log: {e}")
    
    def _log_event_flow(self, log_data: Dict[str, Any]):
        """Log event flow data."""
        with self._event_lock:
            event_log = EventFlowLog(
                timestamp=log_data.get('timestamp', time.time()),
                event_name=log_data.get('event_name', ''),
                priority=log_data.get('priority', 'NORMAL'),
                source_module=log_data.get('source_module', ''),
                target_module=log_data.get('target_module', ''),
                event_id=log_data.get('event_id', ''),
                processing_time_ms=log_data.get('processing_time_ms'),
                success=log_data.get('success', True),
                error_message=log_data.get('error_message'),
                metadata=log_data.get('metadata', {})
            )
            self._event_flow_logs.append(event_log)
            
            # Log to file
            logger.debug(f"EVENT_FLOW: {json.dumps(asdict(event_log))}")
    
    def _log_performance(self, log_data: Dict[str, Any]):
        """Log performance data."""
        with self._performance_lock:
            perf_log = PerformanceLog(
                timestamp=log_data.get('timestamp', time.time()),
                module=log_data.get('module', ''),
                operation=log_data.get('operation', ''),
                duration_ms=log_data.get('duration_ms', 0.0),
                memory_usage_mb=log_data.get('memory_usage_mb'),
                cpu_usage_percent=log_data.get('cpu_usage_percent'),
                queue_size=log_data.get('queue_size'),
                throughput_events_per_sec=log_data.get('throughput_events_per_sec')
            )
            self._performance_logs.append(perf_log)
            
            # Update performance metrics
            module = perf_log.module
            if module not in self._performance_metrics:
                self._performance_metrics[module] = {
                    'total_operations': 0,
                    'total_duration_ms': 0.0,
                    'avg_duration_ms': 0.0,
                    'max_duration_ms': 0.0,
                    'min_duration_ms': float('inf'),
                    'last_operation': None
                }
            
            metrics = self._performance_metrics[module]
            metrics['total_operations'] += 1
            metrics['total_duration_ms'] += perf_log.duration_ms
            metrics['avg_duration_ms'] = metrics['total_duration_ms'] / metrics['total_operations']
            metrics['max_duration_ms'] = max(metrics['max_duration_ms'], perf_log.duration_ms)
            metrics['min_duration_ms'] = min(metrics['min_duration_ms'], perf_log.duration_ms)
            metrics['last_operation'] = perf_log.timestamp
            
            # Log to file
            logger.debug(f"PERFORMANCE: {json.dumps(asdict(perf_log))}")
    
    def _log_connection_state(self, log_data: Dict[str, Any]):
        """Log connection state data."""
        with self._connection_lock:
            conn_log = ConnectionStateLog(
                timestamp=log_data.get('timestamp', time.time()),
                connection_id=log_data.get('connection_id', ''),
                state=log_data.get('state', ''),
                host=log_data.get('host', ''),
                port=log_data.get('port', 0),
                latency_ms=log_data.get('latency_ms'),
                error_code=log_data.get('error_code'),
                error_message=log_data.get('error_message'),
                retry_count=log_data.get('retry_count', 0)
            )
            self._connection_logs.append(conn_log)
            
            # Update connection state
            self._connection_states[conn_log.connection_id] = conn_log.state
            
            # Log to file
            logger.debug(f"CONNECTION: {json.dumps(asdict(conn_log))}")
    
    def log_event_flow(self, event_name: str, priority: str, source_module: str, 
                      target_module: str, processing_time_ms: Optional[float] = None,
                      success: bool = True, error_message: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None):
        """
        Log event flow with structured data.
        
        Args:
            event_name: Name of the event
            priority: Event priority
            source_module: Module that emitted the event
            target_module: Module that processed the event
            processing_time_ms: Time taken to process the event
            success: Whether the event was processed successfully
            error_message: Error message if processing failed
            metadata: Additional metadata
        """
        with self._event_lock:
            self._event_counter += 1
            event_id = f"evt_{self._event_counter}_{int(time.time())}"
        
        log_entry = {
            'category': LogCategory.EVENT_FLOW.value,
            'timestamp': time.time(),
            'event_name': event_name,
            'priority': priority,
            'source_module': source_module,
            'target_module': target_module,
            'event_id': event_id,
            'processing_time_ms': processing_time_ms,
            'success': success,
            'error_message': error_message,
            'metadata': metadata or {}
        }
        
        try:
            self._structured_logs.put_nowait(log_entry)
        except queue.Full:
            logger.warning("Log queue full, dropping event flow log entry")
    
    def log_performance(self, module: str, operation: str, duration_ms: float,
                       memory_usage_mb: Optional[float] = None,
                       cpu_usage_percent: Optional[float] = None,
                       queue_size: Optional[int] = None,
                       throughput_events_per_sec: Optional[float] = None):
        """
        Log performance metrics.
        
        Args:
            module: Module name
            operation: Operation name
            duration_ms: Duration in milliseconds
            memory_usage_mb: Memory usage in MB
            cpu_usage_percent: CPU usage percentage
            queue_size: Current queue size
            throughput_events_per_sec: Events per second
        """
        log_entry = {
            'category': LogCategory.PERFORMANCE.value,
            'timestamp': time.time(),
            'module': module,
            'operation': operation,
            'duration_ms': duration_ms,
            'memory_usage_mb': memory_usage_mb,
            'cpu_usage_percent': cpu_usage_percent,
            'queue_size': queue_size,
            'throughput_events_per_sec': throughput_events_per_sec
        }
        
        try:
            self._structured_logs.put_nowait(log_entry)
        except queue.Full:
            logger.warning("Log queue full, dropping performance log entry")
    
    def log_connection_state(self, connection_id: str, state: str, host: str, port: int,
                           latency_ms: Optional[float] = None,
                           error_code: Optional[int] = None,
                           error_message: Optional[str] = None,
                           retry_count: int = 0):
        """
        Log connection state changes.
        
        Args:
            connection_id: Unique connection identifier
            state: Connection state (connecting, connected, disconnected, error)
            host: Connection host
            port: Connection port
            latency_ms: Connection latency in milliseconds
            error_code: Error code if applicable
            error_message: Error message if applicable
            retry_count: Number of retry attempts
        """
        log_entry = {
            'category': LogCategory.CONNECTION.value,
            'timestamp': time.time(),
            'connection_id': connection_id,
            'state': state,
            'host': host,
            'port': port,
            'latency_ms': latency_ms,
            'error_code': error_code,
            'error_message': error_message,
            'retry_count': retry_count
        }
        
        try:
            self._structured_logs.put_nowait(log_entry)
        except queue.Full:
            logger.warning("Log queue full, dropping connection log entry")
    
    def get_event_flow_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get event flow summary for the specified time window."""
        cutoff_time = time.time() - (time_window_minutes * 60)
        
        with self._event_lock:
            recent_events = [
                event for event in self._event_flow_logs
                if event.timestamp >= cutoff_time
            ]
        
        if not recent_events:
            return {
                'total_events': 0,
                'successful_events': 0,
                'failed_events': 0,
                'avg_processing_time_ms': 0.0,
                'events_by_priority': {},
                'events_by_module': {}
            }
        
        # Calculate summary statistics
        total_events = len(recent_events)
        successful_events = sum(1 for event in recent_events if event.success)
        failed_events = total_events - successful_events
        
        # Calculate average processing time
        processing_times = [
            event.processing_time_ms for event in recent_events
            if event.processing_time_ms is not None
        ]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
        
        # Group by priority
        events_by_priority = defaultdict(int)
        for event in recent_events:
            events_by_priority[event.priority] += 1
        
        # Group by module
        events_by_module = defaultdict(int)
        for event in recent_events:
            events_by_module[event.target_module] += 1
        
        return {
            'total_events': total_events,
            'successful_events': successful_events,
            'failed_events': failed_events,
            'avg_processing_time_ms': avg_processing_time,
            'events_by_priority': dict(events_by_priority),
            'events_by_module': dict(events_by_module),
            'time_window_minutes': time_window_minutes
        }
    
    def get_performance_summary(self, module: Optional[str] = None) -> Dict[str, Any]:
        """Get performance summary for all modules or a specific module."""
        with self._performance_lock:
            if module:
                return self._performance_metrics.get(module, {})
            else:
                return dict(self._performance_metrics)
    
    def get_connection_summary(self) -> Dict[str, Any]:
        """Get connection state summary."""
        with self._connection_lock:
            return {
                'current_states': dict(self._connection_states),
                'total_connections': len(self._connection_logs),
                'recent_connections': len([
                    conn for conn in self._connection_logs
                    if conn.timestamp >= time.time() - 3600  # Last hour
                ])
            }
    
    def cleanup_old_logs(self, max_age_days: int = 7):
        """Clean up old log files."""
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        for log_file in glob.glob(os.path.join(self.log_dir, "*.log")):
            try:
                file_age = os.path.getmtime(log_file)
                if file_age < cutoff_time:
                    os.remove(log_file)
                    logger.info(f"Removed old log file: {log_file}")
            except Exception as e:
                logger.error(f"Error cleaning up log file {log_file}: {e}")
    
    def rotate_logs(self):
        """Rotate log files by creating new files with timestamps."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for log_file in glob.glob(os.path.join(self.log_dir, "*.log")):
            try:
                base_name = os.path.splitext(log_file)[0]
                new_name = f"{base_name}_{timestamp}.log"
                os.rename(log_file, new_name)
                logger.info(f"Rotated log file: {log_file} -> {new_name}")
            except Exception as e:
                logger.error(f"Error rotating log file {log_file}: {e}")
    
    def stop(self):
        """Stop the enhanced logging manager."""
        logger.info("Stopping EnhancedLoggingManager...")
        self._stop_logging.set()
        
        if self._log_worker_thread:
            self._log_worker_thread.join(timeout=5)
        
        logger.info("EnhancedLoggingManager stopped")

# Global instance
_enhanced_logging_manager: Optional[EnhancedLoggingManager] = None

def get_enhanced_logging_manager() -> EnhancedLoggingManager:
    """Get the global enhanced logging manager instance."""
    global _enhanced_logging_manager
    if _enhanced_logging_manager is None:
        _enhanced_logging_manager = EnhancedLoggingManager()
    return _enhanced_logging_manager

def initialize_enhanced_logging(config_manager=None, log_dir: str = "logs"):
    """Initialize the global enhanced logging manager."""
    global _enhanced_logging_manager
    _enhanced_logging_manager = EnhancedLoggingManager(config_manager, log_dir)

def log_event_flow(event_name: str, priority: str, source_module: str, 
                  target_module: str, processing_time_ms: Optional[float] = None,
                  success: bool = True, error_message: Optional[str] = None,
                  metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to log event flow."""
    manager = get_enhanced_logging_manager()
    manager.log_event_flow(event_name, priority, source_module, target_module,
                          processing_time_ms, success, error_message, metadata)

def log_performance(module: str, operation: str, duration_ms: float,
                   memory_usage_mb: Optional[float] = None,
                   cpu_usage_percent: Optional[float] = None,
                   queue_size: Optional[int] = None,
                   throughput_events_per_sec: Optional[float] = None):
    """Convenience function to log performance."""
    manager = get_enhanced_logging_manager()
    manager.log_performance(module, operation, duration_ms, memory_usage_mb,
                           cpu_usage_percent, queue_size, throughput_events_per_sec)

def log_connection_state(connection_id: str, state: str, host: str, port: int,
                        latency_ms: Optional[float] = None,
                        error_code: Optional[int] = None,
                        error_message: Optional[str] = None,
                        retry_count: int = 0):
    """Convenience function to log connection state."""
    manager = get_enhanced_logging_manager()
    manager.log_connection_state(connection_id, state, host, port, latency_ms,
                                error_code, error_message, retry_count) 