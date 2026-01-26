"""
WiFi Manager
Controls hostapd/wpa_supplicant for AP and client modes on Raspberry Pi
"""

import subprocess
import time
import re
from pathlib import Path
from typing import List, Dict, Optional


class WiFiManager:
    """Manages WiFi modes: Access Point or Client"""

    AP_SSID = "VoiceMessenger-Setup"
    AP_IP = "192.168.4.1"
    AP_SUBNET = "192.168.4.0/24"
    AP_DHCP_START = "192.168.4.10"
    AP_DHCP_END = "192.168.4.50"

    HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
    DNSMASQ_CONF = "/etc/dnsmasq.d/captive-portal.conf"
    WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"

    def __init__(self, interface: str = "wlan0"):
        self.interface = interface

    def is_connected(self) -> bool:
        """Check if WiFi is connected to a network"""
        try:
            result = subprocess.run(
                ["iwgetid", "-r", self.interface],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def get_current_ssid(self) -> Optional[str]:
        """Get the SSID of the currently connected network"""
        try:
            result = subprocess.run(
                ["iwgetid", "-r", self.interface],
                capture_output=True, text=True, timeout=5
            )
            ssid = result.stdout.strip()
            return ssid if ssid else None
        except Exception:
            return None

    def can_connect_to_internet(self) -> bool:
        """Check if there's internet connectivity"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
                capture_output=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def scan_networks(self) -> List[Dict[str, str]]:
        """Scan for available WiFi networks"""
        networks = []
        try:
            # Bring interface up and scan
            subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"],
                          capture_output=True, timeout=5)
            time.sleep(1)

            result = subprocess.run(
                ["sudo", "iwlist", self.interface, "scan"],
                capture_output=True, text=True, timeout=30
            )

            # Parse output
            current_network = {}
            for line in result.stdout.split('\n'):
                line = line.strip()

                # ESSID
                if 'ESSID:' in line:
                    match = re.search(r'ESSID:"([^"]*)"', line)
                    if match and match.group(1):
                        current_network['ssid'] = match.group(1)

                # Signal level
                if 'Signal level=' in line:
                    match = re.search(r'Signal level=(-?\d+)', line)
                    if match:
                        current_network['signal'] = int(match.group(1))

                # Encryption
                if 'Encryption key:' in line:
                    current_network['encrypted'] = 'on' in line.lower()

                # Cell boundary - save previous and start new
                if 'Cell ' in line and 'Address:' in line:
                    if current_network.get('ssid'):
                        networks.append(current_network)
                    current_network = {}

            # Don't forget last one
            if current_network.get('ssid'):
                networks.append(current_network)

            # Remove duplicates and sort by signal strength
            seen = set()
            unique_networks = []
            for net in sorted(networks, key=lambda x: x.get('signal', -100), reverse=True):
                if net['ssid'] not in seen:
                    seen.add(net['ssid'])
                    unique_networks.append(net)

            return unique_networks

        except Exception as e:
            print(f"Error scanning networks: {e}")
            return []

    def start_ap_mode(self) -> bool:
        """Start Access Point mode for setup portal"""
        try:
            print(f"Starting AP mode: {self.AP_SSID}")

            # Stop existing services
            subprocess.run(["sudo", "systemctl", "stop", "wpa_supplicant"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "stop", "hostapd"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "stop", "dnsmasq"], capture_output=True)

            # Configure hostapd
            hostapd_config = f"""interface={self.interface}
driver=nl80211
ssid={self.AP_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0
"""
            Path(self.HOSTAPD_CONF).write_text(hostapd_config)

            # Configure dnsmasq for DHCP and DNS redirect (captive portal)
            dnsmasq_config = f"""interface={self.interface}
dhcp-range={self.AP_DHCP_START},{self.AP_DHCP_END},255.255.255.0,24h
address=/#/{self.AP_IP}
"""
            Path(self.DNSMASQ_CONF).write_text(dnsmasq_config)

            # Set static IP for AP interface
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.interface], capture_output=True)
            subprocess.run(["sudo", "ip", "addr", "add", f"{self.AP_IP}/24", "dev", self.interface], capture_output=True)
            subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"], capture_output=True)

            # Start services
            subprocess.run(["sudo", "systemctl", "start", "hostapd"], capture_output=True)
            time.sleep(1)
            subprocess.run(["sudo", "systemctl", "start", "dnsmasq"], capture_output=True)

            print(f"AP mode started. Connect to '{self.AP_SSID}' and open http://{self.AP_IP}")
            return True

        except Exception as e:
            print(f"Error starting AP mode: {e}")
            return False

    def stop_ap_mode(self) -> bool:
        """Stop Access Point mode"""
        try:
            print("Stopping AP mode...")
            subprocess.run(["sudo", "systemctl", "stop", "hostapd"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "stop", "dnsmasq"], capture_output=True)

            # Remove captive portal dnsmasq config
            portal_conf = Path(self.DNSMASQ_CONF)
            if portal_conf.exists():
                portal_conf.unlink()

            return True

        except Exception as e:
            print(f"Error stopping AP mode: {e}")
            return False

    def connect_to_network(self, ssid: str, password: str) -> bool:
        """Connect to a WiFi network"""
        try:
            print(f"Connecting to {ssid}...")

            # Stop AP mode if running
            self.stop_ap_mode()

            # Generate wpa_supplicant config
            wpa_config = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=DE

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""
            # Write config
            subprocess.run(
                ["sudo", "bash", "-c", f"echo '{wpa_config}' > {self.WPA_SUPPLICANT_CONF}"],
                capture_output=True
            )

            # Restart networking
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.interface], capture_output=True)
            subprocess.run(["sudo", "systemctl", "restart", "wpa_supplicant"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "restart", "dhcpcd"], capture_output=True)

            # Wait for connection
            for _ in range(30):  # 30 second timeout
                time.sleep(1)
                if self.is_connected():
                    print(f"Connected to {ssid}")
                    return True

            print(f"Failed to connect to {ssid}")
            return False

        except Exception as e:
            print(f"Error connecting to network: {e}")
            return False

    def get_ip_address(self) -> Optional[str]:
        """Get current IP address"""
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", self.interface],
                capture_output=True, text=True, timeout=5
            )
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
            return match.group(1) if match else None
        except Exception:
            return None


# For testing on non-Pi systems
class MockWiFiManager:
    """Mock WiFi manager for development/testing"""

    AP_SSID = "VoiceMessenger-Setup"
    AP_IP = "192.168.4.1"

    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._connected = False
        self._ssid = None

    def is_connected(self) -> bool:
        return self._connected

    def get_current_ssid(self) -> Optional[str]:
        return self._ssid

    def can_connect_to_internet(self) -> bool:
        return self._connected

    def scan_networks(self) -> List[Dict[str, str]]:
        """Return mock network list"""
        return [
            {'ssid': 'MyHomeWiFi', 'signal': -45, 'encrypted': True},
            {'ssid': 'Neighbor_5G', 'signal': -65, 'encrypted': True},
            {'ssid': 'CoffeeShop', 'signal': -70, 'encrypted': False},
        ]

    def start_ap_mode(self) -> bool:
        print(f"[MOCK] Starting AP mode: {self.AP_SSID}")
        return True

    def stop_ap_mode(self) -> bool:
        print("[MOCK] Stopping AP mode")
        return True

    def connect_to_network(self, ssid: str, password: str) -> bool:
        print(f"[MOCK] Connecting to {ssid}")
        self._connected = True
        self._ssid = ssid
        return True

    def get_ip_address(self) -> Optional[str]:
        return "192.168.1.100" if self._connected else None


def get_wifi_manager(mock: bool = False) -> WiFiManager:
    """Get appropriate WiFi manager based on environment"""
    if mock:
        return MockWiFiManager()
    return WiFiManager()
