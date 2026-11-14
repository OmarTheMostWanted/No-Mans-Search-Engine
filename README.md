# No Man's Sky System Search

A small Python CLI and importable API that calls the real `nms-galactic-map` generator, optionally queries NMS Almanac separately, and stores parsed fields plus complete source responses in SQLite. Repeated generator lookups and Almanac responses are cached persistently.

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

`NMS_ALMANAC_API_KEY` and `NMS_ALMANAC_REQUESTS_PER_HOUR` can override those values. Only actual uncached HTTP requests count; cached results and cached 404 responses do not. Rate-limit history is persisted in SQLite across runs.

## CLI

Portal address is exactly 12 hexadecimal glyphs. Galaxy is the upstream zero-based index (Euclid `0`; valid `0`–`255`).

```sh
python cli.py lookup 0807F07FFFFF --galaxy 0 --json
python cli.py almanac 0807F07FFFFF --galaxy 0 --json
python cli.py search --galaxy 0 --star-type blue --min-planets 5 --max-results 10 --max-checks 1000
python cli.py search --mode sequential --start-address 0807F07FFFFF --max-checks 100 --json
```

Search examines canonical candidate addresses with the leading planet glyph set to zero. Random mode accepts `--seed` for repeatable candidates. Searches are bounded by `--max-checks` and `--max-results`.

## Python functions and exact result shapes

### `generator.lookup_system(address, galaxy=0, *, config=None, store=None, use_cache=True) -> dict`

Input: `address: str` (12 hex characters); `galaxy: int` (zero-based 0–255). Optional `config: AppConfig`, `store: SQLiteStore`, `use_cache: bool`. Output keys: `address`, `galaxy`, `name`, `region`, `star_type`, `planets`, `moons`, `gas_giant`, `safe_start`, `planet_index`, `race`, `economy`, `economy_type`, `economy_tier`, `economy_description`, `sell`, `buy`, `conflict`, `conflict_tier`, `abandoned`, `uncharted`, `outlaw`, `is_black_hole`, `is_atlas`, `coords`, `bodies`, `raw`. `coords` is the generator's coordinate object. `bodies` is a list of `{index: int, name: str|null}`. `raw` is the complete upstream generator result, with original field names.

### `generator.search_systems(galaxy=0, *, filters=None, mode="random", seed=None, start_address=None, max_results=20, max_checks=2000, config=None, store=None) -> list[dict]`

Input: galaxy 0–255; `filters` is `SearchFilters` or `None`; mode is `random` or `sequential`; seed is optional integer; sequential mode requires a 12-hex `start_address`; positive integer result/check limits; optional config/store. Output is a list of the same dictionaries returned by `lookup_system`, in candidate order.

`SearchFilters` accepts optional strings `star_type`, `race`, `economy`, `conflict` (case-insensitive exact matches); optional inclusive integer ranges `min_planets`, `max_planets`, `min_moons`, `max_moons`; and optional booleans `abandoned`, `uncharted`, `outlaw`, `is_black_hole`, `is_atlas`.

### `community.AlmanacClient.lookup_system(address, galaxy=0, *, use_cache=True) -> dict`

Input: same address and galaxy as generator lookup. Output keys: `found: bool`, `source: "nmsalmanac"`, `address`, `galaxy`, `system` (null on miss; otherwise parsed system fields plus complete `raw` API object), `bodies` (list of bodies), and `raw` (complete system and body API responses). Body keys include `portal`, `index`, `name`, `game_name`, `biome`, `size`, `weather`, `sentinels`, `water`, `moon_of`, `fauna`, `flora`, `resources`, `pictures`, `colours`, and `raw`. Values not present in the API are null/empty rather than inferred. Almanac codes are retained as returned; the full raw records are always preserved.

### Other exposed helpers

- `config.load_config(config_path=None) -> AppConfig`: loads local JSON and environment overrides; validates the configured hourly limit.
- `config.normalize_address(address) -> str`: accepts 12 hexadecimal characters and returns uppercase.
- `config.validate_galaxy(galaxy) -> int`: accepts an integer 0–255 and returns it.
- `generator.iter_addresses(mode="random", *, seed=None, start_address=None) -> Iterator[str]`: yields canonical 12-character candidate portal addresses indefinitely.
- `SQLiteStore(path)`: context manager for database persistence. `close() -> None` closes its SQLite connection.
- `NMSMapClient.lookup_system(address, galaxy=0, *, use_cache=True) -> dict`: same normalized output shape as `generator.lookup_system`; uses the upstream Node bridge and SQLite cache.

## SQLite schema and examples

Default database: `data/nms_search.sqlite3` (override with `database` in config). Tables:

- `generated_systems`: galaxy/address identity, indexed searchable fields, full normalized JSON and generation timestamp.
- `generated_bodies`: one indexed row per generated body/name, plus JSON.
- `almanac_systems`: found status, common searchable fields, complete normalized/raw JSON and fetch timestamp.
- `almanac_bodies`: body address, name, biome, weather and complete JSON.
- `api_cache`: cached raw API endpoint payloads, including explicit 404 markers and expiry.
- `api_requests`: timestamps used for the persistent rolling-hour request budget.

Examples (JSON fields can be queried with SQLite JSON1 where available):

```sql
SELECT address, name, star_type, planets, race
FROM generated_systems WHERE galaxy=0 AND star_type='blue' AND planets >= 5;

SELECT system_address, portal, name, biome, weather
FROM almanac_bodies WHERE galaxy=0 AND biome='lush';

SELECT address, json_extract(payload_json, '$.system.suns') AS suns
FROM almanac_systems WHERE galaxy=0 AND found=1;
```

Generated results are deterministic and cached by `(galaxy,address)`. Almanac endpoint responses (including bodies) are cached persistently; successful responses expire after 30 days and not-found responses after one day. The complete parsed result and raw source response are also stored in relational tables for later querying. Source data is not fabricated to fill missing API fields.

Run local checks with `python -m unittest -v` when tests are present. The CLI's `--help` is available via `python cli.py --help`.
