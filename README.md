# No Man's Sky System Search

A command-line search tool that enumerates portal codes and generates system data with the included [`nms-galactic-map`](https://github.com/elegra1965-source/nms-galactic-map) Git submodule. It does not use a remote service or fake generator data. After printing all generated matches, it can enrich each match with community-recorded NMS Almanac system and planet data.

## Requirements

- Python 3.10+
- Node.js 18+ (ES modules and BigInt support)
- Git with submodule support
- Optional NMS Almanac API key for community lookups

## Setup

Clone this branch and initialize the included generator:

```bash
git clone --branch copilot/implement-nms-system-search --recurse-submodules https://github.com/OmarTheMostWanted/No-Mans-Search-Engine.git
cd No-Mans-Search-Engine
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

No Python packages need to be installed. Verify the real generator integration with:

```bash
python -m unittest -v
```

## Community lookup key

The optional client uses the NMS Almanac API (`https://nmsalmanac.com/api/`) with an HTTP Bearer key, matching the integration in the dependency. Keep the key out of source control. Set it in the shell environment:

```bash
# macOS / Linux
export NMS_ALMANAC_API_KEY='your-issued-key'

# PowerShell
$env:NMS_ALMANAC_API_KEY = 'your-issued-key'
```

When this variable is present, community enrichment runs automatically after generated matches have been printed. Use `--no-community-lookup` to skip it, or `--community-lookup` to require it (the latter reports a configuration error if no key is set). The API key is never printed or written to the cache.

The dependency documents a 500-request/hour Almanac key quota and applies a 40 uncached system lookups/hour visitor cap in its own hosted proxy. This local client accesses the Almanac directly, so it conservatively caps all direct API calls at 450 per rolling hour (configurable downward, never above 450), paces calls at least one second apart, stores responses in `data/community.sqlite3`, and stops on HTTP 429. A full record can cost one system request plus one request per planet (up to eight). Cached responses do not consume the local API budget. The direct API key's use is not shared with the dependency's hosted proxy; the 450-call guard only tracks this installation.

## Run a search

Try a bounded search first (search duration otherwise defaults to one hour):

```bash
python cli.py --star-color blue --min-planets 5 --max-systems 500 --duration 60
```

Search sequentially from a portal code:

```bash
python cli.py --mode sequential --start-address 0807F07FFFFF --max-systems 1000 --duration 120
```

Get JSON Lines output (generated matches are emitted first, followed by community lookup records):

```bash
python cli.py --race korvax --economy-tier 3 --max-matches 20 --duration 300 --json
```

For the previously discussed system-level criteria, community lookups and their body data can be viewed with:

```bash
python cli.py --galaxy 19 --economy-tier 3 --conflict-tier 1 --race korvax --max-matches 20 --duration 300
```

The community lookup reports Almanac-recorded sun count, planet biomes, and weather when a matching community record exists. It does not infer a Paradise-world count or require complete community coverage: planet biome/weather labels are displayed as recorded, and database coverage can be sparse. Those results are separate from the procedural address-generated fields.

Use `python cli.py --help` for all options. Filters are case-insensitive where they accept text. Tier values are 1 (low), 2 (medium), 3 (high); the included generator's 0-based tiers are converted to these values. Galaxy numbering in this CLI is human-friendly (Euclid is 1), converted to the submodule's index (Euclid is 0).

Searches cover canonical system addresses, with the planet glyph held at zero so one system is not searched repeatedly through its 16 planet-address variants. Random search is reproducible with `--seed`. `--max-systems` and `--max-matches` bound a run; results are printed before community enrichment begins. Generated systems are cached in `data/systems.sqlite3`; community responses and their request-budget ledger are cached in `data/community.sqlite3`. Disable generated cache with `--no-cache`; disable community lookup with `--no-community-lookup`.

## Data scope

The included upstream API derives star type, planet/moon counts, economy, conflict, race, special-system flags, coordinates, and generated names from portal code and galaxy. Its system and planet-level biome/environment fields are not an address-derived authoritative result. NMS Almanac values are community records and can be missing or incomplete. The upstream API does not provide a generated sun-count field; Almanac may provide a recorded `suns` value.
