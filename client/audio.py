"""
Audio Controller - Recording and playback of voice messages
Uses PipeWire for recording (cleaner audio) and ALSA for playback.
Falls back to PyAudio on other platforms.
"""

import wave
import struct
import time
import signal
import subprocess
import shutil
from pathlib import Path
from typing import Optional

# Check for audio tools
APLAY_AVAILABLE = shutil.which('aplay') is not None
PW_RECORD_AVAILABLE = shutil.which('pw-record') is not None

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    print("⚠️ PyAudio not available")
    PYAUDIO_AVAILABLE = False

AUDIO_AVAILABLE = (PW_RECORD_AVAILABLE and APLAY_AVAILABLE) or PYAUDIO_AVAILABLE


class AudioController:
    """Manages audio recording and playback"""

    CHUNK = 1024
    FORMAT = 8  # pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    ALSA_PLAYBACK_DEVICE = "plughw:1,0"

    def __init__(self, config):
        self.config = config
        self.recording = False
        self.playing = False

        # Software gain for PipeWire recordings (they're quiet but clean)
        audio_settings = getattr(config, 'data', {}).get('audio', {})
        self.mic_gain = audio_settings.get('mic_gain', 2)
        self.playback_gain = audio_settings.get('playback_gain', 1.0)

        self.audio_dir = Path("audio_messages")
        self.audio_dir.mkdir(exist_ok=True)

        self.use_pipewire = PW_RECORD_AVAILABLE and APLAY_AVAILABLE
        self.audio = None

        if self.use_pipewire:
            self._setup_pipewire()
            print(f"🔊 Using PipeWire (pw-record) + ALSA playback")
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

    def _setup_pipewire(self):
        """Setup PipeWire source volume"""
        try:
            # Set PipeWire source volume to 100% (clean signal, minimal noise)
            subprocess.run(
                ['wpctl', 'set-volume', '@DEFAULT_AUDIO_SOURCE@', '1.0'],
                capture_output=True, timeout=2
            )
        except Exception as e:
            print(f"⚠️ Could not set PipeWire volume: {e}")

    def start_recording(self):
        """Start recording audio"""
        if not AUDIO_AVAILABLE:
            print("🎤 [SIMULATION] Recording started")
            self.recording = True
            return

        self.recording = True
        self.record_frames = []

        timestamp = int(time.time() * 1000)
        self.current_record_file = self.audio_dir / f"message_{timestamp}.wav"

        if self.use_pipewire:
            try:
                self.record_process = subprocess.Popen([
                    'pw-record',
                    '--rate', str(self.RATE),
                    '--channels', str(self.CHANNELS),
                    '--format', 's16',
                    str(self.current_record_file)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("🎤 Recording started (pw-record)")
            except Exception as e:
                print(f"❌ Recording error: {e}")
                self.recording = False
        else:
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
            dummy_file = self.audio_dir / f"message_{int(time.time())}.wav"
            dummy_file.touch()
            return str(dummy_file)

        if self.use_pipewire:
            if self.record_process:
                self.record_process.send_signal(signal.SIGINT)
                try:
                    self.record_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.record_process.terminate()
                    self.record_process.wait(timeout=1)
                self.record_process = None

            if self.current_record_file and self.current_record_file.exists():
                # Apply gain to boost the quiet but clean PipeWire recording
                if self.mic_gain != 1.0:
                    self._apply_gain(self.current_record_file, self.mic_gain)
                print(f"💾 Audio saved: {self.current_record_file}")
                return str(self.current_record_file)
            else:
                print("⚠️ No audio recorded")
                return None
        else:
            if self.record_stream:
                self.record_stream.stop_stream()
                self.record_stream.close()
                self.record_stream = None

            if not self.record_frames:
                print("⚠️ No audio recorded")
                return None

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

    @staticmethod
    def _apply_gain(file_path: Path, gain: float):
        """Apply software gain to a 16-bit PCM WAV file."""
        try:
            with wave.open(str(file_path), 'rb') as wf:
                params = wf.getparams()
                raw = wf.readframes(wf.getnframes())
            samples = struct.unpack(f'<{len(raw)//2}h', raw)
            amplified = [max(-32768, min(32767, int(s * gain))) for s in samples]
            with wave.open(str(file_path), 'wb') as wf:
                wf.setparams(params)
                wf.writeframes(struct.pack(f'<{len(amplified)}h', *amplified))
        except Exception as e:
            print(f"⚠️ Could not apply gain: {e}")

    def play_message(self, filename: str) -> float:
        """Play audio message. Returns duration in seconds."""
        if not AUDIO_AVAILABLE:
            print(f"🔊 [SIMULATION] Playing: {filename}")
            return 2.0

        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️ Audio file not found: {filename}")
            return 0.0

        try:
            with wave.open(str(file_path), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
        except Exception as e:
            print(f"⚠️ Could not read audio file: {e}")
            duration = 2.0

        if self.use_pipewire:
            try:
                self.playing = True
                self.playback_process = subprocess.Popen([
                    'aplay',
                    '-D', self.ALSA_PLAYBACK_DEVICE,
                    str(file_path)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
            try:
                with wave.open(str(file_path), 'rb') as wf:
                    self.playback_stream = self.audio.open(
                        format=self.audio.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True
                    )

                    self.playing = True
                    data = wf.readframes(self.CHUNK)
                    while data and self.playing:
                        self.playback_stream.write(data)
                        data = wf.readframes(self.CHUNK)

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
