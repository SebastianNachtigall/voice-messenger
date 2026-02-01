#!/usr/bin/env python3
"""
Voice Messenger - Main Application
Peer-to-peer voice messaging system for Raspberry Pi Zero

New UI: Friend selection, toggle recording, conversation mode, WS2812B LED strip.

Usage:
    python main.py                    # Normal mode (GPIO + network)
    python main.py --mock             # Mock mode (keyboard + simulated network)
    python main.py --keyboard         # GPIO + keyboard input
    python main.py --mock --no-keyboard  # Mock mode without keyboard
"""

import time
import threading
import argparse
import json
import uuid
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path

from hardware import HardwareController
from audio import AudioController
from network import P2PNetwork
from config import Config
from led_strip import COLOR_RED, COLOR_GREEN, COLOR_BLUE, COLOR_OFF


class State(Enum):
    """System states"""
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    PLAYING = "PLAYING"


class VoiceMessenger:
    """Main application controller"""

    CONVERSATION_TIMEOUT = 300  # 5 minutes

    def __init__(self, config_path: str = "config.json", mock_mode: bool = False, keyboard_enabled: bool = True):
        self.config = Config(config_path)
        self.state = State.IDLE
        self.mock_mode = mock_mode

        # State persistence
        self.state_file = Path("state.json")

        # Initialize controllers
        self.hardware = HardwareController(self.config, keyboard_enabled=keyboard_enabled)
        self.audio = AudioController(self.config)
        self.network = P2PNetwork(self.config, mock_mode=mock_mode)

        # --- Friend selection ---
        self.selected_friend: Optional[str] = None

        # --- Message storage ---
        # Conversation history per friend: list of {id, file, timestamp, heard, direction}
        # direction: 'received' or 'sent'
        # Ordered newest-first (index 0 = most recent)
        self.messages: Dict[str, List[dict]] = {
            friend_id: [] for friend_id in self.config.friends.keys()
        }

        # Track sent messages not yet heard (for blue LED)
        self.message_sent_status: Dict[str, bool] = {
            friend_id: False for friend_id in self.config.friends.keys()
        }

        # --- Recording status from friends ---
        self.friend_is_recording: Dict[str, bool] = {
            friend_id: False for friend_id in self.config.friends.keys()
        }

        # --- Playback state ---
        self.playback_friend: Optional[str] = None
        self.playback_index: int = -1  # Index into messages list (0 = most recent)
        self.playback_timer: Optional[threading.Timer] = None

        # --- Conversation mode ---
        self.conversation_mode: bool = False
        self.conversation_timeout_timer: Optional[threading.Timer] = None
        self.pending_autoplay: Optional[dict] = None  # {friend_id, message_data}

        # Threading
        self.state_lock = threading.Lock()

        # Load persisted state
        self.load_state()

        # Auto-select first friend
        if self.config.friends:
            first_friend = list(self.config.friends.keys())[0]
            self.selected_friend = first_friend

        # Register callbacks
        self.hardware.on_friend_button = self.handle_friend_button
        self.hardware.on_record_button = self.handle_record_button
        self.hardware.on_dialog_button = self.handle_dialog_button
        self.network.on_message_received = self.handle_message_received
        self.network.on_message_heard = self.handle_message_heard
        self.network.on_recording_started = self.handle_recording_started
        self.network.on_recording_stopped = self.handle_recording_stopped

        print("Voice Messenger initialized")

    # --- State Persistence ---

    def load_state(self):
        """Load persisted state from file"""
        if not self.state_file.exists():
            print("No saved state found, starting fresh")
            return

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            saved_messages = data.get('messages', {})
            for friend_id in self.config.friends.keys():
                if friend_id in saved_messages:
                    valid_messages = []
                    for msg in saved_messages[friend_id]:
                        # Only validate file existence for received messages
                        if msg.get('direction') == 'sent' or Path(msg.get('file', '')).exists():
                            valid_messages.append(msg)
                    self.messages[friend_id] = valid_messages

            saved_sent = data.get('sent_status', {})
            for friend_id in self.config.friends.keys():
                if friend_id in saved_sent:
                    self.message_sent_status[friend_id] = saved_sent[friend_id]

            total_unheard = sum(
                sum(1 for msg in msgs if not msg.get('heard', True) and msg.get('direction') == 'received')
                for msgs in self.messages.values()
            )
            print(f"State loaded: {total_unheard} unheard message(s)")

        except Exception as e:
            print(f"Error loading state: {e}")

    def save_state(self):
        """Save current state to file"""
        try:
            data = {
                'messages': self.messages,
                'sent_status': self.message_sent_status
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

    # --- State Management ---

    def set_state(self, new_state: State, context: str = ""):
        """Change system state"""
        with self.state_lock:
            old_state = self.state
            self.state = new_state
            print(f"State: {old_state.value} -> {new_state.value} {context}")
            self.update_all_leds()

    # --- LED Updates ---

    def update_all_leds(self):
        """Update all LEDs based on current state"""
        # Update yellow LEDs (selected friend indicator)
        for friend_id in self.config.friends:
            self.hardware.set_yellow_led(friend_id, friend_id == self.selected_friend)

        # Update RGB LEDs for each friend
        for friend_id in self.config.friends:
            self.update_rgb_led(friend_id)

    def update_rgb_led(self, friend_id: str):
        """Update RGB LED for a specific friend based on priority rules"""
        friend_config = self.config.friends.get(friend_id)
        if not friend_config:
            return

        led_index = friend_config.get('led_index')
        if led_index is None:
            return

        strip = self.hardware.led_strip

        # Priority 1: I am recording for this friend
        if self.state == State.RECORDING and self.selected_friend == friend_id:
            strip.start_pulse(led_index, *COLOR_RED)
            return

        # Priority 2: Friend is recording for me
        if self.friend_is_recording.get(friend_id, False):
            strip.start_rainbow(led_index)
            return

        # Priority 3: New unheard message
        unheard = sum(
            1 for msg in self.messages.get(friend_id, [])
            if not msg.get('heard', True) and msg.get('direction') == 'received'
        )
        if unheard > 0:
            strip.start_pulse(led_index, *COLOR_GREEN)
            return

        # Priority 4: Message sent, not yet heard
        if self.message_sent_status.get(friend_id, False):
            strip.set_color(led_index, *COLOR_BLUE)
            return

        # Priority 5: Friend is online
        if self.network.get_peer_status(friend_id) == "online":
            strip.set_color(led_index, *COLOR_GREEN)
            return

        # Priority 6: Offline
        strip.off(led_index)

    # --- Button Handlers ---

    def handle_friend_button(self, friend_id: str):
        """Handle friend button press"""
        friend_name = self.config.friends[friend_id].get('name', friend_id)
        print(f"Friend button: {friend_name}")

        if self.state == State.RECORDING:
            # Cancel recording (don't send)
            self._cancel_recording()

        elif self.state == State.PLAYING:
            if friend_id == self.selected_friend:
                # Same friend button during playback -> previous message
                self._play_previous_message()
            else:
                # Different friend -> stop playback, switch friend
                self._stop_playback()
                self._select_friend(friend_id)

        elif self.state == State.IDLE:
            if friend_id == self.selected_friend:
                # Already selected -> start playing conversation
                self._start_playback(friend_id)
            else:
                # Select this friend
                self._select_friend(friend_id)

    def handle_record_button(self):
        """Handle record button press"""
        print("Record button pressed")

        if self.state == State.RECORDING:
            # Stop recording and send
            self._stop_recording_and_send()

        elif self.state == State.PLAYING:
            # Cancel playback
            self._stop_playback()

        elif self.state == State.IDLE:
            if not self.selected_friend:
                print("No friend selected")
                return

            if self.network.get_peer_status(self.selected_friend) == "online":
                self._start_recording()
            else:
                # Friend offline -> flash all red
                friend_name = self.config.friends[self.selected_friend].get('name', 'friend')
                print(f"{friend_name} is offline, cannot record")
                self.hardware.led_strip.flash_all(*COLOR_RED, times=2)
                # Restore LEDs after flash
                self.update_all_leds()

    def handle_dialog_button(self):
        """Handle dialog button press - toggle conversation mode"""
        # If playing or recording, cancel first
        if self.state == State.PLAYING:
            self._stop_playback()
        elif self.state == State.RECORDING:
            self._cancel_recording()

        self.conversation_mode = not self.conversation_mode
        print(f"Conversation mode: {'ON' if self.conversation_mode else 'OFF'}")

        if self.conversation_mode:
            self._reset_conversation_timeout()
        else:
            self._cancel_conversation_timeout()

    # --- Friend Selection ---

    def _select_friend(self, friend_id: str):
        """Select a friend as the current messaging target"""
        self.selected_friend = friend_id
        friend_name = self.config.friends[friend_id].get('name', friend_id)
        print(f"Selected friend: {friend_name}")
        self.update_all_leds()

    # --- Recording ---

    def _start_recording(self):
        """Start recording audio for selected friend"""
        if not self.selected_friend:
            return

        friend_name = self.config.friends[self.selected_friend].get('name', self.selected_friend)
        self.set_state(State.RECORDING, f"for {friend_name}")

        # Notify friend that we started recording
        self.network.send_recording_started(self.selected_friend)

        # Start audio recording
        self.audio.start_recording()

    def _stop_recording_and_send(self):
        """Stop recording and send the message"""
        if self.state != State.RECORDING or not self.selected_friend:
            return

        friend_id = self.selected_friend
        friend_name = self.config.friends[friend_id].get('name', friend_id)

        # Notify friend that we stopped recording
        self.network.send_recording_stopped(friend_id)

        # Stop audio recording
        audio_file = self.audio.stop_recording()

        if audio_file:
            print(f"Sending message to {friend_name}...")

            # Send via network
            self.network.send_message(friend_id, audio_file)

            # Add to conversation history as sent message
            msg_entry = {
                'id': str(uuid.uuid4()),
                'file': audio_file,
                'timestamp': int(time.time()),
                'heard': True,  # We heard our own message
                'direction': 'sent',
            }
            self.messages[friend_id].insert(0, msg_entry)

            # Set sent status (blue LED)
            self.message_sent_status[friend_id] = True
            self.save_state()

        self.set_state(State.IDLE)

        # Check for pending autoplay (conversation mode)
        if self.pending_autoplay:
            pending = self.pending_autoplay
            self.pending_autoplay = None
            self._auto_play_message(pending['friend_id'], pending['message_data'])

    def _cancel_recording(self):
        """Cancel recording without sending"""
        if self.state != State.RECORDING:
            return

        if self.selected_friend:
            self.network.send_recording_stopped(self.selected_friend)

        self.audio.stop_recording()
        print("Recording cancelled")
        self.set_state(State.IDLE)
        self.pending_autoplay = None

    # --- Playback ---

    def _start_playback(self, friend_id: str):
        """Start playing messages for a friend (most recent first)"""
        if not self.messages.get(friend_id):
            friend_name = self.config.friends[friend_id].get('name', friend_id)
            print(f"No messages from {friend_name}")
            return

        self.playback_friend = friend_id
        self.playback_index = 0  # Start at most recent
        self._play_current_message()

    def _play_previous_message(self):
        """Navigate to the previous (older) message in conversation"""
        if not self.playback_friend:
            return

        # Cancel current playback timer
        if self.playback_timer:
            self.playback_timer.cancel()
            self.playback_timer = None

        # Stop any ongoing audio
        self.audio.stop_playback()

        # Move to next older message
        self.playback_index += 1
        messages = self.messages.get(self.playback_friend, [])

        if self.playback_index >= len(messages):
            # Wrap around to most recent
            self.playback_index = 0

        self._play_current_message()

    def _play_current_message(self):
        """Play the message at the current playback_index"""
        if not self.playback_friend:
            return

        messages = self.messages.get(self.playback_friend, [])
        if not messages or self.playback_index < 0 or self.playback_index >= len(messages):
            self._stop_playback()
            return

        message = messages[self.playback_index]
        friend_name = self.config.friends[self.playback_friend].get('name', self.playback_friend)
        direction = message.get('direction', 'received')
        direction_label = "from" if direction == 'received' else "to"

        if self.state != State.PLAYING:
            self.set_state(State.PLAYING, f"{friend_name}")

        # Check if audio file exists
        if not Path(message.get('file', '')).exists():
            print(f"Audio file missing, skipping: {message.get('file')}")
            # Skip to next
            self._on_playback_finished()
            return

        msg_num = self.playback_index + 1
        total = len(messages)
        print(f"Playing message {msg_num}/{total} ({direction_label} {friend_name})")

        # Mark received messages as heard
        if direction == 'received' and not message.get('heard', True):
            message['heard'] = True
            self.save_state()
            # Notify sender that message was heard
            self.network.notify_message_heard(self.playback_friend, message['id'])

        # Play audio
        duration = self.audio.play_message(message['file'])

        # Schedule transition after playback
        self.playback_timer = threading.Timer(
            duration,
            self._on_playback_finished
        )
        self.playback_timer.start()

    def _on_playback_finished(self):
        """Called when current message playback finishes"""
        self.playback_timer = None

        if self.state != State.PLAYING:
            return

        # After playing, just go back to IDLE
        # User can press friend button again for previous message
        print("Playback finished")
        self._stop_playback()

    def _stop_playback(self):
        """Stop all playback and return to IDLE"""
        if self.playback_timer:
            self.playback_timer.cancel()
            self.playback_timer = None

        self.audio.stop_playback()
        self.playback_friend = None
        self.playback_index = -1

        if self.state == State.PLAYING:
            self.set_state(State.IDLE)

    def _auto_play_message(self, friend_id: str, message_data: dict):
        """Auto-play a message (conversation mode)"""
        if self.state != State.IDLE:
            return

        # Select the friend who sent the message
        if self.selected_friend != friend_id:
            self._select_friend(friend_id)

        self.playback_friend = friend_id
        self.playback_index = 0  # Most recent message (just arrived)
        self._play_current_message()

    # --- Network Event Handlers ---

    def handle_message_received(self, friend_id: str, message_data: dict):
        """Handle incoming voice message"""
        friend_name = self.config.friends.get(friend_id, {}).get('name', friend_id)
        print(f"New message from {friend_name}!")

        # Add to conversation history (newest first)
        self.messages[friend_id].insert(0, {
            'id': message_data['id'],
            'file': message_data['file'],
            'timestamp': message_data['timestamp'],
            'heard': False,
            'direction': 'received',
        })

        self.save_state()

        # Conversation mode: auto-play
        if self.conversation_mode:
            self._reset_conversation_timeout()
            if self.state == State.RECORDING:
                # Queue for after recording finishes
                self.pending_autoplay = {
                    'friend_id': friend_id,
                    'message_data': message_data,
                }
                print(f"Message queued for autoplay after recording")
            elif self.state == State.IDLE:
                self._auto_play_message(friend_id, message_data)
            # If PLAYING, just update LED - user will see pulsating green

        # Update LED for this friend
        self.update_rgb_led(friend_id)

    def handle_message_heard(self, friend_id: str, message_id: str):
        """Handle notification that our message was heard"""
        friend_name = self.config.friends.get(friend_id, {}).get('name', friend_id)
        print(f"{friend_name} heard your message")

        self.message_sent_status[friend_id] = False
        self.save_state()
        self.update_rgb_led(friend_id)

    def handle_recording_started(self, friend_id: str):
        """Handle notification that a friend started recording for us"""
        self.friend_is_recording[friend_id] = True
        self.update_rgb_led(friend_id)

    def handle_recording_stopped(self, friend_id: str):
        """Handle notification that a friend stopped recording"""
        self.friend_is_recording[friend_id] = False
        self.update_rgb_led(friend_id)

    # --- Conversation Mode ---

    def _reset_conversation_timeout(self):
        """Reset the 5-minute conversation mode auto-disable timer"""
        self._cancel_conversation_timeout()
        self.conversation_timeout_timer = threading.Timer(
            self.CONVERSATION_TIMEOUT,
            self._conversation_timeout_expired
        )
        self.conversation_timeout_timer.start()

    def _cancel_conversation_timeout(self):
        """Cancel the conversation timeout timer"""
        if self.conversation_timeout_timer:
            self.conversation_timeout_timer.cancel()
            self.conversation_timeout_timer = None

    def _conversation_timeout_expired(self):
        """Called when conversation mode times out"""
        self.conversation_timeout_timer = None
        self.conversation_mode = False
        print("Conversation mode auto-disabled (timeout)")

    # --- Main Loop ---

    def run(self):
        """Main application loop"""
        print("Voice Messenger running...")
        if self.mock_mode:
            print("  Running in MOCK mode - no real network connections")

        # Start network listener
        self.network.start()

        # Start hardware monitoring
        self.hardware.start()

        # Initial LED update
        self.update_all_leds()

        try:
            while self.hardware.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

        print("\nShutting down...")
        self.shutdown()

    def shutdown(self):
        """Clean shutdown"""
        self.save_state()
        self._cancel_conversation_timeout()

        if self.playback_timer:
            self.playback_timer.cancel()

        self.hardware.stop()
        self.network.stop()
        self.audio.cleanup()
        print("Shutdown complete")


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
            print("--simulate-message requires --mock mode")
        else:
            def simulate():
                time.sleep(1.0)
                app.network.simulate_incoming_message(args.simulate_message)
            threading.Thread(target=simulate, daemon=True).start()

    app.run()


if __name__ == "__main__":
    main()
