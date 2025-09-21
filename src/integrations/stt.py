#!/usr/bin/env python3
"""
Speech-to-Text Module
Unified interface for real-time and batch speech recognition.
"""

import numpy as np
import pyaudio
import threading
import time
import queue
import tempfile
import wave
import os
from collections import deque
from typing import Optional, Callable
from abc import ABC, abstractmethod


class STTEngine(ABC):
    """Abstract base class for STT engines"""
    
    @abstractmethod
    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe audio data to text"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the engine is available"""
        pass


class WhisperEngine(STTEngine):
    """Whisper-based STT engine"""
    
    def __init__(self, model_size: str = "tiny"):
        self.model = None
        self.model_size = model_size
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model"""
        try:
            import whisper
            self.model = whisper.load_model(self.model_size)
            print(f"✅ Whisper '{self.model_size}' model loaded")
        except ImportError:
            print("❌ Whisper not available")
            self.model = None
    
    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe audio using Whisper"""
        if not self.model:
            return ""
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                with wave.open(tmp.name, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(audio_data.tobytes())
                
                # Transcribe
                result = self.model.transcribe(tmp.name, language=None)
                text = result['text'].strip()
                
                # Cleanup
                try:
                    os.unlink(tmp.name)
                except:
                    pass
                
                return text
        except Exception as e:
            print(f"Error transcribing with Whisper: {e}")
            return ""
    
    def is_available(self) -> bool:
        """Check if Whisper is available"""
        return self.model is not None


class SpeechRecognitionEngine(STTEngine):
    """Fallback STT engine using speech_recognition library"""
    
    def __init__(self):
        self.recognizer = None
        self._initialize()
    
    def _initialize(self):
        """Initialize speech recognition"""
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            print("✅ SpeechRecognition engine available")
        except ImportError:
            print("❌ SpeechRecognition not available")
    
    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe using speech_recognition"""
        if not self.recognizer:
            return ""
        
        try:
            import speech_recognition as sr
            
            # Convert to speech_recognition AudioData
            audio_float = audio_data.astype(np.float32) / 32767.0
            audio_data_sr = sr.AudioData(audio_data.tobytes(), 16000, 2)
            
            # Recognize
            text = self.recognizer.recognize_google(audio_data_sr, language='en-US')
            return text.strip()
        except Exception:
            return ""
    
    def is_available(self) -> bool:
        """Check if speech_recognition is available"""
        return self.recognizer is not None


class RealTimeSTT:
    """Real-time Speech-to-Text system with multiple engine support"""
    
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.transcription_callback: Optional[Callable[[str], None]] = None
        self.mic_index = 0
        self.gain = 1.0
        
        # Audio processing parameters
        self.audio_buffer = deque(maxlen=60)
        self.silence_threshold = 0.02
        self.speech_timeout = 0.4
        self.buffer_overlap = 2
        self.min_speech_length = 0.3
        self.last_speech_time = 0
        self.last_rms = 0
        
        # Initialize STT engines in order of preference
        self.engines = [
            WhisperEngine("tiny"),  # Fast for real-time
            SpeechRecognitionEngine()
        ]
        
        # Select the best available engine
        self.current_engine = None
        for engine in self.engines:
            if engine.is_available():
                self.current_engine = engine
                break
        
        if not self.current_engine:
            print("❌ No STT engine available")
    
    def start_listening(self, mic_index: int = 0, gain: float = 1.0, 
                       callback: Optional[Callable[[str], None]] = None) -> bool:
        """Start real-time listening"""
        if self.is_listening or not self.current_engine:
            return False
        
        self.mic_index = mic_index
        self.gain = gain
        self.transcription_callback = callback
        self.is_listening = True
        
        # Start audio capture thread
        self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_thread.start()
        
        # Start transcription processing thread
        self.processing_thread = threading.Thread(target=self._transcription_loop, daemon=True)
        self.processing_thread.start()
        
        print("🎤 Real-time transcription started")
        return True
    
    def stop_listening(self):
        """Stop real-time listening"""
        self.is_listening = False
        time.sleep(0.1)
        print("⏹️ Real-time transcription stopped")
    
    def _audio_capture_loop(self):
        """Continuously capture audio in small chunks"""
        pa = pyaudio.PyAudio()
        stream = None
        
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.mic_index,
                frames_per_buffer=self.chunk_size
            )
            
            print(f"🎤 Capturing real-time audio from microphone {self.mic_index}")
            
            while self.is_listening:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_chunk = np.frombuffer(data, np.int16).astype(np.float32)
                    
                    # Apply gain
                    audio_chunk *= self.gain
                    audio_chunk = np.clip(audio_chunk, -32768, 32767).astype(np.int16)
                    
                    # Voice activity detection
                    rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)) / 32767.0
                    rms_diff = abs(rms - self.last_rms)
                    is_speech = (rms > self.silence_threshold) or (rms_diff > 0.01)
                    self.last_rms = rms
                    
                    if is_speech and rms > 0.005:
                        self.last_speech_time = time.time()
                        self.audio_buffer.append(audio_chunk)
                    elif rms > 0.003:
                        self.audio_buffer.append(audio_chunk)
                    
                    # Process audio when conditions are met
                    buffer_duration = len(self.audio_buffer) * self.chunk_size / self.sample_rate
                    time_since_speech = time.time() - self.last_speech_time
                    
                    should_process = (
                        buffer_duration > self.min_speech_length and
                        (time_since_speech > self.speech_timeout or len(self.audio_buffer) >= 50)
                    )
                    
                    if should_process and len(self.audio_buffer) > 0:
                        audio_data = np.concatenate(list(self.audio_buffer))
                        self.audio_queue.put(audio_data.copy())
                        
                        # Keep overlap to avoid cutting words
                        for _ in range(max(0, len(self.audio_buffer) - self.buffer_overlap)):
                            self.audio_buffer.popleft()
                
                except Exception as e:
                    print(f"Error in audio capture: {e}")
                    time.sleep(0.01)
        
        except Exception as e:
            print(f"Error setting up audio: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()
    
    def _transcription_loop(self):
        """Process transcription in separate thread"""
        while self.is_listening:
            try:
                try:
                    audio_data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                if len(audio_data) > self.sample_rate * self.min_speech_length:
                    text = self.current_engine.transcribe(audio_data)
                    if text and len(text.strip()) > 1:
                        if self.transcription_callback:
                            self.transcription_callback(text.strip())
                
                self.audio_queue.task_done()
            
            except Exception as e:
                print(f"Error in transcription: {e}")
                time.sleep(0.1)


def get_mic_name(index: int) -> str:
    """Get microphone name by index"""
    try:
        import speech_recognition as sr
        names = sr.Microphone.list_microphone_names()
        return names[index] if 0 <= index < len(names) else f"Unknown ({index})"
    except Exception:
        return f"Unknown ({index})"


# Global instance for backward compatibility
realtime_stt = RealTimeSTT()
