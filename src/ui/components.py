#!/usr/bin/env python3
"""
UI Components
Reusable UI components for the application.
"""

import customtkinter as ctk
from typing import Callable, Optional, Any
import threading
import time


class VUMeter(ctk.CTkFrame):
    """Audio level meter component"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(self, height=12)
        self.progress.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.progress.set(0)
        
        # Level label
        self.level_label = ctk.CTkLabel(self, text="0%", font=ctk.CTkFont(size=9))
        self.level_label.grid(row=1, column=0, pady=(0, 5))
    
    def update_level(self, level: float):
        """Update audio level (0.0 to 1.0)"""
        self.progress.set(level)
        self.level_label.configure(text=f"{int(level * 100)}%")


class StatusIndicator(ctk.CTkFrame):
    """Status indicator with colored dot and text"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        
        # Status dot (canvas)
        self.dot_canvas = ctk.CTkCanvas(self, width=20, height=20, highlightthickness=0)
        self.dot_canvas.grid(row=0, column=0, padx=(5, 2), pady=5)
        
        # Status text
        self.status_label = ctk.CTkLabel(self, text="Disconnected")
        self.status_label.grid(row=0, column=1, padx=(2, 5), pady=5, sticky="w")
        
        # Initial state
        self.set_status("disconnected", "Disconnected")
    
    def set_status(self, status: str, text: str):
        """Set status with color and text"""
        colors = {
            'connected': '#4CAF50',    # Green
            'connecting': '#FF9800',   # Orange
            'disconnected': '#F44336', # Red
            'warning': '#FFC107'       # Yellow
        }
        
        color = colors.get(status, '#9E9E9E')  # Default gray
        
        # Clear and redraw dot
        self.dot_canvas.delete("all")
        self.dot_canvas.create_oval(6, 6, 14, 14, fill=color, outline=color)
        
        # Update text
        self.status_label.configure(text=text)


class SettingsPanel(ctk.CTkFrame):
    """Expandable settings panel"""
    
    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        
        self.is_expanded = False
        self.content_widgets = []
        
        # Header with expand/collapse button
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        self.title_label = ctk.CTkLabel(self.header_frame, text=title, 
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.expand_button = ctk.CTkButton(self.header_frame, text="▼", width=30,
                                          command=self.toggle_expansion)
        self.expand_button.grid(row=0, column=1, padx=10, pady=10)
        
        # Content frame (initially hidden)
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid_columnconfigure(0, weight=1)
    
    def toggle_expansion(self):
        """Toggle panel expansion"""
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.content_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
            self.expand_button.configure(text="▲")
        else:
            self.content_frame.grid_remove()
            self.expand_button.configure(text="▼")
    
    def add_setting(self, widget):
        """Add a widget to the settings panel"""
        row = len(self.content_widgets)
        widget.grid(row=row, column=0, sticky="ew", padx=10, pady=5)
        self.content_widgets.append(widget)


class DeviceSelector(ctk.CTkFrame):
    """Device selection component"""
    
    def __init__(self, parent, title: str, devices: list, 
                 callback: Optional[Callable] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        
        self.callback = callback
        self.devices = devices
        
        # Title
        self.title_label = ctk.CTkLabel(self, text=title)
        self.title_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # Device dropdown
        device_names = [dev.get('name', f"Device {dev.get('index', 0)}") for dev in devices]
        self.device_var = ctk.StringVar(value=device_names[0] if device_names else "No devices")
        
        self.device_combo = ctk.CTkComboBox(self, values=device_names, 
                                           variable=self.device_var,
                                           command=self._on_device_changed)
        self.device_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    def _on_device_changed(self, value):
        """Handle device selection change"""
        if self.callback:
            # Find device index by name
            for device in self.devices:
                if device.get('name') == value:
                    self.callback(device.get('index', 0))
                    break
    
    def update_devices(self, devices: list):
        """Update available devices"""
        self.devices = devices
        device_names = [dev.get('name', f"Device {dev.get('index', 0)}") for dev in devices]
        self.device_combo.configure(values=device_names)
        
        if device_names:
            self.device_var.set(device_names[0])
    
    def get_selected_device(self) -> Optional[dict]:
        """Get currently selected device"""
        current_name = self.device_var.get()
        for device in self.devices:
            if device.get('name') == current_name:
                return device
        return None


class LogViewer(ctk.CTkFrame):
    """Log viewer component"""
    
    def __init__(self, parent, max_lines: int = 100, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.max_lines = max_lines
        self.log_lines = []
        
        # Text widget with scrollbar
        self.text_widget = ctk.CTkTextbox(self, state="disabled")
        self.text_widget.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    
    def add_log(self, message: str, level: str = "info"):
        """Add log message"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level.upper()}: {message}"
        
        self.log_lines.append(log_entry)
        
        # Limit number of lines
        if len(self.log_lines) > self.max_lines:
            self.log_lines.pop(0)
        
        # Update display
        self._update_display()
    
    def _update_display(self):
        """Update text widget display"""
        self.text_widget.configure(state="normal")
        self.text_widget.delete(1.0, "end")
        self.text_widget.insert(1.0, "\n".join(self.log_lines))
        self.text_widget.configure(state="disabled")
        self.text_widget.see("end")
    
    def clear_logs(self):
        """Clear all logs"""
        self.log_lines.clear()
        self._update_display()


class ConnectionStatus(ctk.CTkFrame):
    """Connection status display with auto-refresh"""
    
    def __init__(self, parent, check_function: Callable, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        
        self.check_function = check_function
        self.is_monitoring = False
        
        # Status indicator
        self.status_indicator = StatusIndicator(self)
        self.status_indicator.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Refresh button
        self.refresh_button = ctk.CTkButton(self, text="⟳", width=30,
                                           command=self.refresh_status)
        self.refresh_button.grid(row=0, column=1, padx=5, pady=5)
    
    def start_monitoring(self, interval: float = 5.0):
        """Start automatic status monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, 
                                              args=(interval,), daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop automatic status monitoring"""
        self.is_monitoring = False
    
    def refresh_status(self):
        """Manually refresh status"""
        try:
            is_connected = self.check_function()
            if is_connected:
                self.status_indicator.set_status("connected", "Connected")
            else:
                self.status_indicator.set_status("disconnected", "Disconnected")
        except Exception as e:
            self.status_indicator.set_status("warning", f"Error: {str(e)[:30]}")
    
    def _monitor_loop(self, interval: float):
        """Monitoring loop"""
        while self.is_monitoring:
            self.refresh_status()
            time.sleep(interval)
