# Voice Messenger - Komplette Deployment-Anleitung

## Übersicht

Dieses System besteht aus zwei Teilen:
1. **Server** (server/) - Relay-Server für Railway
2. **Client** (client/) - Raspberry Pi Software

## Teil 1: Relay-Server auf Railway

### Schritt 1: GitHub Repository erstellen

```bash
cd server/
git init
git add .
git commit -m "Voice Messenger Relay Server"
```

Erstelle ein **privates** Repository auf GitHub und pushe:
```bash
git remote add origin https://github.com/DEIN_USERNAME/voice-relay.git
git push -u origin main
```

### Schritt 2: Railway Deployment

1. Gehe zu https://railway.app
2. Login mit GitHub
3. "New Project" → "Deploy from GitHub repo"
4. Wähle dein Repository
5. Railway deployt automatisch!

### Schritt 3: URL notieren

Nach Deployment:
- Settings → Domains → "Generate Domain"
- Notiere die URL, z.B.: `voice-relay-prod.up.railway.app`

Deine WebSocket-URL ist dann:
```
wss://voice-relay-prod.up.railway.app/ws
```

## Teil 2: Raspberry Pi Setup

### Hardware Anforderungen

- Raspberry Pi Zero W (mit WiFi)
- USB-Mikrofon oder I2S Mikrofon
- Lautsprecher (3.5mm oder USB)
- Buttons + LEDs (siehe Schaltplan unten)

### Schaltplan

```
BACK Button: GPIO 17 → GND
Record LED:  GPIO 27 → 220Ω → LED → GND

Friend 1 Button: GPIO 22 → GND
Friend 1 LED:    GPIO 23 → 220Ω → LED → GND

Friend 2 Button: GPIO 24 → GND
Friend 2 LED:    GPIO 25 → 220Ω → LED → GND
```

### Installation

1. **Raspberry Pi OS installieren**
   - Raspberry Pi OS Lite (64-bit)
   - SSH aktivieren
   - WiFi konfigurieren

2. **System aktualisieren**
```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

3. **Voice Messenger kopieren**
```bash
# Client-Ordner auf den Pi kopieren (via USB oder SCP)
scp -r client/ pi@raspberrypi.local:~/voice_messenger
```

4. **Installation**
```bash
cd ~/voice_messenger
chmod +x install.sh
./install.sh
```

### Konfiguration

Bearbeite `config.json`:

```json
{
  "device_id": "aaaaaaaa-1111-1111-1111-111111111111",
  "device_name": "Voice Messenger - Anna",
  "relay_server_url": "wss://DEINE-RAILWAY-URL.up.railway.app/ws",
  "back_button_pin": 17,
  "record_led_pin": 27,
  "friends": {
    "max": {
      "name": "Max",
      "device_id": "bbbbbbbb-2222-2222-2222-222222222222",
      "button_pin": 22,
      "led_pin": 23
    }
  }
}
```

**WICHTIG:**
- Jedes Gerät braucht eine **einzigartige** `device_id`
- Setze die Railway-URL als `relay_server_url`
- In `friends` trägst du die device_id der **anderen** Geräte ein

### Starten

```bash
# Test (manuell)
python3 main.py

# Als Service (Auto-Start)
sudo systemctl start voice-messenger
sudo systemctl enable voice-messenger
```

## Teil 3: Mehrere Geräte verbinden

### Device IDs koordinieren

**Gerät 1 (Anna):**
```json
{
  "device_id": "aaaaaaaa-1111-1111-1111-111111111111",
  "friends": {
    "max": {
      "device_id": "bbbbbbbb-2222-2222-2222-222222222222",
      ...
    }
  }
}
```

**Gerät 2 (Max):**
```json
{
  "device_id": "bbbbbbbb-2222-2222-2222-222222222222",
  "friends": {
    "anna": {
      "device_id": "aaaaaaaa-1111-1111-1111-111111111111",
      ...
    }
  }
}
```

### Test

1. Starte beide Geräte
2. Prüfe Railway Logs: `railway logs`
3. Du solltest sehen: "2 devices online"
4. Test: Nachricht von Anna an Max senden

## Troubleshooting

### Server-Probleme

```bash
# Railway Logs
railway logs

# Status prüfen
curl https://DEINE-URL.up.railway.app/status
```

### Pi-Probleme

```bash
# Service Status
sudo systemctl status voice-messenger

# Logs
sudo journalctl -u voice-messenger -f

# Manuell starten
cd ~/voice_messenger
python3 main.py
```

### Häufige Fehler

**"Connection refused"**
- Prüfe `relay_server_url` in config.json
- Muss `wss://` sein, nicht `ws://`!

**"No audio device"**
```bash
arecord -l  # Mikrofone anzeigen
aplay -l    # Lautsprecher anzeigen
```

**"Device not registering"**
- Prüfe Internet-Verbindung
- Prüfe Railway Server läuft
- Prüfe Logs auf beiden Seiten

## LED-Status

| LED | Bedeutung |
|-----|-----------|
| 🟢 Blinkend | Neue Nachricht |
| 🟢 Dauerhaft | Wiedergabe läuft |
| 🔵 Dauerhaft | Nachricht gesendet |
| 🔴 Blinkend | Aufnahme aktiv |
| ⚪ Aus | Keine Aktivität |

## Bedienung

- **Kurz drücken** auf Freund-Button → Nachrichten abhören
- **2 Sekunden halten** → Aufnahme starten
- **BACK während Wiedergabe** → Vorherige Nachricht

## Kosten

**Railway Free Tier:**
- 500 Stunden/Monat (24/7 möglich)
- 100GB Traffic
- Für 5-10 Kinder ausreichend
- Kostenlos!

## Support

Bei Problemen:
1. Prüfe Railway Logs
2. Prüfe Pi Logs
3. Teste Netzwerk-Verbindung
4. Prüfe config.json Syntax

---

🎉 **Viel Spaß mit dem Voice Messenger!**
