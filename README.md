# Flight Tracker LED Matrix Display

Real-time overhead flight tracker that runs on a Raspberry Pi Zero 2 W with an Adafruit RGB Matrix HAT driving 2x chained 64x32 LED panels (128x32 total). It pulls live aircraft data from the [OpenSky Network](https://opensky-network.org/) API and cycles through nearby flights on the display.

## What it shows

Each flight gets a 4-line display that cycles every 5 seconds:

```
UAL1234  B738          <- callsign + aircraft type (cyan)
FL350 450kt            <- altitude + speed (white)
KJFK>EGLL NE045        <- route + heading (green)
12.3km [2/7] US        <- distance + position + country (amber)
```

When no aircraft are nearby it shows "No flights nearby". On first boot before data arrives it shows "Scanning...".

## Hardware

- Raspberry Pi Zero 2 W
- Adafruit RGB Matrix HAT/Bonnet
- 2x 64x32 RGB LED matrix panels (HUB75), daisy-chained

## Setup

1. Clone this repo onto your Pi
2. Edit `config.py` — set `HOME_LAT` and `HOME_LON` to your coordinates
3. Run the install script:

```bash
bash install.sh
```

This installs system packages, builds the [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) Python bindings, installs Python deps, and disables onboard audio (it conflicts with the matrix GPIO). It also optionally creates a systemd service for auto-start at boot.

4. Reboot if audio was just disabled, then:

```bash
sudo python3 main.py
```

Root is required for GPIO access.

## Configuration

Everything is in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `HOME_LAT` / `HOME_LON` | `0.0` | Your location (decimal degrees) |
| `BOUNDING_BOX_RADIUS_KM` | `50` | How far out to query the API |
| `MAX_DISTANCE_KM` | `50` | Max distance to show a flight |
| `MIN_ALTITUDE_M` | `100` | Ignore aircraft below this altitude |
| `EXCLUDE_ON_GROUND` | `True` | Filter out ground traffic |
| `STATES_POLL_INTERVAL` | `15` | Seconds between API polls |
| `FLIGHT_CYCLE_INTERVAL` | `5` | Seconds each flight is displayed |
| `BRIGHTNESS` | `60` | LED brightness (0-100) |
| `GPIO_SLOWDOWN` | `2` | Tuned for Pi Zero 2 W |

OpenSky credentials are optional — anonymous access works but has lower rate limits. Sign up at [opensky-network.org](https://opensky-network.org/) if you need more.

## Project structure

```
config.py              # All user-tunable settings
flight_data.py         # OpenSky API client with TTL caching
flight_processor.py    # Distance calc, filtering, sorting, formatting
display.py             # LED matrix rendering (Pillow + rgbmatrix)
main.py                # Main loop, threading, graceful shutdown
install.sh             # One-time Pi setup
requirements.txt       # Python dependencies
pyproject.toml         # Project metadata
```

## How it works

- **Data thread** polls OpenSky every 15s, filters flights by distance/altitude/ground status, and enriches up to 3 flights per cycle with route and aircraft type info (rate-limit friendly)
- **Display loop** runs on the main thread at ~10Hz, cycling through flights with double-buffered rendering (no flicker)
- Route and metadata lookups are cached (1hr and 24hr TTL respectively) to minimize API calls
- Network failures are handled gracefully — the display retains last known data and never goes blank

## Testing without a Pi

The API client and processor work on any machine:

```bash
# Verify haversine math and formatting
python3 flight_processor.py

# Test API connectivity (set your coords in config.py first)
python3 flight_data.py
```

The display module falls back to headless mode when `rgbmatrix` isn't available.
