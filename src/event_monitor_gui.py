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
from event_monitor import EventMonitor

logger = get_logger('EVENT_MONITOR')

class EventMonitorGUI:
    """
    A GUI window for monitoring event bus updates in a table format.
    Shows unique events and allows manual event emission.
    """
    
    def __init__(self, event_bus=None, parent=None):
        """
        Initialize the event monitor GUI.
        
        Args:
            event_bus: The event bus to monitor and emit events to
            parent: Parent window (optional)
        """
        self.event_bus = event_bus
        self.parent = parent
        
        # Event monitor
        self.event_monitor = None
        if event_bus:
            self.event_monitor = EventMonitor(event_bus)
            # Register for updates
            self.event_monitor.register_update_callback(self._on_event_update)
        
        # Update throttling
        self._last_update_time = 0
        self._update_throttle_ms = 1000  # Update at most once per second
        self._pending_update = False
        
        # Create the window
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Event Bus Monitor")
        self.window.geometry("1200x800")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Setup the GUI
        self._setup_gui()
        
        logger.info("Event Monitor GUI initialized")
    
    def _setup_gui(self):
        """Setup the GUI components."""
        # Main container
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Event Bus Monitor", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Event Monitor Tab
        self._setup_event_monitor_tab()
        
        # Manual Event Emission Tab
        self._setup_manual_emission_tab()
        
        # Statistics Tab
        self._setup_statistics_tab()
    
    def _setup_event_monitor_tab(self):
        """Setup the event monitoring tab."""
        monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="Event Monitor")
        
        # Control panel
        control_frame = ttk.Frame(monitor_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Clear button
        self.clear_button = ttk.Button(control_frame, text="Clear Events", command=self._clear_events)
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.auto_scroll_check = ttk.Checkbutton(
            control_frame, 
            text="Auto-scroll to latest", 
            variable=self.auto_scroll_var
        )
        self.auto_scroll_check.pack(side=tk.LEFT, padx=(0, 10))
        
        # Update frequency slider
        ttk.Label(control_frame, text="Update Freq (ms):").pack(side=tk.LEFT, padx=(10, 2))
        self.update_freq_var = tk.IntVar(value=1000)
        update_freq_scale = ttk.Scale(
            control_frame,
            from_=100,
            to=5000,
            variable=self.update_freq_var,
            orient=tk.HORIZONTAL,
            length=100
        )
        update_freq_scale.pack(side=tk.LEFT, padx=(0, 10))
        update_freq_scale.bind('<ButtonRelease-1>', self._on_update_freq_change)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(control_frame, text="Filters")
        filter_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Event name filter
        ttk.Label(filter_frame, text="Event Name:").pack(side=tk.LEFT, padx=(5, 2))
        self.event_filter_var = tk.StringVar()
        self.event_filter_entry = ttk.Entry(filter_frame, textvariable=self.event_filter_var, width=20)
        self.event_filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.event_filter_entry.bind('<KeyRelease>', self._apply_filters)
        
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
        priority_combo.bind('<<ComboboxSelected>>', self._apply_filters)
        
        # Create treeview for events
        tree_frame = ttk.Frame(monitor_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview with scrollbars
        self.tree = ttk.Treeview(tree_frame, columns=("Event", "Priority", "Count", "First Seen", "Last Seen", "Data"), show="headings")
        
        # Configure columns
        self.tree.heading("Event", text="Event Name")
        self.tree.heading("Priority", text="Priority")
        self.tree.heading("Count", text="Count")
        self.tree.heading("First Seen", text="First Seen")
        self.tree.heading("Last Seen", text="Last Seen")
        self.tree.heading("Data", text="Data Preview")
        
        # Column widths
        self.tree.column("Event", width=200)
        self.tree.column("Priority", width=100)
        self.tree.column("Count", width=80)
        self.tree.column("First Seen", width=150)
        self.tree.column("Last Seen", width=150)
        self.tree.column("Data", width=300)
        
        # Scrollbars
        tree_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        tree_hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to show event details
        self.tree.bind('<Double-1>', self._show_event_details)
    
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
    
    def _setup_statistics_tab(self):
        """Setup the statistics tab."""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Statistics")
        
        # Statistics display
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=20)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Update button
        update_button = ttk.Button(stats_frame, text="Update Statistics", command=self._update_statistics)
        update_button.pack(pady=5)
        
        # Initial statistics
        self._update_statistics()
    
    def _on_event_update(self):
        """Called when events are updated."""
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
        self.window.after(0, self._update_event_display)
    
    def _perform_delayed_update(self):
        """Perform a delayed update after throttling."""
        current_time = time.time() * 1000
        self._last_update_time = current_time
        self._pending_update = False
        self.window.after(0, self._update_event_display)
    
    def _on_update_freq_change(self, event=None):
        """Handle update frequency change."""
        self._update_throttle_ms = self.update_freq_var.get()
        logger.debug(f"Update frequency changed to {self._update_throttle_ms}ms")
    
    def _update_event_display(self):
        """Update the event display table."""
        if not self.event_monitor:
            return
        
        try:
            # Clear current items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Get event records
            event_records = self.event_monitor.get_event_records()
            
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
                self.tree.insert("", "end", values=(
                    event_name,
                    record['priority'].name,
                    record['count'],
                    record['first_seen'].strftime("%H:%M:%S"),
                    record['last_seen'].strftime("%H:%M:%S"),
                    data_preview
                ))
            
            # Auto-scroll to latest if enabled
            if self.auto_scroll_var.get() and self.tree.get_children():
                self.tree.see(self.tree.get_children()[-1])
                
        except Exception as e:
            logger.error(f"Error updating event display: {e}")
    
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
    
    def _apply_filters(self, event=None):
        """Apply filters to the event display."""
        self._update_event_display()
    
    def _clear_events(self):
        """Clear all event records."""
        if self.event_monitor:
            self.event_monitor.clear_records()
        logger.info("Event records cleared")
    
    def _show_event_details(self, event):
        """Show detailed information about an event."""
        if not self.event_monitor:
            return
            
        selection = self.tree.selection()
        if not selection:
            return
        
        # Get the selected item
        item = self.tree.item(selection[0])
        event_name = item['values'][0]
        
        record = self.event_monitor.get_event_details(event_name)
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
    
    def _update_statistics(self):
        """Update the statistics display."""
        if not self.event_monitor:
            stats_text = "No event monitor available.\n"
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", stats_text)
            return
        
        stats = self.event_monitor.get_statistics()
        
        stats_text = "Event Bus Statistics\n"
        stats_text += "=" * 50 + "\n\n"
        
        if stats['total_events'] == 0:
            stats_text += "No events recorded yet.\n"
        else:
            # Basic statistics
            stats_text += f"Total Unique Events: {stats['unique_events']}\n"
            stats_text += f"Total Event Count: {stats['total_count']}\n\n"
            
            # Priority breakdown
            stats_text += "Events by Priority:\n"
            for priority in EventPriority:
                count = stats['priority_breakdown'].get(priority.name, 0)
                stats_text += f"  {priority.name}: {count}\n"
            
            stats_text += "\n"
            
            # Recent events
            if stats['recent_events']:
                stats_text += "Events in Last Minute:\n"
                for event in stats['recent_events']:
                    stats_text += f"  {event['event_name']}: {event['count']} times ({event['seconds_ago']:.1f}s ago)\n"
            else:
                stats_text += "No events in the last minute.\n"
        
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", stats_text)
    
    def on_close(self):
        """Handle window close."""
        try:
            if self.event_monitor:
                self.event_monitor.unregister_update_callback(self._on_event_update)
                self.event_monitor.cleanup()
            
            # Force garbage collection
            gc.collect()
            
            logger.info("Event Monitor GUI closing")
            
            if self.parent:
                self.window.destroy()
            else:
                self.window.quit()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def run(self):
        """Run the GUI main loop."""
        self.window.mainloop()


def create_event_monitor(event_bus=None, parent=None):
    """Create and return an event monitor GUI instance."""
    return EventMonitorGUI(event_bus, parent)


if __name__ == "__main__":
    # Test the event monitor in standalone mode
    monitor = EventMonitorGUI()
    monitor.run() 