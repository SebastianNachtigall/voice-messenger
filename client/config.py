"""
Configuration Manager
Handles loading and saving device configuration
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any


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
        
        # GPIO pins
        self.back_button_pin = self.data.get('back_button_pin', 17)
        self.record_led_pin = self.data.get('record_led_pin', 27)
        
        # Friends configuration
        # {friend_id: {name, device_id, button_pin, led_pin}}
        self.friends: Dict[str, Dict[str, Any]] = self.data.get('friends', {})
        
        # Save if new device
        if 'device_id' not in self.data:
            self.save()
    
    def load(self) -> dict:
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Config load error: {e}")
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
        self.data['back_button_pin'] = self.back_button_pin
        self.data['record_led_pin'] = self.record_led_pin
        self.data['friends'] = self.friends
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.data, f, indent=2)
            print(f"✅ Config saved to {self.config_path}")
        except Exception as e:
            print(f"❌ Config save error: {e}")
    
    def default_config(self) -> dict:
        """Return default configuration"""
        return {
            'device_id': str(uuid.uuid4()),
            'device_name': 'Voice Messenger',
            'relay_server_url': '',
            'wifi_ssid': '',
            'wifi_password': '',
            'back_button_pin': 17,
            'record_led_pin': 27,
            'friends': {}
        }
    
    def add_friend(self, name: str, device_id: str, button_pin: int, led_pin: int) -> str:
        """Add a new friend"""
        friend_id = str(uuid.uuid4())
        self.friends[friend_id] = {
            'name': name,
            'device_id': device_id,
            'button_pin': button_pin,
            'led_pin': led_pin
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
    
    def get_friend_by_button_pin(self, pin: int) -> str:
        """Get friend_id by button pin"""
        for friend_id, config in self.friends.items():
            if config['button_pin'] == pin:
                return friend_id
        return None


# Example configuration for testing
def create_example_config():
    """Create example configuration file"""
    config = {
        'device_id': str(uuid.uuid4()),
        'device_name': 'Voice Messenger - Anna',
        'wifi_ssid': 'MyWiFi',
        'wifi_password': 'password123',
        'back_button_pin': 17,
        'record_led_pin': 27,
        'friends': {
            'friend1': {
                'name': 'Max',
                'device_id': 'device-uuid-max',
                'button_pin': 22,
                'led_pin': 23
            },
            'friend2': {
                'name': 'Lisa',
                'device_id': 'device-uuid-lisa',
                'button_pin': 24,
                'led_pin': 25
            }
        }
    }
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Example config created")


if __name__ == '__main__':
    create_example_config()
