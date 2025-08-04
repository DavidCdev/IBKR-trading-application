"""
Enhanced Event Monitor GUI - Advanced monitoring interface
========================================================

Provides comprehensive monitoring interface for:
- Individual subscription options from IB connections
- Memory leak detection and visualization
- Subscription lifecycle tracking
- Performance metrics and optimization
- Real-time subscription status

Key Features:
- Detailed subscription tracking with status
- Memory usage monitoring and leak detection
- Performance metrics visualization
- Subscription management capabilities
- Real-time updates and alerts
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
import threading
import time
import json
import gc
from typing import Dict, Any, Optional
from logger import get_logger
from event_bus import EventPriority
from enhanced_event_monitor import EnhancedEventMonitor, SubscriptionType, SubscriptionStatus

logger = get_logger('ENHANCED_EVENT_MONITOR_GUI')

class EnhancedEventMonitorGUI:
    """
    Enhanced GUI for monitoring event bus with subscription tracking and memory leak detection.
    """
    
    def __init__(self, event_bus=None, parent=None):
        """
        Initialize the enhanced event monitor GUI.
        
        Args:
            event_bus: The event bus to monitor and emit events to
            parent: Parent window (optional)
        """
        self.event_bus = event_bus
        self.parent = parent
        
        # Enhanced event monitor
        self.enhanced_monitor = None
        if event_bus:
            self.enhanced_monitor = EnhancedEventMonitor(event_bus)
            # Register for updates
            self.enhanced_monitor.register_update_callback(self._on_update)
        
        # Update throttling
        self._last_update_time = 0
        self._update_throttle_ms = 1000  # Update at most once per second
        self._pending_update = False
        
        # Create the window
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Enhanced Event Bus Monitor")
        self.window.geometry("1400x900")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Setup the GUI
        self._setup_gui()
        
        logger.info("Enhanced Event Monitor GUI initialized")
    
    def _setup_gui(self):
        """Setup the GUI components."""
        # Main container
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Enhanced Event Bus Monitor", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Subscription Monitor Tab
        self._setup_subscription_monitor_tab()
        
        # Event Monitor Tab
        self._setup_event_monitor_tab()
        
        # Memory Monitor Tab
        self._setup_memory_monitor_tab()
        
        # Performance Monitor Tab
        self._setup_performance_monitor_tab()
        
        # Manual Event Emission Tab
        self._setup_manual_emission_tab()
    
    def _setup_subscription_monitor_tab(self):
        """Setup the subscription monitoring tab."""
        sub_frame = ttk.Frame(self.notebook)
        self.notebook.add(sub_frame, text="Subscription Monitor")
        
        # Control panel
        control_frame = ttk.Frame(sub_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Clear button
        self.clear_subscriptions_button = ttk.Button(control_frame, text="Clear Subscriptions", command=self._clear_subscriptions)
        self.clear_subscriptions_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Auto-refresh checkbox
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.auto_refresh_check = ttk.Checkbutton(
            control_frame, 
            text="Auto-refresh", 
            variable=self.auto_refresh_var
        )
        self.auto_refresh_check.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filter frame
        filter_frame = ttk.LabelFrame(control_frame, text="Filters")
        filter_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Subscription type filter
        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=(5, 2))
        self.subscription_type_filter_var = tk.StringVar(value="ALL")
        type_combo = ttk.Combobox(
            filter_frame, 
            textvariable=self.subscription_type_filter_var,
            values=["ALL"] + [t.value for t in SubscriptionType],
            width=15,
            state="readonly"
        )
        type_combo.pack(side=tk.LEFT, padx=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', self._apply_subscription_filters)
        
        # Status filter
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=(5, 2))
        self.subscription_status_filter_var = tk.StringVar(value="ALL")
        status_combo = ttk.Combobox(
            filter_frame, 
            textvariable=self.subscription_status_filter_var,
            values=["ALL"] + [s.value for s in SubscriptionStatus],
            width=12,
            state="readonly"
        )
        status_combo.pack(side=tk.LEFT, padx=(0, 10))
        status_combo.bind('<<ComboboxSelected>>', self._apply_subscription_filters)
        
        # Create treeview for subscriptions
        tree_frame = ttk.Frame(sub_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview with scrollbars
        columns = ("ID", "Type", "Symbol", "Contract", "Status", "Created", "Last Update", "Errors", "Data Count")
        self.subscription_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        # Configure columns
        self.subscription_tree.heading("ID", text="Subscription ID")
        self.subscription_tree.heading("Type", text="Type")
        self.subscription_tree.heading("Symbol", text="Symbol")
        self.subscription_tree.heading("Contract", text="Contract Details")
        self.subscription_tree.heading("Status", text="Status")
        self.subscription_tree.heading("Created", text="Created")
        self.subscription_tree.heading("Last Update", text="Last Update")
        self.subscription_tree.heading("Errors", text="Errors")
        self.subscription_tree.heading("Data Count", text="Data Count")
        
        # Column widths
        self.subscription_tree.column("ID", width=200)
        self.subscription_tree.column("Type", width=100)
        self.subscription_tree.column("Symbol", width=80)
        self.subscription_tree.column("Contract", width=200)
        self.subscription_tree.column("Status", width=80)
        self.subscription_tree.column("Created", width=120)
        self.subscription_tree.column("Last Update", width=120)
        self.subscription_tree.column("Errors", width=60)
        self.subscription_tree.column("Data Count", width=80)
        
        # Scrollbars
        tree_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.subscription_tree.yview)
        tree_hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.subscription_tree.xview)
        self.subscription_tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
        
        # Grid layout
        self.subscription_tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        tree_hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to show subscription details
        self.subscription_tree.bind('<Double-1>', self._show_subscription_details)
    
    def _setup_event_monitor_tab(self):
        """Setup the event monitoring tab."""
        event_frame = ttk.Frame(self.notebook)
        self.notebook.add(event_frame, text="Event Monitor")
        
        # Control panel
        control_frame = ttk.Frame(event_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Clear button
        self.clear_events_button = ttk.Button(control_frame, text="Clear Events", command=self._clear_events)
        self.clear_events_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.auto_scroll_check = ttk.Checkbutton(
            control_frame, 
            text="Auto-scroll to latest", 
            variable=self.auto_scroll_var
        )
        self.auto_scroll_check.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filter frame
        filter_frame = ttk.LabelFrame(control_frame, text="Filters")
        filter_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Event name filter
        ttk.Label(filter_frame, text="Event Name:").pack(side=tk.LEFT, padx=(5, 2))
        self.event_filter_var = tk.StringVar()
        self.event_filter_entry = ttk.Entry(filter_frame, textvariable=self.event_filter_var, width=20)
        self.event_filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.event_filter_entry.bind('<KeyRelease>', self._apply_event_filters)
        
        # Priority filter
        ttk.Label(filter_frame, text="Priority:").pack(side=tk.LEFT, padx=(5, 2))
        self.priority_filter_var = tk.StringVar(value="ALL")
        priority_combo = ttk.Combobox(
            filter_frame, 
            textvariable=self.priority_filter_var,
            values=["ALL"] + [p.name for p in EventPriority],
            width=10,
            state="readonly"
        )
        priority_combo.pack(side=tk.LEFT, padx=(0, 10))
        priority_combo.bind('<<ComboboxSelected>>', self._apply_event_filters)
        
        # Create treeview for events
        tree_frame = ttk.Frame(event_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview with scrollbars
        self.event_tree = ttk.Treeview(tree_frame, columns=("Event", "Priority", "Count", "First Seen", "Last Seen", "Data"), show="headings")
        
        # Configure columns
        self.event_tree.heading("Event", text="Event Name")
        self.event_tree.heading("Priority", text="Priority")
        self.event_tree.heading("Count", text="Count")
        self.event_tree.heading("First Seen", text="First Seen")
        self.event_tree.heading("Last Seen", text="Last Seen")
        self.event_tree.heading("Data", text="Data Preview")
        
        # Column widths
        self.event_tree.column("Event", width=200)
        self.event_tree.column("Priority", width=100)
        self.event_tree.column("Count", width=80)
        self.event_tree.column("First Seen", width=150)
        self.event_tree.column("Last Seen", width=150)
        self.event_tree.column("Data", width=300)
        
        # Scrollbars
        tree_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.event_tree.yview)
        tree_hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.event_tree.xview)
        self.event_tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
        
        # Grid layout
        self.event_tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        tree_hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to show event details
        self.event_tree.bind('<Double-1>', self._show_event_details)
    
    def _setup_memory_monitor_tab(self):
        """Setup the memory monitoring tab."""
        memory_frame = ttk.Frame(self.notebook)
        self.notebook.add(memory_frame, text="Memory Monitor")
        
        # Memory metrics display
        metrics_frame = ttk.LabelFrame(memory_frame, text="Memory Metrics")
        metrics_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create labels for memory metrics
        self.memory_labels = {}
        metrics = [
            ("current_memory", "Current Memory (MB):"),
            ("peak_memory", "Peak Memory (MB):"),
            ("growth_rate", "Growth Rate (MB/min):"),
            ("gc_collected", "GC Collected Objects:"),
            ("gc_uncollectable", "GC Uncollectable Objects:")
        ]
        
        for i, (key, label) in enumerate(metrics):
            ttk.Label(metrics_frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            self.memory_labels[key] = ttk.Label(metrics_frame, text="-")
            self.memory_labels[key].grid(row=i, column=1, sticky="w", padx=5, pady=2)
        
        # Memory warnings
        warnings_frame = ttk.LabelFrame(memory_frame, text="Memory Warnings")
        warnings_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.memory_warnings_text = scrolledtext.ScrolledText(warnings_frame, height=10)
        self.memory_warnings_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Update button
        update_button = ttk.Button(memory_frame, text="Update Memory Metrics", command=self._update_memory_metrics)
        update_button.pack(pady=5)
        
        # Initial update
        self._update_memory_metrics()
    
    def _setup_performance_monitor_tab(self):
        """Setup the performance monitoring tab."""
        perf_frame = ttk.Frame(self.notebook)
        self.notebook.add(perf_frame, text="Performance Monitor")
        
        # Performance metrics display
        metrics_frame = ttk.LabelFrame(perf_frame, text="Performance Metrics")
        metrics_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create labels for performance metrics
        self.performance_labels = {}
        metrics = [
            ("total_events", "Total Events:"),
            ("events_per_second", "Events/Second:"),
            ("avg_processing_time", "Avg Processing Time (ms):"),
            ("subscription_count", "Total Subscriptions:"),
            ("active_subscriptions", "Active Subscriptions:")
        ]
        
        for i, (key, label) in enumerate(metrics):
            ttk.Label(metrics_frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            self.performance_labels[key] = ttk.Label(metrics_frame, text="-")
            self.performance_labels[key].grid(row=i, column=1, sticky="w", padx=5, pady=2)
        
        # Performance history
        history_frame = ttk.LabelFrame(perf_frame, text="Performance History")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.performance_history_text = scrolledtext.ScrolledText(history_frame, height=15)
        self.performance_history_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Update button
        update_button = ttk.Button(perf_frame, text="Update Performance Metrics", command=self._update_performance_metrics)
        update_button.pack(pady=5)
        
        # Initial update
        self._update_performance_metrics()
    
    def _setup_manual_emission_tab(self):
        """Setup the manual event emission tab."""
        emission_frame = ttk.Frame(self.notebook)
        self.notebook.add(emission_frame, text="Manual Emission")
        
        # Event name input
        input_frame = ttk.LabelFrame(emission_frame, text="Event Details")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Event name
        ttk.Label(input_frame, text="Event Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.event_name_var = tk.StringVar()
        self.event_name_entry = ttk.Entry(input_frame, textvariable=self.event_name_var, width=40)
        self.event_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        # Priority
        ttk.Label(input_frame, text="Priority:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.priority_var = tk.StringVar(value=EventPriority.NORMAL.name)
        priority_combo = ttk.Combobox(
            input_frame,
            textvariable=self.priority_var,
            values=[p.name for p in EventPriority],
            state="readonly",
            width=15
        )
        priority_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Event data
        ttk.Label(input_frame, text="Event Data (JSON):").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        self.event_data_text = scrolledtext.ScrolledText(input_frame, height=8, width=60)
        self.event_data_text.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        self.event_data_text.insert("1.0", "{}")
        
        input_frame.grid_columnconfigure(1, weight=1)
        
        # Buttons
        button_frame = ttk.Frame(emission_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.emit_button = ttk.Button(button_frame, text="Emit Event", command=self._emit_event)
        self.emit_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_form_button = ttk.Button(button_frame, text="Clear Form", command=self._clear_form)
        self.clear_form_button.pack(side=tk.LEFT)
        
        # Recent emissions
        recent_frame = ttk.LabelFrame(emission_frame, text="Recent Manual Emissions")
        recent_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.recent_emissions_text = scrolledtext.ScrolledText(recent_frame, height=10)
        self.recent_emissions_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _on_update(self):
        """Called when events or subscriptions are updated."""
        current_time = time.time() * 1000  # Convert to milliseconds
        
        # Throttle updates to prevent excessive GUI updates
        if current_time - self._last_update_time < self._update_throttle_ms:
            if not self._pending_update:
                self._pending_update = True
                # Schedule a delayed update
                self.window.after(self._update_throttle_ms, self._perform_delayed_update)
            return
        
        # Update immediately if enough time has passed
        self._last_update_time = current_time
        self._pending_update = False
        self.window.after(0, self._update_displays)
    
    def _perform_delayed_update(self):
        """Perform a delayed update after throttling."""
        current_time = time.time() * 1000
        self._last_update_time = current_time
        self._pending_update = False
        self.window.after(0, self._update_displays)
    
    def _update_displays(self):
        """Update all displays."""
        if self.auto_refresh_var.get():
            self._update_subscription_display()
        if self.auto_scroll_var.get():
            self._update_event_display()
    
    def _update_subscription_display(self):
        """Update the subscription display table."""
        if not self.enhanced_monitor:
            return
        
        try:
            # Clear current items
            for item in self.subscription_tree.get_children():
                self.subscription_tree.delete(item)
            
            # Get subscriptions
            subscriptions = self.enhanced_monitor.get_subscriptions()
            
            # Apply filters
            type_filter = self.subscription_type_filter_var.get()
            status_filter = self.subscription_status_filter_var.get()
            
            # Add filtered subscriptions
            for sub_id, subscription in subscriptions.items():
                # Apply type filter
                if type_filter != "ALL" and subscription.subscription_type.value != type_filter:
                    continue
                
                # Apply status filter
                if status_filter != "ALL" and subscription.status.value != status_filter:
                    continue
                
                # Format contract details
                contract_details = self._format_contract_details(subscription.contract)
                
                # Insert into tree
                self.subscription_tree.insert("", "end", values=(
                    sub_id,
                    subscription.subscription_type.value,
                    subscription.contract.get('symbol', ''),
                    contract_details,
                    subscription.status.value,
                    subscription.created_time.strftime("%H:%M:%S"),
                    subscription.last_update_time.strftime("%H:%M:%S"),
                    subscription.error_count,
                    subscription.data_count
                ))
                
        except Exception as e:
            logger.error(f"Error updating subscription display: {e}")
    
    def _update_event_display(self):
        """Update the event display table."""
        if not self.enhanced_monitor:
            return
        
        try:
            # Clear current items
            for item in self.event_tree.get_children():
                self.event_tree.delete(item)
            
            # Get event records
            event_records = self.enhanced_monitor.get_event_records()
            
            # Apply filters
            event_filter = self.event_filter_var.get().lower()
            priority_filter = self.priority_filter_var.get()
            
            # Add filtered events
            for event_name, record in event_records.items():
                # Apply event name filter
                if event_filter and event_filter not in event_name.lower():
                    continue
                
                # Apply priority filter
                if priority_filter != "ALL" and record['priority'].name != priority_filter:
                    continue
                
                # Format data preview
                data_preview = self._format_data_preview(record['last_data'])
                
                # Insert into tree
                self.event_tree.insert("", "end", values=(
                    event_name,
                    record['priority'].name,
                    record['count'],
                    record['first_seen'].strftime("%H:%M:%S"),
                    record['last_seen'].strftime("%H:%M:%S"),
                    data_preview
                ))
            
            # Auto-scroll to latest if enabled
            if self.auto_scroll_var.get() and self.event_tree.get_children():
                self.event_tree.see(self.event_tree.get_children()[-1])
                
        except Exception as e:
            logger.error(f"Error updating event display: {e}")
    
    def _format_contract_details(self, contract: Dict[str, Any]) -> str:
        """Format contract details for display."""
        try:
            if not contract:
                return "No contract"
            
            details = []
            if contract.get('symbol'):
                details.append(f"Symbol: {contract['symbol']}")
            if contract.get('secType'):
                details.append(f"Type: {contract['secType']}")
            if contract.get('expiration'):
                details.append(f"Exp: {contract['expiration']}")
            if contract.get('strike'):
                details.append(f"Strike: {contract['strike']}")
            if contract.get('right'):
                details.append(f"Right: {contract['right']}")
            if contract.get('exchange'):
                details.append(f"Exchange: {contract['exchange']}")
            
            return ", ".join(details) if details else "Unknown contract"
        except Exception:
            return "Error formatting contract"
    
    def _format_data_preview(self, data: Any) -> str:
        """Format data for display in the table."""
        try:
            if data is None:
                return "None"
            elif isinstance(data, dict):
                # Show first few key-value pairs
                items = list(data.items())[:3]
                preview = ", ".join(f"{k}: {v}" for k, v in items)
                if len(data) > 3:
                    preview += f" ... ({len(data)} items)"
                return preview
            elif isinstance(data, (list, tuple)):
                preview = str(data[:3])
                if len(data) > 3:
                    preview += f" ... ({len(data)} items)"
                return preview
            else:
                return str(data)[:50] + ("..." if len(str(data)) > 50 else "")
        except Exception:
            return "Error formatting data"
    
    def _apply_subscription_filters(self, event=None):
        """Apply filters to the subscription display."""
        self._update_subscription_display()
    
    def _apply_event_filters(self, event=None):
        """Apply filters to the event display."""
        self._update_event_display()
    
    def _clear_subscriptions(self):
        """Clear all subscription records."""
        if self.enhanced_monitor:
            self.enhanced_monitor.clear_records()
        logger.info("Subscription records cleared")
    
    def _clear_events(self):
        """Clear all event records."""
        if self.enhanced_monitor:
            self.enhanced_monitor.clear_records()
        logger.info("Event records cleared")
    
    def _show_subscription_details(self, event):
        """Show detailed information about a subscription."""
        if not self.enhanced_monitor:
            return
            
        selection = self.subscription_tree.selection()
        if not selection:
            return
        
        # Get the selected item
        item = self.subscription_tree.item(selection[0])
        sub_id = item['values'][0]
        
        subscriptions = self.enhanced_monitor.get_subscriptions()
        subscription = subscriptions.get(sub_id)
        
        if subscription:
            # Create detail window
            detail_window = tk.Toplevel(self.window)
            detail_window.title(f"Subscription Details: {sub_id}")
            detail_window.geometry("600x500")
            
            # Subscription info
            info_frame = ttk.LabelFrame(detail_window, text="Subscription Information")
            info_frame.pack(fill=tk.X, padx=10, pady=10)
            
            info_text = f"""
