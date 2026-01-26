# Voice Messenger - Projekt Dokumentation für Claude Code

## Projekt-Übersicht

**Name:** Voice Messenger
**Typ:** Hardware + Software System für Kinder
**Plattform:** Raspberry Pi Zero W
**Programmiersprache:** Python 3
**Architektur:** Client-Server mit WebSocket Relay

## Projekt-Ziel

Ein einfaches Voice-Message-System für Kinder (5-10 Jahre), das ohne Display auskommt. Kinder können sich gegenseitig Voice Messages über das Internet schicken - ähnlich wie Walkie-Talkies, aber asynchron.

### Zielgruppe
- Kinder im Alter 5-10 Jahre
- Keine technischen Kenntnisse erforderlich
- Bedienung nur über physische Buttons und LEDs

### Hardware-Konzept (Neu)
- Jedes Kind hat ein eigenes Raspberry Pi Zero W Gerät
- Pro Freund: 1 Button + 1 RGB LED (WS2812B Strip) + 1 gelbe "Selected" LED
- 1 Record-Button (rot) zum Starten/Stoppen der Aufnahme
- 1 Dialog-Button zum Umschalten des Gesprächsmodus
- USB-Mikrofon und Lautsprecher

## System-Architektur

```
┌──────────────────┐       Internet        ┌──────────────────┐
│  Raspberry Pi    │   (WebSocket/WSS)     │  Raspberry Pi    │
│  (Anna's Device) │◄─────────────────────►│  (Max's Device)  │
└─────────┬────────┘                        └─────────┬────────┘
          │                                           │
          │            WebSocket Connection           │
          │                     │                     │
          └─────────────────────▼─────────────────────┘
                         ┌──────────────┐
                         │ Relay Server │
                         │  (Railway)   │
                         │   Python     │
                         └──────────────┘
```

### Komponenten

1. **Client (Raspberry Pi)**
   - Location: `client/`
   - Hardware-Steuerung (GPIO + WS2812B LED Strip)
   - Audio-Aufnahme/-Wiedergabe
   - State Machine
   - WebSocket Client

2. **Server (Relay)**
   - Location: `server/`
   - WebSocket Server
   - Message Forwarding (keine Speicherung!)
   - Device Registry
   - Recording Status Relay
   - Deployment: Railway.app

## Datei-Struktur

```
voice_messenger_complete/
├── README.md                      # Projekt-Übersicht mit GPIO Pinout
├── DEPLOYMENT_GUIDE.md            # Deployment-Anleitung
├── PLAN-UI-REDESIGN.md            # UI Redesign Plan
├── client/                        # Raspberry Pi Software
│   ├── main.py                   # Hauptanwendung, State Machine
│   ├── hardware.py               # GPIO-Steuerung (Buttons, LEDs)
│   ├── led_strip.py              # WS2812B RGB LED Strip Control
│   ├── audio.py                  # PyAudio (Aufnahme/Wiedergabe)
│   ├── network.py                # WebSocket Client
│   ├── config.py                 # JSON-basierte Konfiguration
│   ├── setup_portal.py           # WiFi Setup Captive Portal
│   ├── wifi_manager.py           # AP/Client Mode Switching
│   ├── startup.py                # Boot Decision Logic
│   ├── templates/setup.html      # Setup Portal Web UI
│   ├── voice-messenger.service   # Systemd Service File
│   ├── install.sh                # Installations-Script
│   ├── requirements.txt          # Python Dependencies
│   ├── README.md                 # Client-Dokumentation
│   └── STATES.md                 # State Machine Details
└── server/                        # Relay Server
    ├── server.py                 # aiohttp WebSocket Server
    ├── devices.json              # Device Registry (auto-generated)
    ├── requirements.txt          # aiohttp
    ├── Procfile                  # Railway Deployment
    ├── railway.json              # Railway Config
    └── README.md                 # Server-Dokumentation
```

## State Machine (Neues Design)

### Zustände

