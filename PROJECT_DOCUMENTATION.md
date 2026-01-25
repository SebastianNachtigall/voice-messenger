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

### Hardware-Konzept
- Jedes Kind hat ein eigenes Raspberry Pi Zero W Gerät
- Pro Freund: 1 Button mit integrierter LED
- 1 zentraler BACK-Button
- 1 zentrale rote Aufnahme-LED
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
   - Hardware-Steuerung (GPIO)
   - Audio-Aufnahme/-Wiedergabe
   - State Machine
   - WebSocket Client

2. **Server (Relay)**
   - Location: `server/`
   - WebSocket Server
   - Message Forwarding (keine Speicherung!)
   - Device Registry
   - Deployment: Railway.app

## Datei-Struktur

```
voice_messenger_complete/
├── README.md                      # Projekt-Übersicht
├── DEPLOYMENT_GUIDE.md            # Deployment-Anleitung
├── client/                        # Raspberry Pi Software
│   ├── main.py                   # Hauptanwendung, State Machine
│   ├── hardware.py               # GPIO-Steuerung (Buttons, LEDs)
│   ├── audio.py                  # PyAudio (Aufnahme/Wiedergabe)
│   ├── network.py                # WebSocket Client
│   ├── config.py                 # JSON-basierte Konfiguration
│   ├── install.sh                # Installations-Script
│   ├── requirements.txt          # Python Dependencies
│   ├── README.md                 # Client-Dokumentation
│   └── STATES.md                 # State Machine Details
└── server/                        # Relay Server
    ├── server.py                 # aiohttp WebSocket Server
    ├── requirements.txt          # aiohttp
    ├── Procfile                  # Railway Deployment
    ├── railway.json              # Railway Config
    └── README.md                 # Server-Dokumentation
```

## State Machine (Kern des Systems)

### Zustände

```
IDLE (Ruhezustand)
  │
  ├─→ Kurzer Klick ──→ PLAYING (Nachricht abspielen)
  │                      │
  │                      └─→ Alle gehört ──→ IDLE
  │
  └─→ Langer Klick (2s) ──→ RECORDING_HOLD
                              │
                              └─→ 2s vergangen ──→ RECORDING
                                                    │
                                                    └─→ Button los ──→ IDLE
```

### LED-Zustände

| LED-Zustand | Bedeutung | Trigger |
|-------------|-----------|---------|
| 🟢 Blinkend | Neue Nachricht(en) | Incoming message |
| 🟢 Dauerhaft | Wiedergabe läuft | State: PLAYING |
| 🔵 Dauerhaft | Nachricht gesendet | After recording |
| 🔴 Blinkend | Aufnahme aktiv | State: RECORDING |
| ⚪ Aus | Keine Aktivität | State: IDLE |

### Wichtige State-Übergänge

```python
# main.py - Zentrale State Machine
class State(Enum):
    IDLE = "IDLE"
    PLAYING = "PLAYING"
    RECORDING_HOLD = "RECORDING_HOLD"
    RECORDING = "RECORDING"

# Transitions
IDLE → PLAYING:          Kurzer Button-Klick
IDLE → RECORDING_HOLD:   Long-Press Start (2s Timer)
RECORDING_HOLD → RECORDING: Timer abgelaufen
RECORDING → IDLE:        Button Release (sendet Nachricht)
PLAYING → IDLE:          Alle Nachrichten abgespielt
```

## Technische Details

### Client (Raspberry Pi)

**Dependencies:**
```
RPi.GPIO>=0.7.1        # GPIO-Steuerung
pyaudio>=0.2.13        # Audio I/O
websockets>=12.0       # WebSocket Client
```

**Wichtige Klassen:**

```python
# main.py
class VoiceMessenger:
    - Hauptanwendung
    - State Machine Verwaltung
    - Callback-Handler für Hardware/Network
    - Message Queue Management

# hardware.py
class HardwareController:
    - GPIO Pin Management
    - Button Event Detection (Press/Release)
    - LED Control (On/Off/Blinking)
    - Separate Threads für Monitoring

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
    - Asyncio Event Loop in Thread

# config.py
class Config:
    - JSON-basierte Konfiguration
    - Device ID Management
    - Friend Registry
    - GPIO Pin Mapping
```

**GPIO Pin-Belegung (BCM):**
```
GPIO 17: BACK Button
GPIO 27: Record LED (rot)
GPIO 22: Friend 1 Button
GPIO 23: Friend 1 LED (grün)
GPIO 24: Friend 2 Button
GPIO 25: Friend 2 LED (grün)
# etc.
```

