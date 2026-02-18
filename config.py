"""User-tunable configuration for flight-tracker-led."""

# ── Location ─────────────────────────────────────────────────────────
HOME_LAT = 0.0  # Your latitude (decimal degrees)
HOME_LON = 0.0  # Your longitude (decimal degrees)
BOUNDING_BOX_RADIUS_KM = 50  # Radius for API query bounding box

# ── OpenSky API ──────────────────────────────────────────────────────
OPENSKY_USERNAME = ""  # Leave empty for anonymous access
OPENSKY_PASSWORD = ""
OPENSKY_BASE_URL = "https://opensky-network.org/api"
STATES_POLL_INTERVAL = 15  # Seconds between state vector polls
ROUTE_CACHE_TTL = 3600  # 1 hour
METADATA_CACHE_TTL = 86400  # 24 hours
FAILED_CACHE_TTL = 300  # 5 minutes for failed lookups
MAX_ENRICHMENT_PER_CYCLE = 3  # Max route/metadata lookups per poll

# ── Filtering ────────────────────────────────────────────────────────
MAX_DISTANCE_KM = 50
MIN_ALTITUDE_M = 100
EXCLUDE_ON_GROUND = True

# ── LED Matrix Display ──────────────────────────────────────────────
MATRIX_ROWS = 32
MATRIX_COLS = 64
MATRIX_CHAIN = 1  # Single 64x32 panel
HARDWARE_MAPPING = "adafruit-hat"
GPIO_SLOWDOWN = 4  # Tuned for Pi Zero 2 W
BRIGHTNESS = 60  # 0-100
PWM_BITS = 5  # Reduced for Pi Zero 2 W CPU
FLIGHT_CYCLE_INTERVAL = 10  # Seconds per flight on display

# ── Colors (R, G, B) ────────────────────────────────────────────────
COLOR_CALLSIGN = (0, 255, 255)  # Cyan
COLOR_DATA = (255, 255, 255)  # White
COLOR_ROUTE = (0, 255, 0)  # Green
COLOR_DISTANCE = (255, 191, 0)  # Amber
COLOR_STATUS = (128, 128, 128)  # Gray for status messages

# ── Local overrides (not checked into git) ───────────────────────────
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
