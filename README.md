# No Man's Sky System Search

A small Python CLI and importable API that calls the real `nms-galactic-map` generator, optionally queries NMS Almanac separately, and stores parsed fields plus complete source responses in one SQLite database. Repeated lookups are served from that database.

## Setup

Requirements: Python 3.10+, Node.js 18+, Git. Initialize the existing upstream submodule:

```sh
git submodule update --init --recursive
cp config.local.example.json config.local.json
```

Edit `config.local.json` and paste your Almanac key there. The program does not prompt for keys and has no key CLI option. The request budget is configurable in that file and defaults to **500 requests per rolling hour**:

```json
{
  "almanac_api_key": "your-key",
  "almanac_requests_per_hour": 500
}
```

`NMS_ALMANAC_API_KEY` and `NMS_ALMANAC_REQUESTS_PER_HOUR` can override those values. Only uncached HTTP requests count; cached results and cached 404 responses do not. Rate-limit history is persisted in the same SQLite database across runs.

## CLI

Portal address is exactly 12 hexadecimal glyphs. Galaxy is the upstream zero-based index (Euclid `0`; valid `0`–`255`). The first glyph selects a body; it is set to zero for system-level lookups so all portal variants for a system use the same persistent system cache entry.

```sh
python cli.py lookup 0807F07FFFFF --galaxy 0 --json
python cli.py almanac 0807F07FFFFF --galaxy 0 --json
python cli.py search --galaxy 0 --star-type blue --min-planets 5 --max-results 10 --max-checks 1000
python cli.py search --mode sequential --start-address 0807F07FFFFF --max-checks 100 --json
```

## One shared cache/database

Both clients use the configured `database` path, defaulting to `data/nms_search.sqlite3`. Generated system records live in `generated_systems` and `generated_bodies`; Almanac records and body data live in `almanac_systems` and `almanac_bodies`; raw endpoint response cache and the rolling-hour request ledger are in `api_cache` and `api_requests`. Both system clients canonicalize a portal address to planet glyph `0` and key system records by `(galaxy, canonical_address)`. That prevents 16 body glyph variants from causing duplicate system generation/lookups. Almanac planet endpoint responses are cached by their own portal addresses as well.

## Python API and output shapes

### `generator.lookup_system(address, galaxy=0, *, config=None, store=None, use_cache=True) -> dict`

Input: `address: str` (12 hex characters); `galaxy: int` (zero-based 0–255). Optional config/store/cache flag. Output keys: `address`, `galaxy`, `name`, `region`, `star_type`, `planets`, `moons`, `gas_giant`, `safe_start`, `planet_index`, `race`, `economy`, `economy_type`, `economy_tier`, `economy_description`, `sell`, `buy`, `conflict`, `conflict_tier`, `abandoned`, `uncharted`, `outlaw`, `is_black_hole`, `is_atlas`, `coords`, `bodies`, `raw`. `bodies` is a list of `{index: int, name: str|null}`. `raw` is the complete upstream generator result. Output address is canonical (first glyph `0`).

### `generator.search_systems(galaxy=0, *, filters=None, mode="random", seed=None, start_address=None, max_results=20, max_checks=2000, config=None, store=None) -> list[dict]`

Input: galaxy 0–255; `filters` is `SearchFilters` or `None`; mode is `random` or `sequential`; seed is optional integer; sequential mode requires a 12-hex start address; positive integer result/check limits; optional config/store. Output is a list of lookup dictionaries.

`SearchFilters` accepts optional strings `star_type`, `race`, `economy`, `conflict` (case-insensitive exact matches); optional inclusive integer ranges `min_planets`, `max_planets`, `min_moons`, `max_moons`; and optional booleans `abandoned`, `uncharted`, `outlaw`, `is_black_hole`, `is_atlas`.

### `community.AlmanacClient.lookup_system(address, galaxy=0, *, use_cache=True) -> dict`

Input: same address and galaxy. Output keys: `found: bool`, `source: "nmsalmanac"`, canonical `address`, `galaxy`, `system` (null on miss; otherwise parsed fields and complete system `raw`), `bodies`, and `raw` (complete system/body API responses). Body records include portal, index, names, biome, size, weather, sentinels, water, moon relationship, fauna, flora, resources, pictures, colours and raw record. Missing API data is left null; it is not guessed.

## Database queries

```sql
SELECT address, name, star_type, planets, race
FROM generated_systems WHERE galaxy=0 AND star_type='blue' AND planets >= 5;

SELECT system_address, portal, name, biome, weather
FROM almanac_bodies WHERE galaxy=0 AND biome='lush';

SELECT address, json_extract(payload_json, '$.system.suns') AS suns
FROM almanac_systems WHERE galaxy=0 AND found=1;
```

Successful API response payloads are cached for 30 days; 404 responses for one day. The normalized complete result and raw response are persisted as well. Generated results are deterministic and cached by system identity. Both clients use the same local database file, not separate caches.
