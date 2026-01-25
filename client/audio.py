"""
Audio Controller - Recording and playback of voice messages
"""

import wave
import time
import threading
from pathlib import Path
from typing import Optional

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    print("⚠️ PyAudio not available, running in simulation mode")
    AUDIO_AVAILABLE = False


class AudioController:
    """Manages audio recording and playback"""
    
    # Audio settings
    CHUNK = 1024
    FORMAT = 8  # pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000  # 16kHz for voice (lower than 44.1kHz to save space)
    
    def __init__(self, config):
        self.config = config
        self.recording = False
        self.playing = False
        
        # Ensure audio directory exists
        self.audio_dir = Path("audio_messages")
        self.audio_dir.mkdir(exist_ok=True)
        
        if AUDIO_AVAILABLE:
            self.audio = pyaudio.PyAudio()
        else:
            self.audio = None
            print("🔧 Audio controller in simulation mode")
        
        self.record_frames = []
        self.record_stream = None
        self.playback_stream = None
    
    def start_recording(self):
        """Start recording audio"""
        if not AUDIO_AVAILABLE:
            print("🎤 [SIMULATION] Recording started")
            self.recording = True
            return
        
        self.recording = True
        self.record_frames = []
        
        try:
            self.record_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=self.record_callback
            )
            
            self.record_stream.start_stream()
            print("🎤 Recording started")
        except Exception as e:
            print(f"❌ Recording error: {e}")
            self.recording = False
    
    def record_callback(self, in_data, frame_count, time_info, status):
        """Callback for recording stream"""
        if self.recording:
            self.record_frames.append(in_data)
            return (in_data, pyaudio.paContinue)
        else:
            return (in_data, pyaudio.paComplete)
    
    def stop_recording(self) -> Optional[str]:
        """Stop recording and save to file"""
        if not self.recording:
            return None
        
        self.recording = False
        
        if not AUDIO_AVAILABLE:
            print("🎤 [SIMULATION] Recording stopped")
            # Return a dummy file path
            dummy_file = self.audio_dir / f"message_{int(time.time())}.wav"
            dummy_file.touch()
            return str(dummy_file)
        
        # Stop stream
        if self.record_stream:
            self.record_stream.stop_stream()
            self.record_stream.close()
            self.record_stream = None
        
        if not self.record_frames:
            print("⚠️ No audio recorded")
            return None
        
        # Save to file
        timestamp = int(time.time() * 1000)
        filename = self.audio_dir / f"message_{timestamp}.wav"
        
        try:
            with wave.open(str(filename), 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.record_frames))
            
            print(f"💾 Audio saved: {filename}")
            return str(filename)
        except Exception as e:
            print(f"❌ Save error: {e}")
            return None
    
    def play_message(self, filename: str) -> float:
        """
        Play audio message
        Returns: duration in seconds
        """
        if not AUDIO_AVAILABLE:
            print(f"🔊 [SIMULATION] Playing: {filename}")
            # Simulate playback duration
            return 2.0
        
        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️ Audio file not found: {filename}")
            return 0.0
        
        try:
            with wave.open(str(file_path), 'rb') as wf:
                # Get duration
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
                
                # Open playback stream
                self.playback_stream = self.audio.open(
                    format=self.audio.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )
                
                # Play audio
                self.playing = True
                data = wf.readframes(self.CHUNK)
                while data and self.playing:
                    self.playback_stream.write(data)
                    data = wf.readframes(self.CHUNK)
                
                # Close stream
                self.playback_stream.stop_stream()
                self.playback_stream.close()
                self.playback_stream = None
                self.playing = False
                
                print(f"🔊 Played: {filename} ({duration:.1f}s)")
                return duration
        except Exception as e:
            print(f"❌ Playback error: {e}")
            return 0.0
    
    def stop_playback(self):
        """Stop current playback"""
        self.playing = False
    
    def cleanup(self):
        """Cleanup audio resources"""
        self.recording = False
        self.playing = False
        
        if self.record_stream:
            try:
                self.record_stream.stop_stream()
                self.record_stream.close()
            except:
                pass
        
        if self.playback_stream:
            try:
                self.playback_stream.stop_stream()
                self.playback_stream.close()
            except:
                pass
        
        if AUDIO_AVAILABLE and self.audio:
            self.audio.terminate()
        
        print("✅ Audio cleanup complete")
