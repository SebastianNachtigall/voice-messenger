# Voice Messenger

A peer-to-peer voice messaging device for children using Raspberry Pi Zero W. Kids can send and receive voice messages to their friends by pressing dedicated buttons - no screens, no typing, just simple voice communication.

## Features

- **Simple Interface** - One button per friend, LED indicators for new messages
- **Internet Connected** - Works across different homes via relay server
- **No Message Storage** - Privacy-focused; messages forwarded in real-time only
- **Setup Portal** - Easy WiFi and friend configuration via captive portal
- **Auto-Reconnect** - Automatically reconnects if connection is lost
- **Persistent State** - Remembers unheard messages across restarts
- **Low Cost** - Runs on Raspberry Pi Zero W (~$15)

## How It Works

```
┌─────────────┐         ┌─────────────────┐         ┌─────────────┐
│   Emma's    │ ──────► │  Relay Server   │ ──────► │   Max's     │
│   Device    │ ◄────── │  (WebSocket)    │ ◄────── │   Device    │
└─────────────┘         └─────────────────┘         └─────────────┘
     │                                                     │
     │ Press & hold button ─────────────────────► LED blinks green
     │ (2 sec to record)                          (new message!)
     │                                                     │
     │ LED turns blue ◄─────────────────────── Press button to play
     │ (message heard)                                     │
```

## Project Structure

```
voice_messenger_complete/
├── client/                    # Raspberry Pi software
│   ├── main.py               # Main application
│   ├── hardware.py           # GPIO button/LED control
│   ├── audio.py              # Recording and playback
│   ├── network.py            # WebSocket communication
│   ├── config.py             # Configuration management
│   ├── setup_portal.py       # WiFi setup web interface
│   ├── wifi_manager.py       # AP/client mode switching
│   ├── startup.py            # Boot decision logic
│   ├── templates/
│   │   └── setup.html        # Setup portal web page
│   └── requirements.txt
├── server/                    # Relay server (deploy to cloud)
│   ├── server.py             # WebSocket relay + device directory
│   ├── requirements.txt
│   ├── Procfile              # For Railway/Heroku
│   └── railway.json
└── README.md                  # This file
```

---

## Hardware Requirements

### Per Device

| Component | Description | Notes |
|-----------|-------------|-------|
| Raspberry Pi Zero W | Main controller | Must have WiFi |
| Micro SD Card | 8GB+ recommended | For Raspberry Pi OS |
| USB Microphone | For recording | USB sound card + mic works too |
| Speaker | For playback | 3.5mm, USB, or I2S DAC |
| Push Buttons | Momentary switches | 1 back + 1 per friend |
| LEDs | Status indicators | 1 record (red) + 1 per friend (green) |
| Resistors | 220-330 ohm | One per LED |
| Power Supply | 5V 2A+ | Micro USB |
| Enclosure | Optional | 3D printed or project box |

### Tools Needed

- Soldering iron (or breadboard for prototyping)
- Jumper wires
- Multimeter (helpful for debugging)

---

## Raspberry Pi Zero W GPIO Pinout

```
                    ┌─────────────────────────────────────┐
                    │         Raspberry Pi Zero W         │
                    │              (USB/HDMI side)        │
                    │                                     │
                    │  ┌─────────────────────────────┐   │
                    │  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│   │
                    │  │ GPIO HEADER (40 pins)       │   │
                    │  └─────────────────────────────┘   │
                    └─────────────────────────────────────┘

    3.3V  (1) ●──────────────────────────────────● (2)  5V
   GPIO2  (3) ●──────────────────────────────────● (4)  5V
   GPIO3  (5) ●──────────────────────────────────● (6)  GND ◄── COMMON GROUND
   GPIO4  (7) ●──────────────────────────────────● (8)  GPIO14
     GND  (9) ●──────────────────────────────────● (10) GPIO15
  GPIO17 (11) ● ◄── BACK BUTTON ─────────────────● (12) GPIO18
  GPIO27 (13) ● ◄── RECORD LED (Red) ────────────● (14) GND
  GPIO22 (15) ● ◄── FRIEND 1 BUTTON ─────────────● (16) GPIO23 ◄── FRIEND 1 LED
    3.3V (17) ●──────────────────────────────────● (18) GPIO24 ◄── FRIEND 2 BUTTON
  GPIO10 (19) ●──────────────────────────────────● (20) GND
   GPIO9 (21) ●──────────────────────────────────● (22) GPIO25 ◄── FRIEND 2 LED
  GPIO11 (23) ●──────────────────────────────────● (24) GPIO8
     GND (25) ●──────────────────────────────────● (26) GPIO7
   GPIO0 (27) ●──────────────────────────────────● (28) GPIO1
   GPIO5 (29) ● ◄── FRIEND 3 BUTTON ─────────────● (30) GND
   GPIO6 (31) ● ◄── FRIEND 3 LED ────────────────● (32) GPIO12
  GPIO13 (33) ● ◄── FRIEND 4 BUTTON ─────────────● (34) GND
  GPIO19 (35) ● ◄── FRIEND 4 LED ────────────────● (36) GPIO16
  GPIO26 (37) ● ◄── FRIEND 5 BUTTON ─────────────● (38) GPIO20 ◄── FRIEND 5 LED
     GND (39) ●──────────────────────────────────● (40) GPIO21
```

