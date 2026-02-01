# Voice Messenger

A peer-to-peer voice messaging device for children using Raspberry Pi Zero W. Kids can send and receive voice messages to their friends by pressing dedicated buttons - no screens, no typing, just simple voice communication.

## Features

- **Simple Interface** - One button per friend, RGB LED strip + yellow selection LEDs
- **Conversation Mode** - Toggle dialog mode for real-time back-and-forth
- **Internet Connected** - Works across different homes via relay server
- **Privacy-Focused** - Messages forwarded via relay server
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
     │ Select friend → Press Record ────────────► RGB LED = rainbow
     │ (RGB pulsates red while recording)         (friend is recording!)
     │                                                     │
     │ RGB LED = pulsating green ◄─────────── Press Record to send
     │ (new message! press friend button to play)          │
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
| WS2812B LED Strip | Addressable RGB LEDs | 1 LED per friend (status indicators) |
| Yellow LEDs | Standard LEDs | 1 per friend ("selected" indicator) |
| Push Buttons | Momentary switches | 1 Record + 1 Dialog + 1 per friend |
| Resistors | 220-330 ohm | One per yellow LED |
| Capacitor | 1000 uF, 6.3V+ | Across LED strip power (recommended) |
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

    3.3V  (1) ●──────────────────────────────────● (2)  5V ◄── WS2812B VCC
   GPIO2  (3) ●──────────────────────────────────● (4)  5V
   GPIO3  (5) ●──────────────────────────────────● (6)  GND ◄── COMMON GROUND
   GPIO4  (7) ● ◄── DIALOG BUTTON ───────────────● (8)  GPIO14
     GND  (9) ●──────────────────────────────────● (10) GPIO15
  GPIO17 (11) ● ◄── RECORD BUTTON ───────────────● (12) GPIO18 ◄── WS2812B DATA
  GPIO27 (13) ●──────────────────────────────────● (14) GND ◄── WS2812B GND
  GPIO22 (15) ● ◄── FRIEND 1 BUTTON ─────────────● (16) GPIO23 ◄── FRIEND 1 YELLOW LED
    3.3V (17) ●──────────────────────────────────● (18) GPIO24 ◄── FRIEND 2 BUTTON
  GPIO10 (19) ●──────────────────────────────────● (20) GND
   GPIO9 (21) ●──────────────────────────────────● (22) GPIO25 ◄── FRIEND 2 YELLOW LED
  GPIO11 (23) ●──────────────────────────────────● (24) GPIO8
     GND (25) ●──────────────────────────────────● (26) GPIO7
   GPIO0 (27) ●──────────────────────────────────● (28) GPIO1
   GPIO5 (29) ● ◄── FRIEND 3 BUTTON ─────────────● (30) GND
   GPIO6 (31) ● ◄── FRIEND 3 YELLOW LED ─────────● (32) GPIO12
  GPIO13 (33) ●──────────────────────────────────● (34) GND
  GPIO19 (35) ●──────────────────────────────────● (36) GPIO16
  GPIO26 (37) ●──────────────────────────────────● (38) GPIO20
     GND (39) ●──────────────────────────────────● (40) GPIO21
```

### Default Pin Configuration

| Function | GPIO | Physical Pin | Notes |
|----------|------|--------------|-------|
| **Record Button** | 17 | 11 | Toggle recording on/off |
| **Dialog Button** | 4 | 7 | Toggle conversation mode |
| **WS2812B Data** | 18 | 12 | RGB LED strip data line (PWM) |
| **Friend 1 Button** | 22 | 15 | Select friend / play messages |
| **Friend 1 Yellow LED** | 23 | 16 | "Currently selected" indicator |
| **Friend 2 Button** | 24 | 18 | Select friend / play messages |
| **Friend 2 Yellow LED** | 25 | 22 | "Currently selected" indicator |
| **Friend 3 Button** | 5 | 29 | Optional |
| **Friend 3 Yellow LED** | 6 | 31 | Optional |

**Note:** GPIO 18 is required for the WS2812B strip (uses PWM hardware). The strip also needs 5V power and GND from the Pi header.

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

### Yellow LED Wiring (per friend)

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
              │         220-330 ohm            │
             ─┴─         ┌───┐                │
              ▼  Yellow  │   │ Resistor        │
             ─┬─  LED    └─┬─┘                │
              │            │                   │
              └────────────┴───────────────────┘

GPIO HIGH = LED ON  (friend is selected)
GPIO LOW  = LED OFF (friend not selected)
```

