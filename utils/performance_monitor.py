import time
import functools
import threading
from typing import Callable, Any, Optional
from .logger import get_logger, log_performance


class PerformanceMonitor:
    """
    Performance monitoring utilities for the IB Trading Application
    """
    
    def __init__(self):
        self._active_monitors = {}
        self._lock = threading.Lock()
        self.logger = get_logger("PERFORMANCE")
    
    def monitor_function(self, operation_name: Optional[str] = None, 
                        log_args: bool = False, 
                        log_result: bool = False,
                        threshold_ms: Optional[float] = None):
        """
        Decorator to monitor function performance
        
        Args:
            operation_name: Custom name for the operation (defaults to function name)
            log_args: Whether to log function arguments
            log_result: Whether to log function result
            threshold_ms: Only log if execution time exceeds this threshold (in milliseconds)
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                op_name = operation_name or f"{func.__module__}.{func.__name__}"
                
                # Start timing
                start_time = time.time()
                
                try:
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Calculate duration
                    duration = time.time() - start_time
                    duration_ms = duration * 1000
                    
                    # Check threshold
                    if threshold_ms is None or duration_ms >= threshold_ms:
                        # Prepare context data
                        context_data = {}
                        
                        if log_args:
                            context_data['args'] = str(args[:3]) + "..." if len(args) > 3 else str(args)
                            context_data['kwargs'] = str(kwargs)
                        
                        if log_result:
                            result_str = str(result)
                            if len(result_str) > 100:
                                result_str = result_str[:100] + "..."
                            context_data['result'] = result_str
                        
                        # Log performance
                        log_performance(op_name, duration, **context_data)
                    
                    return result
                    
                except Exception as e:
                    # Log error with performance data
                    duration = time.time() - start_time
                    self.logger.error(f"PERF_ERROR: {op_name} failed after {duration:.3f}s - {type(e).__name__}: {str(e)}")
                    raise
                    
            return wrapper
        return decorator
    
    def start_monitor(self, operation_name: str) -> str:
        """
        Start a manual performance monitor
        
        Args:
            operation_name: Name of the operation to monitor
            
        Returns:
            Monitor ID for stopping the monitor
        """
        monitor_id = f"{operation_name}_{threading.get_ident()}_{time.time()}"
        
        with self._lock:
            self._active_monitors[monitor_id] = {
                'operation': operation_name,
                'start_time': time.time(),
                'thread_id': threading.get_ident()
            }
        
        return monitor_id
    
    def stop_monitor(self, monitor_id: str, **context_data) -> Optional[float]:
        """
        Stop a manual performance monitor and log the result
        
        Args:
            monitor_id: ID returned from start_monitor
            **context_data: Additional context data to log
            
        Returns:
            Duration in seconds, or None if monitor not found
        """
        with self._lock:
            if monitor_id not in self._active_monitors:
                self.logger.warning(f"Monitor {monitor_id} not found")
                return None
            
            monitor_data = self._active_monitors.pop(monitor_id)
            duration = time.time() - monitor_data['start_time']
            
            # Log performance
            log_performance(monitor_data['operation'], duration, **context_data)
            
            return duration
    
    def monitor_async_function(self, operation_name: Optional[str] = None,
                              log_args: bool = False,
                              log_result: bool = False,
                              threshold_ms: Optional[float] = None):
        """
        Decorator to monitor async function performance
        
        Args:
            operation_name: Custom name for the operation (defaults to function name)
            log_args: Whether to log function arguments
            log_result: Whether to log function result
            threshold_ms: Only log if execution time exceeds this threshold (in milliseconds)
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                op_name = operation_name or f"{func.__module__}.{func.__name__}"
                
                # Start timing
                start_time = time.time()
                
                try:
                    # Execute async function
                    result = await func(*args, **kwargs)
                    
                    # Calculate duration
                    duration = time.time() - start_time
                    duration_ms = duration * 1000
                    
                    # Check threshold
                    if threshold_ms is None or duration_ms >= threshold_ms:
                        # Prepare context data
                        context_data = {}
                        
                        if log_args:
                            context_data['args'] = str(args[:3]) + "..." if len(args) > 3 else str(args)
                            context_data['kwargs'] = str(kwargs)
                        
                        if log_result:
                            result_str = str(result)
                            if len(result_str) > 100:
                                result_str = result_str[:100] + "..."
                            context_data['result'] = result_str
                        
                        # Log performance
                        log_performance(op_name, duration, **context_data)
                    
                    return result
                    
                except Exception as e:
                    # Log error with performance data
                    duration = time.time() - start_time
                    self.logger.error(f"PERF_ERROR: {op_name} failed after {duration:.3f}s - {type(e).__name__}: {str(e)}")
                    raise
                    
            return wrapper
        return decorator


# Global instance
performance_monitor = PerformanceMonitor()


# Convenience functions
def monitor_function(operation_name: Optional[str] = None, 
                    log_args: bool = False, 
                    log_result: bool = False,
                    threshold_ms: Optional[float] = None):
    """Convenience decorator for function performance monitoring"""
    return performance_monitor.monitor_function(operation_name, log_args, log_result, threshold_ms)


def monitor_async_function(operation_name: Optional[str] = None,
                          log_args: bool = False,
                          log_result: bool = False,
                          threshold_ms: Optional[float] = None):
    """Convenience decorator for async function performance monitoring"""
    return performance_monitor.monitor_async_function(operation_name, log_args, log_result, threshold_ms)


def start_monitor(operation_name: str) -> str:
    """Convenience function to start manual performance monitoring"""
    return performance_monitor.start_monitor(operation_name)


def stop_monitor(monitor_id: str, **context_data) -> Optional[float]:
    """Convenience function to stop manual performance monitoring"""
    return performance_monitor.stop_monitor(monitor_id, **context_data)
