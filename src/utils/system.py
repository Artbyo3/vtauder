#!/usr/bin/env python3
"""
System utilities for audio and process management.
"""

import psutil
import win32gui
import win32process
from typing import List, Dict, Optional, Tuple
import pyaudio
import speech_recognition as sr


def get_audio_devices() -> Dict[str, List[Dict]]:
    """Get available audio input and output devices"""
    pa = pyaudio.PyAudio()
    devices = {'input': [], 'output': []}
    
    try:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            device = {
                'index': i,
                'name': info['name'],
                'channels': info['maxInputChannels'] if info['maxInputChannels'] > 0 else info['maxOutputChannels'],
                'sample_rate': int(info['defaultSampleRate'])
            }
            
            if info['maxInputChannels'] > 0:
                devices['input'].append(device)
            if info['maxOutputChannels'] > 0:
                devices['output'].append(device)
    
    except Exception as e:
        print(f"Error getting audio devices: {e}")
    finally:
        pa.terminate()
    
    return devices


def get_microphone_list() -> List[str]:
    """Get list of available microphones"""
    try:
        return sr.Microphone.list_microphone_names()
    except Exception as e:
        print(f"Error getting microphones: {e}")
        return []


def get_running_processes() -> List[Dict]:
    """Get list of running processes with audio"""
    processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name'] and proc_info['exe']:
                    processes.append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'exe': proc_info['exe']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    except Exception as e:
        print(f"Error getting processes: {e}")
    
    return processes


def get_window_processes() -> List[Dict]:
    """Get list of windows with their process information"""
    windows = []
    
    def enum_windows_callback(hwnd, windows_list):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                
                window_info = {
                    'hwnd': hwnd,
                    'title': win32gui.GetWindowText(hwnd),
                    'pid': pid,
                    'process_name': process.name(),
                    'exe_path': process.exe() if process.exe() else ""
                }
                windows_list.append(window_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    
    try:
        win32gui.EnumWindows(enum_windows_callback, windows)
    except Exception as e:
        print(f"Error enumerating windows: {e}")
    
    return windows


def find_vrchat_process() -> Optional[Dict]:
    """Find VRChat process if running"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            if 'vrchat' in proc.info['name'].lower():
                return {
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'exe': proc.info['exe']
                }
    except Exception as e:
        print(f"Error finding VRChat process: {e}")
    
    return None


def is_process_running(process_name: str) -> bool:
    """Check if a process is running"""
    try:
        for proc in psutil.process_iter(['name']):
            if process_name.lower() in proc.info['name'].lower():
                return True
    except Exception:
        pass
    
    return False


def get_system_audio_info() -> Dict:
    """Get system audio information"""
    info = {
        'sample_rate': 44100,
        'channels': 2,
        'bit_depth': 16,
        'devices': get_audio_devices(),
        'microphones': get_microphone_list()
    }
    
    return info


def validate_audio_device(device_index: int, device_type: str = 'input') -> bool:
    """Validate if an audio device index is valid"""
    devices = get_audio_devices()
    device_list = devices.get(device_type, [])
    
    return any(dev['index'] == device_index for dev in device_list)


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} TB"


def get_memory_usage() -> Dict:
    """Get current memory usage information"""
    memory = psutil.virtual_memory()
    return {
        'total': format_bytes(memory.total),
        'available': format_bytes(memory.available),
        'percent': memory.percent,
        'used': format_bytes(memory.used),
        'free': format_bytes(memory.free)
    }


def get_cpu_usage() -> float:
    """Get current CPU usage percentage"""
    return psutil.cpu_percent(interval=1)
