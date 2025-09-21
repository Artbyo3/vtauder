#!/usr/bin/env python3
"""
Configuration Management
Handles application settings and configuration persistence.
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AudioConfig:
    """Audio configuration settings"""
    sample_rate: int = 44100
    chunk_size: int = 1024
    channels: int = 2
    default_mic_index: int = 0
    default_gain: float = 1.0
    silence_threshold: float = 0.02


@dataclass
class STTConfig:
    """Speech-to-Text configuration"""
    engine: str = "whisper"  # whisper, speech_recognition
    model_size: str = "tiny"  # tiny, base, small, medium, large
    language: Optional[str] = None  # Auto-detect if None
    realtime_enabled: bool = False
    speech_timeout: float = 0.4
    min_speech_length: float = 0.3


@dataclass
class VRChatConfig:
    """VRChat integration configuration"""
    osc_enabled: bool = False
    osc_ip: str = "127.0.0.1"
    osc_port: int = 9000
    music_metadata_enabled: bool = True
    auto_detect_music: bool = True


@dataclass
class UIConfig:
    """User interface configuration"""
    theme: str = "dark"
    color_theme: str = "blue"
    window_width: int = 800
    window_height: int = 600
    start_minimized: bool = False
    minimize_to_tray: bool = True


@dataclass
class AppConfig:
    """Main application configuration"""
    audio: AudioConfig
    stt: STTConfig
    vrchat: VRChatConfig
    ui: UIConfig
    
    def __init__(self):
        self.audio = AudioConfig()
        self.stt = STTConfig()
        self.vrchat = VRChatConfig()
        self.ui = UIConfig()


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.join(os.path.expanduser("~"), ".vtauder")
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self.config = AppConfig()
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
        
        # Load existing configuration
        self.load()
    
    def load(self) -> bool:
        """Load configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Update configuration with loaded data
                if 'audio' in data:
                    self.config.audio = AudioConfig(**data['audio'])
                if 'stt' in data:
                    self.config.stt = STTConfig(**data['stt'])
                if 'vrchat' in data:
                    self.config.vrchat = VRChatConfig(**data['vrchat'])
                if 'ui' in data:
                    self.config.ui = UIConfig(**data['ui'])
                
                print(f"✅ Configuration loaded from {self.config_file}")
                return True
        
        except Exception as e:
            print(f"❌ Error loading configuration: {e}")
        
        return False
    
    def save(self) -> bool:
        """Save configuration to file"""
        try:
            data = {
                'audio': asdict(self.config.audio),
                'stt': asdict(self.config.stt),
                'vrchat': asdict(self.config.vrchat),
                'ui': asdict(self.config.ui)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Configuration saved to {self.config_file}")
            return True
        
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset configuration to default values"""
        self.config = AppConfig()
        self.save()
    
    def get_audio_config(self) -> AudioConfig:
        """Get audio configuration"""
        return self.config.audio
    
    def get_stt_config(self) -> STTConfig:
        """Get STT configuration"""
        return self.config.stt
    
    def get_vrchat_config(self) -> VRChatConfig:
        """Get VRChat configuration"""
        return self.config.vrchat
    
    def get_ui_config(self) -> UIConfig:
        """Get UI configuration"""
        return self.config.ui
    
    def update_audio_config(self, **kwargs):
        """Update audio configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config.audio, key):
                setattr(self.config.audio, key, value)
        self.save()
    
    def update_stt_config(self, **kwargs):
        """Update STT configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config.stt, key):
                setattr(self.config.stt, key, value)
        self.save()
    
    def update_vrchat_config(self, **kwargs):
        """Update VRChat configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config.vrchat, key):
                setattr(self.config.vrchat, key, value)
        self.save()
    
    def update_ui_config(self, **kwargs):
        """Update UI configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config.ui, key):
                setattr(self.config.ui, key, value)
        self.save()


# Global configuration manager instance
config_manager = ConfigManager()
