# Voice Messenger Relay Server

Minimaler WebSocket Relay-Server für Voice Messenger.

## Railway Deployment

1. Repository erstellen und pushen
2. Railway: New Project → Deploy from GitHub
3. URL notieren für Raspberry Pi Config

## WebSocket URL

```
wss://your-app.up.railway.app/ws
```

## Endpoints

- GET / - Status-Seite
- GET /status - JSON Status
- GET /ws - WebSocket

## Features

- Echtzeit Message Relay
- Keine Datenspeicherung
- Auto-Reconnect Support
- Delivery Confirmations

Siehe voice_messenger/DEPLOYMENT.md für Details.
