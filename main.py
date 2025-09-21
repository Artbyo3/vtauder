
#!/usr/bin/env python3
"""
VTAuder - Virtual Audio Cable for VR Chat
Main application entry point with modular architecture.
"""

import sys
import os
import customtkinter as ctk
import threading
from pathlib import Path
from PIL import Image, ImageTk

# For lyrics API

# Add src to Python path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Application imports
from config.settings import config_manager
from src.integrations.vrchat import VRChatIntegration
from src.integrations.stt import realtime_stt
from src.ui.components import VUMeter, StatusIndicator, DeviceSelector
from src.utils.system import get_microphone_list, get_window_processes

# UI Configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Custom colors for better aesthetics
COLORS = {
    "primary": ("#3b82f6", "#1d4ed8"),
    "success": ("#10b981", "#059669"),
    "danger": ("#dc2626", "#b91c1c"),
    "warning": ("#f59e0b", "#d97706"),
    "bg_light": ("#f8f9fa", "#1e1e1e"),
    "bg_secondary": ("#f1f5f9", "#2d3748"),
    "text_primary": ("#2b2b2b", "#ffffff"),
    "text_secondary": ("#374151", "#e5e7eb")
}


class VTAuderApp:
    # DVD animation state
    _dvd_anim_running = False
    _dvd_anim_index = 0
    _dvd_anim_after_id = None
    DVD_TRACK_LEN = 7  # Number of dashes in track
    DVD_SPEEDS = [1000, 2000, 3000]  # ms

    def start_dvd_animation(self):
        """Start DVD animation when paused."""
        self._dvd_anim_running = True
        self._dvd_anim_index = 0
        self._dvd_anim_direction = 1  # 1 for right, -1 for left
        self.animate_dvd_status()

    def stop_dvd_animation(self):
        self._dvd_anim_running = False
        if self._dvd_anim_after_id:
            try:
                self.root.after_cancel(self._dvd_anim_after_id)
            except Exception:
                pass
            self._dvd_anim_after_id = None

    def animate_dvd_status(self):
        import random
        if not self._dvd_anim_running:
            return
        # Pick position: 0=left, 1=middle, 2=right
        pos = random.choice([0, 1, 2])
        track = ["—"] * self.DVD_TRACK_LEN
        # Place 'DVD' at pos
        dvd_str = "DVD"
        # Calculate index for DVD
        if pos == 0:
            # Left
            dvd_line = f"🟥{dvd_str}{''.join(track)}🟦"
        elif pos == 1:
            # Middle
            mid = self.DVD_TRACK_LEN // 2
            dvd_line = f"🟥{''.join(track[:mid])}{dvd_str}{''.join(track[mid:])}🟦"
        else:
            # Right
            dvd_line = f"🟥{''.join(track)}{dvd_str}🟦"
        base_msg = f"⏸️ Paused\n{dvd_line}"
        msg = self.format_message_with_time(base_msg)
        sent = self.send_chatbox_message(msg, "dvd")
        if sent:
            print(f"DVD Animation: {msg.replace(chr(10), ' | ')}")
        # Randomly pick next speed (interval)
        next_speed = random.choice(self.DVD_SPEEDS)
        self._dvd_anim_after_id = self.root.after(next_speed, self.animate_dvd_status)
    # --- Global chatbox rate limiter ---
    _last_chatbox_sent = 0
    _chatbox_timeout = False
    _chatbox_timeout_until = 0
    
    # --- Improved message queue system ---
    _message_queue = []  # Queue for pending messages
    _max_queue_size = 10  # Maximum queued messages
    _min_interval = 1.5  # Reduced from 2.0s to 1.5s
    _max_message_length = 144  # VRChat chat limit
    _queue_processing = False  # Prevent multiple queue processors

    def validate_message(self, text: str) -> tuple[bool, str]:
        """Validate and sanitize message text"""
        if not text or not text.strip():
            return False, "Empty message"
        
        # Remove excessive whitespace and newlines
        text = ' '.join(text.split())
        
        # Check length
        if len(text) > self._max_message_length:
            text = text[:self._max_message_length-3] + "..."
        
        # Remove potentially problematic characters
        text = text.replace('\x00', '')  # Remove null bytes
        text = text.replace('\r', '')    # Remove carriage returns
        
        return True, text

    def add_message_to_queue(self, text: str, message_type: str = "general") -> bool:
        """Add message to queue with validation"""
        is_valid, sanitized_text = self.validate_message(text)
        if not is_valid:
            print(f"[QUEUE] Invalid message: {text}")
            return False
        
        # Check queue size
        if len(self._message_queue) >= self._max_queue_size:
            # Remove oldest message
            self._message_queue.pop(0)
            print(f"[QUEUE] Queue full, removed oldest message")
        
        # Add to queue
        import time
        message_data = {
            'text': sanitized_text,
            'type': message_type,
            'timestamp': time.time()
        }
        self._message_queue.append(message_data)
        
        # Start processing if not already running
        if not self._queue_processing:
            self._process_message_queue()
        
        return True

    def _process_message_queue(self):
        """Process queued messages with rate limiting"""
        if self._queue_processing or not self._message_queue:
            return
        
        self._queue_processing = True
        import time
        now = time.time()
        
        # Check if we can send a message
        if (self._chatbox_timeout and now < self._chatbox_timeout_until) or \
           (now - self._last_chatbox_sent < self._min_interval):
            # Schedule retry
            time_until_ready = max(
                self._chatbox_timeout_until - now if self._chatbox_timeout else 0,
                self._min_interval - (now - self._last_chatbox_sent)
            )
            self.root.after(int(time_until_ready * 1000), self._process_message_queue)
            self._queue_processing = False
            return
        
        # Send next message
        if self._message_queue:
            message_data = self._message_queue.pop(0)
            success = self._send_message_direct(message_data['text'])
            
            if success:
                self.append_chat_log(f"{message_data['type'].title()}: {message_data['text']}")
            
            # Schedule next message
            self.root.after(int(self._min_interval * 1000), self._process_message_queue)
        else:
            self._queue_processing = False

    def _send_message_direct(self, text: str) -> bool:
        """Send message directly to VRChat (internal method)"""
        import time
        try:
            osc_client = self.vrchat_integration.osc_client
            print(f"[OSC SEND] Address: /chatbox/input | Message: {text}")
            osc_client.send_chat_message(text)
            self._last_chatbox_sent = time.time()
            return True
        except Exception as e:
            # Detect spam timeout from error message
            if "Timed out for spam" in str(e) or "spam" in str(e).lower():
                self._chatbox_timeout = True
                self._chatbox_timeout_until = time.time() + 30
                print("[CHATBOX] Spam timeout detected, pausing for 30s")
            print(f"Error sending chatbox message: {e}")
            return False

    def send_chatbox_message(self, text, message_type="general"):
        """Send a message to VRChat chatbox using improved queue system."""
        return self.add_message_to_queue(text, message_type)

    def append_chat_log(self, text):
        """Append a message to the chat log panel"""
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", text + "\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def send_vrchat_message(self):
        """Send manual chat message to VRChat using improved queue system"""
        message = self.chat_entry.get()
        if message:
            formatted_message = self.format_message_with_time(message)
            sent = self.send_chatbox_message(formatted_message, "manual")
            if sent:
                self.status_text.configure(text=f"✅ Message queued: {formatted_message}")
                self.chat_entry.delete(0, 'end')
            else:
                self.status_text.configure(text=f"⚠️ Invalid message. Please try again.")
                self.root.after(2000, lambda: self.status_text.configure(text="Ready - Welcome to VTAuder"))
    # Animation frames for music playing
    MUSIC_ASCII_ANIMATION = "ﮩ٨ـﮩﮩ٨ـﮩ٨ـﮩﮩ٨ـ"  # Example animation frames

    MUSIC_ANIMATION_INTERVAL = 2000  # ms (0.5 FPS)
    def start_music_animation(self, title, artist):
        self._music_anim_index = 0
        self._music_anim_title = title
        self._music_anim_artist = artist
        self._music_anim_running = True
        self.animate_music_status(send_osc=True)

    def stop_music_animation(self):
        self._music_anim_running = False
        # Cancel any pending animation callbacks
        if hasattr(self, '_music_anim_after_id') and self._music_anim_after_id:
            try:
                self.root.after_cancel(self._music_anim_after_id)
            except Exception:
                pass
            self._music_anim_after_id = None

    def animate_music_status(self, send_osc=False):
        try:
            if not getattr(self, '_music_anim_running', False):
                print("[ANIM] Animation stopped (_music_anim_running is False)")
                if getattr(self, 'started', False):
                    print("[ANIM] Auto-restarting animation...")
                    self._music_anim_running = True
                    self._music_anim_after_id = self.root.after(1000, lambda: self.animate_music_status(send_osc=True))
                return
            ascii_anim = self.MUSIC_ASCII_ANIMATION
            # Create a circular animation that shows all frames
            idx = self._music_anim_index % len(ascii_anim)
            frame = ascii_anim[idx:idx+3] if idx + 3 <= len(ascii_anim) else ascii_anim[idx:] + ascii_anim[:3-(len(ascii_anim)-idx)]
            base_text = f"{frame} Now Playing: {self._music_anim_title} - {self._music_anim_artist}"
            anim_text = self.format_message_with_time(base_text)
            lyrics_text = ""
            if hasattr(self, '_last_lyrics') and self._last_lyrics:
                lines = [line for line in self._last_lyrics.splitlines() if line.strip()]
                max_lines = 30
                lines = lines[:max_lines]
                lyrics_text = '\n'.join(lines)
                if lyrics_text:
                    anim_text = f"{anim_text}\n{lyrics_text}"
            if hasattr(self, 'send_window_info_var') and self.send_window_info_var.get():
                win_info = self.get_active_window_info()
                if win_info:
                    win_info = win_info[:40] + ("..." if len(win_info) > 40 else "")
                    anim_text = f"{anim_text}\n{win_info}"
            print(f"ANIM DEBUG: idx={self._music_anim_index}, frame='{frame}', anim_text='{anim_text}'")
            self.status_text.configure(text=anim_text)
            # Send only to VRChat chat box (rate limited)
            if send_osc or self._music_anim_index > 0:
                sent = self.send_chatbox_message(anim_text, "music")
                if sent:
                    print(f"OSC CHATBOX: {anim_text}")
                else:
                    print(f"OSC CHATBOX: Message queued")
            self._music_anim_index += 1
        except Exception as exc:
            print(f"[ANIM] Exception in animate_music_status: {exc}")
            if getattr(self, 'started', False):
                print("[ANIM] Exception detected, auto-restarting animation...")
                self._music_anim_running = True
                self._music_anim_after_id = self.root.after(1500, lambda: self.animate_music_status(send_osc=True))
        finally:
            if getattr(self, '_music_anim_running', False):
                self._music_anim_after_id = self.root.after(self.MUSIC_ANIMATION_INTERVAL, lambda: self.animate_music_status(send_osc=True))
    """Main application class"""
    
    def __init__(self):
        print("[INIT] VTAuderApp initializing...")
        # Load configuration
        self.config = config_manager.config
        print(f"[CONFIG] Loaded config: {self.config}")

        # Initialize main window with improved styling
        self.root = ctk.CTk()
        self.root.title("VTAuder - Virtual Audio Cable")
        self.root.geometry("920x720")
        self.root.minsize(650, 450)
        
        # Set application icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'VTauder.png')
            if os.path.exists(icon_path):
                # Load and set the icon
                icon_image = Image.open(icon_path)
                icon_photo = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, icon_photo)
                print(f"[UI] Application icon set: {icon_path}")
            else:
                print(f"[UI] Icon file not found: {icon_path}")
        except Exception as e:
            print(f"[UI] Error setting icon: {e}")
        
        print("[UI] Main window initialized.")

        # VRChat OSC enabled variable (must be before STT usage)
        self.vrchat_enabled_var = ctk.BooleanVar(value=self.config.vrchat.osc_enabled)
        print(f"[VRCHAT] OSC enabled: {self.vrchat_enabled_var.get()}")
        # Option to enable SteamVR gesture support
        self.steamvr_enabled_var = ctk.BooleanVar(value=False)
        print(f"[STEAMVR] Gesture enabled: {self.steamvr_enabled_var.get()}")
        # Core components
        self.audio_router = None  # Audio features paused
        # Always use port 9000 for VRChat OSC
        self.vrchat_integration = VRChatIntegration(osc_port=9000)
        print("[VRCHAT] Integration initialized on port 9000.")
        # SteamVR gesture recognizer
        try:
            from src.integrations.steamvr_gesture import SteamVRGestureRecognizer
            self.steamvr_gesture = SteamVRGestureRecognizer(self.on_gesture_text)
            print("[STEAMVR] Gesture recognizer loaded.")
        except Exception as e:
            print(f"[SteamVR] Gesture recognizer not available: {e}")
            self.steamvr_gesture = None
        # Application state
        self.is_routing = False  # Audio routing paused
        self.started = False  # App started flag
        self.selected_window = None
        self.monitoring_threads = []
        self.all_windows = []  # Store for search filtering
        self.settings_panel = None  # Settings panel reference
        self.settings_visible = False  # Settings panel visibility state
        # UI Components
        print("[UI] Setting up UI...")
        self.setup_ui()
        print("[UI] UI setup complete.")
        self.setup_system_tray()
        print("[TRAY] System tray setup complete.")
        # Start monitoring
        # Auto-refresh
        self.auto_refresh()
        print("[INIT] VTAuderApp initialization complete.")
        # SteamVR gesture will be started only if enabled in UI
    def toggle_steamvr_gesture(self):
        """Enable or disable SteamVR gesture support"""
        enabled = self.steamvr_enabled_var.get()
        print(f"[STEAMVR] toggle_steamvr_gesture called. Enabled: {enabled}")
        if enabled:
            if self.steamvr_gesture:
                try:
                    print("[STEAMVR] Attempting to start gesture recognizer...")
                    started = self.steamvr_gesture.start()
                    if started:
                        print("[STEAMVR] Gesture recognizer started.")
                        self.update_status("SteamVR gesture support enabled")
                    else:
                        print("[STEAMVR] SteamVR not available. Please start SteamVR and connect your headset.")
                        self.update_status("SteamVR not available. Please start SteamVR and connect your headset.")
                        self.steamvr_enabled_var.set(False)
                except Exception as e:
                    print(f"[STEAMVR] Error starting gesture recognizer: {e}")
                    self.update_status(f"SteamVR error: {e}")
                    self.steamvr_enabled_var.set(False)
            else:
                print("[STEAMVR] Gesture module not available.")
                self.update_status("SteamVR gesture module not available.")
                self.steamvr_enabled_var.set(False)
        else:
            if self.steamvr_gesture:
                try:
                    print("[STEAMVR] Stopping gesture recognizer...")
                    self.steamvr_gesture.stop()
                except Exception as e:
                    print(f"[STEAMVR] Error stopping gesture recognizer: {e}")
            print("[STEAMVR] Gesture support disabled.")
            self.update_status("SteamVR gesture support disabled")
    
    def toggle_time_display(self):
        """Enable or disable time display in messages"""
        enabled = self.send_time_var.get()
        print(f"[TIME] toggle_time_display called. Enabled: {enabled}")
        if enabled:
            self.update_status("Time display enabled")
        else:
            self.update_status("Time display disabled")
    
    def get_current_time(self):
        """Get current time formatted for display"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def format_message_with_time(self, message):
        """Format message with current time if time display is enabled"""
        if self.send_time_var.get():
            current_time = self.get_current_time()
            return f"[{current_time}] {message}"
        return message
    
    def on_gesture_text(self, text):
        """Handle gesture-to-text output and send to VRChat chatbox"""
        print(f"[GESTURE] on_gesture_text called with: {text}")
        self.status_text.configure(text=f"🤟 Gesture: {text}")
        if self.vrchat_enabled_var.get():
            formatted_text = self.format_message_with_time(text)
            print(f"[GESTURE] Sending gesture text to VRChat chatbox: {formatted_text}")
            sent = self.send_chatbox_message(formatted_text, "gesture")
            print(f"[GESTURE DEBUG] VRChat message send result: {sent}")
            if sent:
                print(f"[GESTURE] Gesture text sent to VRChat chatbox: {formatted_text}")
                self.status_text.configure(text=f"✅ VRChat: {formatted_text}")
                self.append_chat_log(f"Gesture: {formatted_text}")
            else:
                print(f"[GESTURE] Rate limited or timeout when sending gesture text.")
                self.status_text.configure(text=f"⚠️ Rate limited or timeout. Try again later.")
    
    def setup_ui(self):
        """Setup main user interface"""
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        
        # Header
        self.create_header()
        
        # Main content
        self.create_main_content()
        
        # Status bar
        self.create_status_bar()
    
    def create_header(self):
        """Create application header"""
        header_frame = ctk.CTkFrame(self.root, height=85, corner_radius=15)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header_frame.grid_propagate(False)
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="VTAuder",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="w", padx=18, pady=22)
        
        # Status and controls
        control_frame = ctk.CTkFrame(header_frame, corner_radius=12)
        control_frame.grid(row=0, column=1, sticky="e", padx=18, pady=18)
        control_frame.grid_columnconfigure(0, weight=0)
        control_frame.grid_columnconfigure(1, weight=0)
        control_frame.grid_columnconfigure(2, weight=0)
        
        self.status_indicator = StatusIndicator(control_frame)
        self.status_indicator.grid(row=0, column=0, padx=(12, 18), pady=6)
        
        self.main_button = ctk.CTkButton(
            control_frame,
            text="▶ Start",
            command=self.toggle_routing,
            width=110,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=12
        )
        self.main_button.grid(row=0, column=1, padx=(0, 8), pady=6)
        
        # Settings button
        self.settings_button = ctk.CTkButton(
            control_frame,
            text="⚙️ Settings",
            command=self.open_settings,
            width=100,
            height=38,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=12,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40")
        )
        self.settings_button.grid(row=0, column=2, padx=(0, 12), pady=6)
    
    def create_main_content(self):
        """Create main content area"""
        main_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=0)  # For settings panel
        
        # Left panel: only audio source selection
        self.create_sources_panel(main_frame)
        # Right panel: options in box/menu
        self.create_options_panel(main_frame)
        
        # Settings panel (initially hidden)
        self.create_settings_panel(main_frame)
    def create_options_panel(self, parent):
        """Right panel with options in box/menu"""
        options_frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        options_frame.grid(row=0, column=1, sticky="nsew")
        options_frame.grid_columnconfigure(0, weight=1)
        options_frame.grid_columnconfigure(1, weight=1)
        # Bento box menu: 2 columns, 3 rows
        # Volume
        box_vol = ctk.CTkFrame(options_frame, corner_radius=10)
        box_vol.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        box_vol.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box_vol, text="Volume", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.volume_slider = ctk.CTkSlider(box_vol, from_=0, to=1, command=self.on_volume_change)
        self.volume_slider.grid(row=1, column=0, sticky="ew", padx=10)
        self.volume_slider.set(1.0)
        self.volume_label = ctk.CTkLabel(box_vol, text="100%")
        self.volume_label.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 8))
        # Microphone
        box_mic = ctk.CTkFrame(options_frame, corner_radius=10)
        box_mic.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        box_mic.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box_mic, text="Microphone", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        microphones = get_microphone_list()
        mic_devices = [{'name': name, 'index': i} for i, name in enumerate(microphones)]
        self.mic_selector = DeviceSelector(box_mic, "", mic_devices, callback=self.on_mic_changed)
        self.mic_selector.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        # VU Meter
        box_vu = ctk.CTkFrame(options_frame, corner_radius=10)
        box_vu.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        box_vu.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box_vu, text="Audio Level", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.vu_meter = VUMeter(box_vu)
        self.vu_meter.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        # STT
        box_stt = ctk.CTkFrame(options_frame, corner_radius=10)
        box_stt.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        box_stt.grid_columnconfigure(0, weight=1)
        self.stt_enabled_var = ctk.BooleanVar(value=self.config.stt.realtime_enabled)
        stt_checkbox = ctk.CTkCheckBox(box_stt, text="Enable STT", variable=self.stt_enabled_var, command=self.toggle_stt)
        stt_checkbox.grid(row=0, column=0, sticky="w", padx=10, pady=10)
        # VU Meter for STT mic
        self.stt_vu_meter = VUMeter(box_stt)
        self.stt_vu_meter.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        # Manual VRChat chat box
        box_chat = ctk.CTkFrame(options_frame, corner_radius=10)
        box_chat.grid(row=2, column=1, sticky="nsew", padx=8, pady=8)
        box_chat.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box_chat, text="Send message to VRChat chat", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.chat_entry = ctk.CTkEntry(box_chat, placeholder_text="Type your message...")
        self.chat_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        send_chat_btn = ctk.CTkButton(box_chat, text="Send", command=self.send_vrchat_message)
        send_chat_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        # New option: Send active window info
        box_misc = ctk.CTkFrame(options_frame, corner_radius=10)
        box_misc.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        box_misc.grid_columnconfigure(0, weight=1)
        self.send_window_info_var = ctk.BooleanVar(value=False)
        send_window_checkbox = ctk.CTkCheckBox(box_misc, text="Send active window to OSC chat", variable=self.send_window_info_var)
        send_window_checkbox.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        # SteamVR gesture enable checkbox
        steamvr_checkbox = ctk.CTkCheckBox(box_misc, text="Enable SteamVR Gesture-to-Text", variable=self.steamvr_enabled_var, command=self.toggle_steamvr_gesture)
        steamvr_checkbox.grid(row=1, column=0, sticky="w", padx=10, pady=10)

        # Time display option
        self.send_time_var = ctk.BooleanVar(value=False)
        time_checkbox = ctk.CTkCheckBox(box_misc, text="Send current time", variable=self.send_time_var, command=self.toggle_time_display)
        time_checkbox.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        # Chat log panel
        box_chatlog = ctk.CTkFrame(options_frame, corner_radius=10)
        box_chatlog.grid(row=3, column=1, sticky="nsew", padx=8, pady=8)
        box_chatlog.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box_chatlog, text="Message history", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.chat_log = ctk.CTkTextbox(box_chatlog, height=120, state="disabled")
        self.chat_log.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
    
    def create_settings_panel(self, parent):
        """Create settings panel (initially hidden)"""
        self.settings_panel = ctk.CTkFrame(parent, corner_radius=15, fg_color=("gray90", "gray20"))
        self.settings_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(8, 0))
        self.settings_panel.grid_remove()  # Initially hidden
        
        # Settings content
        settings_content = ctk.CTkFrame(self.settings_panel, fg_color="transparent")
        settings_content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            settings_content,
            text="⚙️ Settings",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Placeholder content
        placeholder_frame = ctk.CTkFrame(settings_content, corner_radius=10)
        placeholder_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        placeholder_label = ctk.CTkLabel(
            placeholder_frame,
            text="Settings panel coming soon!\n\nThis will include:\n• Audio device preferences\n• VRChat connection settings\n• STT configuration\n• Theme customization\n• Advanced options",
            font=ctk.CTkFont(size=14),
            justify="left"
        )
        placeholder_label.pack(pady=30)
        
        # Close button
        close_button = ctk.CTkButton(
            settings_content,
            text="Close Settings",
            command=self.close_settings,
            width=120,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        close_button.pack(pady=(10, 0))
    
    def get_active_window_info(self):
        """Get info about the currently active window. If VS Code, include file name. Always return in English."""
        try:
            import platform
            if platform.system() == "Windows":
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                # If VS Code, try to get file name from title
                if "Visual Studio Code" in title:
                    parts = title.split(" - Visual Studio Code")
                    if len(parts) > 1:
                        file_name = parts[0].strip()
                        return f"Active window: VS Code ({file_name})"
                    return "Active window: VS Code (unknown file)"
                # For other editors, try to extract file/document name if possible
                known_editors = ["Notepad++", "Sublime Text", "Atom", "Notepad", "Word", "Excel", "PowerPoint"]
                for editor in known_editors:
                    if editor in title:
                        parts = title.split(f" - {editor}")
                        if len(parts) > 1:
                            file_name = parts[0].strip()
                            return f"Active window: {editor} ({file_name})"
                        return f"Active window: {editor} (unknown file)"
                # Default: return window title
                return f"Active window: {title}" if title else "Active window: (unknown)"
            else:
                return "Active window: (not supported on this OS)"
        except Exception as e:
            return f"Active window: (error: {e})"
    def update_stt_vu(self, level):
        """Update STT VU meter with current mic level"""
        if hasattr(self, 'stt_vu_meter'):
            self.stt_vu_meter.set_level(level)
    
    def create_sources_panel(self, parent):
        """Create audio sources selection panel"""
        sources_frame = ctk.CTkFrame(parent, corner_radius=15)
        sources_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        sources_frame.grid_columnconfigure(0, weight=1)
        sources_frame.grid_rowconfigure(1, weight=1)
        
        # Header with improved styling
        header_frame = ctk.CTkFrame(sources_frame, corner_radius=10, height=50)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header_frame.grid_propagate(False)
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        
        sources_header = ctk.CTkLabel(
            header_frame,
            text="Audio Sources",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        sources_header.grid(row=0, column=0, sticky="w", padx=15, pady=12)
        
        # Auto-refresh indicator
        self.auto_indicator = ctk.CTkLabel(
            header_frame,
            text="🔄 Auto",
            font=ctk.CTkFont(size=10),
            text_color=("gray60", "gray40")
        )
        self.auto_indicator.grid(row=0, column=1, sticky="e", padx=15, pady=12)
        
        # Sources list with better styling
        self.sources_list = ctk.CTkScrollableFrame(
            sources_frame, 
            corner_radius=12,
            scrollbar_button_color=("gray75", "gray25"),
            scrollbar_button_hover_color=("gray65", "gray35")
        )
        self.sources_list.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.sources_list.grid_columnconfigure(0, weight=1)
        
        # Enhanced refresh button with counter
        button_frame = ctk.CTkFrame(sources_frame, corner_radius=8, height=45)
        button_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        button_frame.grid_propagate(False)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=0)
        
        refresh_button = ctk.CTkButton(
            button_frame,
            text=" Refresh Sources",
            command=self.refresh_sources,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        refresh_button.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        
        # Sources counter
        self.sources_counter = ctk.CTkLabel(
            button_frame,
            text="0 found",
            font=ctk.CTkFont(size=10),
            text_color=("gray60", "gray40")
        )
        self.sources_counter.grid(row=0, column=1, sticky="e", padx=8, pady=6)
    
    def create_status_bar(self):
        """Create status bar"""
        status_frame = ctk.CTkFrame(self.root, height=35, corner_radius=12)
        status_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        status_frame.grid_propagate(False)
        status_frame.grid_columnconfigure(0, weight=1)
        
        self.status_text = ctk.CTkLabel(
            status_frame,
            text="Ready - Welcome to VTAuder",
            font=ctk.CTkFont(size=11, weight="normal")
        )
        self.status_text.grid(row=0, column=0, sticky="w", padx=15, pady=8)
    
    def setup_system_tray(self):
        """Setup system tray functionality"""
        # TODO: Implement system tray
        pass
    
    
    def monitor_vrchat(self):
        """Monitor VRChat connection"""
        while True:
            try:
                if self.vrchat_enabled_var.get():
                    # Check VRChat connection
                    is_connected = self.check_vrchat_connection()
                    # Update UI in main thread if needed
                
                threading.Event().wait(5.0)  # Check every 5 seconds
            except Exception as e:
                print(f"VRChat monitoring error: {e}")
                threading.Event().wait(5.0)
    
    def refresh_sources(self):
        """Refresh audio sources list for song info selection (audio routing paused)"""
        try:
            # Clear existing items
            for widget in self.sources_list.winfo_children():
                widget.destroy()
            # Get window processes
            windows = get_window_processes()
            # Update counter
            if hasattr(self, 'sources_counter'):
                self.sources_counter.configure(text=f"{len(windows)} found")
            for i, window in enumerate(windows):
                window_frame = ctk.CTkFrame(
                    self.sources_list, 
                    corner_radius=10,
                    border_width=1,
                    border_color=("gray80", "gray20")
                )
                window_frame.grid(row=i, column=0, sticky="ew", padx=6, pady=3)
                window_frame.grid_columnconfigure(1, weight=1)
                icon_frame = ctk.CTkFrame(window_frame, width=40, height=40, corner_radius=8)
                icon_frame.grid(row=0, column=0, padx=8, pady=8)
                icon_frame.grid_propagate(False)
                # Center the icon within the frame
                icon_frame.grid_rowconfigure(0, weight=1)
                icon_frame.grid_columnconfigure(0, weight=1)
                
                app_emoji = self.get_app_emoji(window.get('process_name', ''), window.get('title', ''))
                if app_emoji['type'] == 'image':
                    try:
                        img_path = app_emoji['path']
                        if not os.path.isabs(img_path):
                            img_path = os.path.join(os.path.dirname(__file__), img_path)
                        # Use CTkImage for better HighDPI support
                        icon_img = ctk.CTkImage(light_image=Image.open(img_path), dark_image=Image.open(img_path), size=(28, 28))
                        icon_label = ctk.CTkLabel(icon_frame, text="", image=icon_img)
                        icon_label.image = icon_img  # Keep reference
                    except Exception:
                        icon_label = ctk.CTkLabel(icon_frame, text='🎵', font=ctk.CTkFont(size=16))
                else:
                    icon_label = ctk.CTkLabel(icon_frame, text=app_emoji['value'], font=ctk.CTkFont(size=16))
                # Center the icon within the frame
                icon_label.grid(row=0, column=0, padx=0, pady=0, sticky="")
                info_frame = ctk.CTkFrame(window_frame, fg_color="transparent")
                info_frame.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
                info_frame.grid_columnconfigure(0, weight=1)
                title = window.get('title', 'Unknown')[:45]
                title_label = ctk.CTkLabel(
                    info_frame,
                    text=title,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w"
                )
                title_label.grid(row=0, column=0, sticky="ew", pady=(0, 2))
                process = window.get('process_name', 'Unknown')
                process_label = ctk.CTkLabel(
                    info_frame,
                    text=f"📁 {process}",
                    font=ctk.CTkFont(size=10),
                    text_color=("gray60", "gray40"),
                    anchor="w"
                )
                process_label.grid(row=1, column=0, sticky="ew")
                is_selected = (self.selected_window and 
                             self.selected_window.get('title') == window.get('title'))
                select_button = ctk.CTkButton(
                    window_frame,
                    text="✓ Selected" if is_selected else "Select",
                    width=80,
                    height=32,
                    command=lambda w=window: self.select_window(w),
                    corner_radius=8,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=("green", "darkgreen") if is_selected else None
                )
                select_button.grid(row=0, column=2, padx=8, pady=8)
            if not windows:
                no_sources_frame = ctk.CTkFrame(self.sources_list, corner_radius=10)
                no_sources_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=10)
                no_sources_label = ctk.CTkLabel(
                    no_sources_frame,
                    text="🔍 No audio sources found\nTry refreshing or check if applications are running",
                    font=ctk.CTkFont(size=12),
                    text_color=("gray60", "gray40")
                )
                no_sources_label.grid(row=0, column=0, padx=20, pady=15)
            self.update_status(f"Found {len(windows)} audio sources (routing paused)")
            if hasattr(self, 'auto_indicator'):
                self.auto_indicator.configure(text="🔄 Updated")
                self.root.after(2000, lambda: self.auto_indicator.configure(text="🔄 Auto"))
        except Exception as e:
            self.update_status(f"Error refreshing sources: {e}")
            if hasattr(self, 'sources_counter'):
                self.sources_counter.configure(text="Error")
    

    def select_window(self, window):
        """Select audio source window for song info (audio routing paused)"""
        self.selected_window = window
        title = window.get('title', 'Unknown')
        self.update_status(f"Selected: {title[:30]}")
        self.refresh_sources()
        # If started, send song info to VRChat automatically and show in status bar
        if getattr(self, 'started', False) and self.vrchat_enabled_var.get():
            self.last_sent_song_info = None
            self.last_sent_artist = None
            self._keep_sending_song = True
            self.send_and_repeat_song_info()

    def send_and_repeat_song_info(self):
        """Send current song info and keep resending if unchanged (paused/skipped). Only one OSC message at a time."""
        if not getattr(self, 'started', False) or not self.vrchat_enabled_var.get() or not self.selected_window:
            self._keep_sending_song = False
            return
        # Cancel any pending animation before sending new message
        self.stop_music_animation()
        self.stop_dvd_animation()
        # Refresh selected window info from process list
        windows = get_window_processes()
        selected_process = self.selected_window.get('process_name', '')
        updated_window = None
        for w in windows:
            if w.get('process_name', '') == selected_process and w.get('title', ''):
                updated_window = w
                break
        if updated_window:
            self.selected_window = updated_window
        song_info = self.get_current_song_info()
        process = self.selected_window.get('process_name', '').lower()
        window_title = self.selected_window.get('title', '')
        artist = ""
        title = ""
        paused_titles = ["Spotify", "Spotify Free", "Spotify Premium", "Spotify - Web Player"]
        is_paused = False
        if 'spotify' in process:
            if ' - ' in window_title:
                parts = window_title.split(' - ')
                if len(parts) >= 2:
                    artist, title = parts[0].strip(), parts[1].strip()
            elif window_title.strip() in paused_titles:
                title = "⏸️ Paused"
                artist = ""
                is_paused = True
        else:
            if ' - ' in window_title:
                parts = window_title.split(' - ')
                if len(parts) >= 2:
                    artist, title = parts[0].strip(), parts[1].strip()
                else:
                    title = window_title
            else:
                title = song_info if song_info else window_title
        if title:
            try:
                print(f"[DEBUG] Attempting to send Next Song OSC: {title} - {artist}")
                if is_paused:
                    self.status_text.configure(text=f"⏸️ Paused")
                    self.start_dvd_animation()
                else:
                    last_title = getattr(self, 'last_sent_song_info', None)
                    last_artist = getattr(self, 'last_sent_artist', None)
                    if (title != last_title) or (artist != last_artist):
                        next_song_msg = f"⏭️ Next Song: {title} - {artist}" if artist else f"⏭️ Next Song: {title}"
                        sent = self.send_chatbox_message(next_song_msg)
                        if sent:
                            print(f"[DEBUG] OSC sent: {next_song_msg}")
                            self.append_chat_log(f"Next Song: {next_song_msg}")
                        else:
                            print(f"[DEBUG] OSC NOT sent (rate limited or error): {next_song_msg}")
                            self.append_chat_log(f"[Rate Limited] Next Song: {next_song_msg}")
                        self.start_music_animation(title, artist)
                    else:
                        self.start_music_animation(title, artist)
                    self.last_sent_song_info = title
                    self.last_sent_artist = artist
            except Exception as e:
                print(f"Error handling music info: {e}")
                self.root.after(4000, lambda: self.status_text.configure(text="Ready - Welcome to VTAuder"))
        else:
            self.status_text.configure(text="No song info available to send to VRChat.")
            self.root.after(4000, lambda: self.status_text.configure(text="Ready - Welcome to VTAuder"))
        if self._keep_sending_song:
            self.root.after(5000, self.send_and_repeat_song_info)
    
    def get_app_emoji(self, process_name, window_title=""):
        """Get emoji or icon path based on application type and window title"""
        process_lower = process_name.lower()
        title_lower = window_title.lower()
        
        # Check for YouTube Music in browser by title
        if 'youtube music' in title_lower or 'music.youtube.com' in title_lower:
            return {'type': 'image', 'path': os.path.join('assets', 'youtube_music.png')}
        
        # Future: Add more icons for other apps
        icon_map = {
            'spotify': {'type': 'image', 'path': os.path.join('assets', 'spotify.png')},
        }
        for key, icon in icon_map.items():
            if key in process_lower:
                return icon
        emoji_map = {
            'chrome': '🌐', 'firefox': '🦊', 'edge': '🔷', 'opera': '🎭',
            'spotify': '🎵', 'vlc': '🎬', 'discord': '🎮', 'steam': '🎮',
            'obs': '📹', 'streamlabs': '📺', 'zoom': '📞', 'teams': '💼',
            'notepad': '📝', 'code': '💻', 'studio': '🎨', 'photoshop': '🎨',
            'excel': '📊', 'word': '📄', 'powerpoint': '📊',
            'game': '🎯', 'player': '▶️', 'music': '🎼', 'youtube': '📺'
        }
        for key, emoji in emoji_map.items():
            if key in process_lower:
                return {'type': 'emoji', 'value': emoji}
        return {'type': 'emoji', 'value': '📱'}
    
    def toggle_routing(self):
        """Start the app and enable song transmission on source selection"""
        self.started = True
        self.main_button.configure(text=" Stop")
        self.status_indicator.set_status("connected", "Started")
        self.update_status("Program started. Select a source to send song info to VRChat.")
    def get_current_song_info(self):
        """Get current song info from selected window (for VRChat transmission)"""
        if not self.selected_window:
            return None
        process = self.selected_window.get('process_name', '').lower()
        title = self.selected_window.get('title', '')
        title_lower = title.lower()
        
        # Check for music apps and YouTube Music in browser
        if title and (
            'spotify' in process or 
            'music' in process or 
            'youtube music' in title_lower or 
            'music.youtube.com' in title_lower
        ):
            return title
        return None
    
    def on_volume_change(self, value):
        """Volume change paused"""
        self.volume_label.configure(text=f"{int(value * 100)}% (audio paused)")
    
    def on_mic_changed(self, mic_index):
        """Microphone selection paused"""
        self.update_status("Microphone selection paused")
    
    def toggle_stt(self):
        """Toggle Speech-to-Text"""
        enabled = self.stt_enabled_var.get()
        if enabled:
            mic_index = config_manager.config.audio.default_mic_index
            gain = config_manager.config.audio.default_gain
            # Wrap the callback to also update VU meter
            def stt_callback(text, level=None):
                print(f"[STT CALLBACK] Received text: {text} | Level: {level}")
                self.on_stt_text(text)
                if level is not None:
                    self.update_stt_vu(level)
            success = realtime_stt.start_listening(
                mic_index=mic_index,
                gain=gain,
                callback=stt_callback
            )
            if success:
                self.update_status("STT enabled")
            else:
                self.stt_enabled_var.set(False)
                self.update_status("Failed to enable STT")
        else:
            realtime_stt.stop_listening()
            self.update_status("STT disabled")
        config_manager.update_stt_config(realtime_enabled=enabled)
    
    def on_stt_text(self, text):
        """Handle STT text output with improved text combination and queue system"""
        print(f"[STT] on_stt_text called with: {text}")
        
        # Initialize STT buffer if not exists
        if not hasattr(self, '_stt_chat_buffer'):
            self._stt_chat_buffer = ""
        
        # Improved text combination logic
        if self._stt_chat_buffer and text.strip():
            # Check if we should start a new sentence
            last_char = self._stt_chat_buffer[-1] if self._stt_chat_buffer else ""
            first_char = text[0] if text else ""
            
            # If previous text doesn't end with punctuation and new text starts with capital
            if last_char not in ".!?" and first_char.isupper():
                self._stt_chat_buffer += ". " + text
            else:
                # Simple concatenation with space
                self._stt_chat_buffer += " " + text
        else:
            self._stt_chat_buffer = text
        
        # Pause music animation for 10 seconds
        self.stop_music_animation()
        self.status_text.configure(text=f"🗣️ STT: {self._stt_chat_buffer}")
        
        # Send to game if VRChat OSC is enabled using improved queue
        if self.vrchat_enabled_var.get():
            formatted_text = self.format_message_with_time(self._stt_chat_buffer)
            sent = self.send_chatbox_message(formatted_text, "stt")
            if sent:
                self.status_text.configure(text=f"✅ VRChat: {formatted_text}")
            else:
                self.status_text.configure(text=f"⚠️ Message queued, will send when ready")
        
        # Resume music animation after 10 seconds
        self.root.after(10000, lambda: self.start_music_animation(
            getattr(self, '_music_anim_title', ''), 
            getattr(self, '_music_anim_artist', '')
        ))
    
    def clear_stt_buffer(self):
        """Clear the STT text buffer"""
        if hasattr(self, '_stt_chat_buffer'):
            self._stt_chat_buffer = ""
            print("[STT] Buffer cleared")
    
    def get_queue_status(self) -> str:
        """Get current queue status for debugging"""
        queue_size = len(self._message_queue)
        timeout_status = "TIMEOUT" if self._chatbox_timeout else "READY"
        return f"Queue: {queue_size}/{self._max_queue_size} | Status: {timeout_status}"
    
    def toggle_vrchat_osc(self):
        """Toggle VRChat OSC"""
        enabled = self.vrchat_enabled_var.get()
        
        if enabled:
            success = self.vrchat_integration.start_osc()
            if success:
                self.update_status("VRChat OSC enabled")
            else:
                self.vrchat_enabled_var.set(False)
                self.update_status("Failed to enable VRChat OSC")
        else:
            self.vrchat_integration.stop_osc()
            self.update_status("VRChat OSC disabled")
        
        config_manager.update_vrchat_config(osc_enabled=enabled)
    
    def check_vrchat_connection(self) -> bool:
        """Check VRChat connection status"""
        # TODO: Implement actual VRChat connection check
        return self.vrchat_enabled_var.get()
    
    def update_status(self, message):
        """Update status bar message"""
        self.status_text.configure(text=message)
    
    # Auto-refresh for audio sources is currently paused
    def auto_refresh(self):
        pass
    
    def open_settings(self):
        """Toggle settings panel visibility"""
        if not self.settings_visible:
            # Show settings panel
            self.settings_panel.grid()
            self.settings_visible = True
            self.settings_button.configure(text="⚙️ Hide Settings")
            # Adjust window height to accommodate settings panel
            current_geometry = self.root.geometry()
            # Parse geometry: "WIDTHxHEIGHT+X+Y" or "WIDTHxHEIGHT"
            if '+' in current_geometry:
                size_part, pos_part = current_geometry.split('+', 1)
                width, height = size_part.split('x')
                new_height = int(height) + 200  # Add space for settings panel
                self.root.geometry(f"{width}x{new_height}+{pos_part}")
            else:
                width, height = current_geometry.split('x')
                new_height = int(height) + 200  # Add space for settings panel
                self.root.geometry(f"{width}x{new_height}")
            self.update_status("Settings panel opened")
        else:
            # Hide settings panel
            self.close_settings()
    
    def close_settings(self):
        """Close settings panel"""
        if self.settings_panel and self.settings_visible:
            self.settings_panel.grid_remove()
            self.settings_visible = False
            self.settings_button.configure(text="⚙️ Settings")
            # Restore original window height
            current_geometry = self.root.geometry()
            # Parse geometry: "WIDTHxHEIGHT+X+Y" or "WIDTHxHEIGHT"
            if '+' in current_geometry:
                size_part, pos_part = current_geometry.split('+', 1)
                width, height = size_part.split('x')
                new_height = int(height) - 200  # Remove space for settings panel
                self.root.geometry(f"{width}x{new_height}+{pos_part}")
            else:
                width, height = current_geometry.split('x')
                new_height = int(height) - 200  # Remove space for settings panel
                self.root.geometry(f"{width}x{new_height}")
            self.update_status("Settings panel closed")
    
    def run(self):
        """Run the application"""
        self.root.mainloop()
    
    def on_closing(self):
        """Handle application closing"""
        # Save configuration
        config_manager.save()

        # Stop all monitoring
        if self.is_routing:
            self.audio_router.stop_routing()

        if self.stt_enabled_var.get():
            realtime_stt.stop_listening()

        if self.vrchat_enabled_var.get():
            self.vrchat_integration.stop_osc()

        if hasattr(self, 'steamvr_gesture') and self.steamvr_gesture:
            self.steamvr_gesture.stop()

        self.root.destroy()


def main():
    """Main entry point"""
    app = VTAuderApp()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.run()


if __name__ == "__main__":
    main()
