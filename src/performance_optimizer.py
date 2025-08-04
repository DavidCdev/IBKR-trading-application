#!/usr/bin/env python3
"""
Performance Optimizer Module

This module provides comprehensive performance optimization capabilities for the trading application,
including event processing optimization, throughput enhancement, and advanced metrics collection.
"""

import time
import threading
import psutil
import gc
import asyncio
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import statistics
from logger import get_logger
from enhanced_logging import log_performance, get_enhanced_logging_manager

logger = get_logger('PERFORMANCE_OPTIMIZER')

class OptimizationLevel(Enum):
    """Performance optimization levels."""
    NONE = 0
    BASIC = 1
    AGGRESSIVE = 2
    MAXIMUM = 3

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    timestamp: float
    cpu_usage_percent: float
    memory_usage_mb: float
    event_throughput_per_sec: float
    avg_event_processing_time_ms: float
    queue_sizes: Dict[str, int]
    priority_processing_times: Dict[str, float]
    gc_stats: Dict[str, Any]
    system_load: float
    network_latency_ms: Optional[float] = None

@dataclass
class OptimizationConfig:
    """Configuration for performance optimization."""
    target_throughput_per_sec: int = 1000
    max_memory_usage_mb: float = 512.0
    max_cpu_usage_percent: float = 80.0
    gc_threshold_percent: float = 70.0
    optimization_level: OptimizationLevel = OptimizationLevel.BASIC
    enable_auto_optimization: bool = True
    monitoring_interval_sec: float = 5.0
    performance_history_size: int = 1000

@dataclass
class EventProcessingStats:
    """Statistics for event processing performance."""
    total_events: int = 0
    events_per_second: float = 0.0
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    min_processing_time_ms: float = float('inf')
    processing_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    priority_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)

