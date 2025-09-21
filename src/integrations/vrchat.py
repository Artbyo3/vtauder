#!/usr/bin/env python3
"""
VR Chat Integration Module
Handles OSC communication and music metadata for VR Chat.
"""

import threading
import time
import os
from typing import Dict, Optional, List
from pythonosc import udp_client
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
import psutil
import win32gui
import win32process

class MusicMetadataExtractor:
    """Extract music metadata from various audio formats"""
    
    def __init__(self):
        self.supported_formats = ['.mp3', '.flac', '.ogg', '.m4a', '.wav']
    
    def get_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract metadata from audio file"""
        try:
            if not os.path.exists(file_path):
                return {}
            
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.mp3':
                return self._get_mp3_metadata(file_path)
            elif file_ext == '.flac':
                return self._get_flac_metadata(file_path)
            elif file_ext == '.ogg':
                return self._get_ogg_metadata(file_path)
            elif file_ext in ['.m4a', '.wav']:
                return self._get_basic_metadata(file_path)
            
        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
        
        return {}
    
    def _get_mp3_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract metadata from MP3 file"""
        metadata = {}
        try:
            audio = MP3(file_path, ID3=ID3)
            
            # Get basic info
            if audio.info:
                metadata['duration'] = str(int(audio.info.length))
                metadata['bitrate'] = str(audio.info.bitrate // 1000)
            
            # Get ID3 tags
            if audio.tags:
                tags = audio.tags
                metadata['title'] = str(tags.get('TIT2', ['Unknown'])[0])
                metadata['artist'] = str(tags.get('TPE1', ['Unknown'])[0])
                metadata['album'] = str(tags.get('TALB', ['Unknown'])[0])
                metadata['year'] = str(tags.get('TDRC', ['Unknown'])[0])
                metadata['genre'] = str(tags.get('TCON', ['Unknown'])[0])
                
        except Exception as e:
            print(f"Error reading MP3 metadata: {e}")
        
        return metadata
    
    def _get_flac_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract metadata from FLAC file"""
        metadata = {}
        try:
            audio = FLAC(file_path)
            
            # Get basic info
            if audio.info:
                metadata['duration'] = str(int(audio.info.length))
                metadata['bitrate'] = str(audio.info.bits_per_sample)
            
            # Get Vorbis comments
            if audio.tags:
                tags = audio.tags
                metadata['title'] = str(tags.get('title', ['Unknown'])[0])
                metadata['artist'] = str(tags.get('artist', ['Unknown'])[0])
                metadata['album'] = str(tags.get('album', ['Unknown'])[0])
                metadata['date'] = str(tags.get('date', ['Unknown'])[0])
                metadata['genre'] = str(tags.get('genre', ['Unknown'])[0])
                
        except Exception as e:
            print(f"Error reading FLAC metadata: {e}")
        
        return metadata
    
    def _get_ogg_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract metadata from OGG file"""
        metadata = {}
        try:
            audio = OggVorbis(file_path)
            
            # Get basic info
            if audio.info:
                metadata['duration'] = str(int(audio.info.length))
                metadata['bitrate'] = str(audio.info.bitrate // 1000)
            
            # Get Vorbis comments
            if audio.tags:
                tags = audio.tags
                metadata['title'] = str(tags.get('title', ['Unknown'])[0])
                metadata['artist'] = str(tags.get('artist', ['Unknown'])[0])
                metadata['album'] = str(tags.get('album', ['Unknown'])[0])
                metadata['date'] = str(tags.get('date', ['Unknown'])[0])
                metadata['genre'] = str(tags.get('genre', ['Unknown'])[0])
                
        except Exception as e:
            print(f"Error reading OGG metadata: {e}")
        
        return metadata
    
    def _get_basic_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract basic metadata from other formats"""
        metadata = {}
        try:
            audio = mutagen.File(file_path)
            if audio:
                metadata['duration'] = str(int(audio.info.length))
                metadata['title'] = os.path.basename(file_path)
                
        except Exception as e:
            print(f"Error reading basic metadata: {e}")
        
        return metadata

class VRChatOSCClient:
    """OSC client for VR Chat communication"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host = host
        self.port = port
        self.client = udp_client.SimpleUDPClient(host, port)
        self.is_connected = False
        
    def send_music_info(self, title: str, artist: str, album: str = "", duration: str = ""):
        """Send music information to VR Chat chat via OSC"""
        try:
            # Send to VR Chat's chat system - use the provided title/artist directly
            message = f"{title} {('- ' + artist) if artist else ''}".strip()
            self.client.send_message("/chatbox/input", [message, True])  # [message, send]
            # Also send to avatar parameters for compatibility
            combined_info = f"{title} - {artist}".strip()
            self.client.send_message("/avatar/parameters/MusicInfo", combined_info[:64])
            print(f"🎵 Sent to VR Chat chat: {combined_info}")
        except Exception as e:
            print(f"Error sending OSC message: {e}")
    

    def send_chat_message(self, message: str):
        """Send a custom message to VR Chat chatbox via OSC"""
        try:
            self.client.send_message("/chatbox/input", [message, True])
            print(f"💬 Sent to VR Chat chat: {message}")
        except Exception as e:
            print(f"Error sending chat message: {e}")

class MusicTracker:
    """Track currently playing music from various applications"""
    
    def __init__(self):
        self.metadata_extractor = MusicMetadataExtractor()
        self.current_music = {}
        self.last_check = 0
        self.check_interval = 2.0  # Check every 2 seconds
        
    def get_current_music(self) -> Dict[str, str]:
        """Get currently playing music information"""
        current_time = time.time()
        
        # Only check periodically to avoid performance issues
        if current_time - self.last_check < self.check_interval:
            return self.current_music
        
        self.last_check = current_time
        
        try:
            # Check common music applications
            music_apps = [
                "spotify.exe",
                "iTunes.exe", 
                "vlc.exe",
                "chrome.exe",  # For web-based music
                "firefox.exe",
                "msedge.exe",
                "discord.exe",  # For Discord music bots
                "youtube.exe",
                "deezer.exe",
                "tidal.exe"
            ]
            
            found_apps = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'].lower() in [app.lower() for app in music_apps]:
                        found_apps.append(proc.info['name'])
                        music_info = self._get_app_music_info(proc)
                        if music_info:
                            self.current_music = music_info
                            return music_info
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if found_apps:
                print(f"🔍 Found music apps: {found_apps}")
            else:
                print("🔍 No music apps found")
                    
        except Exception as e:
            print(f"Error tracking music: {e}")
        
        return self.current_music
    
    def _get_app_music_info(self, process) -> Optional[Dict[str, str]]:
        """Get music information from specific application"""
        try:
            app_name = process.info['name'].lower()
            
            if app_name == "spotify.exe":
                return self._get_spotify_info()
            elif app_name == "vlc.exe":
                return self._get_vlc_info(process)
            elif app_name in ["chrome.exe", "firefox.exe", "msedge.exe"]:
                return self._get_browser_music_info(process)
            elif app_name == "discord.exe":
                return self._get_discord_music_info()
            else:
                return self._get_generic_music_info(process)
                
        except Exception as e:
            print(f"Error getting app music info: {e}")
            return None
    
    def _get_spotify_info(self) -> Optional[Dict[str, str]]:
        """Get Spotify music information from window title"""
        try:
            windows = []
            
            def enum_windows_callback(hwnd, windows_list):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for Spotify window titles
                    if title and 'spotify' in title.lower():
                        # Remove " - Spotify" from the end
                        if title.endswith(' - Spotify'):
                            title = title[:-10]  # Remove " - Spotify"
                        
                        # Check if it has the format "Song - Artist"
                        if ' - ' in title:
                            parts = title.split(' - ')
                            if len(parts) >= 2:
                                song_title = parts[0].strip()
                                artist = parts[1].strip()
                                
                                # Skip if it's just "Spotify" or empty
                                if song_title and artist and song_title.lower() != 'spotify':
                                    windows_list.append({
                                        'title': song_title,
                                        'artist': artist,
                                        'album': 'Spotify',
                                        'app': 'Spotify'
                                    })
                                    print(f"🎵 Detected Spotify: {song_title} - {artist}")
                return True
            
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            if windows:
                return windows[0]
            
            # If no Spotify window found, return None instead of fallback
            return None
            
        except Exception as e:
            print(f"Error getting Spotify info: {e}")
            return None
    
    def _get_vlc_info(self, process) -> Optional[Dict[str, str]]:
        """Get VLC music information from window title"""
        try:
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for VLC window titles
                    if title and 'vlc' in title.lower():
                        # VLC format: "filename - VLC media player"
                        if ' - VLC media player' in title:
                            filename = title.replace(' - VLC media player', '').strip()
                            # Extract song name from filename
                            if filename:
                                # Remove file extension
                                if '.' in filename:
                                    filename = filename.rsplit('.', 1)[0]
                                return {
                                    'title': filename,
                                    'artist': 'VLC Media',
                                    'album': 'VLC',
                                    'app': 'VLC'
                                }
            return None
        except Exception as e:
            print(f"Error getting VLC info: {e}")
            return None
    
    def _get_browser_music_info(self, process) -> Optional[Dict[str, str]]:
        """Get browser-based music information from window title"""
        try:
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for music services in browser tabs
                    if title:
                        title_lower = title.lower()
                        # Check for common music services
                        if any(service in title_lower for service in ['youtube', 'spotify', 'soundcloud', 'deezer', 'tidal']):
                            # Extract info from title
                            if ' - ' in title:
                                parts = title.split(' - ')
                                if len(parts) >= 2:
                                    # Last part is usually the browser name, second to last might be artist
                                    if len(parts) >= 3:
                                        song_title = parts[-3].strip()
                                        artist = parts[-2].strip()
                                    else:
                                        song_title = parts[0].strip()
                                        artist = parts[1].strip()
                                    
                                    # Remove browser name from artist if present
                                    for browser in ['chrome', 'firefox', 'edge', 'opera']:
                                        if browser in artist.lower():
                                            artist = artist.replace(f' - {browser.capitalize()}', '').strip()
                                    
                                    if song_title and artist:
                                        return {
                                            'title': song_title,
                                            'artist': artist,
                                            'album': 'Web Browser',
                                            'app': 'Browser'
                                        }
            return None
        except Exception as e:
            print(f"Error getting browser music info: {e}")
            return None
    
    def _get_discord_music_info(self) -> Optional[Dict[str, str]]:
        """Get Discord music bot information"""
        try:
            return {
                'title': 'Discord Music',
                'artist': 'Bot',
                'album': 'Discord',
                'app': 'Discord'
            }
        except Exception as e:
            print(f"Error getting Discord music info: {e}")
            return None
    
    def _get_generic_music_info(self, process) -> Optional[Dict[str, str]]:
        """Get generic music information"""
        try:
            return {
                'title': f'{process.info["name"]} Audio',
                'artist': 'Application',
                'album': process.info['name'],
                'app': process.info['name']
            }
        except Exception as e:
            print(f"Error getting generic music info: {e}")
            return None

class VRChatIntegration:
    def start_osc(self):
        """Inicia la integración OSC (alias de start_integration)"""
        return self.start_integration()

    def stop_osc(self):
        """Detiene la integración OSC (alias de stop_integration)"""
        return self.stop_integration()
    """Main VR Chat integration controller"""
    
    def __init__(self, osc_host: str = "127.0.0.1", osc_port: int = 9000):
        self.osc_client = VRChatOSCClient(osc_host, osc_port)
        self.music_tracker = MusicTracker()
        self.is_active = False
        self.update_thread = None
        self.last_music_info = None  # Track last sent music info
        
    def start_integration(self):
        """Start VR Chat integration"""
        if self.is_active:
            return False
        
        self.is_active = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        print("🎮 VR Chat integration started")
        return True
    
    def stop_integration(self):
        """Stop VR Chat integration"""
        self.is_active = False
        if self.update_thread:
            self.update_thread.join(timeout=2)
        
        print("🎮 VR Chat integration stopped")
    
    def _update_loop(self):
        """Main update loop for VR Chat integration"""
        while self.is_active:
            try:
                # VR Chat integration is now handled by the main UI
                # This loop just keeps the integration active
                time.sleep(5.0)  # Check every 5 seconds
                
            except Exception as e:
                print(f"VR Chat integration error: {e}")
                time.sleep(5.0)
    
    def send_global_info(self, info: str):
        """Send all combined info to a single global OSC parameter"""
        self.osc_client.send_global_info(info)
    
    def __del__(self):
        """Cleanup"""
        self.stop_integration() 