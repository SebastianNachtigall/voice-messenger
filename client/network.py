"""
P2P Network Controller - Direct device-to-device communication
Uses UDP broadcasting for device discovery and TCP for message transfer.
Supports mock mode for testing without network.
"""

import socket
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Dict


class P2PNetwork:
    """Peer-to-peer network for direct message delivery"""
    
    DISCOVERY_PORT = 5555
    MESSAGE_PORT = 5556
    BROADCAST_INTERVAL = 10  # seconds
    
    def __init__(self, config, mock_mode: bool = False):
        self.config = config
        self.running = False
        self.mock_mode = mock_mode

        # Callbacks
        self.on_message_received: Optional[Callable] = None
        self.on_message_heard: Optional[Callable] = None

        # Known peers: {device_id: {'ip': '...', 'last_seen': timestamp}}
        self.peers: Dict[str, dict] = {}
        self.peers_lock = threading.Lock()

        # Message tracking
        self.sent_messages: Dict[str, dict] = {}  # {message_id: {friend_id, timestamp}}

        # Threads
        self.discovery_thread = None
        self.listener_thread = None
        self.broadcast_thread = None

        if mock_mode:
            print("🔧 Network running in MOCK mode (no actual network connections)")
    
    def start(self):
        """Start network services"""
        self.running = True

        if self.mock_mode:
            # In mock mode, simulate all friends being online
            for friend_id, friend_config in self.config.friends.items():
                device_id = friend_config.get('device_id', friend_id)
                self.peers[device_id] = {
                    'ip': '127.0.0.1',
                    'name': friend_config.get('name', friend_id),
                    'port': self.MESSAGE_PORT,
                    'last_seen': time.time()
                }
            print(f"✅ Network started in MOCK mode (device_id: {self.config.device_id})")
            return

        # Start discovery listener
        self.discovery_thread = threading.Thread(
            target=self.discovery_listener,
            daemon=True
        )
        self.discovery_thread.start()

        # Start broadcast
        self.broadcast_thread = threading.Thread(
            target=self.broadcast_presence,
            daemon=True
        )
        self.broadcast_thread.start()

        # Start message listener
        self.listener_thread = threading.Thread(
            target=self.message_listener,
            daemon=True
        )
        self.listener_thread.start()

        print(f"✅ Network started (device_id: {self.config.device_id})")
    
    def stop(self):
        """Stop network services"""
        self.running = False
        
        if self.discovery_thread:
            self.discovery_thread.join(timeout=1.0)
        if self.listener_thread:
            self.listener_thread.join(timeout=1.0)
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=1.0)
        
        print("✅ Network stopped")
    
    def broadcast_presence(self):
        """Broadcast presence to discover other devices"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        message = json.dumps({
            'type': 'presence',
            'device_id': self.config.device_id,
            'device_name': self.config.device_name,
            'port': self.MESSAGE_PORT
        }).encode()
        
        while self.running:
            try:
                sock.sendto(message, ('<broadcast>', self.DISCOVERY_PORT))
                print(f"📡 Broadcasting presence...")
            except Exception as e:
                print(f"⚠️ Broadcast error: {e}")
            
            time.sleep(self.BROADCAST_INTERVAL)
        
        sock.close()
    
    def discovery_listener(self):
        """Listen for presence broadcasts from other devices"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.DISCOVERY_PORT))
        sock.settimeout(1.0)
        
        print(f"👂 Listening for devices on port {self.DISCOVERY_PORT}")
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                message = json.loads(data.decode())
                
                if message['type'] == 'presence':
                    device_id = message['device_id']
                    
                    # Don't add ourselves
                    if device_id == self.config.device_id:
                        continue
                    
                    # Add/update peer
                    with self.peers_lock:
                        if device_id not in self.peers:
                            print(f"🔍 Discovered device: {message['device_name']} ({device_id})")
                        
                        self.peers[device_id] = {
                            'ip': addr[0],
                            'name': message['device_name'],
                            'port': message['port'],
                            'last_seen': time.time()
                        }
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️ Discovery error: {e}")
        
        sock.close()
    
    def message_listener(self):
        """Listen for incoming messages"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.MESSAGE_PORT))
        sock.listen(5)
        sock.settimeout(1.0)
        
        print(f"👂 Listening for messages on port {self.MESSAGE_PORT}")
        
        while self.running:
            try:
                client_sock, addr = sock.accept()
                # Handle in separate thread
                thread = threading.Thread(
                    target=self.handle_incoming_connection,
                    args=(client_sock, addr),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️ Listener error: {e}")
        
        sock.close()
    
    def handle_incoming_connection(self, sock, addr):
        """Handle incoming message connection"""
        try:
            # Receive header
            header_size = int.from_bytes(sock.recv(4), byteorder='big')
            header_data = sock.recv(header_size)
            header = json.loads(header_data.decode())
            
            msg_type = header['type']
            
            if msg_type == 'voice_message':
                self.receive_voice_message(sock, header)
            elif msg_type == 'message_heard':
                self.receive_message_heard(header)
            
            sock.close()
        except Exception as e:
            print(f"⚠️ Connection handling error: {e}")
    
    def receive_voice_message(self, sock, header):
        """Receive voice message file"""
        try:
            sender_id = header['sender_id']
            message_id = header['message_id']
            file_size = header['file_size']
            timestamp = header['timestamp']
            
            # Receive file data
            file_data = b''
            remaining = file_size
            while remaining > 0:
                chunk = sock.recv(min(4096, remaining))
                if not chunk:
                    break
                file_data += chunk
                remaining -= len(chunk)
            
            # Save file
            audio_dir = Path("audio_messages")
            audio_dir.mkdir(exist_ok=True)
            filename = audio_dir / f"received_{message_id}.wav"
            
            with open(filename, 'wb') as f:
                f.write(file_data)
            
            print(f"📥 Received message from {sender_id} ({len(file_data)} bytes)")
            
            # Find which friend this is
            friend_id = None
            for fid, friend_config in self.config.friends.items():
                if friend_config.get('device_id') == sender_id:
                    friend_id = fid
                    break
            
            if friend_id and self.on_message_received:
                self.on_message_received(friend_id, {
                    'id': message_id,
                    'file': str(filename),
                    'timestamp': timestamp
                })
        except Exception as e:
            print(f"⚠️ Receive error: {e}")
    
    def receive_message_heard(self, header):
        """Receive notification that message was heard"""
        try:
            message_id = header['message_id']
            listener_id = header['listener_id']
            
            # Find which friend this is
            friend_id = None
            for fid, friend_config in self.config.friends.items():
                if friend_config.get('device_id') == listener_id:
                    friend_id = fid
                    break
            
            if friend_id and self.on_message_heard:
                self.on_message_heard(friend_id, message_id)
        except Exception as e:
            print(f"⚠️ Heard notification error: {e}")
    
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
                file_data = f.read()

            # Create message
            message_id = str(uuid.uuid4())

            # Track sent message
            self.sent_messages[message_id] = {
                'friend_id': friend_id,
                'timestamp': time.time()
            }

            # Mock mode: simulate successful send
            if self.mock_mode:
                print(f"📤 [MOCK] Sent message to {friend_name} ({len(file_data)} bytes)")
                print(f"   Message ID: {message_id[:8]}...")
                # Simulate "heard" notification after 2 seconds
                threading.Timer(2.0, self._mock_message_heard, args=[friend_id, message_id]).start()
                return

            # Find peer
            with self.peers_lock:
                peer = self.peers.get(target_device_id)

            if not peer:
                print(f"⚠️ Peer {target_device_id} not found (device offline?)")
                return

            header = {
                'type': 'voice_message',
                'sender_id': self.config.device_id,
                'message_id': message_id,
                'file_size': len(file_data),
                'timestamp': int(time.time())
            }

            # Send to peer
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer['ip'], peer['port']))

            # Send header
            header_data = json.dumps(header).encode()
            sock.send(len(header_data).to_bytes(4, byteorder='big'))
            sock.send(header_data)

            # Send file
            sock.sendall(file_data)
            sock.close()

            print(f"📤 Sent message to {friend_name} ({len(file_data)} bytes)")
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

            target_device_id = friend_config.get('device_id')
            if not target_device_id:
                return

            # Find peer
            with self.peers_lock:
                peer = self.peers.get(target_device_id)

            if not peer:
                print(f"⚠️ Cannot notify {friend_name} - device offline")
                return

            # Create notification
            header = {
                'type': 'message_heard',
                'listener_id': self.config.device_id,
                'message_id': message_id
            }

            # Send notification
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer['ip'], peer['port']))

            header_data = json.dumps(header).encode()
            sock.send(len(header_data).to_bytes(4, byteorder='big'))
            sock.send(header_data)
            sock.close()

            print(f"✅ Notified {friend_name} that message was heard")
        except Exception as e:
            print(f"⚠️ Notify error: {e}")
    
    def get_peer_status(self, friend_id: str) -> str:
        """Get online status of a friend"""
        # In mock mode, all friends are online
        if self.mock_mode:
            return "online"

        friend_config = self.config.friends.get(friend_id)
        if not friend_config:
            return "unknown"

        target_device_id = friend_config.get('device_id')
        if not target_device_id:
            return "not_configured"

        with self.peers_lock:
            peer = self.peers.get(target_device_id)
            if peer and (time.time() - peer['last_seen']) < 30:
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
