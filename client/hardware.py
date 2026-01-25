"""
Hardware Controller - GPIO management for buttons and LEDs
Supports keyboard input for testing when GPIO is not available or buttons aren't wired.
"""

import threading
import time
import sys
import select
from typing import Callable, Optional

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("⚠️ RPi.GPIO not available, running in simulation mode")
    GPIO_AVAILABLE = False

# Try to import termios for keyboard input (Unix/Linux/macOS)
try:
    import termios
    import tty
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


class HardwareController:
    """Manages GPIO pins for buttons and LEDs"""
    
    def __init__(self, config, keyboard_enabled: bool = True):
        self.config = config
        self.running = False
        self.monitor_thread = None
        self.keyboard_thread = None
        self.keyboard_enabled = keyboard_enabled and KEYBOARD_AVAILABLE

        # Callbacks
        self.on_button_press: Optional[Callable] = None
        self.on_button_release: Optional[Callable] = None
        self.on_back_button: Optional[Callable] = None

        # Button states
        self.button_states = {}
        self.button_press_times = {}

        # LED states
        self.led_states = {}
        self.led_blink_threads = {}

        # Keyboard state tracking
        self.keyboard_held_button: Optional[str] = None
        self.old_terminal_settings = None

        # Map keyboard keys to friend IDs (will be populated from config)
        self.key_to_friend = {}

        if GPIO_AVAILABLE:
            self.setup_gpio()
        else:
            print("🔧 Hardware controller in simulation mode")

        if self.keyboard_enabled:
            self.setup_keyboard_mapping()
            print("⌨️  Keyboard input enabled")
            print("   Keys: 1-9 = friend buttons (hold to record, release to send)")
            print("   Press key = button press, release key = button release")
            print("   'b' = back button, 'q' = quit")
    
    def setup_gpio(self):
        """Initialize GPIO pins"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup friend buttons and LEDs
        for friend_id, friend_config in self.config.friends.items():
            button_pin = friend_config['button_pin']
            led_pin = friend_config['led_pin']
            
            # Setup button with pull-up resistor
            GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.button_states[friend_id] = GPIO.HIGH
            
            # Setup LED
            GPIO.setup(led_pin, GPIO.OUT)
            GPIO.output(led_pin, GPIO.LOW)
            self.led_states[friend_id] = 'off'
        
        # Setup BACK button
        GPIO.setup(self.config.back_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Setup record LED
        GPIO.setup(self.config.record_led_pin, GPIO.OUT)
        GPIO.output(self.config.record_led_pin, GPIO.LOW)
        
        print("✅ GPIO initialized")

    def setup_keyboard_mapping(self):
        """Map number keys to friend IDs"""
        friends = list(self.config.friends.keys())
        for i, friend_id in enumerate(friends):
            if i < 9:  # Keys 1-9
                key = str(i + 1)
                self.key_to_friend[key] = friend_id
                friend_name = self.config.friends[friend_id].get('name', friend_id)
                print(f"   Key '{key}' = {friend_name}")

    def start(self):
        """Start monitoring buttons (GPIO and/or keyboard)"""
        self.running = True

        if GPIO_AVAILABLE:
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("✅ GPIO monitoring started")

        if self.keyboard_enabled:
            self.keyboard_thread = threading.Thread(target=self.keyboard_monitor_loop, daemon=True)
            self.keyboard_thread.start()
            print("✅ Keyboard monitoring started")
    
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

        # Stop all blinking threads
        for thread in self.led_blink_threads.values():
            if thread and thread.is_alive():
                thread.join(timeout=0.5)

        if GPIO_AVAILABLE:
            GPIO.cleanup()
        print("✅ Hardware stopped")
    
    def monitor_loop(self):
        """Monitor button states"""
        if not GPIO_AVAILABLE:
            return
        
        last_back_state = GPIO.HIGH
        
        while self.running:
            # Check friend buttons
            for friend_id, friend_config in self.config.friends.items():
                button_pin = friend_config['button_pin']
                current_state = GPIO.input(button_pin)
                last_state = self.button_states.get(friend_id, GPIO.HIGH)
                
                # Button pressed (LOW because of pull-up)
                if current_state == GPIO.LOW and last_state == GPIO.HIGH:
                    self.button_press_times[friend_id] = time.time()
                    if self.on_button_press:
                        self.on_button_press(friend_id)
                
                # Button released
                elif current_state == GPIO.HIGH and last_state == GPIO.LOW:
                    if self.on_button_release:
                        self.on_button_release(friend_id)
                    self.button_press_times.pop(friend_id, None)
                
                self.button_states[friend_id] = current_state
            
            # Check BACK button
            back_state = GPIO.input(self.config.back_button_pin)
            if back_state == GPIO.LOW and last_back_state == GPIO.HIGH:
                if self.on_back_button:
                    self.on_back_button()
            last_back_state = back_state
            
            time.sleep(0.05)  # 50ms poll rate

    def keyboard_monitor_loop(self):
        """Monitor keyboard input for button simulation"""
        if not KEYBOARD_AVAILABLE:
            return

        # Save and modify terminal settings for raw input
        try:
            self.old_terminal_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except Exception as e:
            print(f"⚠️ Could not set terminal to raw mode: {e}")
            return

        print("\n🎮 Keyboard control active. Press keys to simulate buttons.\n")

        try:
            while self.running:
                # Check if input is available (non-blocking)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).lower()

                    if key == 'q':
                        print("\n🛑 Quit requested via keyboard")
                        self.running = False
                        break

                    elif key == 'b':
                        # Back button
                        print("⏪ [BACK] button pressed")
                        if self.on_back_button:
                            self.on_back_button()

                    elif key in self.key_to_friend:
                        friend_id = self.key_to_friend[key]
                        friend_name = self.config.friends[friend_id].get('name', friend_id)

                        if self.keyboard_held_button == friend_id:
                            # Release the button
                            print(f"🔼 [{friend_name}] button RELEASED")
                            self.keyboard_held_button = None
                            if self.on_button_release:
                                self.on_button_release(friend_id)
                        else:
                            # If another button was held, release it first
                            if self.keyboard_held_button:
                                old_friend = self.keyboard_held_button
                                old_name = self.config.friends[old_friend].get('name', old_friend)
                                print(f"🔼 [{old_name}] button RELEASED (switching)")
                                if self.on_button_release:
                                    self.on_button_release(old_friend)

                            # Press the new button
                            print(f"🔽 [{friend_name}] button PRESSED (press again to release)")
                            self.keyboard_held_button = friend_id
                            self.button_press_times[friend_id] = time.time()
                            if self.on_button_press:
                                self.on_button_press(friend_id)

                    elif key == ' ' or key == '\n':
                        # Space or Enter releases any held button
                        if self.keyboard_held_button:
                            friend_id = self.keyboard_held_button
                            friend_name = self.config.friends[friend_id].get('name', friend_id)
                            print(f"🔼 [{friend_name}] button RELEASED")
                            self.keyboard_held_button = None
                            if self.on_button_release:
                                self.on_button_release(friend_id)

        except Exception as e:
            print(f"⚠️ Keyboard monitor error: {e}")
        finally:
            # Restore terminal settings
            if self.old_terminal_settings:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
                except:
                    pass

    def set_friend_led(self, friend_id: str, state: str):
        """
        Set LED state for a friend
        States: 'off', 'on', 'blinking', 'sent' (blue)
        """
        friend_config = self.config.friends.get(friend_id)
        if not friend_config:
            return

        friend_name = friend_config.get('name', friend_id)

        # Visual feedback in simulation mode
        if not GPIO_AVAILABLE:
            led_icons = {'off': '⚫', 'on': '🟢', 'blinking': '🟢💫', 'sent': '🔵'}
            icon = led_icons.get(state, '❓')
            print(f"💡 LED [{friend_name}]: {icon} {state}")
            self.led_states[friend_id] = state
            return

        led_pin = friend_config['led_pin']
        
        # Stop existing blink thread if any
        if friend_id in self.led_blink_threads:
            thread = self.led_blink_threads[friend_id]
            if thread and thread.is_alive():
                self.led_states[friend_id] = 'off'  # Signal thread to stop
                thread.join(timeout=0.5)
        
        self.led_states[friend_id] = state
        
        if state == 'off':
            GPIO.output(led_pin, GPIO.LOW)
        elif state == 'on':
            GPIO.output(led_pin, GPIO.HIGH)
        elif state == 'sent':
            # Blue LED (for RGB LEDs, or just solid for single color)
            # For now, treat as solid on
            GPIO.output(led_pin, GPIO.HIGH)
        elif state == 'blinking':
            # Start blink thread
            thread = threading.Thread(
                target=self.blink_led,
                args=(friend_id, led_pin),
                daemon=True
            )
            self.led_blink_threads[friend_id] = thread
            thread.start()
    
    def blink_led(self, friend_id: str, led_pin: int):
        """Blink LED in separate thread"""
        while self.led_states.get(friend_id) == 'blinking' and self.running:
            GPIO.output(led_pin, GPIO.HIGH)
            time.sleep(0.5)
            GPIO.output(led_pin, GPIO.LOW)
            time.sleep(0.5)
        
        # Ensure LED is off when stopping
        GPIO.output(led_pin, GPIO.LOW)
    
    def set_record_led(self, blinking: bool):
        """Set record LED state"""
        # Visual feedback in simulation mode
        if not GPIO_AVAILABLE:
            if blinking:
                print("🔴 RECORD LED: blinking (recording active)")
            else:
                print("⚫ RECORD LED: off")
            self.led_states['record'] = 'blinking' if blinking else 'off'
            return

        if blinking:
            # Start blink thread for record LED
            if 'record' not in self.led_blink_threads or \
               not self.led_blink_threads['record'].is_alive():
                self.led_states['record'] = 'blinking'
                thread = threading.Thread(
                    target=self.blink_record_led,
                    daemon=True
                )
                self.led_blink_threads['record'] = thread
                thread.start()
        else:
            self.led_states['record'] = 'off'
            if 'record' in self.led_blink_threads:
                thread = self.led_blink_threads['record']
                if thread and thread.is_alive():
                    thread.join(timeout=0.5)
            GPIO.output(self.config.record_led_pin, GPIO.LOW)
    
    def blink_record_led(self):
        """Blink record LED in separate thread"""
        while self.led_states.get('record') == 'blinking' and self.running:
            GPIO.output(self.config.record_led_pin, GPIO.HIGH)
            time.sleep(0.25)  # Faster blink for recording
            GPIO.output(self.config.record_led_pin, GPIO.LOW)
            time.sleep(0.25)
        
        # Ensure LED is off when stopping
        GPIO.output(self.config.record_led_pin, GPIO.LOW)
