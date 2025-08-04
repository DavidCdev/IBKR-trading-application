"""
Enhanced Event Monitor - Advanced event bus monitoring with subscription tracking
================================================================================

Provides comprehensive monitoring of:
- Individual subscription options from IB connections
- Memory leak detection and prevention
- Subscription lifecycle tracking
- Performance metrics and optimization
- Real-time subscription status

Key Features:
- Tracks individual market data subscriptions
- Monitors memory usage and detects leaks
- Shows subscription details and status
- Provides subscription management capabilities
- Real-time performance metrics
"""

import threading
import time
import gc
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List, Set
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import json
from logger import get_logger
from event_bus import EventBus, EventPriority

logger = get_logger('ENHANCED_EVENT_MONITOR')

class SubscriptionType(Enum):
    """Types of subscriptions that can be tracked."""
    MARKET_DATA = "market_data"
    ACCOUNT_DATA = "account_data"
    POSITIONS = "positions"
    ORDERS = "orders"
    OPTIONS_CHAIN = "options_chain"
    FOREX = "forex"
    UNDERLYING = "underlying"

class SubscriptionStatus(Enum):
    """Status of a subscription."""
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

@dataclass
class SubscriptionInfo:
    """Detailed information about a subscription."""
    subscription_id: str
    subscription_type: SubscriptionType
    contract: Dict[str, Any]
    status: SubscriptionStatus
    created_time: datetime
    last_update_time: datetime
    error_count: int = 0
    last_error: Optional[str] = None
    data_count: int = 0
    last_data: Optional[Dict[str, Any]] = None
    memory_usage_mb: float = 0.0
    priority: EventPriority = EventPriority.NORMAL

@dataclass
class MemoryMetrics:
    """Memory usage metrics."""
    current_memory_mb: float
    peak_memory_mb: float
    memory_growth_rate_mb_per_min: float
    gc_collected_objects: int
    gc_uncollectable_objects: int
    timestamp: datetime

