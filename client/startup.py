#!/usr/bin/env python3
"""
Startup Script
Boot decision logic: check WiFi configured & connectable -> start main.py or AP mode + portal
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from wifi_manager import get_wifi_manager, WiFiManager


# GPIO pin for force-setup button (hold during boot to enter setup mode)
SETUP_BUTTON_PIN = 17  # Same as record button

# Flag file indicating setup was just completed
SETUP_COMPLETE_FLAG = Path(__file__).parent / ".setup_complete"


def check_setup_button() -> bool:
    """Check if setup button is held during boot"""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SETUP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        time.sleep(0.1)
        # Button pressed = LOW (pulled to ground)
        pressed = GPIO.input(SETUP_BUTTON_PIN) == GPIO.LOW
        GPIO.cleanup(SETUP_BUTTON_PIN)
        return pressed
    except Exception:
        # Not on Pi or GPIO not available
        return False


def is_wifi_configured(config: Config) -> bool:
    """Check if WiFi credentials are configured"""
    return bool(config.wifi_ssid and config.wifi_password)


def is_relay_server_configured(config: Config) -> bool:
    """Check if relay server is configured"""
    return bool(config.relay_server_url)


def has_friends_configured(config: Config) -> bool:
    """Check if at least one friend is configured"""
    return len(config.friends) > 0


def wait_for_wifi_connection(wifi: WiFiManager, timeout: int = 30) -> bool:
    """Wait for WiFi connection with timeout"""
    print(f"Waiting for WiFi connection (timeout: {timeout}s)...")
    for i in range(timeout):
        if wifi.is_connected():
            print(f"WiFi connected after {i+1}s")
            return True
        time.sleep(1)
    print("WiFi connection timeout")
    return False


def start_setup_portal(wifi: WiFiManager):
    """Start AP mode and setup portal"""
    print("Starting setup portal...")

    # Start AP mode
    wifi.start_ap_mode()

    # Start portal
    from setup_portal import init_portal, run_portal
    init_portal(mock_wifi=False)

    try:
        # Run on port 80 for captive portal
        run_portal(port=80)
    except PermissionError:
        print("Port 80 requires root. Trying port 8080...")
        run_portal(port=8080)


def start_main_app():
    """Start the main voice messenger application"""
    print("Starting main application...")

    # Remove setup complete flag if present
    if SETUP_COMPLETE_FLAG.exists():
        SETUP_COMPLETE_FLAG.unlink()

    main_script = Path(__file__).parent / "main.py"

    # Run main.py in the same process (exec)
    os.execv(sys.executable, [sys.executable, str(main_script)])


def main():
    """Main startup logic"""
    print("=" * 50)
    print("Voice Messenger - Startup")
    print("=" * 50)

    # Load configuration
    config_path = Path(__file__).parent / "config.json"
    config = Config(str(config_path))

    # Check for force-setup mode (button held during boot)
    if check_setup_button():
        print("Setup button held - entering setup mode")
        wifi = get_wifi_manager()
        start_setup_portal(wifi)
        return

    # Check if setup was just completed (flag file exists)
    if SETUP_COMPLETE_FLAG.exists():
        print("Setup just completed - starting main app")
        start_main_app()
        return

    # Check configuration completeness
    wifi_ok = is_wifi_configured(config)
    server_ok = is_relay_server_configured(config)
    friends_ok = has_friends_configured(config)

    print(f"Configuration status:")
    print(f"  WiFi configured: {wifi_ok}")
    print(f"  Server configured: {server_ok}")
    print(f"  Friends configured: {friends_ok}")

    if not wifi_ok:
        print("WiFi not configured - entering setup mode")
        wifi = get_wifi_manager()
        start_setup_portal(wifi)
        return

    # WiFi is configured - try to connect
    wifi = get_wifi_manager()

    # Check if already connected
    if wifi.is_connected():
        current_ssid = wifi.get_current_ssid()
        if current_ssid == config.wifi_ssid:
            print(f"Already connected to {current_ssid}")
            if server_ok and friends_ok:
                start_main_app()
            else:
                print("Missing server or friends config - entering setup mode")
                start_setup_portal(wifi)
            return

    # Try to connect to configured network
    print(f"Attempting to connect to {config.wifi_ssid}...")
    connected = wifi.connect_to_network(config.wifi_ssid, config.wifi_password)

    if not connected:
        # Wait a bit more
        connected = wait_for_wifi_connection(wifi, timeout=30)

    if connected:
        print("WiFi connected successfully")
        if server_ok and friends_ok:
            start_main_app()
        else:
            print("Missing configuration - entering setup mode (WiFi connected)")
            # Don't start AP mode, just run portal on existing network
            from setup_portal import init_portal, run_portal
            init_portal(mock_wifi=False)
            ip = wifi.get_ip_address()
            print(f"Open http://{ip}:8080 to complete setup")
            run_portal(port=8080)
    else:
        print("WiFi connection failed - entering AP setup mode")
        start_setup_portal(wifi)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStartup interrupted")
        sys.exit(0)