### Default Pin Configuration

| Function | GPIO | Physical Pin | Notes |
|----------|------|--------------|-------|
| **Back Button** | 17 | 11 | Returns to previous message / cancels |
| **Record LED** | 27 | 13 | Red LED, blinks during recording |
| **Friend 1 Button** | 22 | 15 | Press to play, hold to record |
| **Friend 1 LED** | 23 | 16 | Green: new message, Blue: sent |
| **Friend 2 Button** | 24 | 18 | Press to play, hold to record |
| **Friend 2 LED** | 25 | 22 | Green: new message, Blue: sent |
| **Friend 3 Button** | 5 | 29 | Optional |
| **Friend 3 LED** | 6 | 31 | Optional |
| **Friend 4 Button** | 13 | 33 | Optional |
| **Friend 4 LED** | 19 | 35 | Optional |
| **Friend 5 Button** | 26 | 37 | Optional |
| **Friend 5 LED** | 20 | 38 | Optional |

---

## Wiring Diagram

### Button Wiring (Active Low with Internal Pull-up)

```
                            Raspberry Pi
                           ┌───────────┐
                           │           │
    ┌──────────────────────┤ GPIO Pin  │
    │                      │           │
    │                      │   GND     ├──────────────┐
    │                      └───────────┘              │
    │                                                 │
    │    ┌─────────┐                                 │
    └────┤         ├─────────────────────────────────┘
         │ Button  │
         │  (NO)   │  ◄── Normally Open momentary switch
         └─────────┘

When pressed: GPIO reads LOW (0)
When released: GPIO reads HIGH (1) via internal pull-up
```

### LED Wiring

```
                            Raspberry Pi
                           ┌───────────┐
                           │           │
                           │ GPIO Pin  ├───────┐
                           │           │       │
                           │   GND     ├───┐   │
                           └───────────┘   │   │
                                           │   │
              ┌────────────────────────────┘   │
              │                                │
              │         220-330Ω               │
             ─┴─         ┌───┐                │
              ▼  LED     │   │ Resistor        │
             ─┬─         └─┬─┘                │
              │            │                   │
              └────────────┴───────────────────┘

GPIO HIGH = LED ON
GPIO LOW = LED OFF
```

### Complete Wiring Example (2 Friends)

```
                                    Raspberry Pi Zero W
                                   ┌─────────────────────┐
                                   │                     │
    [BACK BUTTON]──────────────────┤ GPIO 17 (pin 11)   │
           │                       │                     │
           └───────────────────────┤ GND (pin 6)        │
                                   │                     │
    [RECORD LED]───[220Ω]──────────┤ GPIO 27 (pin 13)   │
           │                       │                     │
           └───────────────────────┤ GND (pin 14)       │
                                   │                     │
    [FRIEND 1 BUTTON]──────────────┤ GPIO 22 (pin 15)   │
           │                       │                     │
           └───────────────────────┤ GND (pin 6)        │
                                   │                     │
    [FRIEND 1 LED]───[220Ω]────────┤ GPIO 23 (pin 16)   │
           │                       │                     │
           └───────────────────────┤ GND (pin 6)        │
                                   │                     │
    [FRIEND 2 BUTTON]──────────────┤ GPIO 24 (pin 18)   │
           │                       │                     │
           └───────────────────────┤ GND (pin 20)       │
                                   │                     │
    [FRIEND 2 LED]───[220Ω]────────┤ GPIO 25 (pin 22)   │
           │                       │                     │
           └───────────────────────┤ GND (pin 20)       │
                                   │                     │
    [USB MICROPHONE]───────────────┤ USB Port           │
                                   │                     │
    [SPEAKER]──────────────────────┤ 3.5mm Audio Jack   │
                                   │                     │
    [5V POWER]─────────────────────┤ Micro USB Power    │
                                   └─────────────────────┘
```

