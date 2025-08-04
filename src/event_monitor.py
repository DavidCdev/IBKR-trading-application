import threading
import time
import gc
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from collections import defaultdict, deque
from logger import get_logger
from event_bus import EventBus, EventPriority

logger = get_logger('EVENT_MONITOR')

class EventMonitor:
    """
    A monitor that tracks all events emitted through the event bus.
    This class wraps the event bus to intercept all events without modifying
    the original event bus implementation.
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the event monitor.
        
        Args:
            event_bus: The event bus to monitor
        """
        self.event_bus = event_bus
        self.event_records: Dict[str, Dict[str, Any]] = {}
        self.event_history: deque = deque(maxlen=500)  # Reduced from 1000 to 500
        self.max_history = 500  # Reduced from 1000 to 500
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Callbacks for GUI updates
        self._update_callbacks: list = []
        
        # Memory management
        self._last_cleanup_time = time.time()
        self._cleanup_interval = 30.0  # Cleanup every 30 seconds
        self._max_records = 1000  # Maximum number of event records to keep
        
        # Start monitoring
        self._start_monitoring()
        
        logger.info("Event monitor initialized")
    
    def _start_monitoring(self):
        """Start monitoring the event bus."""
        # Create a wrapper for the emit method
        original_emit = self.event_bus.emit
        
        def monitored_emit(event_name: str, *args, priority: EventPriority = EventPriority.NORMAL, **kwargs):
            """Monitored version of emit that tracks all events."""
            try:
                # Record the event before emitting
                self._record_event(event_name, priority, args, kwargs)
                
                # Call the original emit method
                return original_emit(event_name, *args, priority=priority, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in monitored emit: {e}")
                # Still call original emit even if monitoring fails
                return original_emit(event_name, *args, priority=priority, **kwargs)
        
        # Replace the emit method
        self.event_bus.emit = monitored_emit
        logger.info("Event bus monitoring started")
    
    def _record_event(self, event_name: str, priority: EventPriority, args: tuple, kwargs: dict):
        """Record an event occurrence."""
        with self._lock:
            current_time = datetime.now()
            
            # Extract data from args or kwargs
            data = args[0] if args else kwargs
            
            # Update event record
            if event_name in self.event_records:
                record = self.event_records[event_name]
                record['count'] += 1
                record['last_seen'] = current_time
                record['last_data'] = data
                record['last_priority'] = priority
            else:
                # Create new record
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
            
            # Periodic cleanup
            self._periodic_cleanup()
            
            # Notify callbacks
            self._notify_update_callbacks()
    
    def _periodic_cleanup(self):
        """Perform periodic cleanup to prevent memory leaks."""
        current_time = time.time()
        if current_time - self._last_cleanup_time > self._cleanup_interval:
            self._last_cleanup_time = current_time
            
            # Limit number of event records
            if len(self.event_records) > self._max_records:
                # Remove oldest records based on last_seen time
                sorted_records = sorted(
                    self.event_records.items(),
                    key=lambda x: x[1]['last_seen']
                )
                records_to_remove = len(self.event_records) - self._max_records
                for i in range(records_to_remove):
                    del self.event_records[sorted_records[i][0]]
                
                logger.debug(f"Cleaned up {records_to_remove} old event records")
            
            # Force garbage collection periodically
            if current_time % 60 < 1:  # Every minute
                collected = gc.collect()
                if collected > 0:
                    logger.debug(f"Garbage collection collected {collected} objects")
    
    def get_event_records(self) -> Dict[str, Dict[str, Any]]:
        """Get all event records."""
        with self._lock:
            return self.event_records.copy()
    
    def get_event_history(self, limit: Optional[int] = None) -> list:
        """Get event history."""
        with self._lock:
            if limit:
                return list(self.event_history)[-limit:]
            return list(self.event_history)
    
    def get_events_by_priority(self, priority: EventPriority) -> Dict[str, Dict[str, Any]]:
        """Get events filtered by priority."""
        with self._lock:
            return {
                name: record for name, record in self.event_records.items()
                if record['priority'] == priority
            }
    
    def get_events_by_name_pattern(self, pattern: str) -> Dict[str, Dict[str, Any]]:
        """Get events filtered by name pattern."""
        with self._lock:
            pattern_lower = pattern.lower()
            return {
                name: record for name, record in self.event_records.items()
                if pattern_lower in name.lower()
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about events."""
        with self._lock:
            if not self.event_records:
                return {
                    'total_events': 0,
                    'unique_events': 0,
                    'total_count': 0,
                    'priority_breakdown': {},
                    'recent_events': []
                }
            
            # Basic stats
            total_events = len(self.event_records)
            total_count = sum(record['count'] for record in self.event_records.values())
            
            # Priority breakdown
            priority_counts = defaultdict(int)
            for record in self.event_records.values():
                priority_counts[record['priority'].name] += 1
            
            # Recent events (last minute)
            current_time = datetime.now()
            recent_events = []
            for event_name, record in self.event_records.items():
                time_diff = (current_time - record['last_seen']).total_seconds()
                if time_diff < 60:  # Last minute
                    recent_events.append({
                        'event_name': event_name,
                        'count': record['count'],
                        'seconds_ago': time_diff
                    })
            
            # Sort recent events by time
            recent_events.sort(key=lambda x: x['seconds_ago'])
            
            return {
                'total_events': total_events,
                'unique_events': total_events,
                'total_count': total_count,
                'priority_breakdown': dict(priority_counts),
                'recent_events': recent_events
            }
    
    def clear_records(self):
        """Clear all event records."""
        with self._lock:
            self.event_records.clear()
            self.event_history.clear()
            self._notify_update_callbacks()
        logger.info("Event records cleared")
    
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
    
    def get_event_details(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific event."""
        with self._lock:
            return self.event_records.get(event_name)
    
    def get_events_in_time_range(self, start_time: datetime, end_time: datetime) -> list:
        """Get events that occurred within a time range."""
        with self._lock:
            return [
                entry for entry in self.event_history
                if start_time <= entry['timestamp'] <= end_time
            ]
    
    def cleanup(self):
        """Clean up resources and stop monitoring."""
        with self._lock:
            self._update_callbacks.clear()
            self.event_records.clear()
            self.event_history.clear()
        
        # Force garbage collection
        gc.collect()
        logger.info("Event monitor cleaned up")


class EventBusWrapper:
    """
    A wrapper around the event bus that provides monitoring capabilities
    while maintaining the original event bus interface.
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the event bus wrapper.
        
        Args:
            event_bus: The original event bus to wrap
        """
        self.event_bus = event_bus
        self.monitor = EventMonitor(event_bus)
        
        # Expose event bus methods
        self.emit = event_bus.emit
        self.on = event_bus.on
        self.request = event_bus.request
        self.register_request_handler = event_bus.register_request_handler
        self.stop = event_bus.stop
        
        logger.info("Event bus wrapper initialized")
    
    def get_monitor(self) -> EventMonitor:
        """Get the event monitor."""
        return self.monitor
    
    def get_event_bus(self) -> EventBus:
        """Get the original event bus."""
        return self.event_bus
    
    def cleanup(self):
        """Clean up the wrapper and monitor."""
        if self.monitor:
            self.monitor.cleanup()
        logger.info("Event bus wrapper cleaned up")


def create_monitored_event_bus(max_workers: int = 8) -> EventBusWrapper:
    """
    Create an event bus with monitoring capabilities.
    
    Args:
        max_workers: Maximum number of worker threads
        
    Returns:
        EventBusWrapper with monitoring capabilities
    """
    event_bus = EventBus(max_workers=max_workers)
    return EventBusWrapper(event_bus) 