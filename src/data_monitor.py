import threading
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from logger import get_logger

logger = get_logger('DATA_MONITOR')


@dataclass
class DataRequest:
    """Represents a data request to TWS Gateway"""
    request_id: str
    request_type: str  # 'mkt_data', 'historical', 'account', 'position', etc.
    symbol: Optional[str] = None
    contract_details: Optional[Dict] = None
    timestamp: datetime = None
    status: str = 'pending'  # 'pending', 'success', 'error', 'cancelled'
    error_message: Optional[str] = None
    data_count: int = 0
    last_update: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class DataResponse:
    """Represents a data response from TWS Gateway"""
    request_id: str
    data_type: str
    data: Any
    timestamp: datetime = None
    sequence_number: int = 0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class DataMonitor:
    """
    Monitors and tracks all data requests and responses from TWS Gateway.
    Provides methods to check request status and display results.
    """
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.requests: Dict[str, DataRequest] = {}
        self.responses: Dict[str, List[DataResponse]] = {}
        self.request_counter = 0
        self.lock = threading.Lock()
        
        # Subscribe to relevant events
        self._subscribe_to_events()
        
        logger.info("DataMonitor initialized")
    
    def _subscribe_to_events(self):
        """Subscribe to data-related events"""
        self.event_bus.subscribe("ib.data", self._handle_data_event)
        self.event_bus.subscribe("ib.error", self._handle_error_event)
        self.event_bus.subscribe("ib.request", self._handle_request_event)
        self.event_bus.subscribe("ib.response", self._handle_response_event)
    
    def _handle_data_event(self, event_data):
        """Handle incoming data events"""
        with self.lock:
            request_id = event_data.get('request_id')
            if request_id and request_id in self.requests:
                request = self.requests[request_id]
                request.data_count += 1
                request.last_update = datetime.now()
                
                # Store the response
                if request_id not in self.responses:
                    self.responses[request_id] = []
                
                response = DataResponse(
                    request_id=request_id,
                    data_type=request.request_type,
                    data=event_data.get('data'),
                    sequence_number=len(self.responses[request_id])
                )
                self.responses[request_id].append(response)
                
                logger.debug(f"Data received for request {request_id}: {len(self.responses[request_id])} responses")
    
    def _handle_error_event(self, event_data):
        """Handle error events"""
        with self.lock:
            request_id = event_data.get('request_id')
            if request_id and request_id in self.requests:
                request = self.requests[request_id]
                request.status = 'error'
                request.error_message = event_data.get('error_message', 'Unknown error')
                logger.error(f"Error for request {request_id}: {request.error_message}")
    
    def _handle_request_event(self, event_data):
        """Handle outgoing request events"""
        with self.lock:
            request_id = event_data.get('request_id')
            if request_id:
                request = DataRequest(
                    request_id=request_id,
                    request_type=event_data.get('request_type', 'unknown'),
                    symbol=event_data.get('symbol'),
                    contract_details=event_data.get('contract_details')
                )
                self.requests[request_id] = request
                logger.info(f"New request tracked: {request_id} ({request.request_type})")
    
    def _handle_response_event(self, event_data):
        """Handle response events"""
        with self.lock:
            request_id = event_data.get('request_id')
            if request_id and request_id in self.requests:
                request = self.requests[request_id]
                request.status = 'success'
                request.last_update = datetime.now()
                logger.info(f"Request {request_id} completed successfully")
    
    def track_request(self, request_type: str, symbol: str = None, contract_details: Dict = None) -> str:
        """Track a new data request"""
        with self.lock:
            self.request_counter += 1
            request_id = f"{request_type}_{self.request_counter}_{int(time.time())}"
            
            request = DataRequest(
                request_id=request_id,
                request_type=request_type,
                symbol=symbol,
                contract_details=contract_details
            )
            
            self.requests[request_id] = request
            self.responses[request_id] = []
            
            logger.info(f"Tracking new request: {request_id} ({request_type})")
            return request_id
    
    def get_request_status(self, request_id: str) -> Optional[DataRequest]:
        """Get the status of a specific request"""
        with self.lock:
            return self.requests.get(request_id)
    
    def get_request_data(self, request_id: str) -> List[DataResponse]:
        """Get all data responses for a specific request"""
        with self.lock:
            return self.responses.get(request_id, [])
    
    def get_all_requests(self) -> List[DataRequest]:
        """Get all tracked requests"""
        with self.lock:
            return list(self.requests.values())
    
    def get_active_requests(self) -> List[DataRequest]:
        """Get all active (pending) requests"""
        with self.lock:
            return [req for req in self.requests.values() if req.status == 'pending']
    
    def get_recent_requests(self, minutes: int = 5) -> List[DataRequest]:
        """Get requests from the last N minutes"""
        with self.lock:
            cutoff_time = datetime.now().timestamp() - (minutes * 60)
            return [req for req in self.requests.values() 
                   if req.timestamp.timestamp() > cutoff_time]
    
    def get_request_summary(self) -> Dict[str, Any]:
        """Get a summary of all requests"""
        with self.lock:
            total_requests = len(self.requests)
            pending_requests = len([r for r in self.requests.values() if r.status == 'pending'])
            successful_requests = len([r for r in self.requests.values() if r.status == 'success'])
            error_requests = len([r for r in self.requests.values() if r.status == 'error'])
            
            total_responses = sum(len(responses) for responses in self.responses.values())
            
            return {
                'total_requests': total_requests,
                'pending_requests': pending_requests,
                'successful_requests': successful_requests,
                'error_requests': error_requests,
                'total_responses': total_responses,
                'request_types': self._get_request_type_breakdown()
            }
    
    def _get_request_type_breakdown(self) -> Dict[str, int]:
        """Get breakdown of requests by type"""
        breakdown = {}
        for request in self.requests.values():
            req_type = request.request_type
            breakdown[req_type] = breakdown.get(req_type, 0) + 1
        return breakdown
    
    def display_request_results(self, request_id: str = None, format_type: str = 'table'):
        """
        Display request results in various formats
        
        Args:
            request_id: Specific request to display, or None for all
            format_type: 'table', 'json', 'summary'
        """
        if request_id:
            self._display_single_request(request_id, format_type)
        else:
            self._display_all_requests(format_type)
    
    def _display_single_request(self, request_id: str, format_type: str):
        """Display results for a single request"""
        request = self.get_request_status(request_id)
        if not request:
            print(f"Request {request_id} not found")
            return
        
        responses = self.get_request_data(request_id)
        
        if format_type == 'json':
            self._display_json(request, responses)
        elif format_type == 'summary':
            self._display_summary(request, responses)
        else:  # table
            self._display_table(request, responses)
    
    def _display_all_requests(self, format_type: str):
        """Display results for all requests"""
        requests = self.get_all_requests()
        
        if format_type == 'json':
            print(json.dumps([asdict(req) for req in requests], indent=2, default=str))
        elif format_type == 'summary':
            summary = self.get_request_summary()
            print(json.dumps(summary, indent=2))
        else:  # table
            self._display_all_table(requests)
    
    def _display_json(self, request: DataRequest, responses: List[DataResponse]):
        """Display request and responses in JSON format"""
        output = {
            'request': asdict(request),
            'responses': [asdict(resp) for resp in responses]
        }
        print(json.dumps(output, indent=2, default=str))
    
    def _display_summary(self, request: DataRequest, responses: List[DataResponse]):
        """Display a summary of the request and responses"""
        print(f"Request ID: {request.request_id}")
        print(f"Type: {request.request_type}")
        print(f"Symbol: {request.symbol or 'N/A'}")
        print(f"Status: {request.status}")
        print(f"Timestamp: {request.timestamp}")
        print(f"Response Count: {len(responses)}")
        print(f"Last Update: {request.last_update or 'N/A'}")
        
        if request.error_message:
            print(f"Error: {request.error_message}")
        
        if responses:
            print(f"\nLatest Response:")
            latest = responses[-1]
            print(f"  Data: {latest.data}")
            print(f"  Timestamp: {latest.timestamp}")
    
    def _display_table(self, request: DataRequest, responses: List[DataResponse]):
        """Display request and responses in table format"""
        print(f"\n{'='*60}")
        print(f"REQUEST DETAILS")
        print(f"{'='*60}")
        print(f"ID: {request.request_id}")
        print(f"Type: {request.request_type}")
        print(f"Symbol: {request.symbol or 'N/A'}")
        print(f"Status: {request.status}")
        print(f"Created: {request.timestamp}")
        print(f"Last Update: {request.last_update or 'N/A'}")
        print(f"Response Count: {len(responses)}")
        
        if request.error_message:
            print(f"Error: {request.error_message}")
        
        if responses:
            print(f"\n{'='*60}")
            print(f"RESPONSES ({len(responses)} total)")
            print(f"{'='*60}")
            
            for i, response in enumerate(responses[-10:], 1):  # Show last 10 responses
                print(f"\nResponse {i}:")
                print(f"  Sequence: {response.sequence_number}")
                print(f"  Timestamp: {response.timestamp}")
                print(f"  Data: {response.data}")
    
    def _display_all_table(self, requests: List[DataRequest]):
        """Display all requests in table format"""
        print(f"\n{'='*100}")
        print(f"ALL REQUESTS SUMMARY")
        print(f"{'='*100}")
        
        summary = self.get_request_summary()
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Pending: {summary['pending_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Errors: {summary['error_requests']}")
        print(f"Total Responses: {summary['total_responses']}")
        
        print(f"\n{'='*100}")
        print(f"REQUEST BREAKDOWN BY TYPE")
        print(f"{'='*100}")
        for req_type, count in summary['request_types'].items():
            print(f"{req_type}: {count}")
        
        print(f"\n{'='*100}")
        print(f"RECENT REQUESTS (Last 10)")
        print(f"{'='*100}")
        
        recent_requests = sorted(requests, key=lambda x: x.timestamp, reverse=True)[:10]
        
        for request in recent_requests:
            print(f"\nID: {request.request_id}")
            print(f"Type: {request.request_type}")
            print(f"Symbol: {request.symbol or 'N/A'}")
            print(f"Status: {request.status}")
            print(f"Created: {request.timestamp}")
            print(f"Responses: {len(self.responses.get(request.request_id, []))}")
            print("-" * 50)
    
    def clear_old_requests(self, hours: int = 24):
        """Clear requests older than specified hours"""
        with self.lock:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            old_request_ids = [
                req_id for req_id, req in self.requests.items()
                if req.timestamp.timestamp() < cutoff_time
            ]
            
            for req_id in old_request_ids:
                del self.requests[req_id]
                if req_id in self.responses:
                    del self.responses[req_id]
            
            logger.info(f"Cleared {len(old_request_ids)} old requests")
            return len(old_request_ids)


# Global instance
_data_monitor = None


def initialize_data_monitor(event_bus):
    """Initialize the global data monitor instance"""
    global _data_monitor
    _data_monitor = DataMonitor(event_bus)
    return _data_monitor


def get_data_monitor() -> Optional[DataMonitor]:
    """Get the global data monitor instance"""
    return _data_monitor


def track_request(request_type: str, symbol: str = None, contract_details: Dict = None) -> str:
    """Convenience function to track a request"""
    monitor = get_data_monitor()
    if monitor:
        return monitor.track_request(request_type, symbol, contract_details)
    else:
        logger.warning("Data monitor not initialized")
        return None


def display_results(request_id: str = None, format_type: str = 'table'):
    """Convenience function to display results"""
    monitor = get_data_monitor()
    if monitor:
        monitor.display_request_results(request_id, format_type)
    else:
        logger.warning("Data monitor not initialized") 