```
┌─────────────────────────────────────────────────────────────────┐
│                         STATES                                   │
├─────────────────────────────────────────────────────────────────┤
│  IDLE          - Ruhezustand, wartet auf Eingabe                │
│  RECORDING     - Nimmt Audio für ausgewählten Freund auf        │
│  PLAYING       - Spielt Nachricht(en) ab                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    MODE FLAGS                                    │
├─────────────────────────────────────────────────────────────────┤
│  conversation_mode: bool  - Auto-Play bei neuen Nachrichten     │
│  selected_friend: str     - Aktuell ausgewählter Freund         │
└─────────────────────────────────────────────────────────────────┘
```

### State-Übergänge

```
                              ┌──────────────┐
                              │     IDLE     │
                              └──────┬───────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Record gedrückt │       │ Friend gedrückt │       │ Nachricht kommt │
│ (Freund online) │       │ (= ausgewählt)  │       │ (Gesprächsmod.) │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   RECORDING     │       │    PLAYING      │       │    PLAYING      │
│                 │       │                 │       │   (auto-play)   │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │ Record erneut           │ Wiedergabe endet        │
         │ ODER anderer Button     │ ODER anderer Button     │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Senden (Record) │       │     IDLE        │       │     IDLE        │
│ Abbruch (other) │       │                 │       │                 │
└────────┬────────┘       └─────────────────┘       └─────────────────┘
         │
         ▼
         IDLE
```

### LED-Zustände (Neu mit RGB Strip)

#### RGB LED pro Freund (WS2812B) - Prioritätsreihenfolge

| Priorität | Bedingung | Effekt |
|-----------|-----------|--------|
| 1 | Ich nehme auf für diesen Freund | Pulsierend ROT |
| 2 | Freund nimmt auf für mich | Regenbogen-Cycling |
| 3 | Neue ungehörte Nachricht | Pulsierend GRÜN |
| 4 | Nachricht gesendet, noch nicht gehört | Dauerhaft BLAU |
| 5 | Freund ist online | Dauerhaft GRÜN |
| 6 | Freund ist offline | AUS |

**Hinweis:** Keine separate Record-LED! Die RGB-LED des ausgewählten Freundes zeigt pulsierend ROT während der Aufnahme (Priorität 1).

#### Gelbe LED pro Freund (Standard GPIO)

| Bedingung | Zustand |
|-----------|---------|
| Dieser Freund ist ausgewählt | AN |
| Dieser Freund ist nicht ausgewählt | AUS |

### Button-Logik (Neu)

#### Friend Button gedrückt
```python
if state == RECORDING:
    # Aufnahme abbrechen (nicht senden)
    cancel_recording()
elif state == PLAYING:
    if friend_id == selected_friend:
        # Gleicher Freund-Button - zur VORHERIGEN Nachricht springen
        play_previous_message(friend_id)
    else:
        # Anderer Freund-Button - Wiedergabe abbrechen und wechseln
        stop_playback()
        select_friend(friend_id)
elif state == IDLE:
    if friend_id == selected_friend:
        # Bereits ausgewählt - Konversation abspielen (neueste zuerst)
        play_messages(friend_id)
    else:
        # Diesen Freund auswählen
        select_friend(friend_id)
```

#### Record Button gedrückt
```python
if state == RECORDING:
    # Aufnahme stoppen und an ausgewählten Freund senden
    # RGB LED des Freundes hört auf rot zu pulsieren
    stop_recording_and_send()
elif state == PLAYING:
    # Wiedergabe abbrechen
    stop_playback()
elif state == IDLE:
    if is_friend_online(selected_friend):
        # Aufnahme starten - RGB LED des Freundes pulsiert rot
        start_recording()
    else:
        # Alle RGB LEDs 2x rot blinken
        flash_error()
```

#### Dialog Button gedrückt
```python
conversation_mode = not conversation_mode
# Visuelles/Audio-Feedback
reset_conversation_timeout()  # 5 Minuten Timer
```

