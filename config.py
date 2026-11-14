# No Man's Sky system search

This repository is a thin Python wrapper around the real NMS generator shipped in the upstream `nms-galactic-map` project, plus a separate client for `https://nmsalmanac.com`.

The goal is simple:

- query the real system generator by portal address or by scanning candidate addresses
- optionally enrich the result with NMS Almanac data
- keep all results in a local SQLite database with caching so repeat lookups do not trigger unnecessary regeneration or API requests
- expose everything through a small CLI and documented Python functions

Everything here is intentionally stripped down to the parts that matter.

## Project structure

- `cli.py` — command-line interface
- `config.py` — local runtime configuration
- `generator.py` — system generation + search logic
- `nms_map_client.py` — bridge to the upstream JavaScript generator
- `community.py` — Almanac client
- `database.py` — SQLite persistence and cache
- `models.py` — Python data models and filter logic
- `js_bridge.py` — low-level bridge for the Node-based generator

## Required setup

This project expects the upstream JavaScript code to be available in a local checkout at:

- `nms-galactic-map/nms-tools/nms-lookup.js`
- `nms-galactic-map/nms-core`

If the submodule is not already present, initialize it from the upstream repo before running the CLI.

## Local config for NMS Almanac

Do not use a CLI prompt for the key.

Place the key into `config.local.json` in the project root with this shape:

```json
{
  "almanac_api_key": "your-key-here",
  "almanac_requests_per_hour": 500
}
```

You may also set the environment variables:

```bash
export NMS_ALMANAC_API_KEY="your-key-here"
export NMS_ALMANAC_REQUESTS_PER_HOUR=500
```

The default request budget is 500 requests per hour.

## CLI examples

### Direct lookup

```bash
python cli.py lookup --address 0807F07FFFFF --galaxy 0
```

### Search with filters

```bash
python cli.py search --galaxy 0 --star-color yellow --min-planets 3 --max-results 10
```

### Sequential scan

```bash
python cli.py search --galaxy 0 --mode sequential --start-address 0807F07FFFFF --max-results 20
```

### Almanac lookup

```bash
python cli.py almanac --address 0807F07FFFFF --galaxy 0
```

## Python API

The project exposes a small Python API with explicit shapes.

### `generator.lookup_system`

Input:

```python
lookup_system(address: str, galaxy: int = 0, *, use_cache: bool = True) -> dict
```

Output:

```python
{
  "address": "0807F07FFFFF",
  "galaxy": 0,
  "name": "...",
  "region": "...",
  "star_type": "yellow",
  "planets": 4,
  "moons": 1,
  "gas_giant": False,
  "safe_start": 2,
  "race": "Gek",
  "economy": "Advanced Mining",
  "economy_type": "Mining",
  "economy_tier": 2,
  "economy_desc": "...",
  "sell": 24.5,
  "buy": -18.3,
  "conflict": "Fractious",
  "conflict_tier": 2,
  "abandoned": False,
  "uncharted": False,
  "outlaw": False,
  "is_black_hole": False,
  "is_atlas": False,
  "coords": {"x": 123, "y": 45, "z": 678},
  "planet_names": ["...", "..."],
  "raw": {...}
}
```

### `generator.search_systems`

Input:

```python
search_systems(
    galaxy: int = 0,
    *,
    filters: SearchFilters | None = None,
    mode: str = "random",
    seed: int | None = None,
    start_address: str | None = None,
    max_results: int | None = None,
    max_checks: int | None = None,
    use_cache: bool = True,
) -> list[dict]
```

Output is a list of the same per-system dicts shown above.

### `community.lookup_system`

Input:

```python
lookup_system(address: str, galaxy: int = 0, *, use_cache: bool = True) -> dict
```

Output:

```python
{
  "found": True,
  "source": "nmsalmanac",
  "address": "0807F07FFFFF",
  "galaxy": 0,
  "system": {
    "name": "...",
    "game_name": "...",
    "star": "...",
    "spectral_class": "...",
    "suns": 2,
    "race": "...",
    "economy": "...",
    "wealth": "...",
    "conflict": "...",
    "discoverer": "...",
    "platform": "...",
    "discovered": "2026-11-01",
    "sell": 24.5,
    "buy": -18.3,
    "demand": "...",
    "raw": {...}
  },
  "planets": [
    {
      "portal": "...",
      "name": "...",
      "biome": "...",
      "weather": "...",
      "water": True,
      "moon_of": None,
      "raw": {...}
    }
  ],
  "raw": {...}
}
```

## Database layout

The project stores data in `data/nms_search.sqlite3`.

Tables:

- `generated_systems`
  - `address TEXT`
  - `galaxy INTEGER`
  - `system_json TEXT`
  - `created_at REAL`
  - `PRIMARY KEY (galaxy, address)`

- `almanac_systems`
  - `address TEXT`
  - `galaxy INTEGER`
  - `system_json TEXT`
  - `created_at REAL`
  - `PRIMARY KEY (galaxy, address)`

- `almanac_planets`
  - `portal TEXT`
  - `galaxy INTEGER`
  - `system_address TEXT`
  - `planet_json TEXT`
  - `created_at REAL`
  - `PRIMARY KEY (galaxy, portal)`

- `cache_entries`
  - `cache_key TEXT PRIMARY KEY`
  - `payload TEXT`
  - `expires_at REAL`
  - `created_at REAL`

Example queries:

```sql
SELECT address, galaxy, system_json
FROM generated_systems
WHERE galaxy = 0
LIMIT 20;
```

```sql
SELECT a.address, a.system_json
FROM almanac_systems a
WHERE a.galaxy = 0
ORDER BY a.created_at DESC
LIMIT 20;
```

## Caching behavior

- generated systems are cached by `(galaxy, address)`
- Almanac lookups are cached by `(galaxy, address)`
- rate-limited API requests are cached into the same SQLite store for repeat lookups
- if a cache entry is fresh, the code returns it without regenerating or calling the network again

## Notes

This project intentionally does not ask the user for an API key in the CLI. The key must already exist in `config.local.json` or in the environment before a lookup is attempted.

The upstream generator is treated as the authoritative system source. The previous prototype code that invented its own behaviors or hardcoded options is not kept.

The code is built for readability and future extension rather than for preserving dead experimentation.
