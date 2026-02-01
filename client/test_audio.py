#!/usr/bin/env python3
"""
Audio test script for the Pi with Google Voice HAT.
Compares different recording methods:
1. Direct ALSA (plughw:1,0) - raw, very quiet
2. ALSA with softvol (boosted_mic) - hardware-level gain, recommended
3. PipeWire (pw-record) - alternative if available

Usage: python3 test_audio.py [method]
  method: all, alsa, softvol, pipewire (default: all)
"""

import subprocess
import sys
import os
import wave
import struct
import time
from pathlib import Path

ALSA_DEVICE = "plughw:1,0"
BOOSTED_DEVICE = "boosted_mic"
DURATION = 3

# ALSA softvol configuration
ASOUNDRC_CONTENT = """# Software volume control for capture (mic boost)
pcm.mic_boost {
    type softvol
    slave.pcm "plughw:1,0"
    control {
        name "Mic Boost"
        card 1
    }
    min_dB -5.0
    max_dB 40.0
}

pcm.boosted_mic {
    type plug
    slave.pcm "mic_boost"
}
"""


def analyze(filepath, label=""):
    """Analyze WAV file and print stats"""
    if not os.path.exists(filepath):
        print(f"{label}File not found!")
        return None
    
    try:
        with wave.open(filepath, 'rb') as wf:
            fmt = f"{wf.getnchannels()}ch, {wf.getsampwidth()*8}-bit, {wf.getframerate()}Hz"
            raw = wf.readframes(wf.getnframes())
    except Exception as e:
        print(f"{label}Error reading file: {e}")
        return None
    
    if len(raw) < 2:
        print(f"{label}Empty recording")
        return None
    
    samples = struct.unpack(f'<{len(raw)//2}h', raw)
    peak = max(abs(s) for s in samples)
    rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
    
    print(f"{label}Format: {fmt}")
    print(f"{label}Peak: {peak} / 32768  ({peak/32768*100:.1f}%)")
    print(f"{label}RMS:  {rms:.0f} / 32768  ({rms/32768*100:.1f}%)")
    
    if peak < 100:
        quality = "SILENT"
    elif peak < 1000:
        quality = "Very quiet"
    elif peak < 5000:
        quality = "Quiet"
    elif peak < 15000:
        quality = "Moderate"
    elif peak < 25000:
        quality = "Good"
    else:
        quality = "Excellent"
    
    print(f"{label}Quality: {quality}")
    return peak


def setup_softvol():
    """Ensure ALSA softvol is configured"""
    asoundrc = Path.home() / ".asoundrc"
    
    if not asoundrc.exists() or "boosted_mic" not in asoundrc.read_text():
        print("Setting up ALSA softvol configuration...")
        asoundrc.write_text(ASOUNDRC_CONTENT)
    
    # Trigger control creation with a very short recording
    try:
        proc = subprocess.Popen(
            ['arecord', '-D', 'boosted_mic', '-f', 'S16_LE', '-r', '16000', '-c', '1', '/dev/null'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(0.5)
        proc.terminate()
        proc.wait(timeout=1)
    except:
        pass
    
    # Set boost to 90% (~34dB)
    result = subprocess.run(
        ['amixer', '-c', '1', 'set', 'Mic Boost', '90%'],
        capture_output=True, text=True
    )
    if "Front Left:" in result.stdout:
        for line in result.stdout.split('\n'):
            if "Front Left:" in line:
                print(f"Mic Boost: {line.strip()}")
                break


def test_alsa_direct():
    """Test direct ALSA recording (no boost)"""
    filepath = "/tmp/test_alsa_direct.wav"
    print(f"\n=== ALSA Direct ({ALSA_DEVICE}) ===")
    print(f"Recording {DURATION}s... speak now!")
    
    result = subprocess.run([
        'arecord', '-D', ALSA_DEVICE,
        '-f', 'S16_LE', '-r', '16000', '-c', '1',
        '-d', str(DURATION), filepath
    ], capture_output=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr.decode()}")
        return None
    
    analyze(filepath)
    return filepath


def test_softvol():
    """Test ALSA with softvol boost"""
    filepath = "/tmp/test_softvol.wav"
    print(f"\n=== ALSA Softvol ({BOOSTED_DEVICE}) ===")
    
    setup_softvol()
    
    print(f"Recording {DURATION}s... speak now!")
    result = subprocess.run([
        'arecord', '-D', BOOSTED_DEVICE,
        '-f', 'S16_LE', '-r', '16000', '-c', '1',
        '-d', str(DURATION), filepath
    ], capture_output=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr.decode()}")
        return None
    
    analyze(filepath)
    return filepath


def test_pipewire():
    """Test PipeWire recording"""
    filepath = "/tmp/test_pipewire.wav"
    print(f"\n=== PipeWire (pw-record) ===")
    
    if not subprocess.run(['which', 'pw-record'], capture_output=True).returncode == 0:
        print("pw-record not available")
        return None
    
    # Check PipeWire source volume
    result = subprocess.run(['wpctl', 'status'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'Built-in Audio Stereo' in line and 'vol:' in line:
            print(f"PipeWire source: {line.strip()}")
            break
    
    print(f"Recording {DURATION}s... speak now!")
    proc = subprocess.Popen([
        'pw-record',
        '--rate', '16000',
        '--channels', '1',
        '--format', 's16',
        filepath
    ], stderr=subprocess.DEVNULL)
    
    time.sleep(DURATION)
    proc.terminate()
    proc.wait(timeout=2)
    
    analyze(filepath)
    return filepath


def playback(filepath, label=""):
    """Play back a recording"""
    if filepath and os.path.exists(filepath):
        print(f"\nPlaying {label}...")
        subprocess.run(['aplay', '-D', ALSA_DEVICE, filepath])


def main():
    method = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print("=" * 50)
    print("Google Voice HAT Audio Test")
    print("=" * 50)
    
    files = {}
    
    if method in ("all", "alsa"):
        files['alsa'] = test_alsa_direct()
    
    if method in ("all", "softvol"):
        files['softvol'] = test_softvol()
    
    if method in ("all", "pipewire"):
        files['pipewire'] = test_pipewire()
    
    # Playback comparison
    if len(files) > 0:
        print("\n" + "=" * 50)
        print("Playback Comparison")
        print("=" * 50)
        
        for name, filepath in files.items():
            if filepath:
                playback(filepath, name)
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print("""
The Google Voice HAT mic has very low sensitivity (~0.6% peak raw).

Recommended solution: Use ALSA softvol (boosted_mic device)
- Applies gain at driver level before 32-bit to 16-bit conversion
- Much cleaner than post-processing
- Configure in ~/.asoundrc and set level with: amixer -c 1 set 'Mic Boost' 90%

In audio.py, set ALSA_RECORD_DEVICE = "boosted_mic"
""")


if __name__ == '__main__':
    main()
