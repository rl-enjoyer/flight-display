"""Main entry point — data thread + display loop with graceful shutdown."""

import logging
import signal
import sys
import threading
import time

import config
from display import FlightDisplay
from flight_data import FlightState, OpenSkyClient
from flight_processor import process_flights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class FlightTracker:
    def __init__(self):
        self._client = OpenSkyClient()
        self._display = FlightDisplay()
        self._flights: list[FlightState] = []
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._bbox = OpenSkyClient.get_bounding_box(
            config.HOME_LAT, config.HOME_LON, config.BOUNDING_BOX_RADIUS_KM
        )

    # ── Data thread ──────────────────────────────────────────────────

    def _data_loop(self) -> None:
        """Poll OpenSky, process, and enrich flights."""
        logger.info("Data thread started (poll every %ds)", config.STATES_POLL_INTERVAL)
        cache_cleanup_counter = 0
        while not self._shutdown.is_set():
            try:
                raw = self._client.fetch_states(self._bbox)
                processed = process_flights(raw)

                # Carry over enrichment data from previous cycle
                with self._lock:
                    old_map = {f.icao24: f for f in self._flights}

                for f in processed:
                    old = old_map.get(f.icao24)
                    if old:
                        if old.origin_airport:
                            f.origin_airport = old.origin_airport
                        if old.dest_airport:
                            f.dest_airport = old.dest_airport
                        if old.aircraft_type:
                            f.aircraft_type = old.aircraft_type
                        if old.registration:
                            f.registration = old.registration

                self._client.enrich_flights(processed)

                with self._lock:
                    self._flights = processed

                logger.info("Tracking %d flights", len(processed))

                # Periodic cache cleanup
                cache_cleanup_counter += 1
                if cache_cleanup_counter >= 20:
                    self._client.cleanup_caches()
                    cache_cleanup_counter = 0

            except Exception:
                logger.exception("Error in data loop")

            # Sleep in small increments for responsive shutdown
            for _ in range(int(config.STATES_POLL_INTERVAL / 0.1)):
                if self._shutdown.is_set():
                    break
                time.sleep(0.1)

    # ── Display loop (main thread) ───────────────────────────────────

    def _display_loop(self) -> None:
        """Run display updates at ~10Hz on the main thread."""
        self._display.show_status("Scanning...")
        while not self._shutdown.is_set():
            with self._lock:
                flights = list(self._flights)
            self._display.cycle_flights(flights)
            time.sleep(0.1)

    # ── Lifecycle ────────────────────────────────────────────────────

    def _handle_signal(self, signum: int, frame) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        self._shutdown.set()

    def run(self) -> None:
        """Start data thread, run display loop on main thread."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info(
            "Flight Tracker starting (%.4f, %.4f) radius=%dkm",
            config.HOME_LAT, config.HOME_LON, config.BOUNDING_BOX_RADIUS_KM,
        )

        data_thread = threading.Thread(target=self._data_loop, daemon=True, name="data")
        data_thread.start()

        try:
            self._display_loop()
        finally:
            self._shutdown.set()
            logger.info("Waiting for data thread...")
            data_thread.join(timeout=5)
            self._display.shutdown()
            logger.info("Shutdown complete")


def main() -> None:
    if config.HOME_LAT == 0.0 and config.HOME_LON == 0.0:
        print("WARNING: HOME_LAT and HOME_LON are at 0,0 (Gulf of Guinea).")
        print("Edit config.py to set your location.")
        print()

    tracker = FlightTracker()
    tracker.run()


if __name__ == "__main__":
    main()
