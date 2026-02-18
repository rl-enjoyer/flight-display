"""Flight filtering, sorting, and formatting — pure functions."""

from math import asin, cos, radians, sin, sqrt

import config
from flight_data import FlightState

# ── Distance ─────────────────────────────────────────────────────────

_EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


# ── Processing pipeline ─────────────────────────────────────────────

def process_flights(
    raw: list[FlightState],
    home_lat: float | None = None,
    home_lon: float | None = None,
) -> list[FlightState]:
    """Calculate distances, filter, and sort flights by distance."""
    if home_lat is None:
        home_lat = config.HOME_LAT
    if home_lon is None:
        home_lon = config.HOME_LON

    result = []
    for f in raw:
        # Need valid position
        if f.latitude is None or f.longitude is None:
            continue

        # Filter ground traffic
        if config.EXCLUDE_ON_GROUND and f.on_ground:
            continue

        # Filter low altitude (but allow None — might just be missing data)
        if f.baro_altitude is not None and f.baro_altitude < config.MIN_ALTITUDE_M:
            continue

        # Calculate distance
        f.distance_km = haversine(home_lat, home_lon, f.latitude, f.longitude)

        # Filter by distance
        if f.distance_km > config.MAX_DISTANCE_KM:
            continue

        result.append(f)

    result.sort(key=lambda f: f.distance_km or 0)
    return result


# ── Formatting helpers ───────────────────────────────────────────────

_CARDINALS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def format_altitude(meters: float | None) -> str:
    """Convert meters to flight level or feet."""
    if meters is None:
        return "---"
    feet = meters * 3.28084
    if feet >= 18000:
        return f"FL{int(round(feet / 100))}"
    return f"{int(round(feet))}ft"


def format_speed(mps: float | None) -> str:
    """Convert m/s to knots."""
    if mps is None:
        return "---"
    knots = mps * 1.94384
    return f"{int(round(knots))}kt"


def format_heading(degrees: float | None) -> str:
    """Convert degrees to cardinal direction + 3-digit heading."""
    if degrees is None:
        return "---"
    idx = int((degrees + 11.25) / 22.5) % 16
    cardinal = _CARDINALS[idx]
    return f"{cardinal}{int(degrees):03d}"


def format_distance(km: float | None) -> str:
    """Format distance in km."""
    if km is None:
        return "---"
    if km < 10:
        return f"{km:.1f}km"
    return f"{int(round(km))}km"


def format_vertical_rate(mps: float | None) -> str:
    """Convert m/s vertical rate to fpm string."""
    if mps is None or abs(mps) < 0.5:
        return ""
    fpm = int(round(mps * 196.85))
    return f"{fpm:+d}fpm"


def format_route(origin: str, dest: str) -> str:
    """Format origin>destination, handling missing values."""
    if origin and dest:
        return f"{origin} > {dest}"
    if origin:
        return f"{origin} > ?"
    if dest:
        return f"? > {dest}"
    return ""


if __name__ == "__main__":
    # Verify haversine: JFK to LHR ≈ 5,539 km
    jfk_lat, jfk_lon = 40.6413, -73.7781
    lhr_lat, lhr_lon = 51.4700, -0.4543
    dist = haversine(jfk_lat, jfk_lon, lhr_lat, lhr_lon)
    print(f"JFK → LHR: {dist:.0f} km (expected ~5539)")

    # Verify formatting
    print(f"Altitude: {format_altitude(10668)}")  # FL350
    print(f"Speed: {format_speed(231.5)}")  # ~450kt
    print(f"Heading: {format_heading(45)}")  # NE045
    print(f"Distance: {format_distance(12.34)}")  # 12km
    print(f"Distance: {format_distance(5.7)}")  # 5.7km
    print(f"Route: {format_route('KJFK', 'EGLL')}")  # KJFK>EGLL
