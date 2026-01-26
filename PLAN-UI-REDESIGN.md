# Voice Messenger - New UI Redesign Plan

## Overview

Complete redesign of the user interface with new button logic, RGB LED strip (WS2812B), conversation mode, and simplified state machine.

---

## Hardware Changes

### New Button Layout
| Button | GPIO | Function |
|--------|------|----------|
| Friend 1 | configurable | Select friend / Play messages |
| Friend 2 | configurable | Select friend / Play messages |
| Friend 3 | configurable | Select friend / Play messages |
| Record | configurable | Toggle recording on/off |
| Dialog | configurable | Toggle conversation mode |

**Removed:** Back button (no longer needed)

### New LED Configuration
| LED Type | Hardware | Function |
|----------|----------|----------|
| RGB Strip | WS2812B (1 per friend) | Status indicators (see LED states below) |
| Yellow LEDs | Standard GPIO (1 per friend) | "Currently selected" indicator |

**No separate Record LED** - The RGB LED of the selected friend pulsates red during recording.

**LED Strip Wiring:** Single continuous WS2812B strip, one data pin, LEDs indexed 0, 1, 2... for friends 1, 2, 3...

---

## LED State Logic

### RGB LED (per friend) - Priority Order
| Priority | Condition | Effect |
|----------|-----------|--------|
| 1 | I am recording for this friend | Pulsating RED |
| 2 | Friend is recording for me | Rainbow cycling |
| 3 | New unheard message | Pulsating GREEN |
| 4 | Message sent, not yet heard | Solid BLUE |
| 5 | Friend is online | Solid GREEN |
| 6 | Friend is offline | OFF |

### Yellow LED (per friend)
| Condition | State |
|-----------|-------|
| This friend is currently selected | ON |
| This friend is not selected | OFF |

**Note:** No separate Record LED. The RGB LED of the selected friend shows pulsating RED during recording (Priority 1 in table above).

---

## New State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                         STATES                                   │
├─────────────────────────────────────────────────────────────────┤
│  IDLE          - Default state, waiting for input               │
│  RECORDING     - Recording audio for selected friend            │
│  PLAYING       - Playing back message(s)                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    MODE FLAGS                                    │
├─────────────────────────────────────────────────────────────────┤
│  conversation_mode: bool  - Auto-play incoming messages         │
│  selected_friend: str     - Currently selected friend ID        │
└─────────────────────────────────────────────────────────────────┘
```

### State Transitions

```
                              ┌──────────────┐
                              │     IDLE     │
                              └──────┬───────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Record pressed  │       │ Friend pressed  │       │ Message arrives │
│ (friend online) │       │ (same as sel.)  │       │ (conv. mode)    │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   RECORDING     │       │    PLAYING      │       │    PLAYING      │
│                 │       │                 │       │   (auto-play)   │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │ Record pressed          │ Playback ends           │ Playback ends
         │ OR any other button     │ OR other button         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Send (if Record)│       │     IDLE        │       │     IDLE        │
