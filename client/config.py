"""
Configuration Manager
Handles loading and saving device configuration.
Supports the new hardware layout: WS2812B LED strip, yellow LEDs, record/dialog buttons.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Device configuration"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.data = self.load()

        # Device info
        self.device_id = self.data.get('device_id', str(uuid.uuid4()))
        self.device_name = self.data.get('device_name', 'Voice Messenger')

        # Relay server URL (WebSocket)
        self.relay_server_url = self.data.get('relay_server_url', '')

        # WiFi settings
        self.wifi_ssid = self.data.get('wifi_ssid', '')
        self.wifi_password = self.data.get('wifi_password', '')

        # Hardware settings (new structure)
        hardware = self.data.get('hardware', {})
        self.led_strip_pin = hardware.get('led_strip_pin', 18)
        self.led_count = hardware.get('led_count', 3)
        self.record_button_pin = hardware.get('record_button_pin', 17)
        self.dialog_button_pin = hardware.get('dialog_button_pin', 4)

        # Friends configuration
        # {friend_id: {name, device_id, button_pin, yellow_led_pin, led_index}}
        self.friends: Dict[str, Dict[str, Any]] = self.data.get('friends', {})

        # Migrate old config format if needed
        self._migrate_if_needed()

        # Save if new device
        if 'device_id' not in self.data:
            self.save()

    def _migrate_if_needed(self):
        """Migrate from old config format (back_button_pin, record_led_pin, led_pin) to new format"""
        migrated = False

        # Migrate top-level pins to hardware section
        if 'back_button_pin' in self.data or 'record_led_pin' in self.data:
            # Old config had back_button_pin on GPIO 17, reuse as record_button_pin
            if 'back_button_pin' in self.data:
                self.record_button_pin = self.data['back_button_pin']
            migrated = True

        # Migrate friend led_pin to yellow_led_pin
        for friend_id, friend_config in self.friends.items():
            if 'led_pin' in friend_config and 'yellow_led_pin' not in friend_config:
                friend_config['yellow_led_pin'] = friend_config.pop('led_pin')
                if 'led_index' not in friend_config:
                    # Auto-assign led_index based on order
                    friend_config['led_index'] = list(self.friends.keys()).index(friend_id)
                migrated = True

        if migrated:
            print("Config migrated to new format")
            self.save()

    def load(self) -> dict:
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Config load error: {e}")
                return self.default_config()
        else:
            return self.default_config()

    def save(self):
        """Save configuration to file"""
        self.data['device_id'] = self.device_id
        self.data['device_name'] = self.device_name
        self.data['relay_server_url'] = self.relay_server_url
        self.data['wifi_ssid'] = self.wifi_ssid
        self.data['wifi_password'] = self.wifi_password
        self.data['hardware'] = {
            'led_strip_pin': self.led_strip_pin,
            'led_count': self.led_count,
            'record_button_pin': self.record_button_pin,
            'dialog_button_pin': self.dialog_button_pin,
        }
        self.data['friends'] = self.friends

        # Remove old keys if present
        self.data.pop('back_button_pin', None)
        self.data.pop('record_led_pin', None)

        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.data, f, indent=2)
            print(f"Config saved to {self.config_path}")
        except Exception as e:
            print(f"Config save error: {e}")

    def default_config(self) -> dict:
        """Return default configuration"""
        return {
            'device_id': str(uuid.uuid4()),
            'device_name': 'Voice Messenger',
            'relay_server_url': '',
            'wifi_ssid': '',
            'wifi_password': '',
            'hardware': {
                'led_strip_pin': 18,
                'led_count': 3,
                'record_button_pin': 17,
                'dialog_button_pin': 4,
            },
            'friends': {}
        }

    def add_friend(self, name: str, device_id: str, button_pin: int,
                   yellow_led_pin: int, led_index: int) -> str:
        """Add a new friend"""
        friend_id = str(uuid.uuid4())
        self.friends[friend_id] = {
            'name': name,
            'device_id': device_id,
            'button_pin': button_pin,
            'yellow_led_pin': yellow_led_pin,
            'led_index': led_index,
        }
        self.save()
        return friend_id

    def remove_friend(self, friend_id: str):
        """Remove a friend"""
        if friend_id in self.friends:
            del self.friends[friend_id]
            self.save()

    def update_wifi(self, ssid: str, password: str):
        """Update WiFi credentials"""
        self.wifi_ssid = ssid
        self.wifi_password = password
        self.save()

    def get_friend_by_button_pin(self, pin: int) -> Optional[str]:
        """Get friend_id by button pin"""
        for friend_id, config in self.friends.items():
            if config['button_pin'] == pin:
                return friend_id
        return None

    def is_configured(self) -> bool:
        """Check if device is fully configured for operation"""
        return bool(
            self.wifi_ssid and
            self.wifi_password and
            self.relay_server_url and
            len(self.friends) > 0
        )

    def get_friend_device_ids(self) -> list:
        """Get list of friend device IDs"""
        return [
            friend.get('device_id')
            for friend in self.friends.values()
            if friend.get('device_id')
        ]

    def update_device_name(self, name: str):
        """Update device name"""
        self.device_name = name
        self.save()

    def update_relay_server(self, url: str):
        """Update relay server URL"""
        self.relay_server_url = url
        self.save()

    def clear_friends(self):
        """Remove all friends"""
        self.friends = {}
        self.save()


# Example configuration for testing
def create_example_config():
    """Create example configuration file"""
    config = {
        'device_id': str(uuid.uuid4()),
        'device_name': 'Voice Messenger - Anna',
        'relay_server_url': 'ws://localhost:8080/ws',
        'wifi_ssid': 'MyWiFi',
        'wifi_password': 'password123',
        'hardware': {
            'led_strip_pin': 18,
            'led_count': 3,
            'record_button_pin': 17,
            'dialog_button_pin': 4,
        },
        'friends': {
            'friend1': {
                'name': 'Max',
                'device_id': 'device-uuid-max',
                'button_pin': 22,
                'yellow_led_pin': 23,
                'led_index': 0,
            },
            'friend2': {
                'name': 'Lisa',
                'device_id': 'device-uuid-lisa',
                'button_pin': 24,
                'yellow_led_pin': 25,
                'led_index': 1,
            }
        }
    }

    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("Example config created")


if __name__ == '__main__':
    create_example_config()