### Nachrichten-Wiedergabe

Nachrichten werden als **Konversationshistorie** pro Freund gespeichert:
- **Empfangene Nachrichten** (vom Freund)
- **Gesendete Nachrichten** (an den Freund)

Dies ermöglicht das Abspielen der gesamten Konversation in chronologischer Reihenfolge.

**Navigation während Wiedergabe:**
- **Gleicher Friend-Button** → Zur vorherigen (älteren) Nachricht springen
- **Anderer Friend-Button** → Wiedergabe abbrechen, Freund wechseln
- **Record/Dialog Button** → Wiedergabe abbrechen

### Gesprächsmodus (Conversation Mode)

- **Aktiviert:** Eingehende Nachrichten werden automatisch abgespielt
- **Während Aufnahme:** Nachricht wird in Queue gestellt, nach Senden abgespielt
- **Auto-Deaktivierung:** Nach 5 Minuten ohne neue Nachrichten

## Technische Details

### Client (Raspberry Pi)

**Dependencies:**
```
RPi.GPIO>=0.7.1           # GPIO-Steuerung
pyaudio>=0.2.13           # Audio I/O
websockets>=12.0          # WebSocket Client
rpi_ws281x>=5.0.0         # WS2812B LED Strip
adafruit-circuitpython-neopixel>=6.3.0
flask>=3.0.0              # Setup Portal
requests>=2.31.0          # HTTP Client
```

**Wichtige Klassen:**

```python
# main.py
class VoiceMessenger:
    - Hauptanwendung
    - State Machine Verwaltung
    - Callback-Handler für Hardware/Network
    - Message Queue Management
    - Conversation Mode Logic
    - Selected Friend Tracking

# hardware.py
class HardwareController:
    - GPIO Pin Management
    - Button Event Detection (Friend, Record, Dialog)
    - Yellow LED Control
    - LED Strip Integration
    - Keyboard Simulation für Testing

# led_strip.py (NEU)
class LEDStrip:
    - WS2812B Control via neopixel
    - Solid Colors
    - Pulsating Effects
    - Rainbow Cycling
    - Flash All (Error Feedback)

# audio.py
class AudioController:
    - PyAudio Wrapper
    - Recording (16kHz, Mono, WAV)
    - Playback mit Duration-Tracking
    - File Management

# network.py
class P2PNetwork:
    - WebSocket Client
    - Auto-Reconnect
    - Message Serialization (Base64)
    - Recording Status Broadcast
    - Friend Online Status

# config.py
class Config:
    - JSON-basierte Konfiguration
    - Device ID Management
    - Friend Registry
    - Hardware Pin Mapping
```

**GPIO Pin-Belegung (BCM) - Neu:**
```
Hardware Section:
  GPIO 18: LED Strip Data (WS2812B)
  GPIO 17: Record Button
  GPIO  4: Dialog Button

Per Friend:
  GPIO 22: Friend 1 Button
  GPIO 23: Friend 1 Yellow LED
  LED Index 0: Friend 1 RGB (pulsiert rot bei Aufnahme)

  GPIO 24: Friend 2 Button
  GPIO 25: Friend 2 Yellow LED
  LED Index 1: Friend 2 RGB

  # etc.

Hinweis: Keine separate Record-LED - RGB LED zeigt Aufnahmestatus
```

**Konfigurationsformat (config.json) - Neu:**
```json
{
  "device_id": "unique-uuid",
  "device_name": "Voice Messenger - Anna",
  "relay_server_url": "wss://your-server.railway.app/ws",
  "wifi_ssid": "MyWiFi",
  "wifi_password": "secret",

  "hardware": {
    "led_strip_pin": 18,
    "led_count": 3,
    "record_button_pin": 17,
    "dialog_button_pin": 4
  },

  "friends": {
    "friend_id_1": {
      "name": "Max",
      "device_id": "other-device-uuid",
      "button_pin": 22,
      "yellow_led_pin": 23,
      "led_index": 0
    },
    "friend_id_2": {
      "name": "Lisa",
      "device_id": "lisa-device-uuid",
      "button_pin": 24,
      "yellow_led_pin": 25,
      "led_index": 1
    }
  }
}
```

