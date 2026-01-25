# Voice Messenger - System States & LED Codes

## System States (State Machine)

```
┌─────────────────────────────────────────────────────────────┐
│                        IDLE (Bereit)                        │
│  - Keine Aktion läuft                                       │
│  - Wartet auf Knopfdruck                                    │
└───────────┬─────────────────────────────────┬───────────────┘
            │                                 │
    Kurzer Klick                      Langer Klick (2 Sek.)
            │                                 │
            ▼                                 ▼
┌───────────────────────┐          ┌──────────────────────────┐
│   PLAYING             │          │  RECORDING_HOLD          │
│  - Spielt Nachrichten │          │  - Timer läuft           │
│  - Auto-weiter bei    │          │  - Noch keine Aufnahme   │
│    mehreren Messages  │          └────────┬─────────────────┘
└───────┬───────────────┘                   │
        │                              Nach 2 Sek.
  Alle gehört                                │
   oder Abbruch                              ▼
        │                          ┌──────────────────────────┐
        │                          │   RECORDING              │
        │                          │  - Aufnahme läuft        │
        │                          │  - Rote LED blinkt       │
        │                          └────────┬─────────────────┘
        │                                   │
        │                            Button loslassen
        │                                   │
        └───────────────────────────────────┴──────────────────┐
                                                                │
                                                                ▼
                                                        Zurück zu IDLE
```

## LED-Zustände (Pro Freund-Knopf)

### 🟢 Grün Blinkend - Neue Nachricht(en)
```
Status: Ungelesene Nachricht(en) vorhanden
Priorität: HÖCHSTE (überschreibt alle anderen Zustände)
Aktion: Kurz drücken zum Abhören
```

### 🟢 Grün Durchgehend - Wiedergabe
```
Status: Nachricht wird abgespielt
System State: PLAYING
Aktion: Nochmal drücken = Abbrechen
        BACK = Vorherige Nachricht
```

### 🔵 Blau Durchgehend - Nachricht Gesendet
```
Status: Warte auf Bestätigung vom Empfänger
Dauer: Bis Empfänger abhört (~5 Sek. Simulation)
Wird überschrieben durch: Neue eingehende Nachricht (→ Grün Blinkend)
```

### ⚪ Aus/Grau - Ruhezustand
```
Status: Keine neuen Nachrichten, keine gesendeten Nachrichten
Standard-Zustand
```

## Zentrale Aufnahme-LED (Rot)

### 🔴 Rot Blinkend - Aufnahme aktiv
```
System State: RECORDING
Frequenz: Schnelles Blinken (4x pro Sekunde)
```

### ⚪ Aus - Keine Aufnahme
```
Alle anderen States
```

## State-Übergänge

| Von State | Zu State | Trigger |
|-----------|----------|---------|
| IDLE | PLAYING | Kurzer Klick auf Freund-Button |
| IDLE | RECORDING_HOLD | Long Press Start (2 Sek. halten) |
| RECORDING_HOLD | RECORDING | Timer abgelaufen (nach 2 Sek.) |
| RECORDING_HOLD | IDLE | Maus/Finger verlässt Button |
| RECORDING | IDLE | Button loslassen (= Senden) |
| RECORDING | IDLE | BACK drücken (= Abbrechen) |
| PLAYING | IDLE | Alle Nachrichten abgespielt |
| PLAYING | IDLE | Button klicken (= Abbrechen) |
| PLAYING | PLAYING | Auto-weiter zur nächsten Nachricht |

## Verhalten während verschiedener States

### Während IDLE ✅
- ✅ Freund-Knopf kurz → Nachrichten abspielen
- ✅ Freund-Knopf lang → Aufnahme starten
- ✅ BACK → Keine Aktion (ignoriert)

### Während RECORDING 🔴
- ✅ Gleicher Freund-Knopf loslassen → Aufnahme stoppen & senden
- ❌ Anderer Freund-Knopf → Ignoriert (nur aktiver Button funktioniert)
- ✅ BACK → Aufnahme abbrechen

### Während RECORDING_HOLD ⏱️
- ✅ Button loslassen vor 2 Sek. → Abbruch (zurück zu IDLE)
- ✅ Button halten 2 Sek. → Wechsel zu RECORDING
- ❌ Anderer Freund-Knopf → Ignoriert

### Während PLAYING ▶️
- ✅ Gleicher Freund-Knopf → Wiedergabe stoppen
- ❌ Anderer Freund-Knopf → Ignoriert (nur aktiver Button funktioniert)
- ✅ BACK → Vorherige Nachricht abspielen
- ✅ Auto-weiter → Nächste ungehörte Nachricht

## Beispiel-Ablauf

### Nachricht senden
```
1. IDLE → Freund-Button 2 Sek. halten
2. RECORDING_HOLD → Nach 2 Sek. automatisch → RECORDING
3. Rote LED blinkt 🔴
4. Sprechen...
5. Button loslassen
6. RECORDING → IDLE
7. Freund-LED wechselt zu Blau 🔵
8. Nach ~5 Sek: Empfänger hört ab
9. LED erlischt ⚪
```

### Nachricht abhören
```
1. IDLE, Freund-LED blinkt grün 🟢
2. Kurz auf Freund-Button klicken
3. IDLE → PLAYING
4. LED wechselt zu Grün durchgehend 🟢
5. Nachricht 1 wird abgespielt
6. Auto-weiter zu Nachricht 2
7. Nachricht 2 wird abgespielt
8. Keine weiteren Nachrichten
9. PLAYING → IDLE
10. LED erlischt ⚪
```

## Netzwerk-Protokoll

### Device Discovery (UDP Broadcast)
```json
{
  "type": "presence",
  "device_id": "uuid",
  "device_name": "Voice Messenger - Anna",
  "port": 5556
}
```

### Voice Message (TCP)
```
Header (JSON):
{
  "type": "voice_message",
  "sender_id": "uuid",
  "message_id": "msg-uuid",
  "file_size": 12345,
  "timestamp": 1234567890
}

Body: Raw WAV file bytes
```

### Message Heard Notification (TCP)
```json
{
  "type": "message_heard",
  "listener_id": "uuid",
  "message_id": "msg-uuid"
}
```
