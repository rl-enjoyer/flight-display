# Flight Route Data Sources

## Problem

ADS-B transmissions do not include origin/destination info. Any service providing route data must infer or cross-reference it from external databases (airline schedules, historical data, etc.).

OpenSky Network's `/routes` endpoint was our original source. Testing against 34 live flights returned **0% hit rate** — every callsign got a 404. The database appears to have stopped being updated around 2022-2024.

## Options Evaluated

| Source | Cost | Route Quality | Notes |
|--------|------|--------------|-------|
| **adsbdb.com** | Free, no key | Decent, gaps on uncommon callsigns | Simple REST API, no auth |
| **adsb.lol** `/api/0/routeset` | Free, no key (for now) | "Plausible" routes from schedule data | Batch POST for multiple callsigns |
| **AeroDataBox** (RapidAPI) | Free: 300 calls/mo | Good (schedule-fused) | Requires RapidAPI key |
| **FlightAware AeroAPI** | ~100 free calls/mo | Best quality | Requires credit card on file |
| **hexdb.io** | Free, no key | Poor for routes | Better for aircraft metadata |
| **FlightRadar24** (unofficial) | Free | Excellent coverage | ToS violation, risk of breakage |
| **aviationstack** | Free: 100 req/mo | Reasonable | Routes locked behind $50/mo paywall |
| **OpenFlights CSV** | Free | N/A | Last updated 2014, no callsign mapping |

## Current Choice: adsbdb.com

Selected for:
- Free with no API key or registration
- Simple REST GET: `https://api.adsbdb.com/v0/callsign/{CALLSIGN}`
- Returns ICAO airport codes for origin and destination
- No rate limit documented

Known limitations:
- Coverage gaps on uncommon/regional callsigns
- Route data "may not be copied, published, or incorporated into other databases without explicit permission"

## Future Improvements

If adsbdb coverage proves insufficient, next steps would be:
1. **adsb.lol** as a fallback (free, supports batch queries)
2. **AeroDataBox** as a higher-quality source (300 free calls/mo, needs RapidAPI key)
3. Tiered lookup: try adsbdb first, fall back to adsb.lol, then AeroDataBox