class MemoryLeakDetector:
    """Detects and reports memory leaks."""
    
    def __init__(self, warning_threshold_mb: float = 1000.0, critical_threshold_mb: float = 2000.0):
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.memory_history: deque = deque(maxlen=100)
        self.leak_warnings: List[str] = []
        self.last_cleanup_time = time.time()
        
    def record_memory_usage(self) -> MemoryMetrics:
        """Record current memory usage."""
        process = psutil.Process(os.getpid())
        current_memory_mb = process.memory_info().rss / 1024 / 1024
        
        # Get garbage collection stats
        gc_stats = gc.get_stats()
        collected_objects = sum(stat['collections'] for stat in gc_stats)
        uncollectable_objects = sum(stat['uncollectable'] for stat in gc_stats)
        
        # Calculate memory growth rate
        memory_growth_rate = 0.0
        if len(self.memory_history) >= 2:
            time_diff = (datetime.now() - self.memory_history[-1].timestamp).total_seconds() / 60.0
            if time_diff > 0:
                memory_diff = current_memory_mb - self.memory_history[-1].current_memory_mb
                memory_growth_rate = memory_diff / time_diff
        
        metrics = MemoryMetrics(
            current_memory_mb=current_memory_mb,
            peak_memory_mb=max(current_memory_mb, self.memory_history[-1].peak_memory_mb if self.memory_history else 0),
            memory_growth_rate_mb_per_min=memory_growth_rate,
            gc_collected_objects=collected_objects,
            gc_uncollectable_objects=uncollectable_objects,
            timestamp=datetime.now()
        )
        
        self.memory_history.append(metrics)
        
        # Check for memory leaks
        self._check_memory_leak(metrics)
        
        return metrics
    
    def _check_memory_leak(self, metrics: MemoryMetrics):
        """Check for potential memory leaks."""
        if metrics.current_memory_mb > self.critical_threshold_mb:
            warning = f"CRITICAL: Memory usage {metrics.current_memory_mb:.1f}MB exceeds {self.critical_threshold_mb}MB"
            if warning not in self.leak_warnings:
                self.leak_warnings.append(warning)
                logger.critical(warning)
        elif metrics.current_memory_mb > self.warning_threshold_mb:
            warning = f"WARNING: Memory usage {metrics.current_memory_mb:.1f}MB exceeds {self.warning_threshold_mb}MB"
            if warning not in self.leak_warnings:
                self.leak_warnings.append(warning)
                logger.warning(warning)
        
        # Check for rapid memory growth
        if metrics.memory_growth_rate_mb_per_min > 50.0:  # 50MB per minute
            warning = f"WARNING: Rapid memory growth detected: {metrics.memory_growth_rate_mb_per_min:.1f}MB/min"
            if warning not in self.leak_warnings:
                self.leak_warnings.append(warning)
                logger.warning(warning)
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of memory usage."""
        if not self.memory_history:
            return {"error": "No memory data available"}
        
        latest = self.memory_history[-1]
        return {
            "current_memory_mb": latest.current_memory_mb,
            "peak_memory_mb": latest.peak_memory_mb,
            "memory_growth_rate_mb_per_min": latest.memory_growth_rate_mb_per_min,
            "gc_collected_objects": latest.gc_collected_objects,
            "gc_uncollectable_objects": latest.gc_uncollectable_objects,
            "warnings": self.leak_warnings[-10:] if self.leak_warnings else []
        }

class EnhancedEventMonitor:
    """
    Enhanced event monitor with subscription tracking and memory leak detection.
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the enhanced event monitor.
        
        Args:
            event_bus: The event bus to monitor
        """
        self.event_bus = event_bus
        
        # Subscription tracking
        self.subscriptions: Dict[str, SubscriptionInfo] = {}
        self.subscription_counter = 0
        
        # Event tracking
        self.event_records: Dict[str, Dict[str, Any]] = {}
        self.event_history: deque = deque(maxlen=1000)
        
        # Memory leak detection
        self.memory_detector = MemoryLeakDetector()
        
        # Performance metrics
        self.performance_metrics = {
            'total_events': 0,
            'events_per_second': 0,
            'avg_processing_time_ms': 0,
            'subscription_count': 0,
            'active_subscriptions': 0
        }
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Callbacks for GUI updates
        self._update_callbacks: List[Callable] = []
        
        # Memory management
        self._last_cleanup_time = time.time()
        self._cleanup_interval = 30.0
        self._max_records = 2000
        
        # Start monitoring
        self._start_monitoring()
        
        logger.info("Enhanced Event Monitor initialized")
    
    def _start_monitoring(self):
        """Start monitoring the event bus."""
        original_emit = self.event_bus.emit
        
        def monitored_emit(event_name: str, *args, priority: EventPriority = EventPriority.NORMAL, **kwargs):
            """Monitored version of emit that tracks all events and subscriptions."""
            try:
                # Record the event
                self._record_event(event_name, priority, args, kwargs)
                
                # Track subscriptions
                self._track_subscription_event(event_name, args, kwargs)
                
                # Call the original emit method
                return original_emit(event_name, *args, priority=priority, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in monitored emit: {e}")
                return original_emit(event_name, *args, priority=priority, **kwargs)
        
        # Replace the emit method
        self.event_bus.emit = monitored_emit
        logger.info("Enhanced event bus monitoring started")
    
    def _record_event(self, event_name: str, priority: EventPriority, args: tuple, kwargs: dict):
        """Record an event occurrence."""
        with self._lock:
            current_time = datetime.now()
            data = args[0] if args else kwargs
            
            # Update event record
            if event_name in self.event_records:
                record = self.event_records[event_name]
                record['count'] += 1
                record['last_seen'] = current_time
                record['last_data'] = data
                record['last_priority'] = priority
            else:
                record = {
                    'event_name': event_name,
                    'priority': priority,
                    'count': 1,
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'last_data': data,
                    'last_priority': priority
                }
                self.event_records[event_name] = record
            
            # Add to history
            history_entry = {
                'timestamp': current_time,
                'event_name': event_name,
                'priority': priority,
                'data': data
            }
            self.event_history.append(history_entry)
            
            # Update performance metrics
            self.performance_metrics['total_events'] += 1
            
            # Periodic cleanup
            self._periodic_cleanup()
            
            # Notify callbacks
            self._notify_update_callbacks()
    
    def _track_subscription_event(self, event_name: str, args: tuple, kwargs: dict):
        """Track subscription-related events."""
        data = args[0] if args else kwargs
        
        if event_name == 'market_data.subscribe':
            self._handle_subscription_start(data, SubscriptionType.MARKET_DATA)
        elif event_name == 'market_data.unsubscribe':
            self._handle_subscription_end(data, SubscriptionType.MARKET_DATA)
        elif event_name == 'market_data.error':
            self._handle_subscription_error(data, SubscriptionType.MARKET_DATA)
        elif event_name == 'account.request_summary':
            self._handle_subscription_start(data, SubscriptionType.ACCOUNT_DATA)
        elif event_name == 'get_positions':
            self._handle_subscription_start(data, SubscriptionType.POSITIONS)
        elif event_name == 'get_open_orders':
            self._handle_subscription_start(data, SubscriptionType.ORDERS)
        elif event_name == 'options.request_chain':
            self._handle_subscription_start(data, SubscriptionType.OPTIONS_CHAIN)
    
    def _handle_subscription_start(self, data: Dict[str, Any], subscription_type: SubscriptionType):
        """Handle the start of a subscription."""
        with self._lock:
            contract = data.get('contract', {})
            subscription_id = self._generate_subscription_id(contract, subscription_type)
            
            # Check if subscription already exists
            if subscription_id in self.subscriptions:
                # Update existing subscription
                sub = self.subscriptions[subscription_id]
                sub.status = SubscriptionStatus.ACTIVE
                sub.last_update_time = datetime.now()
                sub.error_count = 0
                sub.last_error = None
                logger.debug(f"Updated existing subscription: {subscription_id}")
            else:
                # Create new subscription
                sub = SubscriptionInfo(
                    subscription_id=subscription_id,
                    subscription_type=subscription_type,
                    contract=contract,
                    status=SubscriptionStatus.PENDING,
                    created_time=datetime.now(),
                    last_update_time=datetime.now()
                )
                self.subscriptions[subscription_id] = sub
                logger.info(f"New subscription started: {subscription_id}")
            
            # Update performance metrics
            self.performance_metrics['subscription_count'] = len(self.subscriptions)
            self.performance_metrics['active_subscriptions'] = len([
                s for s in self.subscriptions.values() 
                if s.status == SubscriptionStatus.ACTIVE
            ])
    
    def _handle_subscription_end(self, data: Dict[str, Any], subscription_type: SubscriptionType):
        """Handle the end of a subscription."""
        with self._lock:
            contract = data.get('contract', {})
            subscription_id = self._generate_subscription_id(contract, subscription_type)
            
            if subscription_id in self.subscriptions:
                sub = self.subscriptions[subscription_id]
                sub.status = SubscriptionStatus.CANCELLED
                sub.last_update_time = datetime.now()
                logger.info(f"Subscription ended: {subscription_id}")
                
                # Update performance metrics
                self.performance_metrics['active_subscriptions'] = len([
                    s for s in self.subscriptions.values() 
                    if s.status == SubscriptionStatus.ACTIVE
                ])
    
    def _handle_subscription_error(self, data: Dict[str, Any], subscription_type: SubscriptionType):
        """Handle subscription errors."""
        with self._lock:
            contract = data.get('contract', {})
            subscription_id = self._generate_subscription_id(contract, subscription_type)
            
            if subscription_id in self.subscriptions:
                sub = self.subscriptions[subscription_id]
                sub.status = SubscriptionStatus.ERROR
                sub.error_count += 1
                sub.last_error = data.get('errorString', 'Unknown error')
                sub.last_update_time = datetime.now()
                logger.warning(f"Subscription error: {subscription_id} - {sub.last_error}")
    
    def _generate_subscription_id(self, contract: Dict[str, Any], subscription_type: SubscriptionType) -> str:
        """Generate a unique subscription ID."""
        symbol = contract.get('symbol', '')
        sec_type = contract.get('secType', '')
        exchange = contract.get('exchange', '')
        currency = contract.get('currency', '')
        
        if sec_type == 'OPT':
            expiration = contract.get('expiration', '')
            strike = contract.get('strike', '')
            right = contract.get('right', '')
            return f"{subscription_type.value}_{symbol}_{sec_type}_{expiration}_{strike}_{right}"
        else:
            return f"{subscription_type.value}_{symbol}_{sec_type}_{exchange}_{currency}"
    
    def _periodic_cleanup(self):
        """Perform periodic cleanup to prevent memory leaks."""
        current_time = time.time()
        if current_time - self._last_cleanup_time > self._cleanup_interval:
            self._last_cleanup_time = current_time
            
            # Limit number of event records
            if len(self.event_records) > self._max_records:
                sorted_records = sorted(
                    self.event_records.items(),
                    key=lambda x: x[1]['last_seen']
                )
                records_to_remove = len(self.event_records) - self._max_records
                for i in range(records_to_remove):
                    del self.event_records[sorted_records[i][0]]
                
                logger.debug(f"Cleaned up {records_to_remove} old event records")
            
            # Force garbage collection
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"Garbage collection collected {collected} objects")
            
            # Record memory usage
            self.memory_detector.record_memory_usage()
    
    def get_subscriptions(self) -> Dict[str, SubscriptionInfo]:
        """Get all subscriptions."""
        with self._lock:
            return self.subscriptions.copy()
    
    def get_subscriptions_by_type(self, subscription_type: SubscriptionType) -> Dict[str, SubscriptionInfo]:
        """Get subscriptions filtered by type."""
        with self._lock:
            return {
                sub_id: sub for sub_id, sub in self.subscriptions.items()
                if sub.subscription_type == subscription_type
            }
    
    def get_subscriptions_by_status(self, status: SubscriptionStatus) -> Dict[str, SubscriptionInfo]:
        """Get subscriptions filtered by status."""
        with self._lock:
            return {
                sub_id: sub for sub_id, sub in self.subscriptions.items()
                if sub.status == status
            }
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Get current memory metrics."""
        return self.memory_detector.get_memory_summary()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        with self._lock:
            # Calculate events per second
            if self.event_history:
                recent_events = [
                    e for e in self.event_history 
                    if (datetime.now() - e['timestamp']).total_seconds() < 60
                ]
                self.performance_metrics['events_per_second'] = len(recent_events) / 60.0
            
            return self.performance_metrics.copy()
    
    def get_event_records(self) -> Dict[str, Dict[str, Any]]:
        """Get all event records."""
        with self._lock:
            return self.event_records.copy()
    
    def get_event_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get event history."""
        with self._lock:
            if limit:
                return list(self.event_history)[-limit:]
            return list(self.event_history)
    
    def register_update_callback(self, callback: Callable):
        """Register a callback to be called when events are updated."""
        with self._lock:
            if callback not in self._update_callbacks:
                self._update_callbacks.append(callback)
    
    def unregister_update_callback(self, callback: Callable):
        """Unregister an update callback."""
        with self._lock:
            if callback in self._update_callbacks:
                self._update_callbacks.remove(callback)
    
    def _notify_update_callbacks(self):
        """Notify all registered callbacks of updates."""
        callbacks = self._update_callbacks.copy()
        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in update callback: {e}")
    
    def clear_records(self):
        """Clear all event records and subscriptions."""
        with self._lock:
            self.event_records.clear()
            self.event_history.clear()
            self.subscriptions.clear()
            self.performance_metrics['total_events'] = 0
            self.performance_metrics['subscription_count'] = 0
            self.performance_metrics['active_subscriptions'] = 0
            self._notify_update_callbacks()
        logger.info("All records cleared")
    
    def cleanup(self):
        """Clean up resources and stop monitoring."""
        with self._lock:
            self._update_callbacks.clear()
            self.event_records.clear()
            self.event_history.clear()
            self.subscriptions.clear()
        
        # Force garbage collection
        gc.collect()
        logger.info("Enhanced Event Monitor cleaned up") 