---

## Software Setup

### 1. Deploy the Relay Server

The relay server forwards messages between devices. Deploy to a cloud service:

**Option A: Railway (Recommended)**
```bash
cd server/
git init && git add . && git commit -m "Initial"
# Create Railway account, link repo, deploy
# Note your URL: https://your-app.up.railway.app
```

**Option B: Local Server (for testing)**
```bash
cd server/
pip install aiohttp
python server.py
# Server runs at ws://YOUR_IP:8080/ws
```

### 2. Setup Raspberry Pi

**Install Raspberry Pi OS Lite** on SD card, enable SSH and WiFi.

**Copy files to Pi:**
```bash
rsync -avz client/ pi@raspberrypi:~/voice_messenger/
```

**Install dependencies on Pi:**
```bash
ssh pi@raspberrypi
cd ~/voice_messenger
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install system audio tools
sudo apt install -y python3-pyaudio alsa-utils
```

### 3. Configure Device

**Option A: Setup Portal (Recommended)**

If WiFi isn't configured, the device automatically starts a setup portal:

1. Device creates WiFi network: `VoiceMessenger-Setup`
2. Connect phone/laptop to this network
3. Open browser - redirects to setup page
4. Configure: WiFi, device name, server URL, friends

**Option B: Manual Configuration**

Create `config.json`:
```json
{
  "device_id": "emma-device-001",
  "device_name": "Emma",
  "relay_server_url": "wss://your-server.up.railway.app/ws",
  "wifi_ssid": "YourWiFi",
  "wifi_password": "YourPassword",
  "back_button_pin": 17,
  "record_led_pin": 27,
  "friends": {
    "friend1": {
      "name": "Max",
      "device_id": "max-device-001",
      "button_pin": 22,
      "led_pin": 23
    }
  }
}
```

### 4. Run the Application

**Test mode (with keyboard simulation):**
```bash
source venv/bin/activate
python main.py --mock  # No network, simulates friends
python main.py         # Real network, GPIO buttons
```

**Production (auto-start on boot):**
```bash
# Install required system packages
sudo apt install -y hostapd dnsmasq

# Disable auto-start (Python controls these)
sudo systemctl disable hostapd dnsmasq
sudo systemctl stop hostapd dnsmasq

# Install and enable the voice-messenger service
sudo cp voice-messenger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-messenger
sudo systemctl start voice-messenger
```

---

## Boot Flow & System Services

When the Pi boots, the `voice-messenger.service` runs `startup.py` which determines the operating mode:

```
                              Pi Boot
                                 │
                                 ▼
                    systemd starts voice-messenger.service
                                 │
                                 ▼
                          startup.py runs
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
   Setup button            WiFi configured         WiFi configured
   held during boot?       in config.json?         & connectable?
         │                       │                       │
         │ YES                   │ NO                    │ NO (30s timeout)
         ▼                       ▼                       ▼
    ┌─────────────────────────────────────────────────────────┐
    │              START AP MODE + SETUP PORTAL               │
    │                                                         │
    │  • Creates WiFi network: "VoiceMessenger-Setup"        │
    │  • Starts hostapd (access point)                        │
    │  • Starts dnsmasq (DHCP + DNS redirect)                │
    │  • Runs Flask portal on port 80                         │
    │  • All DNS queries redirect to 192.168.4.1 (portal)    │
    └─────────────────────────────────────────────────────────┘
                                 │
                                 │ User completes setup
                                 ▼
         ┌───────────────────────────────────────────────┐
         │                                               │
         │ WiFi connected + Server configured + Friends? │
         │                                               │
         └───────────────────────────────────────────────┘
                                 │
                                 │ YES
                                 ▼
                    ┌─────────────────────────┐
                    │   START MAIN APP        │
                    │                         │
                    │  • Runs main.py         │
                    │  • Normal operation     │
                    │  • Connects to server   │
                    └─────────────────────────┘
```

### System Services

