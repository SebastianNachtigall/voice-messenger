#!/usr/bin/env python3
"""
Voice Messenger - Main Application
Peer-to-peer voice messaging system for Raspberry Pi Zero

Usage:
    python main.py                    # Normal mode (GPIO + network)
    python main.py --mock             # Mock mode (keyboard + simulated network)
    python main.py --keyboard         # GPIO + keyboard input
    python main.py --mock --no-keyboard  # Mock mode without keyboard
"""

import time
import threading
import argparse
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path

from hardware import HardwareController
from audio import AudioController
from network import P2PNetwork
from config import Config


class State(Enum):
    """System states"""
    IDLE = "IDLE"
    PLAYING = "PLAYING"
    RECORDING_HOLD = "RECORDING_HOLD"
    RECORDING = "RECORDING"


class VoiceMessenger:
    """Main application controller"""

    def __init__(self, config_path: str = "config.json", mock_mode: bool = False, keyboard_enabled: bool = True):
        self.config = Config(config_path)
        self.state = State.IDLE
        self.current_friend = None
        self.current_message_index = -1
        self.mock_mode = mock_mode

        # Initialize controllers
        self.hardware = HardwareController(self.config, keyboard_enabled=keyboard_enabled)
        self.audio = AudioController(self.config)
        self.network = P2PNetwork(self.config, mock_mode=mock_mode)
        
        # Message storage per friend
        self.messages: Dict[str, List[dict]] = {
            friend_id: [] for friend_id in self.config.friends.keys()
        }
        
        # Track sent messages (for blue LED)
        self.message_sent_status: Dict[str, bool] = {
            friend_id: False for friend_id in self.config.friends.keys()
        }
        
        # Threading locks
        self.state_lock = threading.Lock()
        self.playback_timer = None
        self.recording_timer = None
        
        # Register callbacks
        self.hardware.on_button_press = self.handle_button_press
        self.hardware.on_button_release = self.handle_button_release
        self.hardware.on_back_button = self.handle_back_button
        self.network.on_message_received = self.handle_message_received
        self.network.on_message_heard = self.handle_message_heard
        
        print("✨ Voice Messenger initialized")
        
    def set_state(self, new_state: State, context: str = ""):
        """Change system state"""
        with self.state_lock:
            old_state = self.state
            self.state = new_state
            print(f"🔄 State: {old_state.value} → {new_state.value} {context}")
            self.update_ui()
    
    def update_ui(self):
        """Update all LEDs based on current state"""
        # Update record LED
        if self.state == State.RECORDING:
            self.hardware.set_record_led(True)
        else:
            self.hardware.set_record_led(False)
        
        # Update friend LEDs
        for friend_id in self.config.friends.keys():
            self.update_friend_led(friend_id)
    
    def update_friend_led(self, friend_id: str):
        """Update LED for a specific friend"""
        unheard_count = sum(1 for msg in self.messages[friend_id] if not msg['heard'])
        
        if self.current_friend == friend_id and self.state == State.PLAYING:
            # Green solid during playback
            self.hardware.set_friend_led(friend_id, 'on')
        elif unheard_count > 0:
            # Green blinking for new messages
            self.hardware.set_friend_led(friend_id, 'blinking')
        elif self.message_sent_status.get(friend_id, False):
            # Blue solid when message sent
            self.hardware.set_friend_led(friend_id, 'sent')
        else:
            # Off
            self.hardware.set_friend_led(friend_id, 'off')
    
    def handle_button_press(self, friend_id: str):
        """Handle friend button press (start of press)"""
        print(f"👇 {friend_id} button pressed")
        
        if self.state == State.IDLE:
            # Start long press timer for recording
            self.recording_timer = threading.Timer(
                2.0,  # 2 seconds
                self.start_recording,
                args=(friend_id,)
            )
            self.recording_timer.start()
    
    def handle_button_release(self, friend_id: str):
        """Handle friend button release"""
        print(f"👆 {friend_id} button released")
        
        # Cancel long press timer if running
        if self.recording_timer:
            self.recording_timer.cancel()
            self.recording_timer = None
        
        if self.state == State.IDLE:
            # Short press: play new messages
            self.play_new_messages(friend_id)
        elif self.state in [State.RECORDING_HOLD, State.RECORDING]:
            # Stop recording
            if self.current_friend == friend_id:
                self.stop_recording(friend_id)
        elif self.state == State.PLAYING:
            # Stop playback
            if self.playback_timer:
                self.playback_timer.cancel()
                self.playback_timer = None
            print("⏸️ Wiedergabe unterbrochen")
            self.set_state(State.IDLE)
            self.current_friend = None
            self.current_message_index = -1
    
    def handle_back_button(self):
        """Handle BACK button press"""
        print("⬅️ BACK button pressed")
        
        if self.state in [State.RECORDING, State.RECORDING_HOLD]:
            # Cancel recording
            if self.recording_timer:
                self.recording_timer.cancel()
                self.recording_timer = None
            print("❌ Aufnahme abgebrochen")
            self.set_state(State.IDLE)
            self.current_friend = None
        elif self.state == State.PLAYING and self.current_friend:
            # Go to previous message
            if self.current_message_index > 0:
                if self.playback_timer:
                    self.playback_timer.cancel()
                    self.playback_timer = None
                self.current_message_index -= 1
                self.play_message(self.current_friend, self.current_message_index)
            else:
                print("⚠️ Keine vorherige Nachricht")
    
    def start_recording(self, friend_id: str):
        """Start recording audio message"""
        if self.state != State.IDLE:
            return
        
        self.set_state(State.RECORDING_HOLD, friend_id)
        self.current_friend = friend_id
        
        # Start actual recording
        self.set_state(State.RECORDING, friend_id)
        print(f"🔴 Aufnahme für {friend_id} gestartet...")
        
        self.audio.start_recording()
    
    def stop_recording(self, friend_id: str):
        """Stop recording and send message"""
        if self.state not in [State.RECORDING, State.RECORDING_HOLD]:
            return
        
        # Stop recording
        audio_file = self.audio.stop_recording()
        
        if audio_file:
            print(f"✅ Nachricht an {friend_id} wird gesendet...")
            
            # Send via network
            self.network.send_message(friend_id, audio_file)
            
            # Set sent status (blue LED)
            self.message_sent_status[friend_id] = True
            print("💙 LED wechselt zu Blau (Nachricht gesendet)")
        
        self.set_state(State.IDLE)
        self.current_friend = None
    
    def play_new_messages(self, friend_id: str):
        """Play all new messages from a friend"""
        if self.state in [State.RECORDING, State.RECORDING_HOLD]:
            print("⚠️ Cannot play during recording")
            return
        
        # Find first unheard message
        unheard_messages = [
            (i, msg) for i, msg in enumerate(self.messages[friend_id])
            if not msg['heard']
        ]
        
        if not unheard_messages:
            print(f"📭 Keine neuen Nachrichten von {friend_id}")
            return
        
        self.current_friend = friend_id
        self.current_message_index = unheard_messages[0][0]
        
        self.play_message(friend_id, self.current_message_index)
    
    def play_message(self, friend_id: str, index: int):
        """Play a specific message"""
        if index >= len(self.messages[friend_id]):
            print(f"✅ Alle neuen Nachrichten von {friend_id} abgespielt")
            self.set_state(State.IDLE)
            self.current_friend = None
            self.current_message_index = -1
            return
        
        message = self.messages[friend_id][index]
        
        if message['heard']:
            # Skip to next unheard message
            next_unheard = next(
                (i for i in range(index + 1, len(self.messages[friend_id]))
                 if not self.messages[friend_id][i]['heard']),
                None
            )
            if next_unheard is not None:
                self.current_message_index = next_unheard
                self.play_message(friend_id, next_unheard)
            else:
                print(f"✅ Alle neuen Nachrichten von {friend_id} abgespielt")
                self.set_state(State.IDLE)
                self.current_friend = None
                self.current_message_index = -1
            return
        
        if self.state == State.IDLE:
            self.set_state(State.PLAYING, friend_id)
        
        unheard_count = sum(1 for msg in self.messages[friend_id] if not msg['heard'])
        print(f"▶️ Spiele Nachricht von {friend_id} (noch {unheard_count} neue)")
        
        # Mark as heard
        message['heard'] = True
        
        # Notify sender that message was heard
        self.network.notify_message_heard(friend_id, message['id'])
        
        # Play audio
        duration = self.audio.play_message(message['file'])
        
        # Schedule next message after playback
        self.playback_timer = threading.Timer(
            duration,
            self.on_playback_finished,
            args=(friend_id, index)
        )
        self.playback_timer.start()
    
    def on_playback_finished(self, friend_id: str, index: int):
        """Called when message playback finishes"""
        self.playback_timer = None
        print("⏹️ Wiedergabe beendet")
        
        # Check for next unheard message
        next_unheard = next(
            (i for i in range(index + 1, len(self.messages[friend_id]))
             if not self.messages[friend_id][i]['heard']),
            None
        )
        
        if next_unheard is not None:
            # Auto-play next message
            self.current_message_index = next_unheard
            self.play_message(friend_id, next_unheard)
        else:
            # All done
            print(f"✅ Alle neuen Nachrichten von {friend_id} abgespielt")
            self.set_state(State.IDLE)
            self.current_friend = None
            self.current_message_index = -1
    
    def handle_message_received(self, friend_id: str, message_data: dict):
        """Handle incoming message from network"""
        print(f"📨 Neue Nachricht von {friend_id} empfangen!")
        
        # Add to messages
        self.messages[friend_id].insert(0, {
            'id': message_data['id'],
            'file': message_data['file'],
            'timestamp': message_data['timestamp'],
            'heard': False
        })
        
        # Update LED (will override blue sent status)
        self.update_friend_led(friend_id)
    
    def handle_message_heard(self, friend_id: str, message_id: str):
        """Handle notification that our message was heard"""
        print(f"👂 {friend_id} hat deine Nachricht abgehört")
        
        # Clear sent status
        self.message_sent_status[friend_id] = False
        print("💡 LED erlischt (Nachricht wurde abgehört)")
        
        self.update_friend_led(friend_id)
    
    def run(self):
        """Main application loop"""
        print("🚀 Voice Messenger läuft...")
        if self.mock_mode:
            print("   Running in MOCK mode - no real network connections")

        # Start network listener
        self.network.start()

        # Start hardware monitoring
        self.hardware.start()

        try:
            # Keep running until keyboard 'q' or Ctrl+C
            while self.hardware.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

        print("\n👋 Shutting down...")
        self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        self.hardware.stop()
        self.network.stop()
        self.audio.cleanup()
        print("✅ Shutdown complete")