Subscription ID: {subscription.subscription_id}
Type: {subscription.subscription_type.value}
Status: {subscription.status.value}
Created: {subscription.created_time}
Last Update: {subscription.last_update_time}
Error Count: {subscription.error_count}
Data Count: {subscription.data_count}
Priority: {subscription.priority.name}
            """
            
            if subscription.last_error:
                info_text += f"\nLast Error: {subscription.last_error}"
            
            info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
            info_label.pack(padx=10, pady=10)
            
            # Contract details
            contract_frame = ttk.LabelFrame(detail_window, text="Contract Details")
            contract_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            contract_text = scrolledtext.ScrolledText(contract_frame)
            contract_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Format contract nicely
            try:
                formatted_contract = json.dumps(subscription.contract, indent=2, default=str)
                contract_text.insert("1.0", formatted_contract)
            except Exception:
                contract_text.insert("1.0", str(subscription.contract))
    
    def _show_event_details(self, event):
        """Show detailed information about an event."""
        if not self.enhanced_monitor:
            return
            
        selection = self.event_tree.selection()
        if not selection:
            return
        
        # Get the selected item
        item = self.event_tree.item(selection[0])
        event_name = item['values'][0]
        
        event_records = self.enhanced_monitor.get_event_records()
        record = event_records.get(event_name)
        
        if record:
            # Create detail window
            detail_window = tk.Toplevel(self.window)
            detail_window.title(f"Event Details: {event_name}")
            detail_window.geometry("600x400")
            
            # Event info
            info_frame = ttk.LabelFrame(detail_window, text="Event Information")
            info_frame.pack(fill=tk.X, padx=10, pady=10)
            
            info_text = f"""
