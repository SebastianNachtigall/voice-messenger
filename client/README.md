# Voice Messenger - Raspberry Pi Zero

Ein Peer-to-Peer Voice-Message System für Kinder ohne Backend-Server.

## Features

✅ **Kein Server benötigt** - Direkte Gerät-zu-Gerät Kommunikation
✅ **Einfache Bedienung** - Nur Knöpfe und LEDs
✅ **State Machine** - Robustes Zustandsmanagement
✅ **Audio Aufnahme/Wiedergabe** - Voice Messages
✅ **Automatisches Device Discovery** - Geräte finden sich im lokalen Netzwerk
✅ **LED Feedback** - Grün blinkend (neue Nachricht), Blau (gesendet), Grün solid (spielt ab)

## Hardware Requirements

- Raspberry Pi Zero W (mit WiFi)
- Mikrofon (USB oder I2S)
- Lautsprecher/Kopfhörer (3.5mm oder USB)
- Buttons mit LED (ein Button pro Freund + 1 BACK Button)
- Separate rote LED für Aufnahme-Anzeige

## Installation

### 1. System vorbereiten

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev portaudio19-dev
```

### 2. Dependencies installieren

```bash
pip3 install -r requirements.txt
```

### 3. Audio testen

```bash
# Mikrofon testen
arecord -l

# Lautsprecher testen
aplay -l

# Test-Aufnahme
arecord -d 5 test.wav
aplay test.wav
```

## Konfiguration

### config.json erstellen

Beispiel-Konfiguration generieren:

```bash
python3 config.py
```

Das erstellt eine `config.json` mit folgendem Format:

```json
{
  "device_id": "unique-device-uuid",
  "device_name": "Voice Messenger - Anna",
  "wifi_ssid": "MyWiFi",
  "wifi_password": "password123",
  "back_button_pin": 17,
  "record_led_pin": 27,
  "friends": {
    "friend1": {
      "name": "Max",
      "device_id": "device-uuid-max",
      "button_pin": 22,
      "led_pin": 23
    },
    "friend2": {
      "name": "Lisa",
      "device_id": "device-uuid-lisa",
      "button_pin": 24,
      "led_pin": 25
    }
  }
}
```

### GPIO Pin-Belegung

Standard-Pins (BCM Nummerierung):

- **BACK Button**: GPIO 17
- **Record LED**: GPIO 27
- **Friend 1 Button**: GPIO 22, LED: GPIO 23
- **Friend 2 Button**: GPIO 24, LED: GPIO 25
- etc.

Anpassen in `config.json` nach Bedarf.

## Verwendung

### App starten

```bash
python3 main.py
```

### Auto-Start beim Boot (systemd)

1. Service-File erstellen:

```bash
sudo nano /etc/systemd/system/voice-messenger.service
```

2. Inhalt:

```ini
[Unit]
Description=Voice Messenger
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/voice_messenger
ExecStart=/usr/bin/python3 /home/pi/voice_messenger/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

3. Service aktivieren:

```bash
sudo systemctl enable voice-messenger
sudo systemctl start voice-messenger
```

4. Status prüfen:

```bash
sudo systemctl status voice-messenger
```

## Bedienung

### Nachrichten abhören
- **Kurz** auf Freund-Knopf drücken → Spielt alle neuen Nachrichten ab

### Nachricht senden
- **Lang** (2 Sek.) auf Freund-Knopf halten → Aufnahme startet
- **Loslassen** → Nachricht wird gesendet

### Navigation
- **BACK** während Wiedergabe → Vorherige Nachricht

### LED-Status

| LED-Zustand | Bedeutung |
|-------------|-----------|
| 🟢 Blinkend | Neue Nachricht(en) |
| 🟢 Durchgehend | Wiedergabe läuft |
| 🔵 Durchgehend | Nachricht gesendet (wartet auf Bestätigung) |
| ⚪ Aus | Keine Aktivität |
| 🔴 Blinkend | Aufnahme aktiv |

## Netzwerk

### Peer-to-Peer Kommunikation

Die App nutzt:
- **UDP Broadcasting** (Port 5555) für Device Discovery
- **TCP** (Port 5556) für Message Transfer

Alle Geräte müssen im **gleichen WiFi-Netzwerk** sein!

### Firewall

Falls Firewall aktiv, Ports freigeben:

```bash
sudo ufw allow 5555/udp
sudo ufw allow 5556/tcp
```

## Troubleshooting

### Kein Audio

```bash
# Audio-Geräte anzeigen
aplay -l
arecord -l

# ALSA-Konfiguration prüfen
alsamixer
```

### GPIO-Fehler

```bash
# GPIO-Zugriff prüfen
sudo usermod -a -G gpio pi
```

### Netzwerk-Probleme

```bash
# Geräte im Netzwerk finden
sudo nmap -sn 192.168.1.0/24

# Ports prüfen
sudo netstat -tulpn | grep 555
```

### Logs anzeigen

```bash
# Systemd logs
sudo journalctl -u voice-messenger -f
```

## Nächste Schritte

- [ ] Web-Interface für Konfiguration (später)
- [ ] WiFi-Setup per Access Point Modus
- [ ] Mehr Freunde unterstützen (5-10)
- [ ] Audio-Kompression für kleinere Dateien
- [ ] Offline-Message-Queue

## Architektur

```
main.py              - Hauptanwendung mit State Machine
hardware.py          - GPIO/Button/LED Steuerung
audio.py            - Audio Aufnahme/Wiedergabe
network.py          - P2P Kommunikation
config.py           - Konfigurationsverwaltung
```

## Sicherheit

⚠️ **Wichtig**: 
- Geräte nur in vertrauenswürdigen Netzwerken betreiben
- Keine Verschlüsselung implementiert (für Kinder-Projekt OK)
- Zugriff über Firewall beschränken

## Lizenz

Privates Projekt - Keine öffentliche Lizenz
