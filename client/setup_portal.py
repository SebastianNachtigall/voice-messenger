"""
Setup Portal
Flask web server for device configuration via captive portal
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict

try:
    from flask import Flask, render_template, request, jsonify, redirect
except ImportError:
    print("Flask not installed. Run: pip install flask")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Requests not installed. Run: pip install requests")
    requests = None

from config import Config
from wifi_manager import get_wifi_manager


app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)

# Global state
wifi_manager = None
config = None


def init_portal(mock_wifi: bool = False, config_path: str = "config.json"):
    """Initialize the portal with WiFi manager and config"""
    global wifi_manager, config
    wifi_manager = get_wifi_manager(mock=mock_wifi)
    config = Config(config_path)


@app.route('/')
def index():
    """Main setup page"""
    return render_template('setup.html')


@app.route('/api/wifi/scan', methods=['GET'])
def scan_wifi():
    """Scan for available WiFi networks"""
    networks = wifi_manager.scan_networks()
    return jsonify({'networks': networks})


@app.route('/api/wifi/status', methods=['GET'])
def wifi_status():
    """Get current WiFi status"""
    return jsonify({
        'connected': wifi_manager.is_connected(),
        'ssid': wifi_manager.get_current_ssid(),
        'ip': wifi_manager.get_ip_address(),
        'internet': wifi_manager.can_connect_to_internet()
    })


@app.route('/api/wifi/connect', methods=['POST'])
def connect_wifi():
    """Connect to a WiFi network"""
    data = request.get_json()
    ssid = data.get('ssid')
    password = data.get('password', '')

    if not ssid:
        return jsonify({'success': False, 'error': 'SSID required'}), 400

    success = wifi_manager.connect_to_network(ssid, password)

    if success:
        # Update config
        config.update_wifi(ssid, password)
        return jsonify({'success': True, 'ssid': ssid})
    else:
        return jsonify({'success': False, 'error': 'Connection failed'}), 500


@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Get list of registered devices from relay server"""
    server_url = config.relay_server_url or request.args.get('server_url', '')

    if not server_url:
        return jsonify({'devices': [], 'error': 'No server URL configured'})

    # Convert WebSocket URL to HTTP
    http_url = server_url.replace('ws://', 'http://').replace('wss://', 'https://')
    # Remove /ws suffix if present
    if http_url.endswith('/ws'):
        http_url = http_url[:-3]

    try:
        response = requests.get(f"{http_url}/api/devices", timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Filter out our own device
            devices = [d for d in data.get('devices', []) if d['device_id'] != config.device_id]
            return jsonify({'devices': devices})
        else:
            return jsonify({'devices': [], 'error': f'Server error: {response.status_code}'})
    except Exception as e:
        return jsonify({'devices': [], 'error': str(e)})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'device_id': config.device_id,
        'device_name': config.device_name,
        'relay_server_url': config.relay_server_url,
        'wifi_ssid': config.wifi_ssid,
        'friends': config.friends
    })


@app.route('/api/config', methods=['POST'])
def save_config():
    """Save configuration"""
    data = request.get_json()

    # Update device name
    if 'device_name' in data:
        config.device_name = data['device_name']

    # Update relay server URL
    if 'relay_server_url' in data:
        config.relay_server_url = data['relay_server_url']

    # Update friends (complete replacement)
    if 'friends' in data:
        config.friends = data['friends']

    config.save()

    return jsonify({'success': True, 'message': 'Configuration saved'})


@app.route('/api/config/friend', methods=['POST'])
def add_friend():
    """Add a friend configuration"""
    data = request.get_json()

    name = data.get('name')
    device_id = data.get('device_id')
    button_pin = data.get('button_pin')
    led_pin = data.get('led_pin')

    if not all([name, device_id, button_pin, led_pin]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    friend_id = config.add_friend(name, device_id, int(button_pin), int(led_pin))

    return jsonify({'success': True, 'friend_id': friend_id})


@app.route('/api/config/friend/<friend_id>', methods=['DELETE'])
def remove_friend(friend_id):
    """Remove a friend configuration"""
    config.remove_friend(friend_id)
    return jsonify({'success': True})


@app.route('/api/finish', methods=['POST'])
def finish_setup():
    """Complete setup and restart in normal mode"""
    # Ensure config is saved
    config.save()

    # Signal startup script to switch modes
    # This is done by writing a flag file
    flag_file = Path(__file__).parent / ".setup_complete"
    flag_file.touch()

    return jsonify({
        'success': True,
        'message': 'Setup complete. Device will restart in normal mode.'
    })


@app.route('/generate_204')
@app.route('/hotspot-detect.html')
@app.route('/ncsi.txt')
@app.route('/connecttest.txt')
def captive_portal_detect():
    """Handle captive portal detection from various OS"""
    return redirect('/')


# Apple captive portal detection
@app.route('/library/test/success.html')
def apple_captive():
    return redirect('/')


def run_portal(host: str = '0.0.0.0', port: int = 80, debug: bool = False):
    """Run the setup portal"""
    print(f"Starting setup portal on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Voice Messenger Setup Portal')
    parser.add_argument('--mock', action='store_true', help='Use mock WiFi manager')
    parser.add_argument('--port', type=int, default=80, help='Port to run on (default: 80)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--config', type=str, default='config.json', help='Config file path')

    args = parser.parse_args()

    init_portal(mock_wifi=args.mock, config_path=args.config)
    run_portal(port=args.port, debug=args.debug)