**Hinweis:** Keine `record_led_pin` - Aufnahmeanzeige nutzt die RGB LED des ausgewählten Freundes.

### Server (Relay)

**Dependencies:**
```
aiohttp>=3.9.0         # Async HTTP + WebSocket
```

**Hauptfunktionen:**
```python
# server.py

# WebSocket Handler
async def handle_websocket(request):
    # Manages connected devices
    # Routes messages between devices
    # Forwards recording status

# Message Types:
# 1. register           - Device registration
# 2. voice_message      - Audio forwarding
# 3. message_heard      - Read receipt
# 4. recording_started  - Recording status (NEU)
# 5. recording_stopped  - Recording status (NEU)
# 6. ping/pong          - Keep-alive

# REST API:
# GET /api/devices      - List registered devices
# GET /api/devices/{id} - Get device details
```

**Nachrichten-Protokoll:**

```python
# Registration
{
    "type": "register",
    "device_id": "uuid",
    "device_name": "Voice Messenger - Anna",
    "friends": ["friend-uuid-1", "friend-uuid-2"]
}

# Voice Message
{
    "type": "voice_message",
    "recipient_id": "friend-uuid",
    "message_id": "msg-uuid",
    "audio_data": "base64-encoded-wav",
    "timestamp": 1234567890
}

# Message Heard
{
    "type": "message_heard",
    "sender_id": "original-sender-uuid",
    "message_id": "msg-uuid"
}

# Recording Started (NEU)
{
    "type": "recording_started",
    "sender_id": "my-uuid",
    "recipient_id": "friend-uuid"
}

# Recording Stopped (NEU)
{
    "type": "recording_stopped",
    "sender_id": "my-uuid",
    "recipient_id": "friend-uuid"
}
```

## Setup Portal

Das Gerät verfügt über einen integrierten Setup-Portal für einfache Konfiguration:

### Boot-Flow
```
Boot → WiFi konfiguriert?
  ├─ JA → Verbinden → Server/Friends konfiguriert?
  │         ├─ JA → main.py starten
  │         └─ NEIN → Portal auf Port 8080
  └─ NEIN → AP-Modus ("VoiceMessenger-Setup") → Portal auf Port 80
```

### Portal-Features
1. WiFi-Netzwerk scannen und verbinden
2. Gerätename (Kindername) setzen
3. Server-URL konfigurieren
4. Freunde aus Server-Directory auswählen
5. GPIO-Pins für Buttons/LEDs zuweisen

## Entwicklungs-Workflow

### Lokale Entwicklung

**Server lokal testen:**
```bash
cd server/
pip install -r requirements.txt
python server.py
# Server läuft auf http://localhost:8080
```

**Client testen (ohne Hardware):**
```bash
cd client/
pip install -r requirements.txt
python main.py --mock
# Läuft im Simulation-Mode mit Keyboard-Steuerung
```

### Deployment

**Server (Railway):**
1. GitHub Repository erstellen (privat!)
2. Code pushen
3. Railway: "New Project" → "Deploy from GitHub"
4. URL notieren

**Client (Raspberry Pi):**
1. `rsync` zum Pi
2. venv erstellen und Dependencies installieren
3. `config.json` anpassen ODER Setup-Portal nutzen
4. systemd service aktivieren

## Wichtige Design-Entscheidungen

### 1. Warum RGB LED Strip statt einzelne LEDs?
- **Visuell:** Mehr Ausdrucksmöglichkeiten (Pulsieren, Regenbogen)
- **Verkabelung:** Nur ein Datenkabel für alle Freund-LEDs
- **Erweiterbar:** Einfach mehr Freunde hinzufügen