**Konfigurationsformat (config.json):**
```json
{
  "device_id": "unique-uuid",
  "device_name": "Voice Messenger - Anna",
  "relay_server_url": "wss://your-server.railway.app/ws",
  "back_button_pin": 17,
  "record_led_pin": 27,
  "friends": {
    "friend_id_1": {
      "name": "Max",
      "device_id": "other-device-uuid",
      "button_pin": 22,
      "led_pin": 23
    }
  }
}
```

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
    # Managed connected devices
    # Routes messages between devices
    
# Message Types:
# 1. register      - Device registration
# 2. voice_message - Audio forwarding
# 3. message_heard - Read receipt
# 4. ping/pong     - Keep-alive
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
```

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
python main.py
# Läuft im Simulation-Mode wenn RPi.GPIO nicht verfügbar
```

### Deployment

**Server (Railway):**
1. GitHub Repository erstellen (privat!)
2. Code pushen
3. Railway: "New Project" → "Deploy from GitHub"
4. URL notieren

**Client (Raspberry Pi):**
1. `client/` auf Pi kopieren
2. `./install.sh` ausführen
3. `config.json` anpassen
4. `python3 main.py` oder systemd service

## Wichtige Design-Entscheidungen

### 1. Warum WebSocket statt direktes P2P?
- **Problem:** Kinder sind in verschiedenen Häusern/Netzwerken
- **Lösung:** Relay-Server im Internet
- **Vorteil:** Funktioniert hinter NAT/Firewall

### 2. Warum keine Datenspeicherung?
- **Privacy:** Keine Audio-Daten auf Server
- **Einfachheit:** Weniger Code, weniger Fehlerquellen
- **Kosten:** Kein Database-Hosting nötig

### 3. Warum State Machine?
- **Robustheit:** Klare Zustandsübergänge
- **Debugging:** Nachvollziehbar was passiert
- **Erweiterbar:** Neue States einfach hinzufügbar

### 4. Warum Base64 für Audio?
- **WebSocket:** JSON-Messages
- **Einfachheit:** Keine separate File-Upload-Logik
- **Größe:** Audio-Files sind klein (16kHz, kurz)

### 5. Warum Asyncio + Threading Mix?
- **Network:** Asyncio für WebSocket (sauber)
- **Hardware:** Threading für GPIO (blocking I/O)
- **Audio:** PyAudio hat eigene Callbacks

## Bekannte Limitierungen

1. **Offline Messages:** Aktuell nicht gespeichert
   - Wenn Empfänger offline: Nachricht geht verloren
   - TODO: Server könnte Queue implementieren

2. **Audio-Qualität:** 16kHz Mono
   - Ausreichend für Sprache
   - Könnte höher sein für bessere Qualität

3. **Security:** Keine Verschlüsselung
   - TLS/WSS schützt Transport
   - Audio-Inhalt ist nicht verschlüsselt
   - OK für Kinder-Projekt

4. **Authentifizierung:** Nur device_id
   - Jeder mit der UUID kann sich als Gerät ausgeben
   - TODO: Token-basierte Auth

5. **Rate Limiting:** Nicht implementiert
   - Server könnte missbraucht werden
   - TODO: Limits pro Device

## Häufige Entwicklungs-Tasks

### Neuen Freund hinzufügen
```python
# config.py
config.add_friend(
    name="Lisa",
    device_id="lisa-device-uuid",
    button_pin=26,
    led_pin=19
)
```

### State Machine erweitern
```python
# main.py
class State(Enum):
    # Neuen State hinzufügen
    NEW_STATE = "NEW_STATE"

# In set_state() neue Transitions definieren
# In handle_button_release() neue Actions
```

### Neue Message Types
```python
# server.py - handle_message()
elif msg_type == 'new_message_type':
    await handle_new_message_type(data)

# network.py - handle_message()
elif msg_type == 'new_message_type':
    self.handle_new_message_type_sync(data)
```

## Testing-Strategie

### Unit Tests (TODO)
- State Machine Transitions
- Audio File Handling
- Config Validation

### Integration Tests (TODO)
- WebSocket Connection
- Message Flow End-to-End

### Hardware Tests
```bash
# GPIO Test
python -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(22, GPIO.IN); print(GPIO.input(22))"

# Audio Test
arecord -d 3 test.wav && aplay test.wav
```

## Troubleshooting

### Client startet nicht
```bash
# Logs prüfen
sudo journalctl -u voice-messenger -f

# Dependencies prüfen
pip list | grep -E "(RPi.GPIO|pyaudio|websockets)"

# GPIO Permissions
sudo usermod -a -G gpio pi
```

