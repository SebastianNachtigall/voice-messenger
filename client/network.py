"""
WebSocket Network Controller - Communication via relay server
Connects to a central WebSocket relay server for message delivery between devices.
Supports mock mode for testing without network.
"""

import asyncio
import json
import threading
import time
import uuid
import base64
from pathlib import Path
from typing import Callable, Optional, Dict

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    print("⚠️ websockets not installed, run: pip install websockets")
    WEBSOCKETS_AVAILABLE = False


class WebSocketNetwork:
    """WebSocket-based network for relay server communication"""

    RECONNECT_DELAY = 5  # seconds between reconnection attempts
    PING_INTERVAL = 30   # seconds between ping messages

    def __init__(self, config, mock_mode: bool = False):
        self.config = config
        self.running = False
        self.mock_mode = mock_mode
        self.connected = False

        # WebSocket connection
        self.ws = None
        self.loop = None
        self.ws_thread = None

        # Callbacks
        self.on_message_received: Optional[Callable] = None
        self.on_message_heard: Optional[Callable] = None
        self.on_connection_changed: Optional[Callable] = None
        self.on_recording_started: Optional[Callable] = None
        self.on_recording_stopped: Optional[Callable] = None

        # Message tracking
        self.sent_messages: Dict[str, dict] = {}  # {message_id: {friend_id, timestamp}}

        # Friend online status
        self.online_friends: set = set()

        if mock_mode:
            print("🔧 Network running in MOCK mode (no actual network connections)")

    def start(self):
        """Start network services"""
        self.running = True

        if self.mock_mode:
            # In mock mode, simulate all friends being online
            for friend_id, friend_config in self.config.friends.items():
                self.online_friends.add(friend_id)
            print(f"✅ Network started in MOCK mode (device_id: {self.config.device_id})")
            return

        if not WEBSOCKETS_AVAILABLE:
            print("❌ Cannot start network: websockets not installed")
            return

        if not self.config.relay_server_url:
            print("⚠️ No relay_server_url configured, network disabled")
            return

        # Start WebSocket client in separate thread
        self.ws_thread = threading.Thread(target=self._run_websocket_loop, daemon=True)
        self.ws_thread.start()

        print(f"✅ Network starting (device_id: {self.config.device_id})")

    def stop(self):
        """Stop network services"""
        self.running = False
        self.connected = False

        if self.ws and self.loop:
            # Schedule close on the event loop
            asyncio.run_coroutine_threadsafe(self._close_websocket(), self.loop)

        if self.ws_thread:
            self.ws_thread.join(timeout=2.0)

        print("✅ Network stopped")

    def _run_websocket_loop(self):
        """Run the asyncio event loop for WebSocket in a separate thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._websocket_handler())
        except Exception as e:
            print(f"❌ WebSocket loop error: {e}")
        finally:
            self.loop.close()

    async def _websocket_handler(self):
        """Main WebSocket connection handler with auto-reconnect"""
        while self.running:
            try:
                print(f"📡 Connecting to {self.config.relay_server_url}...")

                async with websockets.connect(
                    self.config.relay_server_url,
                    ping_interval=self.PING_INTERVAL,
                    ping_timeout=10
                ) as ws:
                    self.ws = ws
                    self.connected = True
                    print("✅ Connected to relay server")

                    # Register with server
                    await self._register()

                    # Notify connection change
                    if self.on_connection_changed:
                        self.on_connection_changed(True)

                    # Handle incoming messages
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                print(f"⚠️ Connection closed: {e}")
            except Exception as e:
                print(f"⚠️ WebSocket error: {e}")

            self.connected = False
            self.ws = None

            if self.on_connection_changed:
                self.on_connection_changed(False)

            if self.running:
                print(f"🔄 Reconnecting in {self.RECONNECT_DELAY}s...")
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _close_websocket(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()

    async def _register(self):
        """Register device with the relay server"""
        # Get list of friend device_ids
        friend_device_ids = [
            friend_config.get('device_id')
            for friend_config in self.config.friends.values()
            if friend_config.get('device_id')
        ]

        register_msg = {
            'type': 'register',
            'device_id': self.config.device_id,
            'device_name': self.config.device_name,
            'friends': friend_device_ids
        }

        await self.ws.send(json.dumps(register_msg))
        print(f"📝 Registered as {self.config.device_name}")

    async def _handle_message(self, raw_message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(raw_message)
            msg_type = data.get('type')

            if msg_type == 'registered':
                print(f"✅ Registration confirmed by server")

            elif msg_type == 'friends_online':
                online_device_ids = data.get('friends', [])
                self._update_online_friends(online_device_ids)

            elif msg_type == 'voice_message':
                await self._receive_voice_message(data)

            elif msg_type == 'message_heard':
                self._receive_message_heard(data)

            elif msg_type == 'recording_started':
                self._receive_recording_started(data)

            elif msg_type == 'recording_stopped':
                self._receive_recording_stopped(data)

            elif msg_type == 'message_delivered':
                message_id = data.get('message_id')
                print(f"✅ Message {message_id[:8]}... delivered")

            elif msg_type == 'recipient_offline':
                recipient_id = data.get('recipient_id')
                friend_name = self._get_friend_name_by_device_id(recipient_id)
                print(f"⚠️ {friend_name} is offline, message not delivered")

            elif msg_type == 'pong':
                pass  # Keep-alive response

            elif msg_type == 'error':
                print(f"❌ Server error: {data.get('message')}")

        except json.JSONDecodeError:
            print(f"⚠️ Invalid JSON received")
        except Exception as e:
            print(f"⚠️ Error handling message: {e}")

    def _update_online_friends(self, online_device_ids: list):
        """Update which friends are online"""
        self.online_friends.clear()
        for friend_id, friend_config in self.config.friends.items():
            if friend_config.get('device_id') in online_device_ids:
                self.online_friends.add(friend_id)
                friend_name = friend_config.get('name', friend_id)
                print(f"🟢 {friend_name} is online")

    def _get_friend_id_by_device_id(self, device_id: str) -> Optional[str]:
        """Find friend_id by their device_id"""
        for friend_id, friend_config in self.config.friends.items():
            if friend_config.get('device_id') == device_id:
                return friend_id
        return None

    def _get_friend_name_by_device_id(self, device_id: str) -> str:
        """Get friend name by device_id"""
        for friend_config in self.config.friends.values():
            if friend_config.get('device_id') == device_id:
                return friend_config.get('name', device_id)
        return device_id

    async def _receive_voice_message(self, data: dict):
        """Handle incoming voice message"""
        try:
            sender_device_id = data.get('sender_id')
            message_id = data.get('message_id')
            audio_data_b64 = data.get('audio_data')
            timestamp = data.get('timestamp')

            # Decode audio data
            audio_data = base64.b64decode(audio_data_b64)

            # Save to file
            audio_dir = Path("audio_messages")
            audio_dir.mkdir(exist_ok=True)
            filename = audio_dir / f"received_{message_id}.wav"

            with open(filename, 'wb') as f:
                f.write(audio_data)

            # Find friend_id
            friend_id = self._get_friend_id_by_device_id(sender_device_id)
            friend_name = self._get_friend_name_by_device_id(sender_device_id)

            print(f"📥 Received message from {friend_name} ({len(audio_data)} bytes)")

            if friend_id and self.on_message_received:
                self.on_message_received(friend_id, {
                    'id': message_id,
                    'file': str(filename),
                    'timestamp': timestamp
                })

        except Exception as e:
            print(f"⚠️ Error receiving voice message: {e}")

    def _receive_message_heard(self, data: dict):
        """Handle message heard notification"""
        try:
            listener_device_id = data.get('listener_id')
            message_id = data.get('message_id')

            friend_id = self._get_friend_id_by_device_id(listener_device_id)
            friend_name = self._get_friend_name_by_device_id(listener_device_id)

            print(f"👂 {friend_name} heard your message")

            if friend_id and self.on_message_heard:
                self.on_message_heard(friend_id, message_id)

        except Exception as e:
            print(f"⚠️ Error handling heard notification: {e}")

    def _receive_recording_started(self, data: dict):
        """Handle incoming recording_started notification"""
        try:
            sender_device_id = data.get('sender_id')
            friend_id = self._get_friend_id_by_device_id(sender_device_id)
            friend_name = self._get_friend_name_by_device_id(sender_device_id)
            print(f"🎙️ {friend_name} started recording for you")
            if friend_id and self.on_recording_started:
                self.on_recording_started(friend_id)
        except Exception as e:
            print(f"⚠️ Error handling recording_started: {e}")

    def _receive_recording_stopped(self, data: dict):
        """Handle incoming recording_stopped notification"""
        try:
            sender_device_id = data.get('sender_id')
            friend_id = self._get_friend_id_by_device_id(sender_device_id)
            friend_name = self._get_friend_name_by_device_id(sender_device_id)
            print(f"🎙️ {friend_name} stopped recording")
            if friend_id and self.on_recording_stopped:
                self.on_recording_stopped(friend_id)
        except Exception as e:
            print(f"⚠️ Error handling recording_stopped: {e}")

    def send_recording_started(self, friend_id: str):
        """Notify a friend that we started recording for them"""
        try:
            friend_config = self.config.friends.get(friend_id)
            if not friend_config:
                return
            target_device_id = friend_config.get('device_id')
            if not target_device_id:
                return

            if self.mock_mode:
                friend_name = friend_config.get('name', friend_id)
                print(f"🎙️ [MOCK] Notified {friend_name}: recording started")
                return

            if not self.connected:
                return

            message = {
                'type': 'recording_started',
                'sender_id': self.config.device_id,
                'recipient_id': target_device_id,
            }
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(message)),
                self.loop
            )
        except Exception as e:
            print(f"⚠️ Error sending recording_started: {e}")

    def send_recording_stopped(self, friend_id: str):
        """Notify a friend that we stopped recording"""
        try:
            friend_config = self.config.friends.get(friend_id)
            if not friend_config:
                return
            target_device_id = friend_config.get('device_id')
            if not target_device_id:
                return

            if self.mock_mode:
                friend_name = friend_config.get('name', friend_id)
                print(f"🎙️ [MOCK] Notified {friend_name}: recording stopped")
                return

            if not self.connected:
                return

            message = {
                'type': 'recording_stopped',
                'sender_id': self.config.device_id,
                'recipient_id': target_device_id,
            }
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(message)),
                self.loop
            )
        except Exception as e:
            print(f"⚠️ Error sending recording_stopped: {e}")

    def send_message(self, friend_id: str, audio_file: str):
        """Send voice message to a friend"""
        try:
            friend_config = self.config.friends.get(friend_id)
            if not friend_config:
                print(f"⚠️ Friend {friend_id} not found in config")
                return

            friend_name = friend_config.get('name', friend_id)
            target_device_id = friend_config.get('device_id')

            if not target_device_id:
                print(f"⚠️ No device_id for friend {friend_id}")
                return

            # Read audio file
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # Create message
            message_id = str(uuid.uuid4())

            # Track sent message
            self.sent_messages[message_id] = {
                'friend_id': friend_id,
                'timestamp': time.time()
            }

            # Mock mode: simulate successful send
            if self.mock_mode:
                print(f"📤 [MOCK] Sent message to {friend_name} ({len(audio_data)} bytes)")
                print(f"   Message ID: {message_id[:8]}...")
                # Simulate "heard" notification after 2 seconds
                threading.Timer(2.0, self._mock_message_heard, args=[friend_id, message_id]).start()
                return

            if not self.connected:
                print(f"⚠️ Not connected to server, cannot send message")
                return

            # Encode audio as base64
            audio_data_b64 = base64.b64encode(audio_data).decode('utf-8')

            # Send via WebSocket
            message = {
                'type': 'voice_message',
                'recipient_id': target_device_id,
                'message_id': message_id,
                'audio_data': audio_data_b64,
                'timestamp': int(time.time())
            }

            # Schedule send on event loop
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(message)),
                self.loop
            )

            print(f"📤 Sending message to {friend_name} ({len(audio_data)} bytes)")

        except Exception as e:
            print(f"❌ Send error: {e}")

    def _mock_message_heard(self, friend_id: str, message_id: str):
        """Mock callback for simulating message heard notification"""
        friend_config = self.config.friends.get(friend_id)
        friend_name = friend_config.get('name', friend_id) if friend_config else friend_id
        print(f"✅ [MOCK] {friend_name} heard your message!")
        if self.on_message_heard:
            self.on_message_heard(friend_id, message_id)

    def notify_message_heard(self, friend_id: str, message_id: str):
        """Notify sender that their message was heard"""
        try:
            friend_config = self.config.friends.get(friend_id)
            if not friend_config:
                return

            friend_name = friend_config.get('name', friend_id)

            # Mock mode: just print
            if self.mock_mode:
                print(f"✅ [MOCK] Notified {friend_name} that message was heard")
                return

            if not self.connected:
                print(f"⚠️ Not connected, cannot send heard notification")
                return

            target_device_id = friend_config.get('device_id')
            if not target_device_id:
                return

            # Send notification via WebSocket
            message = {
                'type': 'message_heard',
                'sender_id': target_device_id,
                'message_id': message_id
            }

            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(message)),
                self.loop
            )

            print(f"✅ Notified {friend_name} that message was heard")

        except Exception as e:
            print(f"⚠️ Notify error: {e}")

    def get_peer_status(self, friend_id: str) -> str:
        """Get online status of a friend"""
        # In mock mode, all friends are online
        if self.mock_mode:
            return "online"

        if not self.connected:
            return "disconnected"

        if friend_id in self.online_friends:
            return "online"
        else:
            return "offline"

    def simulate_incoming_message(self, friend_id: str, audio_file: Optional[str] = None):
        """
        Simulate receiving a message from a friend (for testing).
        If no audio_file is provided, creates a simple test tone.
        """
        if not self.mock_mode:
            print("⚠️ simulate_incoming_message only works in mock mode")
            return

        friend_config = self.config.friends.get(friend_id)
        if not friend_config:
            print(f"⚠️ Friend {friend_id} not found")
            return

        friend_name = friend_config.get('name', friend_id)
        message_id = str(uuid.uuid4())

        # Create audio directory
        audio_dir = Path("audio_messages")
        audio_dir.mkdir(exist_ok=True)

        if audio_file and Path(audio_file).exists():
            # Copy provided file
            import shutil
            filename = audio_dir / f"received_{message_id}.wav"
            shutil.copy(audio_file, filename)
        else:
            # Create a simple test audio file (silence or beep)
            filename = audio_dir / f"received_{message_id}.wav"
            self._create_test_audio(filename)

        print(f"📥 [MOCK] Received message from {friend_name}")

        if self.on_message_received:
            self.on_message_received(friend_id, {
                'id': message_id,
                'file': str(filename),
                'timestamp': int(time.time())
            })

    def _create_test_audio(self, filename: Path):
        """Create a simple test audio file (1 second beep)"""
        import wave
        import struct
        import math

        sample_rate = 16000
        duration = 1.0  # seconds
        frequency = 440  # Hz (A4 note)

        num_samples = int(sample_rate * duration)

        with wave.open(str(filename), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            for i in range(num_samples):
                t = i / sample_rate
                # Generate sine wave with fade in/out
                envelope = min(t * 10, 1.0) * min((duration - t) * 10, 1.0)
                sample = int(32767 * 0.3 * envelope * math.sin(2 * math.pi * frequency * t))
                wav_file.writeframes(struct.pack('<h', sample))

        print(f"   Created test audio: {filename}")


# Alias for backwards compatibility
P2PNetwork = WebSocketNetwork