### WS2812B LED Strip Wiring

```
                                            WS2812B LED Strip
                                   ┌──────┬──────┬──────┬─────
    Raspberry Pi                   │ LED0 │ LED1 │ LED2 │ ...
   ┌───────────┐                   │Friend│Friend│Friend│
   │            │                  │  1   │  2   │  3   │
   │  5V (pin2) ├──────────┐      └──┬───┴──┬───┴──┬───┴─────
   │            │          │         │      │      │
   │ GND (pin6) ├──────┐   │    ┌────┴──────┴──────┴────┐
   │            │      │   │    │                        │
   │GPIO18(pin12├──┐   │   │    │   WS2812B Strip        │
   └───────────┘  │   │   │    │   (continuous strip,    │
                  │   │   │    │    one data line)       │
                  │   │   │    │                        │
                  │   │   │    │  VCC ──────────────────┤◄── 5V
                  │   │   │    │  GND ──────────────────┤◄── GND
                  │   │   │    │  DIN ──────────────────┤◄── GPIO 18
                  │   │   │    └────────────────────────┘
                  │   │   │
                  │   │   └─── 5V (red wire)
                  │   └─────── GND (black/white wire)
                  └─────────── Data In (green wire)

    IMPORTANT: Add a 1000uF capacitor between 5V and GND
    at the strip's power input to prevent power surges.

    Optional: Add a 330 ohm resistor in series on the
    data line (GPIO 18 → resistor → DIN) to protect
    against voltage spikes.
```

```
    Detailed Strip Connection:

    Pi Pin 2 (5V) ───────┬──────────────────── Strip VCC (red)
                         │
                    ┌────┴────┐
                    │ 1000uF  │  ◄── Electrolytic capacitor
                    │  6.3V+  │      (+ to 5V, - to GND)
                    └────┬────┘
                         │
    Pi Pin 6 (GND) ──────┴──────────────────── Strip GND (white/black)

    Pi Pin 12 (GPIO 18) ──[330 ohm]────────── Strip DIN (green)
```

### Complete Wiring Example (2 Friends)

```
                                        Raspberry Pi Zero W
                                       ┌─────────────────────┐
                                       │                     │
                          ┌────────────┤ 5V (pin 2)         │
                          │  ┌─────────┤ GND (pin 6)        │
                          │  │         │                     │
    [WS2812B STRIP]       │  │         │                     │
      VCC ────────────────┘  │         │                     │
      GND ───────────────────┘         │                     │
      DIN ──[330 ohm]─────────────────┤ GPIO 18 (pin 12)   │
      (1000uF cap between VCC & GND)  │                     │
                                       │                     │
    [RECORD BUTTON]────────────────────┤ GPIO 17 (pin 11)   │
           │                           │                     │
           └───────────────────────────┤ GND (pin 9)        │
                                       │                     │
    [DIALOG BUTTON]────────────────────┤ GPIO 4 (pin 7)     │
           │                           │                     │
           └───────────────────────────┤ GND (pin 9)        │
                                       │                     │
    [FRIEND 1 BUTTON]─────────────────┤ GPIO 22 (pin 15)   │
           │                           │                     │
           └───────────────────────────┤ GND (pin 6)        │
                                       │                     │
    [FRIEND 1 YELLOW LED]──[220 ohm]──┤ GPIO 23 (pin 16)   │
           │                           │                     │
           └───────────────────────────┤ GND (pin 14)       │
                                       │                     │
    [FRIEND 2 BUTTON]─────────────────┤ GPIO 24 (pin 18)   │
           │                           │                     │
           └───────────────────────────┤ GND (pin 20)       │
                                       │                     │
    [FRIEND 2 YELLOW LED]──[220 ohm]──┤ GPIO 25 (pin 22)   │
           │                           │                     │
           └───────────────────────────┤ GND (pin 20)       │
                                       │                     │
    [USB MICROPHONE]───────────────────┤ USB Port           │
                                       │                     │
    [SPEAKER]──────────────────────────┤ 3.5mm Audio Jack   │
                                       │                     │
    [5V POWER]─────────────────────────┤ Micro USB Power    │
                                       └─────────────────────┘
```