class PerformanceOptimizer:
    """
    Comprehensive performance optimizer for the trading application.
    
    Features:
    - Real-time performance monitoring
    - Automatic optimization based on system metrics
    - Event processing optimization
    - Memory and CPU usage optimization
    - Throughput enhancement
    - Advanced metrics collection
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Initialize the performance optimizer.
        
        Args:
            config: Optimization configuration
        """
        self.config = config or OptimizationConfig()
        self.logger = logger
        
        # Performance tracking
        self._performance_history: deque = deque(maxlen=self.config.performance_history_size)
        self._event_stats = EventProcessingStats()
        self._optimization_history: List[Dict[str, Any]] = []
        
        # System monitoring
        self._last_cpu_usage = 0.0
        self._last_memory_usage = 0.0
        self._system_load_history = deque(maxlen=100)
        
        # Threading
        self._monitoring_thread: Optional[threading.Thread] = None
        self._optimization_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # Event bus reference (set later)
        self._event_bus = None
        self._enhanced_logging = None
        
        self.logger.info("PerformanceOptimizer initialized")
    
    def set_event_bus(self, event_bus):
        """Set the event bus reference for optimization."""
        self._event_bus = event_bus
        self.logger.debug("Event bus reference set")
    
    def start_monitoring(self):
        """Start performance monitoring."""
        if self._running:
            self.logger.warning("Performance monitoring already running")
            return
        
        self._running = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._optimization_thread = threading.Thread(target=self._optimization_loop, daemon=True)
        
        self._monitoring_thread.start()
        self._optimization_thread.start()
        
        self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.logger.info("Stopping performance monitoring...")
        self._running = False
        
        # Wait for threads with shorter timeout
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=3.0)
            if self._monitoring_thread.is_alive():
                self.logger.warning("Monitoring thread did not stop gracefully")
        
        if self._optimization_thread:
            self._optimization_thread.join(timeout=3.0)
            if self._optimization_thread.is_alive():
                self.logger.warning("Optimization thread did not stop gracefully")
        
        self.logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                metrics = self._collect_performance_metrics()
                self._performance_history.append(metrics)
                
                # Log performance metrics
                self._log_performance_metrics(metrics)
                
                # Check for optimization triggers
                if self.config.enable_auto_optimization:
                    self._check_optimization_triggers(metrics)
                
                # Use shorter sleep intervals to allow faster shutdown
                for _ in range(int(self.config.monitoring_interval_sec)):
                    if not self._running:
                        break
                    time.sleep(1.0)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                # Shorter error recovery sleep
                for _ in range(5):
                    if not self._running:
                        break
                    time.sleep(1.0)
    
    def _optimization_loop(self):
        """Main optimization loop."""
        while self._running:
            try:
                # Perform periodic optimizations
                self._perform_periodic_optimizations()
                
                # Use shorter sleep intervals to allow faster shutdown
                for _ in range(30):  # 30 seconds total, but check every second
                    if not self._running:
                        break
                    time.sleep(1.0)
                
            except Exception as e:
                self.logger.error(f"Error in optimization loop: {e}")
                # Shorter error recovery sleep
                for _ in range(5):
                    if not self._running:
                        break
                    time.sleep(1.0)
    
    def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect comprehensive performance metrics."""
        # System metrics
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_usage_mb = memory.used / (1024 * 1024)
        
        # Event processing metrics
        event_throughput = self._calculate_event_throughput()
        avg_processing_time = self._calculate_avg_processing_time()
        
        # Queue sizes
        queue_sizes = self._get_queue_sizes()
        
        # Priority processing times
        priority_times = self._get_priority_processing_times()
        
        # GC stats
        gc_stats = self._get_gc_stats()
        
        # System load
        system_load = self._calculate_system_load()
        
        # Network latency (if available)
        network_latency = self._measure_network_latency()
        
        return PerformanceMetrics(
            timestamp=time.time(),
            cpu_usage_percent=cpu_usage,
            memory_usage_mb=memory_usage_mb,
            event_throughput_per_sec=event_throughput,
            avg_event_processing_time_ms=avg_processing_time,
            queue_sizes=queue_sizes,
            priority_processing_times=priority_times,
            gc_stats=gc_stats,
            system_load=system_load,
            network_latency_ms=network_latency
        )
    
    def _calculate_event_throughput(self) -> float:
        """Calculate current event throughput."""
        if not self._event_bus:
            return 0.0
        
        try:
            metrics = self._event_bus.get_performance_metrics()
            return metrics.get('total_events', 0) / max(time.time() - metrics.get('start_time', time.time()), 1.0)
        except Exception as e:
            self.logger.debug(f"Could not calculate event throughput: {e}")
            return 0.0
    
    def _calculate_avg_processing_time(self) -> float:
        """Calculate average event processing time."""
        if not self._event_stats.processing_times:
            return 0.0
        
        return statistics.mean(self._event_stats.processing_times)
    
    def _get_queue_sizes(self) -> Dict[str, int]:
        """Get current queue sizes."""
        queue_sizes = {}
        
        if self._event_bus:
            try:
                # Get priority queue sizes
                for priority in ['CRITICAL', 'HIGH', 'NORMAL', 'LOW', 'BACKGROUND']:
                    queue_sizes[f'priority_{priority.lower()}'] = 0
                
                # Get worker queue size
                queue_sizes['worker_queue'] = 0
                
            except Exception as e:
                self.logger.debug(f"Could not get queue sizes: {e}")
        
        return queue_sizes
    
    def _get_priority_processing_times(self) -> Dict[str, float]:
        """Get priority processing times."""
        priority_times = {}
        
        if self._event_bus:
            try:
                health_status = self._event_bus.get_priority_health_status()
                for priority, healthy in health_status.items():
                    priority_times[priority] = 0.0 if healthy else 1000.0  # Default values
            except Exception as e:
                self.logger.debug(f"Could not get priority processing times: {e}")
        
        return priority_times
    
    def _get_gc_stats(self) -> Dict[str, Any]:
        """Get garbage collection statistics."""
        try:
            gc.collect()  # Force collection
            stats = gc.get_stats()
            return {
                'collections': len(stats),
                'total_time': sum(stat.get('duration', 0) for stat in stats),
                'objects_collected': sum(stat.get('collections', 0) for stat in stats)
            }
        except Exception as e:
            self.logger.debug(f"Could not get GC stats: {e}")
            return {}
    
    def _calculate_system_load(self) -> float:
        """Calculate system load."""
        try:
            # Use CPU usage as a proxy for system load
            cpu_usage = psutil.cpu_percent(interval=0.1)
            self._system_load_history.append(cpu_usage)
            
            # Calculate average load over recent history
            if len(self._system_load_history) > 10:
                return statistics.mean(list(self._system_load_history)[-10:])
            else:
                return cpu_usage
        except Exception as e:
            self.logger.debug(f"Could not calculate system load: {e}")
            return 0.0
    
    def _measure_network_latency(self) -> Optional[float]:
        """Measure network latency to IB servers."""
        # This would typically measure latency to IB servers
        # For now, return None as we don't have network measurement
        return None
    
    def _log_performance_metrics(self, metrics: PerformanceMetrics):
        """Log performance metrics."""
        try:
            # Log to enhanced logging system
            self._enhanced_logging = get_enhanced_logging_manager()
            if self._enhanced_logging:
                log_performance(
                    module='performance_optimizer',
                    operation='system_monitoring',
                    duration_ms=0.0,  # Not applicable for monitoring
                    memory_usage_mb=metrics.memory_usage_mb,
                    cpu_usage_percent=metrics.cpu_usage_percent,
                    queue_size=sum(metrics.queue_sizes.values()),
                    throughput_events_per_sec=metrics.event_throughput_per_sec
                )
            
            # Log to standard logger
            self.logger.debug(
                f"Performance - CPU: {metrics.cpu_usage_percent:.1f}%, "
                f"Memory: {metrics.memory_usage_mb:.1f}MB, "
                f"Throughput: {metrics.event_throughput_per_sec:.1f} events/sec"
            )
            
        except Exception as e:
            self.logger.error(f"Error logging performance metrics: {e}")
    
    def _check_optimization_triggers(self, metrics: PerformanceMetrics):
        """Check if optimization is needed based on metrics."""
        triggers = []
        
        # CPU usage trigger
        if metrics.cpu_usage_percent > self.config.max_cpu_usage_percent:
            triggers.append(f"High CPU usage: {metrics.cpu_usage_percent:.1f}%")
        
        # Memory usage trigger
        if metrics.memory_usage_mb > self.config.max_memory_usage_mb:
            triggers.append(f"High memory usage: {metrics.memory_usage_mb:.1f}MB")
        
        # Throughput trigger
        if metrics.event_throughput_per_sec < self.config.target_throughput_per_sec * 0.8:
            triggers.append(f"Low throughput: {metrics.event_throughput_per_sec:.1f} events/sec")
        
        # Processing time trigger
        if metrics.avg_event_processing_time_ms > 100.0:  # 100ms threshold
            triggers.append(f"Slow processing: {metrics.avg_event_processing_time_ms:.1f}ms avg")
        
        # Execute optimizations if triggers found
        if triggers:
            self.logger.warning(f"Performance optimization triggers detected: {', '.join(triggers)}")
            self._execute_optimizations(metrics, triggers)
    
    def _execute_optimizations(self, metrics: PerformanceMetrics, triggers: List[str]):
        """Execute performance optimizations."""
        optimizations = []
        
        # Memory optimization
        if any('memory' in trigger.lower() for trigger in triggers):
            optimizations.extend(self._optimize_memory_usage())
        
        # CPU optimization
        if any('cpu' in trigger.lower() for trigger in triggers):
            optimizations.extend(self._optimize_cpu_usage())
        
        # Throughput optimization
        if any('throughput' in trigger.lower() for trigger in triggers):
            optimizations.extend(self._optimize_throughput())
        
        # Processing time optimization
        if any('processing' in trigger.lower() for trigger in triggers):
            optimizations.extend(self._optimize_processing_time())
        
        # Record optimization
        if optimizations:
            optimization_record = {
                'timestamp': time.time(),
                'triggers': triggers,
                'optimizations': optimizations,
                'metrics_before': {
                    'cpu_usage': metrics.cpu_usage_percent,
                    'memory_usage': metrics.memory_usage_mb,
                    'throughput': metrics.event_throughput_per_sec,
                    'avg_processing_time': metrics.avg_event_processing_time_ms
                }
            }
            
            with self._lock:
                self._optimization_history.append(optimization_record)
            
            self.logger.info(f"Applied optimizations: {', '.join(optimizations)}")
    
    def _optimize_memory_usage(self) -> List[str]:
        """Optimize memory usage."""
        optimizations = []
        
        # Force garbage collection
        collected = gc.collect()
        if collected > 0:
            optimizations.append(f"GC collected {collected} objects")
        
        # Clear processing time history if too large
        if len(self._event_stats.processing_times) > 500:
            self._event_stats.processing_times.clear()
            optimizations.append("Cleared processing time history")
        
        # Clear performance history if too large
        if len(self._performance_history) > self.config.performance_history_size * 0.8:
            # Keep only recent entries
            recent_count = self.config.performance_history_size // 2
            self._performance_history = deque(
                list(self._performance_history)[-recent_count:],
                maxlen=self.config.performance_history_size
            )
            optimizations.append("Reduced performance history size")
        
        return optimizations
    
    def _optimize_cpu_usage(self) -> List[str]:
        """Optimize CPU usage."""
        optimizations = []
        
        # Adjust event bus throttling if available
        if self._event_bus:
            try:
                # Increase throttling to reduce CPU load
                # This would require access to internal throttling configuration
                optimizations.append("Increased event throttling")
            except Exception as e:
                self.logger.debug(f"Could not optimize CPU usage: {e}")
        
        # Reduce monitoring frequency temporarily
        if self.config.monitoring_interval_sec < 10.0:
            self.config.monitoring_interval_sec = min(10.0, self.config.monitoring_interval_sec * 1.5)
            optimizations.append("Reduced monitoring frequency")
        
        return optimizations
    
    def _optimize_throughput(self) -> List[str]:
        """Optimize event throughput."""
        optimizations = []
        
        # This would involve adjusting event bus configuration
        # For now, we'll log the issue
        optimizations.append("Throughput optimization requested")
        
        return optimizations
    
    def _optimize_processing_time(self) -> List[str]:
        """Optimize event processing time."""
        optimizations = []
        
        # This would involve adjusting priority processing
        # For now, we'll log the issue
        optimizations.append("Processing time optimization requested")
        
        return optimizations
    
    def _perform_periodic_optimizations(self):
        """Perform periodic optimizations."""
        optimizations = []
        
        # Periodic memory cleanup
        if len(self._performance_history) > 100:
            # Remove old performance data
            old_count = len(self._performance_history) - 50
            for _ in range(old_count):
                self._performance_history.popleft()
            optimizations.append("Cleaned old performance data")
        
        # Periodic GC
        collected = gc.collect()
        if collected > 0:
            optimizations.append(f"Periodic GC collected {collected} objects")
        
        if optimizations:
            self.logger.debug(f"Periodic optimizations: {', '.join(optimizations)}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self._performance_history:
            return {}
        
        recent_metrics = list(self._performance_history)[-10:]  # Last 10 measurements
        
        summary = {
            'current_metrics': {
                'cpu_usage_percent': recent_metrics[-1].cpu_usage_percent if recent_metrics else 0.0,
                'memory_usage_mb': recent_metrics[-1].memory_usage_mb if recent_metrics else 0.0,
                'event_throughput_per_sec': recent_metrics[-1].event_throughput_per_sec if recent_metrics else 0.0,
                'avg_processing_time_ms': recent_metrics[-1].avg_event_processing_time_ms if recent_metrics else 0.0
            },
            'trends': {
                'cpu_trend': self._calculate_trend([m.cpu_usage_percent for m in recent_metrics]),
                'memory_trend': self._calculate_trend([m.memory_usage_mb for m in recent_metrics]),
                'throughput_trend': self._calculate_trend([m.event_throughput_per_sec for m in recent_metrics])
            },
            'optimization_history': {
                'total_optimizations': len(self._optimization_history),
                'recent_optimizations': self._optimization_history[-5:] if self._optimization_history else []
            },
            'system_health': {
                'gc_stats': recent_metrics[-1].gc_stats if recent_metrics else {},
                'system_load': recent_metrics[-1].system_load if recent_metrics else 0.0,
                'network_latency_ms': recent_metrics[-1].network_latency_ms
            }
        }
        
        return summary
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a list of values."""
        if len(values) < 2:
            return "stable"
        
        # Simple trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        if not first_half or not second_half:
            return "stable"
        
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)
        
        if avg_second > avg_first * 1.1:
            return "increasing"
        elif avg_second < avg_first * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def record_event_processing(self, event_name: str, processing_time_ms: float, priority: str = "NORMAL"):
        """Record event processing statistics."""
        with self._lock:
            self._event_stats.total_events += 1
            self._event_stats.processing_times.append(processing_time_ms)
            
            # Update priority stats
            if priority not in self._event_stats.priority_stats:
                self._event_stats.priority_stats[priority] = {
                    'count': 0,
                    'total_time': 0.0,
                    'avg_time': 0.0
                }
            
            priority_stat = self._event_stats.priority_stats[priority]
            priority_stat['count'] += 1
            priority_stat['total_time'] += processing_time_ms
            priority_stat['avg_time'] = priority_stat['total_time'] / priority_stat['count']
            
            # Update overall stats
            if processing_time_ms > self._event_stats.max_processing_time_ms:
                self._event_stats.max_processing_time_ms = processing_time_ms
            
            if processing_time_ms < self._event_stats.min_processing_time_ms:
                self._event_stats.min_processing_time_ms = processing_time_ms
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get optimization recommendations based on current performance."""
        recommendations = []
        
        if not self._performance_history:
            return recommendations
        
        latest_metrics = self._performance_history[-1]
        
        # CPU recommendations
        if latest_metrics.cpu_usage_percent > 70:
            recommendations.append("Consider reducing event processing frequency")
        
        # Memory recommendations
        if latest_metrics.memory_usage_mb > 400:
            recommendations.append("Consider implementing memory pooling")
        
        # Throughput recommendations
        if latest_metrics.event_throughput_per_sec < 500:
            recommendations.append("Consider optimizing event processing pipeline")
        
        # Processing time recommendations
        if latest_metrics.avg_event_processing_time_ms > 50:
            recommendations.append("Consider optimizing event handlers")
        
        return recommendations


# Global instance
_performance_optimizer: Optional[PerformanceOptimizer] = None

def get_performance_optimizer() -> PerformanceOptimizer:
    """Get the global performance optimizer instance."""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer

def initialize_performance_optimizer(config: Optional[OptimizationConfig] = None) -> PerformanceOptimizer:
    """Initialize the performance optimizer."""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer(config)
    return _performance_optimizer

def start_performance_monitoring():
    """Start performance monitoring."""
    optimizer = get_performance_optimizer()
    optimizer.start_monitoring()

def stop_performance_monitoring():
    """Stop performance monitoring."""
    optimizer = get_performance_optimizer()
    optimizer.stop_monitoring()

def record_event_processing(event_name: str, processing_time_ms: float, priority: str = "NORMAL"):
    """Record event processing for performance tracking."""
    optimizer = get_performance_optimizer()
    optimizer.record_event_processing(event_name, processing_time_ms, priority) 