Event Name: {record['event_name']}
Priority: {record['priority'].name}
Total Count: {record['count']}
First Seen: {record['first_seen']}
Last Seen: {record['last_seen']}
            """
            
            info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
            info_label.pack(padx=10, pady=10)
            
            # Data details
            data_frame = ttk.LabelFrame(detail_window, text="Latest Data")
            data_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            data_text = scrolledtext.ScrolledText(data_frame)
            data_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Format data nicely
            try:
                formatted_data = json.dumps(record['last_data'], indent=2, default=str)
                data_text.insert("1.0", formatted_data)
            except Exception:
                data_text.insert("1.0", str(record['last_data']))
    
    def _update_memory_metrics(self):
        """Update memory metrics display."""
        if not self.enhanced_monitor:
            return
        
        try:
            memory_metrics = self.enhanced_monitor.get_memory_metrics()
            
            if 'error' in memory_metrics:
                for key in self.memory_labels:
                    self.memory_labels[key].config(text="No data")
                return
            
            # Update memory labels
            self.memory_labels['current_memory'].config(text=f"{memory_metrics['current_memory_mb']:.1f}")
            self.memory_labels['peak_memory'].config(text=f"{memory_metrics['peak_memory_mb']:.1f}")
            self.memory_labels['growth_rate'].config(text=f"{memory_metrics['memory_growth_rate_mb_per_min']:.1f}")
            self.memory_labels['gc_collected'].config(text=str(memory_metrics['gc_collected_objects']))
            self.memory_labels['gc_uncollectable'].config(text=str(memory_metrics['gc_uncollectable_objects']))
            
            # Update warnings
            warnings_text = ""
            if memory_metrics.get('warnings'):
                for warning in memory_metrics['warnings']:
                    warnings_text += f"{warning}\n"
            else:
                warnings_text = "No memory warnings"
            
            self.memory_warnings_text.delete("1.0", tk.END)
            self.memory_warnings_text.insert("1.0", warnings_text)
            
        except Exception as e:
            logger.error(f"Error updating memory metrics: {e}")
    
    def _update_performance_metrics(self):
        """Update performance metrics display."""
        if not self.enhanced_monitor:
            return
        
        try:
            performance_metrics = self.enhanced_monitor.get_performance_metrics()
            
            # Update performance labels
            self.performance_labels['total_events'].config(text=str(performance_metrics['total_events']))
            self.performance_labels['events_per_second'].config(text=f"{performance_metrics['events_per_second']:.2f}")
            self.performance_labels['avg_processing_time'].config(text=f"{performance_metrics['avg_processing_time_ms']:.2f}")
            self.performance_labels['subscription_count'].config(text=str(performance_metrics['subscription_count']))
            self.performance_labels['active_subscriptions'].config(text=str(performance_metrics['active_subscriptions']))
            
            # Update performance history
            timestamp = datetime.now().strftime("%H:%M:%S")
            history_entry = f"[{timestamp}] Events: {performance_metrics['total_events']}, " \
                          f"Events/sec: {performance_metrics['events_per_second']:.2f}, " \
                          f"Subscriptions: {performance_metrics['active_subscriptions']}/{performance_metrics['subscription_count']}\n"
            
            self.performance_history_text.insert(tk.END, history_entry)
            self.performance_history_text.see(tk.END)
            
            # Limit history to last 100 entries
            lines = self.performance_history_text.get("1.0", tk.END).splitlines()
            if len(lines) > 100:
                self.performance_history_text.delete("1.0", tk.END)
                self.performance_history_text.insert("1.0", "\n".join(lines[-100:]) + "\n")
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def _emit_event(self):
        """Emit an event manually."""
        if not self.event_bus:
            messagebox.showerror("Error", "No event bus available")
            return
        
        event_name = self.event_name_var.get().strip()
        if not event_name:
            messagebox.showerror("Error", "Event name is required")
            return
        
        try:
            # Parse priority
            priority = EventPriority[self.priority_var.get()]
            
            # Parse event data
            data_text = self.event_data_text.get("1.0", tk.END).strip()
            if data_text:
                data = json.loads(data_text)
            else:
                data = {}
            
            # Emit the event
            self.event_bus.emit(event_name, data, priority=priority)
            
            # Log the emission
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] Emitted: {event_name} (Priority: {priority.name})\n"
            self.recent_emissions_text.insert(tk.END, log_entry)
            self.recent_emissions_text.see(tk.END)
            
            # Clear form
            self._clear_form()
            
            logger.info(f"Manually emitted event: {event_name}")
            
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON data: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to emit event: {e}")
    
    def _clear_form(self):
        """Clear the manual emission form."""
        self.event_name_var.set("")
        self.event_data_text.delete("1.0", tk.END)
        self.event_data_text.insert("1.0", "{}")
        self.priority_var.set(EventPriority.NORMAL.name)
    
    def on_close(self):
        """Handle window close."""
        try:
            if self.enhanced_monitor:
                self.enhanced_monitor.unregister_update_callback(self._on_update)
                self.enhanced_monitor.cleanup()
            
            # Force garbage collection
            gc.collect()
            
            logger.info("Enhanced Event Monitor GUI closing")
            
            if self.parent:
                self.window.destroy()
            else:
                self.window.quit()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def run(self):
        """Run the GUI main loop."""
        self.window.mainloop()


def create_enhanced_event_monitor(event_bus=None, parent=None):
    """Create and return an enhanced event monitor GUI instance."""
    return EnhancedEventMonitorGUI(event_bus, parent)


if __name__ == "__main__":
    # Test the enhanced event monitor in standalone mode
    monitor = EnhancedEventMonitorGUI()
    monitor.run() 