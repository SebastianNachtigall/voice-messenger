"""
Hardware Controller - GPIO management for buttons and LEDs
New UI: Record button, Dialog button, Friend buttons, Yellow LEDs, WS2812B LED strip.
Supports keyboard input for testing when GPIO is not available.
"""

import threading
import time
import sys
import select
from typing import Callable, Optional, Dict

from led_strip import LEDStrip

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# Try to import termios for keyboard input (Unix/Linux/macOS)
try:
    import termios
    import tty
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


class HardwareController:
    """Manages GPIO pins for buttons and LEDs (new UI layout)"""

    def __init__(self, config, keyboard_enabled: bool = True):
        self.config = config
        self.running = False
        self.monitor_thread = None
        self.keyboard_thread = None
        self.keyboard_enabled = keyboard_enabled and KEYBOARD_AVAILABLE

        # Callbacks
        self.on_friend_button: Optional[Callable] = None   # (friend_id)
        self.on_record_button: Optional[Callable] = None    # ()
        self.on_dialog_button: Optional[Callable] = None    # ()

        # Button debounce tracking
        self._last_press_time: Dict[str, float] = {}
        self._debounce_ms = 300

        # Keyboard state
        self.old_terminal_settings = None
        self.key_to_friend: Dict[str, str] = {}

        # LED strip
        self.led_strip = LEDStrip(
            pin=config.led_strip_pin,
            count=config.led_count
        )

        # Yellow LED states
        self._yellow_led_states: Dict[str, bool] = {}

        if GPIO_AVAILABLE:
            self._setup_gpio()
        else:
            print("Hardware controller in simulation mode")

        if self.keyboard_enabled:
            self._setup_keyboard_mapping()
            print("Keyboard input enabled")
            print("  Keys: 1-9 = friend buttons, r = record, d = dialog, q = quit")

    def _setup_gpio(self):
        """Initialize GPIO pins"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Record button with pull-up
        GPIO.setup(self.config.record_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Dialog button with pull-up
        GPIO.setup(self.config.dialog_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Friend buttons (yellow LEDs now handled by LED strip)
        for friend_id, friend_config in self.config.friends.items():
            button_pin = friend_config['button_pin']
            GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        print("GPIO initialized")

    def _setup_keyboard_mapping(self):
        """Map number keys to friend IDs"""
        friends = list(self.config.friends.keys())
        for i, friend_id in enumerate(friends):
            if i < 9:
                key = str(i + 1)
                self.key_to_friend[key] = friend_id
                friend_name = self.config.friends[friend_id].get('name', friend_id)
                print(f"  Key '{key}' = {friend_name}")

    def start(self):
        """Start monitoring buttons (GPIO and/or keyboard)"""
        self.running = True

        if GPIO_AVAILABLE:
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("GPIO monitoring started")

        if self.keyboard_enabled:
            self.keyboard_thread = threading.Thread(target=self._keyboard_loop, daemon=True)
            self.keyboard_thread.start()
            print("Keyboard monitoring started")

    def stop(self):
        """Stop monitoring and cleanup"""
        self.running = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

        if self.keyboard_thread:
            self.keyboard_thread.join(timeout=1.0)

        # Restore terminal settings
        if self.old_terminal_settings and KEYBOARD_AVAILABLE:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
            except:
                pass

        # Cleanup LED strip
        self.led_strip.cleanup()

        if GPIO_AVAILABLE:
            GPIO.cleanup()
        print("Hardware stopped")

    # --- GPIO Monitoring ---

    def _monitor_loop(self):
        """Monitor button states via GPIO polling"""
        if not GPIO_AVAILABLE:
            return

        last_record_state = GPIO.HIGH
        last_dialog_state = GPIO.HIGH
        last_friend_states: Dict[str, int] = {}

        for friend_id in self.config.friends:
            last_friend_states[friend_id] = GPIO.HIGH

        while self.running:
            now = time.time()

            # Check Record button (press only, not release)
            record_state = GPIO.input(self.config.record_button_pin)
            if record_state == GPIO.LOW and last_record_state == GPIO.HIGH:
                if self._debounce('record', now):
                    if self.on_record_button:
                        self.on_record_button()
            last_record_state = record_state

            # Check Dialog button
            dialog_state = GPIO.input(self.config.dialog_button_pin)
            if dialog_state == GPIO.LOW and last_dialog_state == GPIO.HIGH:
                if self._debounce('dialog', now):
                    if self.on_dialog_button:
                        self.on_dialog_button()
            last_dialog_state = dialog_state

            # Check Friend buttons
            for friend_id, friend_config in self.config.friends.items():
                button_pin = friend_config['button_pin']
                current_state = GPIO.input(button_pin)
                last_state = last_friend_states.get(friend_id, GPIO.HIGH)

                if current_state == GPIO.LOW and last_state == GPIO.HIGH:
                    if self._debounce(friend_id, now):
                        if self.on_friend_button:
                            self.on_friend_button(friend_id)

                last_friend_states[friend_id] = current_state

            time.sleep(0.05)  # 50ms poll rate

    def _debounce(self, key: str, now: float) -> bool:
        """Returns True if enough time has passed since last press"""
        last = self._last_press_time.get(key, 0)
        if (now - last) * 1000 >= self._debounce_ms:
            self._last_press_time[key] = now
            return True
        return False

    # --- Keyboard Monitoring ---

    def _keyboard_loop(self):
        """Monitor keyboard input for button simulation"""
        if not KEYBOARD_AVAILABLE:
            return

        try:
            self.old_terminal_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except Exception as e:
            print(f"Could not set terminal to raw mode: {e}")
            return

        print("\nKeyboard control active. Press keys to simulate buttons.\n")

        try:
            while self.running:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).lower()

                    now = time.time()

                    if key == 'q':
                        print("\nQuit requested via keyboard")
                        self.running = False
                        break

                    elif key == 'r':
                        if self._debounce('record_kb', now):
                            print("[RECORD] button pressed")
                            if self.on_record_button:
                                self.on_record_button()

                    elif key == 'd':
                        if self._debounce('dialog_kb', now):
                            print("[DIALOG] button pressed")
                            if self.on_dialog_button:
                                self.on_dialog_button()

                    elif key in self.key_to_friend:
                        friend_id = self.key_to_friend[key]
                        if self._debounce(f'kb_{friend_id}', now):
                            friend_name = self.config.friends[friend_id].get('name', friend_id)
                            print(f"[{friend_name}] button pressed")
                            if self.on_friend_button:
                                self.on_friend_button(friend_id)

        except Exception as e:
            print(f"Keyboard monitor error: {e}")
        finally:
            if self.old_terminal_settings:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
                except:
                    pass

    # --- Yellow LED Control (now uses LED strip) ---

    def set_yellow_led(self, friend_id: str, on: bool):
        """Turn a friend's selection LED on or off (using LED strip)"""
        friend_config = self.config.friends.get(friend_id)
        if not friend_config:
            return

        selection_led_index = friend_config.get('selection_led_index')
        self._yellow_led_states[friend_id] = on

        if selection_led_index is not None:
            if on:
                # Yellow color for selection
                self.led_strip.set_color(selection_led_index, 255, 180, 0)
            else:
                self.led_strip.off(selection_led_index)
        else:
            # Fallback to GPIO if configured (legacy support)
            yellow_led_pin = friend_config.get('yellow_led_pin')
            if GPIO_AVAILABLE and yellow_led_pin is not None:
                GPIO.output(yellow_led_pin, GPIO.HIGH if on else GPIO.LOW)

    def set_all_yellow_leds_off(self):
        """Turn off all yellow LEDs"""
        for friend_id in self.config.friends:
            self.set_yellow_led(friend_id, False)
