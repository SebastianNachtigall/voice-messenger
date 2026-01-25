"""
Hardware Controller - GPIO management for buttons and LEDs
"""

import threading
import time
from typing import Callable, Optional

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("⚠️ RPi.GPIO not available, running in simulation mode")
    GPIO_AVAILABLE = False


class HardwareController:
    """Manages GPIO pins for buttons and LEDs"""
    
    def __init__(self, config):
        self.config = config
        self.running = False
        self.monitor_thread = None
        
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
        
        if GPIO_AVAILABLE:
            self.setup_gpio()
        else:
            print("🔧 Hardware controller in simulation mode")
    
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
    
    def start(self):
        """Start monitoring buttons"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ Hardware monitoring started")
    
    def stop(self):
        """Stop monitoring and cleanup"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
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
    
    def set_friend_led(self, friend_id: str, state: str):
        """
        Set LED state for a friend
        States: 'off', 'on', 'blinking', 'sent' (blue)
        """
        if not GPIO_AVAILABLE:
            return
        
        friend_config = self.config.friends.get(friend_id)
        if not friend_config:
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
        if not GPIO_AVAILABLE:
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