def main():
    parser = argparse.ArgumentParser(description='Voice Messenger - P2P voice messaging for kids')
    parser.add_argument('--mock', action='store_true',
                        help='Run in mock mode (simulated network, no real connections)')
    parser.add_argument('--keyboard', action='store_true',
                        help='Enable keyboard input (default: auto-detect)')
    parser.add_argument('--no-keyboard', action='store_true',
                        help='Disable keyboard input')
    parser.add_argument('--config', type=str, default='config.json',
                        help='Path to config file (default: config.json)')
    parser.add_argument('--simulate-message', type=str, metavar='FRIEND_ID',
                        help='Simulate receiving a message from a friend (requires --mock)')

    args = parser.parse_args()

    # Determine keyboard mode
    keyboard_enabled = True
    if args.no_keyboard:
        keyboard_enabled = False
    elif args.keyboard:
        keyboard_enabled = True

    # Create and run app
    app = VoiceMessenger(
        config_path=args.config,
        mock_mode=args.mock,
        keyboard_enabled=keyboard_enabled
    )

    # Simulate message if requested
    if args.simulate_message:
        if not args.mock:
            print("⚠️ --simulate-message requires --mock mode")
        else:
            # Schedule message simulation after startup
            def simulate():
                time.sleep(1.0)
                app.network.simulate_incoming_message(args.simulate_message)
            threading.Thread(target=simulate, daemon=True).start()

    app.run()


if __name__ == "__main__":
    main()