### Physical Layout (per friend)

```
    Each friend has 3 components arranged together:

    ┌─────────────────────────────────────────┐
    │                                         │
    │   (●) Yellow LED     ◄── "Selected"     │
    │                         indicator       │
    │   [●] RGB LED        ◄── WS2812B strip  │
    │       (from strip)      status LED      │
    │                                         │
    │   [Button]           ◄── Friend select  │
    │                         / play button   │
    │                                         │
    └─────────────────────────────────────────┘

    Plus two global buttons:

    [Record Button]  ◄── Start/stop recording
    [Dialog Button]  ◄── Toggle conversation mode
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
  "hardware": {
    "led_strip_pin": 18,
    "led_count": 3,
    "record_button_pin": 17,
    "dialog_button_pin": 4
  },
  "friends": {
    "friend1": {
      "name": "Max",
      "device_id": "max-device-001",
      "button_pin": 22,
      "yellow_led_pin": 23,
      "led_index": 0
    },
    "friend2": {
      "name": "Lisa",
      "device_id": "lisa-device-001",
      "button_pin": 24,
      "yellow_led_pin": 25,
      "led_index": 1
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

# Force enter setup mode (hold Record button during reboot)
sudo reboot
# Then hold GPIO 17 (Record button) during boot
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
5. GPIO pin assignment for buttons, yellow LEDs, and LED strip

---

## Usage

### Selecting a Friend

1. Press a **friend button** to select that friend
2. The **yellow LED** next to that button lights up
3. One friend is always selected (even if offline)

### Sending a Message

1. Select a friend (if not already selected)
2. Press the **Record button** once to start recording
3. The RGB LED of the selected friend **pulsates red**
4. Speak your message
5. Press the **Record button** again to stop and send
6. RGB LED turns **solid blue** (message sent, not yet heard)
7. If you press **any other button** during recording, it cancels (message not sent)

### Receiving a Message

1. Friend's RGB LED **pulsates green** - new message!
2. Press that **friend's button** (select, then press again) to play
3. Messages play in order, most recent first
4. Press the **same friend button** again to hear the previous (older) message
5. Keep pressing to navigate back through the full conversation history
6. Any **other button** press stops playback

### Conversation Mode

1. Press the **Dialog button** to toggle conversation mode on/off
2. When on: incoming messages **auto-play immediately**
3. If recording when a message arrives, it queues until recording finishes
4. Auto-disables after 5 minutes of no incoming messages

---

## LED Status Guide

### RGB LED (WS2812B strip, per friend) - Priority Order

| Priority | LED State | Meaning |
|----------|-----------|---------|
| 1 | **Pulsating Red** | You are recording a message for this friend |
| 2 | **Rainbow Cycling** | This friend is currently recording for you |
| 3 | **Pulsating Green** | New unheard message(s) from this friend |
| 4 | **Solid Blue** | Message sent, friend hasn't heard it yet |
| 5 | **Solid Green** | Friend is online |
| 6 | **Off** | Friend is offline |

### Yellow LED (per friend)

| LED State | Meaning |
|-----------|---------|
| **On** | This friend is currently selected |
| **Off** | This friend is not selected |

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

**Recording Started (forwarded to recipient):**
```json
{"type": "recording_started", "sender_id": "...", "recipient_id": "..."}
```

**Recording Stopped (forwarded to recipient):**
```json
{"type": "recording_stopped", "sender_id": "...", "recipient_id": "..."}
```

---

## Contributing

This is a private project. Feel free to fork and adapt for your own use.

---

## License

Private project - All rights reserved.

---

**Built with love for kids who want to stay connected with their friends.**
