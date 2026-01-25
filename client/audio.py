"""
Audio Controller - Recording and playback of voice messages
Uses aplay/arecord on Pi for reliable audio with seeed hat.
Falls back to PyAudio on other platforms.
"""

import wave
import time
import threading
import subprocess
import shutil
from pathlib import Path
from typing import Optional

# Check for aplay/arecord (Linux/Pi)
APLAY_AVAILABLE = shutil.which('aplay') is not None
ARECORD_AVAILABLE = shutil.which('arecord') is not None

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    print("⚠️ PyAudio not available")
    PYAUDIO_AVAILABLE = False

# Prefer aplay/arecord on Pi, fallback to PyAudio
AUDIO_AVAILABLE = APLAY_AVAILABLE or PYAUDIO_AVAILABLE


class AudioController:
    """Manages audio recording and playback"""

    # Audio settings
    CHUNK = 1024
    FORMAT = 8  # pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000  # 16kHz for voice (lower than 44.1kHz to save space)

    # ALSA device for seeed hat (card 1)
    ALSA_DEVICE = "plughw:1,0"

    def __init__(self, config):
        self.config = config
        self.recording = False
        self.playing = False

        # Ensure audio directory exists
        self.audio_dir = Path("audio_messages")
        self.audio_dir.mkdir(exist_ok=True)

        # Determine audio backend
        self.use_alsa = APLAY_AVAILABLE and ARECORD_AVAILABLE
        self.audio = None

        if self.use_alsa:
            print(f"🔊 Using ALSA (aplay/arecord) with device {self.ALSA_DEVICE}")
        elif PYAUDIO_AVAILABLE:
            self.audio = pyaudio.PyAudio()
            print("🔊 Using PyAudio")
        else:
            print("🔧 Audio controller in simulation mode")

        self.record_frames = []
        self.record_stream = None
        self.playback_stream = None
        self.record_process = None
        self.playback_process = None
        self.current_record_file = None
    
    def start_recording(self):
        """Start recording audio"""
        if not AUDIO_AVAILABLE:
            print("🎤 [SIMULATION] Recording started")
            self.recording = True
            return

        self.recording = True
        self.record_frames = []

        # Generate filename for this recording
        timestamp = int(time.time() * 1000)
        self.current_record_file = self.audio_dir / f"message_{timestamp}.wav"

        if self.use_alsa:
            # Use arecord
            try:
                self.record_process = subprocess.Popen([
                    'arecord',
                    '-D', self.ALSA_DEVICE,
                    '-f', 'S16_LE',
                    '-r', str(self.RATE),
                    '-c', str(self.CHANNELS),
                    str(self.current_record_file)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("🎤 Recording started (arecord)")
            except Exception as e:
                print(f"❌ Recording error: {e}")
                self.recording = False
        else:
            # Use PyAudio
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
                print("🎤 Recording started (PyAudio)")
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

        if self.use_alsa:
            # Stop arecord process
            if self.record_process:
                self.record_process.terminate()
                self.record_process.wait(timeout=2)
                self.record_process = None

            if self.current_record_file and self.current_record_file.exists():
                print(f"💾 Audio saved: {self.current_record_file}")
                return str(self.current_record_file)
            else:
                print("⚠️ No audio recorded")
                return None
        else:
            # Stop PyAudio stream
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

        # Get duration from file
        try:
            with wave.open(str(file_path), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
        except Exception as e:
            print(f"⚠️ Could not read audio file: {e}")
            duration = 2.0  # Default estimate

        if self.use_alsa:
            # Use aplay
            try:
                self.playing = True
                self.playback_process = subprocess.Popen([
                    'aplay',
                    '-D', self.ALSA_DEVICE,
                    str(file_path)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Wait for playback to complete
                self.playback_process.wait()
                self.playback_process = None
                self.playing = False

                print(f"🔊 Played: {filename} ({duration:.1f}s)")
                return duration
            except Exception as e:
                print(f"❌ Playback error: {e}")
                self.playing = False
                return 0.0
        else:
            # Use PyAudio
            try:
                with wave.open(str(file_path), 'rb') as wf:
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

        # Stop arecord/aplay processes
        if self.record_process:
            try:
                self.record_process.terminate()
                self.record_process.wait(timeout=1)
            except:
                pass

        if self.playback_process:
            try:
                self.playback_process.terminate()
                self.playback_process.wait(timeout=1)
            except:
                pass

        # Stop PyAudio streams
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

        if self.audio:
            self.audio.terminate()

        print("✅ Audio cleanup complete")
