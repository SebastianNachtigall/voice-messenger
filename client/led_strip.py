"""
LED Strip Controller - WS2812B (NeoPixel) addressable RGB LED strip
One LED per friend for status indication. Supports solid colors, pulsing, and rainbow effects.
Falls back to simulation mode when hardware is not available.
"""

import threading
import time
import math
from typing import Optional, Tuple

try:
    import board
    import neopixel
    NEOPIXEL_AVAILABLE = True
except ImportError:
    NEOPIXEL_AVAILABLE = False

# Color constants
COLOR_OFF = (0, 0, 0)
COLOR_RED = (255, 0, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_WHITE = (255, 255, 255)

# GPIO to board pin mapping (use GPIO 10/SPI to avoid I2S conflict on GPIO 18)
GPIO_TO_BOARD = {
    10: board.D10 if NEOPIXEL_AVAILABLE else None,
    12: board.D12 if NEOPIXEL_AVAILABLE else None,
    18: board.D18 if NEOPIXEL_AVAILABLE else None,
    21: board.D21 if NEOPIXEL_AVAILABLE else None,
}


class LEDStrip:
    """Controls a WS2812B (NeoPixel) addressable RGB LED strip"""

    def __init__(self, pin: int, count: int, brightness: float = 0.3):
        self.pin = pin
        self.count = count
        self.brightness = brightness
        self.pixels = None
        self.running = True

        # Animation state per LED
        self._animations: dict = {}  # {index: threading.Event} for stopping
        self._animation_threads: dict = {}  # {index: threading.Thread}
        self._current_state: dict = {}  # {index: state_name} for logging
        self._lock = threading.Lock()

        if NEOPIXEL_AVAILABLE:
            board_pin = GPIO_TO_BOARD.get(pin)
            if board_pin is None:
                print(f"Warning: GPIO {pin} not mapped for NeoPixel, using D10 (SPI)")
                board_pin = board.D10
            try:
                self.pixels = neopixel.NeoPixel(
                    board_pin, count,
                    brightness=brightness,
                    auto_write=True,
                    pixel_order=neopixel.GRB
                )
                self.pixels.fill(COLOR_OFF)
                print(f"RGB LED strip initialized: {count} LEDs on GPIO {pin}")
            except Exception as e:
                print(f"Failed to initialize NeoPixel: {e}")
                self.pixels = None
        else:
            print("NeoPixel not available, LED strip in simulation mode")

    def _log_state(self, index: int, state: str):
        """Log LED state change only if it changed"""
        if self._current_state.get(index) != state:
            self._current_state[index] = state
            if not self.pixels:
                print(f"  💡 LED[{index}]: {state}")

    def set_color(self, index: int, r: int, g: int, b: int):
        """Set a specific LED to a solid color, stopping any animation"""
        self._stop_animation(index)
        self._log_state(index, f"solid {self._color_name(r, g, b)}")
        self._set_pixel(index, r, g, b)

    def start_pulse(self, index: int, r: int, g: int, b: int):
        """Start pulsating effect on an LED (runs in background thread)"""
        self._stop_animation(index)
        self._log_state(index, f"pulse {self._color_name(r, g, b)}")
        stop_event = threading.Event()
        self._animations[index] = stop_event
        thread = threading.Thread(
            target=self._pulse_loop,
            args=(index, r, g, b, stop_event),
            daemon=True
        )
        self._animation_threads[index] = thread
        thread.start()

    def start_rainbow(self, index: int):
        """Start rainbow cycling effect on an LED (runs in background thread)"""
        self._stop_animation(index)
        self._log_state(index, "rainbow")
        stop_event = threading.Event()
        self._animations[index] = stop_event
        thread = threading.Thread(
            target=self._rainbow_loop,
            args=(index, stop_event),
            daemon=True
        )
        self._animation_threads[index] = thread
        thread.start()

    def stop_animation(self, index: int):
        """Stop any animation on an LED and turn it off"""
        self._stop_animation(index)
        self._log_state(index, "OFF")
        self._set_pixel(index, 0, 0, 0)

    def off(self, index: int):
        """Turn off an LED"""
        self._stop_animation(index)
        self._log_state(index, "OFF")
        self._set_pixel(index, 0, 0, 0)

    def flash_all(self, r: int, g: int, b: int, times: int = 2):
        """Flash all LEDs a color (blocking). Used for error feedback."""
        for _ in range(times):
            for i in range(self.count):
                self._set_pixel(i, r, g, b)
            time.sleep(0.2)
            for i in range(self.count):
                self._set_pixel(i, 0, 0, 0)
            time.sleep(0.2)

    def cleanup(self):
        """Stop all animations and turn off all LEDs"""
        self.running = False
        for index in list(self._animations.keys()):
            self._stop_animation(index)
        if self.pixels:
            self.pixels.fill(COLOR_OFF)
        print("RGB LED strip cleaned up")

    # --- Internal methods ---

    def _set_pixel(self, index: int, r: int, g: int, b: int):
        """Set a single pixel color"""
        if index < 0 or index >= self.count:
            return
        if self.pixels:
            with self._lock:
                self.pixels[index] = (r, g, b)

    def _stop_animation(self, index: int):
        """Signal an animation thread to stop and wait for it"""
        if index in self._animations:
            self._animations[index].set()
            del self._animations[index]
        if index in self._animation_threads:
            thread = self._animation_threads[index]
            if thread.is_alive():
                thread.join(timeout=1.0)
            del self._animation_threads[index]

    def _pulse_loop(self, index: int, r: int, g: int, b: int, stop_event: threading.Event):
        """Pulsating effect: smoothly fades brightness up and down"""
        step = 0
        while not stop_event.is_set() and self.running:
            # Sine wave for smooth pulsing, range 0.1 to 1.0
            brightness = 0.1 + 0.9 * (0.5 + 0.5 * math.sin(step * 0.1))
            pr = int(r * brightness)
            pg = int(g * brightness)
            pb = int(b * brightness)
            self._set_pixel(index, pr, pg, pb)
            step += 1
            stop_event.wait(0.05)  # ~20fps

        # Turn off when done
        if self.running:
            self._set_pixel(index, 0, 0, 0)

    def _rainbow_loop(self, index: int, stop_event: threading.Event):
        """Rainbow cycling effect: cycles through hue spectrum"""
        hue = 0
        while not stop_event.is_set() and self.running:
            r, g, b = self._hsv_to_rgb(hue / 360.0, 1.0, 1.0)
            self._set_pixel(index, r, g, b)
            hue = (hue + 3) % 360
            stop_event.wait(0.05)  # ~20fps

        if self.running:
            self._set_pixel(index, 0, 0, 0)

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
        """Convert HSV (0-1 range) to RGB (0-255 range)"""
        if s == 0.0:
            val = int(v * 255)
            return (val, val, val)
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = int(255 * v * (1.0 - s))
        q = int(255 * v * (1.0 - s * f))
        t = int(255 * v * (1.0 - s * (1.0 - f)))
        v = int(255 * v)
        i = i % 6
        if i == 0: return (v, t, p)
        if i == 1: return (q, v, p)
        if i == 2: return (p, v, t)
        if i == 3: return (p, q, v)
        if i == 4: return (t, p, v)
        if i == 5: return (v, p, q)
        return (0, 0, 0)

    @staticmethod
    def _color_name(r: int, g: int, b: int) -> str:
        """Human-readable color name for simulation output"""
        if r == 0 and g == 0 and b == 0:
            return "OFF"
        if r > 200 and g < 50 and b < 50:
            return "RED"
        if r < 50 and g > 200 and b < 50:
            return "GREEN"
        if r < 50 and g < 50 and b > 200:
            return "BLUE"
        return f"RGB"