│ Cancel (if other│       │                 │       │                 │
└────────┬────────┘       └─────────────────┘       └─────────────────┘
         │
         ▼
┌─────────────────┐
│     IDLE        │
└─────────────────┘
```

---

## Button Logic (Detailed)

### Friend Button Press
```python
if state == RECORDING:
    # Cancel recording (don't send)
    cancel_recording()
elif state == PLAYING:
    if friend_id == selected_friend:
        # Same friend button - go to PREVIOUS message in conversation
        play_previous_message(friend_id)
    else:
        # Different friend button - cancel playback and switch
        stop_playback()
        select_friend(friend_id)
elif state == IDLE:
    if friend_id == selected_friend:
        # Already selected - start playing conversation (most recent first)
        play_messages(friend_id)
    else:
        # Select this friend
        select_friend(friend_id)
```

### Record Button Press
```python
if state == RECORDING:
    # Stop recording and send to selected friend
    # RGB LED of selected friend stops pulsating red
    stop_recording_and_send()
elif state == PLAYING:
    # Cancel playback (Record button = cancel during playback)
    stop_playback()
elif state == IDLE:
    if is_friend_online(selected_friend):
        # Start recording - RGB LED of selected friend pulsates red
        start_recording()
    else:
        # Flash all RGB LEDs red 2 times
        flash_error()
```

### Dialog Button Press
```python
conversation_mode = not conversation_mode
# Visual/audio feedback
if conversation_mode:
    # Maybe play a short tone or flash LEDs
    pass
# Reset conversation timeout
reset_conversation_timeout()
```

---

## Message Playback Logic

### Conversation History
Messages are stored as a **conversation history** per friend, including:
- **Received messages** (from friend)
- **Sent messages** (to friend)

This allows replaying the entire conversation in chronological order.

### When friend button pressed (and already selected):
1. Start playing the **most recent message** (sent or received)
2. Each subsequent press of same button → play **previous (older) message**
3. Continue until all messages in conversation played
4. When oldest message reached → cycle back to most recent

### During playback:
- **Same friend button** → Skip to previous message (navigate back through history)
- **Different friend button** → Cancel playback, switch to that friend
- **Record button** → Cancel playback
- **Dialog button** → Cancel playback, toggle conversation mode

### Message Display Priority (newest first):
```
[Most Recent]
  ↑ Friend button press
[Older Message]
  ↑ Friend button press
[Even Older]
  ↑ Friend button press
[Oldest Message]
  ↑ Friend button press (cycles back to most recent)
```

---

## Conversation Mode

### Behavior:
- When enabled: incoming messages auto-play immediately
- If recording when message arrives:
  1. Continue recording until Record pressed
  2. Send message
  3. Auto-play the received message
- Auto-disable after 5 minutes of no incoming messages

### Implementation:
```python
conversation_mode: bool = False
conversation_timeout: float = None  # timestamp when to auto-disable

def on_message_received(friend_id, message):
    if conversation_mode:
        conversation_timeout = time.time() + 300  # Reset 5-min timer
        if state == RECORDING:
            pending_autoplay = message  # Queue for after send
        else:
            auto_play_message(message)
```

---

## Network Protocol Changes

### New Message Types

**Recording Started (client → server → recipient):**
```json
{
  "type": "recording_started",
  "sender_id": "device-123",
  "recipient_id": "device-456"
}
```

**Recording Stopped (client → server → recipient):**
```json
{
  "type": "recording_stopped",
  "sender_id": "device-123",
  "recipient_id": "device-456"
}
```

### Server Changes:
- Forward `recording_started` and `recording_stopped` to specific recipient
- Track online status (already exists)

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `client/led_strip.py` | **NEW** | WS2812B control with neopixel library |
| `client/hardware.py` | **REWRITE** | New button logic, LED integration |
| `client/main.py` | **REWRITE** | New state machine, conversation mode |
| `client/network.py` | **MODIFY** | Add recording status messages |
| `client/config.py` | **MODIFY** | New config structure for LEDs |
| `server/server.py` | **MODIFY** | Forward recording status messages |
| `client/requirements.txt` | **MODIFY** | Add rpi_ws281x, adafruit-circuitpython-neopixel |

---

## New Config Structure

```json
{
  "device_id": "emma-device-001",
  "device_name": "Emma",
  "relay_server_url": "wss://server.example.com/ws",
  "wifi_ssid": "...",
  "wifi_password": "...",

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

**Note:** No `record_led_pin` - recording indicator uses the RGB LED of the selected friend.

---

## New Module: led_strip.py

### Class: LEDStrip
```python
class LEDStrip:
    def __init__(self, pin: int, count: int)

    # Set specific LED to solid color
    def set_color(self, index: int, r: int, g: int, b: int)

    # Start pulsating effect (runs in thread)
    def start_pulse(self, index: int, r: int, g: int, b: int)

    # Start rainbow cycling effect (runs in thread)
    def start_rainbow(self, index: int)

    # Stop any animation on LED
    def stop_animation(self, index: int)

    # Turn off LED
    def off(self, index: int)

    # Flash all LEDs (for error feedback)
    def flash_all(self, r: int, g: int, b: int, times: int = 2)

    # Cleanup
    def cleanup(self)
```

### Color Constants
```python
COLOR_OFF = (0, 0, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_RED = (255, 0, 0)
```

---

## Implementation Order

### Phase 1: LED Strip Module
1. Create `led_strip.py` with WS2812B support
2. Implement solid colors, pulsing, rainbow effects
3. Add mock mode for development without hardware
4. Test independently

### Phase 2: Hardware Controller Rewrite
1. Remove back button support
2. Add Record button and Dialog button handling
3. Integrate LED strip module
4. Add yellow LED control
5. Update keyboard simulation for new buttons

### Phase 3: State Machine Rewrite
1. Implement new State enum (IDLE, RECORDING, PLAYING)
2. Add conversation_mode flag and timeout logic
3. Implement new button handlers
4. Implement message playback cycling logic
5. Add selected_friend tracking

### Phase 4: Network Updates
1. Add recording_started/stopped message types
2. Update server to forward these messages
3. Handle incoming recording status on client
4. Update LED states based on friend recording status

### Phase 5: Config & Integration
1. Update config.py for new structure
2. Update setup portal for new hardware config
3. Integration testing
4. Update README

---

## Verification Plan

### Unit Tests
1. LED strip effects (pulse, rainbow) work correctly
2. State transitions are correct
3. Button logic follows specification
4. Conversation mode timeout works

### Integration Tests
1. Send message → recipient sees rainbow while recording
2. Conversation mode auto-plays incoming messages
3. Recording during conversation mode queues playback
4. Offline friend → flash red on record attempt
5. Friend selection persists correctly
6. Conversation replay includes both sent and received messages
7. Friend button during playback → plays previous message
8. Other button during playback → cancels playback
9. RGB LED pulsates red during recording (no separate LED)

### Hardware Tests
1. WS2812B strip responds to all colors/effects
2. Yellow LEDs turn on/off correctly
3. All buttons register presses
4. Audio recording/playback still works

---

## Dependencies

### New Python Packages
```
rpi_ws281x>=5.0.0
adafruit-circuitpython-neopixel>=6.3.0
```

### System Requirements (Pi)
```bash
# Already should be available, but verify:
sudo apt install -y python3-dev
```

---

## Notes

- Keep existing audio.py mostly unchanged
- Keep existing network.py WebSocket logic, just add new message types
- Setup portal will need updates for new config structure (Phase 5)
- Conversation mode is a "nice to have" - core functionality first
