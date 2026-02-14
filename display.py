"""LED matrix rendering via Pillow + rgbmatrix (double-buffered)."""

import logging
import time

from PIL import Image, ImageDraw, ImageFont

import config
from flight_data import FlightState
from flight_processor import (
    format_altitude,
    format_distance,
    format_heading,
    format_route,
    format_speed,
    format_vertical_rate,
)

logger = logging.getLogger(__name__)

# Total display dimensions
DISPLAY_WIDTH = config.MATRIX_COLS * config.MATRIX_CHAIN  # 128
DISPLAY_HEIGHT = config.MATRIX_ROWS  # 32
ROW_HEIGHT = 8  # pixels per text row
MAX_CHARS = DISPLAY_WIDTH // 5  # 25 chars at 5px wide


def _load_font() -> ImageFont.ImageFont:
    """Load a small bitmap/TTF font suitable for 5x8 rendering."""
    # Try the BDF font shipped with rpi-rgb-led-matrix
    bdf_paths = [
        "/usr/local/share/fonts/5x8.bdf",
        "/home/pi/rpi-rgb-led-matrix/fonts/5x8.bdf",
        "/opt/rpi-rgb-led-matrix/fonts/5x8.bdf",
    ]
    for path in bdf_paths:
        try:
            return ImageFont.load(path)
        except (OSError, IOError):
            continue

    # Fallback: small TTF
    ttf_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for path in ttf_paths:
        try:
            return ImageFont.truetype(path, 8)
        except (OSError, IOError):
            continue

    logger.warning("No suitable font found, using Pillow default")
    return ImageFont.load_default()


class FlightDisplay:
    def __init__(self):
        self._matrix = None
        self._canvas = None
        self._font = _load_font()
        self._current_index = 0
        self._last_cycle_time = 0.0
        self._init_matrix()

    def _init_matrix(self) -> None:
        """Initialize the RGB matrix hardware."""
        try:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions

            options = RGBMatrixOptions()
            options.rows = config.MATRIX_ROWS
            options.cols = config.MATRIX_COLS
            options.chain_length = config.MATRIX_CHAIN
            options.hardware_mapping = config.HARDWARE_MAPPING
            options.gpio_slowdown = config.GPIO_SLOWDOWN
            options.brightness = config.BRIGHTNESS
            options.pwm_bits = config.PWM_BITS
            options.drop_privileges = False

            self._matrix = RGBMatrix(options=options)
            self._canvas = self._matrix.CreateFrameCanvas()
            logger.info("RGB matrix initialized (%dx%d)", DISPLAY_WIDTH, DISPLAY_HEIGHT)
        except ImportError:
            logger.warning("rgbmatrix not available — running in headless mode")
        except Exception as e:
            logger.error("Failed to initialize matrix: %s", e)

    def _render_to_image(self, lines: list[tuple]) -> Image.Image:
        """Render up to 4 lines of colored text to a Pillow Image.

        Each element is (left, color) or (left, color, right).
        When *right* is present and non-empty, it is drawn right-aligned.
        """
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        for i, entry in enumerate(lines[:4]):
            y = i * ROW_HEIGHT
            if len(entry) == 3:
                left, color, right = entry
            else:
                left, color = entry
                right = ""
            draw.text((0, y), left[:MAX_CHARS], font=self._font, fill=color)
            if right:
                right = right[:MAX_CHARS]
                rx = DISPLAY_WIDTH - draw.textlength(right, font=self._font)
                draw.text((rx, y), right, font=self._font, fill=color)
        return img

    def _show_image(self, img: Image.Image) -> None:
        """Push a Pillow Image to the matrix (double-buffered)."""
        if self._matrix is None:
            return
        self._canvas.SetImage(img)
        self._canvas = self._matrix.SwapOnVSync(self._canvas)

    def show_status(self, message: str) -> None:
        """Display a single centered status message."""
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Center vertically (row 1 of 4)
        draw.text((0, ROW_HEIGHT), message[:MAX_CHARS], font=self._font, fill=config.COLOR_STATUS)
        self._show_image(img)

    def show_flight(self, flight: FlightState, index: int, total: int) -> None:
        """Render one flight's info across 4 rows (left + right aligned)."""
        # Row 0: callsign + type (left), registration (right)
        callsign = flight.callsign or flight.icao24
        atype = flight.aircraft_type
        left0 = f"{callsign} {atype}" if atype else callsign
        right0 = flight.registration or ""

        # Row 1: altitude + speed (left), vertical rate (right)
        alt = format_altitude(flight.baro_altitude)
        spd = format_speed(flight.velocity)
        left1 = f"{alt} {spd}"
        right1 = format_vertical_rate(flight.vertical_rate)

        # Row 2: route (left), heading (right)
        left2 = format_route(flight.origin_airport, flight.dest_airport)
        right2 = format_heading(flight.true_track)

        # Row 3: distance (left), position + country (right)
        left3 = format_distance(flight.distance_km)
        pos = f"[{index + 1}/{total}]"
        country = flight.origin_country[:2].upper() if flight.origin_country else ""
        right3 = f"{pos} {country}" if country else pos

        lines = [
            (left0, config.COLOR_CALLSIGN, right0),
            (left1, config.COLOR_DATA, right1),
            (left2, config.COLOR_ROUTE, right2),
            (left3, config.COLOR_DISTANCE, right3),
        ]
        img = self._render_to_image(lines)
        self._show_image(img)

    def cycle_flights(self, flights: list[FlightState]) -> None:
        """Advance to next flight if interval elapsed, then render."""
        now = time.monotonic()

        if not flights:
            self.show_status("No flights nearby")
            self._current_index = 0
            self._last_cycle_time = now
            return

        # Advance index on interval
        if now - self._last_cycle_time >= config.FLIGHT_CYCLE_INTERVAL:
            self._current_index = (self._current_index + 1) % len(flights)
            self._last_cycle_time = now

        # Clamp index if flight list shrank
        if self._current_index >= len(flights):
            self._current_index = 0

        self.show_flight(flights[self._current_index], self._current_index, len(flights))

    def clear(self) -> None:
        """Turn off all LEDs."""
        if self._matrix is None:
            return
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
        self._show_image(img)

    def shutdown(self) -> None:
        """Show goodbye and clear display."""
        self.show_status("Goodbye!")
        time.sleep(1)
        self.clear()