### Server-Verbindung schlägt fehl
```bash
# WebSocket testen
pip install websocket-client
python -c "import websocket; ws = websocket.create_connection('wss://your-url/ws'); print(ws.recv())"

# Railway Logs
railway logs
```

### Audio funktioniert nicht
```bash
# Devices anzeigen
arecord -l
aplay -l

# Volume prüfen
alsamixer

# Test-Aufnahme
arecord -d 3 -f cd test.wav
```

## Erweiterungs-Ideen

### Kurzfristig
- [ ] Offline Message Queue (Server speichert bis zu 10 Messages)
- [ ] Battery Status LED
- [ ] Message Counter (wie viele neue Messages)

### Mittelfristig
- [ ] Web-Interface für Konfiguration
- [ ] Gruppen-Nachrichten (an mehrere Freunde gleichzeitig)
- [ ] Message-Löschung durch langes Drücken

### Langfristig
- [ ] End-to-End Verschlüsselung
- [ ] Eltern-Dashboard (Monitoring ohne Inhalte)
- [ ] Audio-Kompression (Opus statt WAV)

## Git-Workflow

```bash
# Feature Branch
git checkout -b feature/neue-funktion

# Entwicklung
# ... Code ändern ...

# Commit
git add .
git commit -m "feat: Beschreibung der Änderung"

# Push
git push origin feature/neue-funktion

# Deployment (Server)
git checkout main
git merge feature/neue-funktion
git push origin main
# Railway deployt automatisch!

# Update auf Pi
scp -r client/ pi@raspberrypi.local:~/voice_messenger
ssh pi@raspberrypi.local "sudo systemctl restart voice-messenger"
```

## Wichtige Code-Patterns

### 1. Callback Pattern
```python
# main.py registriert Callbacks
self.hardware.on_button_press = self.handle_button_press
self.network.on_message_received = self.handle_message_received
```

### 2. Threading mit Locks
```python
# main.py
with self.state_lock:
    old_state = self.state
    self.state = new_state
```

### 3. Asyncio in Thread
```python
# network.py
def run_websocket_client(self):
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.loop)
    self.loop.run_until_complete(self.websocket_handler())
```

### 4. LED Blinking mit Threading
```python
# hardware.py
def blink_led(self, friend_id: str, led_pin: int):
    while self.led_states.get(friend_id) == 'blinking':
        GPIO.output(led_pin, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(led_pin, GPIO.LOW)
        time.sleep(0.5)
```

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
```

## Performance-Überlegungen

### Client
- **GPIO Polling:** 50ms ist OK (20Hz)
- **Audio Buffer:** 1024 frames = ~64ms Latenz
- **WebSocket:** Async, blockiert nicht

### Server
- **Memory:** ~10MB pro Client-Verbindung
- **CPU:** Minimal (nur forwarding)
- **Bandwidth:** ~50KB pro Message (Base64 WAV)

### Skalierung
- Railway Free Tier: ~100 gleichzeitige Connections
- Für 5-10 Kinder: Kein Problem
- Für 100+ Kinder: Upgrade oder Load Balancer

## Sicherheits-Checkliste

- [ ] HTTPS/WSS aktiviert (Railway: automatisch ✓)
- [ ] device_ids sind UUIDs (nicht vorhersagbar ✓)
- [ ] Keine Passwörter im Code
- [ ] Private GitHub Repos
- [ ] Railway Logs nicht öffentlich
- [ ] Audio-Dateien haben Permissions 600
- [ ] Systemd läuft als User, nicht root

---

## Schnellreferenz für Claude Code

**Hauptdateien:**
- `client/main.py` - State Machine, Hauptlogik
- `client/network.py` - WebSocket Client
- `server/server.py` - Relay Server

**State Machine:**
- IDLE → PLAYING → IDLE
- IDLE → RECORDING_HOLD → RECORDING → IDLE

**Wichtige Callbacks:**
- `on_button_press/release` - Hardware Events
- `on_message_received` - Neue Nachricht
- `on_message_heard` - Read Receipt

**Config:**
- `config.json` - Device-spezifische Einstellungen
- Jedes Gerät braucht unique device_id
- Friends-Liste mit anderen device_ids

**Deployment:**
- Server: GitHub → Railway (automatisch)
- Client: SCP/USB → Pi → systemd

---

**Version:** 1.0  
**Letzte Aktualisierung:** 2025-01-25  
**Status:** Production Ready
