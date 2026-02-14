"""OpenSky Network API client with TTL caching."""

import logging
import time
from dataclasses import dataclass, field
from math import cos, radians

import requests

import config

logger = logging.getLogger(__name__)


@dataclass
class FlightState:
    """Single aircraft state vector plus enriched fields."""
    icao24: str = ""
    callsign: str = ""
    origin_country: str = ""
    longitude: float | None = None
    latitude: float | None = None
    baro_altitude: float | None = None  # meters
    on_ground: bool = False
    velocity: float | None = None  # m/s
    true_track: float | None = None  # degrees clockwise from north
    vertical_rate: float | None = None  # m/s
    geo_altitude: float | None = None  # meters
    squawk: str | None = None
    # Enriched fields
    origin_airport: str = ""
    dest_airport: str = ""
    aircraft_type: str = ""
    registration: str = ""
    distance_km: float | None = None


class _CacheEntry:
    """Value with expiration timestamp."""
    __slots__ = ("value", "expires_at")

    def __init__(self, value, ttl: float):
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class OpenSkyClient:
    def __init__(self):
        self._session = requests.Session()
        if config.OPENSKY_USERNAME:
            self._session.auth = (config.OPENSKY_USERNAME, config.OPENSKY_PASSWORD)
        self._session.headers["User-Agent"] = "flight-tracker-led/1.0"
        self._route_cache: dict[str, _CacheEntry] = {}
        self._meta_cache: dict[str, _CacheEntry] = {}

    @staticmethod
    def get_bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
        """Convert center + radius to (lamin, lomin, lamax, lomax)."""
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * cos(radians(lat))
        if km_per_deg_lon < 1:
            km_per_deg_lon = 1  # avoid division by zero near poles
        dlat = radius_km / km_per_deg_lat
        dlon = radius_km / km_per_deg_lon
        return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)

    def fetch_states(self, bbox: tuple[float, float, float, float]) -> list[FlightState]:
        """Fetch current state vectors within bounding box."""
        lamin, lomin, lamax, lomax = bbox
        url = f"{config.OPENSKY_BASE_URL}/states/all"
        params = {"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax}
        try:
            resp = self._session.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                logger.warning("Rate limited by OpenSky (429)")
                return []
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch states: %s", e)
            return []

        data = resp.json()
        states = data.get("states") or []
        flights = []
        for s in states:
            flights.append(FlightState(
                icao24=s[0] or "",
                callsign=(s[1] or "").strip(),
                origin_country=s[2] or "",
                longitude=s[5],
                latitude=s[6],
                baro_altitude=s[7],
                on_ground=bool(s[8]),
                velocity=s[9],
                true_track=s[10],
                vertical_rate=s[11],
                geo_altitude=s[13],
                squawk=s[14] if len(s) > 14 else None,
            ))
        return flights

    def fetch_route(self, callsign: str) -> tuple[str, str]:
        """Fetch origin/destination airports for a callsign via adsbdb.com."""
        if not callsign:
            return ("", "")

        cached = self._route_cache.get(callsign)
        if cached and not cached.expired:
            return cached.value

        url = f"https://api.adsbdb.com/v0/callsign/{callsign}"
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code == 404:
                self._route_cache[callsign] = _CacheEntry(("", ""), config.FAILED_CACHE_TTL)
                return ("", "")
            if resp.status_code == 429:
                logger.warning("Rate limited fetching route for %s", callsign)
                return ("", "")
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch route for %s: %s", callsign, e)
            return ("", "")

        data = resp.json()
        flightroute = data.get("response", {})
        if isinstance(flightroute, str):
            # "unknown callsign"
            self._route_cache[callsign] = _CacheEntry(("", ""), config.FAILED_CACHE_TTL)
            return ("", "")
        flightroute = flightroute.get("flightroute", {})
        origin = (flightroute.get("origin") or {}).get("icao_code", "")
        dest = (flightroute.get("destination") or {}).get("icao_code", "")
        result = (origin, dest)
        self._route_cache[callsign] = _CacheEntry(result, config.ROUTE_CACHE_TTL)
        return result

    def fetch_metadata(self, icao24: str) -> tuple[str, str]:
        """Fetch aircraft type and registration. Returns cached if available."""
        if not icao24:
            return ("", "")

        cached = self._meta_cache.get(icao24)
        if cached and not cached.expired:
            return cached.value

        url = f"{config.OPENSKY_BASE_URL}/metadata/aircraft/icao24/{icao24}"
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code == 404:
                self._meta_cache[icao24] = _CacheEntry(("", ""), config.FAILED_CACHE_TTL)
                return ("", "")
            if resp.status_code == 429:
                logger.warning("Rate limited fetching metadata for %s", icao24)
                return ("", "")
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch metadata for %s: %s", icao24, e)
            return ("", "")

        data = resp.json()
        typecode = data.get("typecode", "") or ""
        registration = data.get("registration", "") or ""
        result = (typecode, registration)
        self._meta_cache[icao24] = _CacheEntry(result, config.METADATA_CACHE_TTL)
        return result

    def enrich_flights(self, flights: list[FlightState], max_per_cycle: int | None = None) -> None:
        """Enrich flights with route and metadata, up to max_per_cycle new lookups."""
        if max_per_cycle is None:
            max_per_cycle = config.MAX_ENRICHMENT_PER_CYCLE
        lookups = 0
        for flight in flights:
            if lookups >= max_per_cycle:
                break

            needs_route = not flight.origin_airport and not flight.dest_airport
            needs_meta = not flight.aircraft_type

            # Check if we already have cached data (doesn't count as a lookup)
            if needs_route:
                cached = self._route_cache.get(flight.callsign)
                if cached and not cached.expired:
                    flight.origin_airport, flight.dest_airport = cached.value
                    needs_route = False

            if needs_meta:
                cached = self._meta_cache.get(flight.icao24)
                if cached and not cached.expired:
                    flight.aircraft_type, flight.registration = cached.value
                    needs_meta = False

            # Perform actual API calls (counts toward limit)
            if needs_route:
                flight.origin_airport, flight.dest_airport = self.fetch_route(flight.callsign)
                lookups += 1

            if needs_meta and lookups < max_per_cycle:
                flight.aircraft_type, flight.registration = self.fetch_metadata(flight.icao24)
                lookups += 1

    def cleanup_caches(self) -> None:
        """Remove expired cache entries to prevent unbounded growth."""
        for cache in (self._route_cache, self._meta_cache):
            expired_keys = [k for k, v in cache.items() if v.expired]
            for k in expired_keys:
                del cache[k]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    client = OpenSkyClient()
    bbox = OpenSkyClient.get_bounding_box(config.HOME_LAT, config.HOME_LON, config.BOUNDING_BOX_RADIUS_KM)
    print(f"Bounding box: {bbox}")
    flights = client.fetch_states(bbox)
    print(f"Got {len(flights)} flights")
    for f in flights[:5]:
        print(f"  {f.callsign or f.icao24}: alt={f.baro_altitude}m, spd={f.velocity}m/s, on_ground={f.on_ground}")
    if flights:
        client.enrich_flights(flights[:3])
        for f in flights[:3]:
            print(f"  {f.callsign}: {f.origin_airport}>{f.dest_airport} type={f.aircraft_type}")