| Service | Purpose | Auto-start |
|---------|---------|------------|
| `voice-messenger` | Main application (runs startup.py) | **Enabled** |
| `hostapd` | Creates WiFi access point | Disabled (controlled by Python) |
| `dnsmasq` | DHCP server + DNS redirect for captive portal | Disabled (controlled by Python) |

### How WiFi Check Works

`startup.py` checks WiFi connectivity using:

```python
# 1. Check if credentials exist in config.json
has_config = bool(config.wifi_ssid and config.wifi_password)

# 2. Check if currently connected (uses iwgetid command)
result = subprocess.run(["iwgetid", "-r", "wlan0"], capture_output=True)
is_connected = bool(result.stdout.strip())

# 3. Optionally test internet connectivity
result = subprocess.run(["ping", "-c", "1", "-W", "3", "8.8.8.8"])
has_internet = (result.returncode == 0)
```

### Service Management Commands

```bash
# View live logs
sudo journalctl -u voice-messenger -f

# Restart the service
sudo systemctl restart voice-messenger

# Stop the service
sudo systemctl stop voice-messenger

# Check service status
sudo systemctl status voice-messenger

# Force enter setup mode (hold back button during reboot)
sudo reboot
# Then hold GPIO 17 (back button) during boot
```

### Setup Portal Details

When in AP mode, the portal:

- **SSID:** `VoiceMessenger-Setup` (open, no password)
- **IP Address:** `192.168.4.1`
- **DHCP Range:** `192.168.4.10` - `192.168.4.50`
- **Captive Portal:** All DNS queries redirect to portal (triggers auto-open on phones)

The portal allows configuration of:
1. WiFi network selection and password
2. Device name (child's name)
3. Relay server URL
4. Friend selection from server directory
5. GPIO pin assignment for each friend's button/LED

---

## Usage

### Sending a Message

1. **Press and hold** a friend's button for **2 seconds**
2. Record LED starts **blinking red** - you're recording!
3. Speak your message
4. **Release button** to send
5. Friend's LED turns **blue** (message sent)
6. When friend listens, LED turns **off**

### Receiving a Message

1. Friend's LED **blinks green** - new message!
2. **Short press** the button to play
3. Message plays through speaker
4. If multiple messages, they play in sequence

### Back Button

- During playback: Go to previous message
- During recording: Cancel recording
- Hold during boot: Enter setup mode

---

## LED Status Guide

| LED State | Meaning |
|-----------|---------|
| **Off** | No activity |
| **Blinking Green** | New unheard message(s) |
| **Solid Green** | Currently playing message |
| **Solid Blue** | Message sent, waiting for friend to listen |
| **Blinking Red** (Record LED) | Currently recording |

---

## Troubleshooting

### No Sound Output

```bash
# Test speaker
aplay /usr/share/sounds/alsa/Front_Center.wav

# Check audio devices
aplay -l

# Set default output
sudo raspi-config  # Advanced > Audio > Force 3.5mm
```

### Microphone Not Working

```bash
# Test recording
arecord -d 5 test.wav && aplay test.wav

# List recording devices
arecord -l

# Check levels
alsamixer  # Press F6 to select USB device
```

### Connection Issues

```bash
# Check WiFi
iwconfig wlan0

# Test server connection
curl http://your-server:8080/status

# View logs
journalctl -u voice-messenger -f
```

### GPIO Issues

```bash
# Test button (should print 0 when pressed, 1 when released)
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP); print(GPIO.input(22))"

# Test LED
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(23, GPIO.OUT); GPIO.output(23, 1); input('LED on? Press enter'); GPIO.cleanup()"
```

---

## API Reference

### Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server status page |
| `/status` | GET | JSON status |
| `/ws` | WebSocket | Device connection |
| `/api/devices` | GET | List registered devices |
| `/api/devices/{id}` | GET | Get device details |

### WebSocket Messages

**Register:**
```json
{"type": "register", "device_id": "...", "device_name": "...", "friends": ["..."]}
```

**Voice Message:**
```json
{"type": "voice_message", "recipient_id": "...", "message_id": "...", "audio_data": "base64..."}
```

**Message Heard:**
```json
{"type": "message_heard", "sender_id": "...", "message_id": "..."}
```

---

## Contributing

This is a private project. Feel free to fork and adapt for your own use.

---

## License

Private project - All rights reserved.

---

**Built with love for kids who want to stay connected with their friends.**