### 2. Warum Toggle-Recording statt Hold-to-Record?
- **Kindgerecht:** Kein langes Drücken erforderlich
- **Komfort:** Längere Nachrichten ohne Anstrengung
- **Klar:** Ein Knopf = An/Aus

### 3. Warum Freund-Auswahl vor Aufnahme?
- **Visuell:** Gelbe LED zeigt immer an, wer ausgewählt ist
- **Einfacher:** Kein Merken welcher Knopf gedrückt wird
- **Flexibler:** Auswahl kann geändert werden

### 4. Warum Conversation Mode?
- **Natürlicher:** Wie echtes Gespräch, keine manuelle Wiedergabe
- **Kindgerecht:** Weniger Buttons drücken
- **Optional:** Kann ein-/ausgeschaltet werden

### 5. Warum Recording-Status an Empfänger?
- **Feedback:** Kind sieht, dass Freund gerade aufnimmt
- **Spannend:** Regenbogen-Animation weckt Vorfreude
- **Real-time:** Gefühl der Verbundenheit

## Bekannte Limitierungen

1. **Offline Messages:** Aktuell nicht gespeichert
   - Wenn Empfänger offline: Nachricht geht verloren
   - TODO: Server könnte Queue implementieren

2. **Audio-Qualität:** 16kHz Mono
   - Ausreichend für Sprache
   - Könnte höher sein für bessere Qualität

3. **WS2812B benötigt Root:**
   - LED-Strip-Bibliothek braucht erhöhte Rechte
   - Workaround: setcap oder root-Service

## Testing-Strategie

### Hardware Tests
```bash
# LED Strip Test
python -c "from led_strip import LEDStrip; l = LEDStrip(18, 3); l.set_color(0, 255, 0, 0)"

# Button Test
python -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP); print(GPIO.input(22))"

# Audio Test
arecord -d 3 test.wav && aplay test.wav
```

### Integration Tests
1. Aufnahme starten → Empfänger sieht Regenbogen
2. Nachricht senden → Empfänger-LED pulsiert grün
3. Conversation Mode → Auto-Play funktioniert
4. Offline-Freund → Rotes Blinken bei Record

## Konventionen

### Code Style
- PEP 8 (Python Style Guide)
- Type Hints wo möglich
- Docstrings für Public Functions

### Naming
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### Logging
```python
# Immer mit Kontext
print(f"✅ Success message")
print(f"⚠️ Warning message")
print(f"❌ Error message")
print(f"📡 Network message")
print(f"🔴 Recording message")
print(f"▶️ Playback message")
print(f"🌈 LED effect message")
```

---

## Schnellreferenz für Claude Code

**Hauptdateien:**
- `client/main.py` - State Machine, Hauptlogik
- `client/hardware.py` - Buttons, Yellow LEDs
- `client/led_strip.py` - RGB LED Strip (WS2812B)
- `client/network.py` - WebSocket Client
- `server/server.py` - Relay Server

**State Machine:**
- IDLE → RECORDING → IDLE (Record Button toggle)
- IDLE → PLAYING → IDLE (Friend Button wenn ausgewählt)

**Wichtige Callbacks:**
- `on_friend_button` - Friend auswählen oder abspielen
- `on_record_button` - Aufnahme starten/stoppen
- `on_dialog_button` - Conversation Mode toggle
- `on_message_received` - Neue Nachricht
- `on_recording_status` - Freund nimmt auf (Regenbogen)

**Config:**
- `config.json` - Device-spezifische Einstellungen
- `hardware` Section für Pins
- `friends` mit led_index für RGB Strip

**LED Strip:**
- `set_color(index, r, g, b)` - Solid color
- `start_pulse(index, r, g, b)` - Pulsating
- `start_rainbow(index)` - Rainbow cycling
- `flash_all(r, g, b, times)` - Error feedback

---

**Version:** 2.0
**Letzte Aktualisierung:** 2025-01-26
**Status:** UI Redesign geplant, Implementation ausstehend
