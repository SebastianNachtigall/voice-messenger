# Voice Messenger - Komplett-Paket

🎙️ Peer-to-Peer Voice Messenger für Kinder mit Raspberry Pi Zero W

## 📦 Was ist enthalten?

```
voice_messenger_complete/
├── DEPLOYMENT_GUIDE.md    ← START HIER! Komplette Anleitung
├── client/                 ← Raspberry Pi Software
│   ├── main.py
│   ├── hardware.py
│   ├── audio.py
│   ├── network.py
│   ├── config.py
│   ├── install.sh
│   ├── requirements.txt
│   ├── README.md
│   └── STATES.md
└── server/                 ← Relay-Server für Railway
    ├── server.py
    ├── requirements.txt
    ├── Procfile
    ├── railway.json
    └── README.md
```

## 🚀 Quick Start

### 1. Server deployen (5 Minuten)

```bash
cd server/
git init && git add . && git commit -m "Initial commit"
# Push zu GitHub (privates Repo!)
# Deploy auf Railway → URL notieren
```

### 2. Raspberry Pi einrichten (15 Minuten pro Gerät)

```bash
# client/ auf den Pi kopieren
cd client/
./install.sh

# config.json anpassen:
# - relay_server_url mit Railway-URL
# - device_id (einzigartig pro Gerät!)
# - friends mit anderen device_ids

python3 main.py
```

### 3. Testen 🎉

- Nachricht aufnehmen (2 Sek. halten)
- Auf anderem Gerät sollte LED grün blinken
- Abspielen (kurz drücken)

## 📖 Dokumentation

**Hauptanleitung:** `DEPLOYMENT_GUIDE.md` ← Lese das zuerst!

**Weitere Docs:**
- `client/README.md` - Client-Details
- `client/STATES.md` - State Machine Dokumentation
- `server/README.md` - Server-Details

## ✨ Features

✅ **Keine monatlichen Kosten** - Railway Free Tier
✅ **Kein Backend** - Server speichert keine Daten
✅ **Internet-fähig** - Kinder können in verschiedenen Häusern sein
✅ **Einfache Bedienung** - Nur Knöpfe und LEDs
✅ **Auto-Reconnect** - Verbindung wird automatisch wiederhergestellt
✅ **State Machine** - Robustes Zustandsmanagement

## 🎯 Hardware

**Pro Gerät benötigt:**
- Raspberry Pi Zero W
- USB-Mikrofon
- Lautsprecher (3.5mm oder USB)
- 1x BACK Button
- 1x rote LED (Aufnahme)
- 1-5x Freund-Buttons mit grüner LED

## 💡 Support

Bei Problemen:
1. Lies `DEPLOYMENT_GUIDE.md`
2. Prüfe Railway Logs
3. Prüfe Pi Logs: `sudo journalctl -u voice-messenger -f`

## 📝 Lizenz

Privates Projekt - Keine öffentliche Lizenz

---

**Erstellt mit ❤️ für Kinder**
