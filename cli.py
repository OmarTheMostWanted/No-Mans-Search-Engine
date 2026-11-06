from __future__ import annotations

import argparse
import getpass
import json
import sys

from cache import SQLiteSystemCache
from community import CommunityClient, CommunityLookupError, CommunityRateLimit
from config import SearchConfig, save_community_api_key
from generator import search_systems
from js_bridge import JSBridge


def _bool_arg(value: str) -> bool:
    value = value.strip().lower()
    if value in {"true", "yes", "1", "on"}:
        return True
    if value in {"false", "no", "0", "off"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search real No Man's Sky systems with nms-galactic-map.")
    parser.add_argument("--configure-community-key", action="store_true",
                        help="Prompt privately for an Almanac key and save it to the Git-ignored config.local.json, then exit.")
    parser.add_argument("--galaxy", type=int, default=1, help="Galaxy number (1-255; Euclid is 1).")
    parser.add_argument("--star-color", choices=("yellow", "red", "green", "blue", "purple"))
    parser.add_argument("--min-planets", type=int)
    parser.add_argument("--exact-planets", type=int)
    parser.add_argument("--min-moons", type=int)
    parser.add_argument("--max-moons", type=int)
    parser.add_argument("--economy", help="Case-insensitive economy label substring or exact category.")
    parser.add_argument("--economy-tier", type=int, choices=(1, 2, 3))
    parser.add_argument("--conflict", help="Case-insensitive conflict label.")
    parser.add_argument("--conflict-tier", type=int, choices=(1, 2, 3))
    parser.add_argument("--race", choices=("gek", "vy'keen", "korvax", "uninhabited"))
    for flag in ("pirate", "abandoned", "uncharted", "black-hole", "atlas-system"):
        parser.add_argument(f"--{flag}", type=_bool_arg, metavar="BOOL")
    parser.add_argument("--min-core-distance", type=float)
    parser.add_argument("--max-core-distance", type=float)
    parser.add_argument("--mode", dest="search_mode", choices=("random", "sequential"), default="random")
    parser.add_argument("--start-address", help="12-digit portal code; used with --mode sequential.")
    parser.add_argument("--seed", dest="random_seed", type=int, help="Reproducible random address sequence.")
    parser.add_argument("--duration", dest="duration_seconds", type=int, default=3600)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-systems", type=int, help="Stop after inspecting this many systems.")
    parser.add_argument("--max-matches", type=int, help="Stop after finding this many matches.")
    parser.add_argument("--cache", dest="cache_enabled", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cache-path", default="data/systems.sqlite3")
    parser.add_argument("--bridge", default="js/bridge.mjs")
    parser.add_argument("--node", default="node")
    parser.add_argument("--json", action="store_true", help="Output matching systems as JSON Lines.")
    parser.add_argument("--community-lookup", action=argparse.BooleanOptionalAction, default=None,
                        help="After printing generated matches, enrich them from NMS Almanac (auto-enabled when API key is configured).")
    parser.add_argument("--community-cache-path", default="data/community.sqlite3")
    parser.add_argument("--community-hourly-limit", type=int, default=450,
                        help="Conservative local rolling-hour API-call cap (maximum 450; upstream documents a 500/hour key quota).")
    parser.add_argument("--community-request-interval", type=float, default=1.0,
                        help="Minimum seconds between community API requests.")
    return parser


def config_from_args(args: argparse.Namespace) -> SearchConfig:
    values = vars(args).copy()
    for key in ("bridge", "node", "json", "community_lookup", "configure_community_key"):
        values.pop(key, None)
    values["black_hole"] = values.pop("black_hole", None)
    values["atlas_system"] = values.pop("atlas_system", None)
    values["community_cache_path"] = values.pop("community_cache_path")
    values["community_hourly_request_limit"] = values.pop("community_hourly_limit")
    values["community_min_request_interval"] = values.pop("community_request_interval")
    config = SearchConfig(**values)
    config.validate()
    return config


def _configure_key() -> int:
    try:
        key = getpass.getpass("NMS Almanac API key (input hidden): ").strip()
        path = save_community_api_key(key)
    except (EOFError, OSError, ValueError) as exc:
        print(f"Could not save API key: {exc}", file=sys.stderr)
        return 2
    print(f"API key saved to Git-ignored local config: {path}")
    print("The key is excluded from git by .gitignore. Do not remove that ignore rule or share this file.")
    return 0


def _print_generated(results, as_json: bool) -> None:
    if as_json:
        for result in results:
            print(json.dumps({"type": "generated_system", "address": result.portal_address,
                              "galaxy": result.galaxy, **result.data}, sort_keys=True), flush=True)
    else:
        print(f"Found {len(results)} matching generated system(s).", flush=True)
        for result in results:
            data = result.data
            print(f"{result.portal_address}  {data.get('name') or '(unnamed)'}  {result.star_color or '?'}  "
                  f"{result.planets} planets/{result.moons} moons  {result.race or '?'}  {result.economy or '?'}",
                  flush=True)


def _print_community(record: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"type": "community_lookup", **record}, sort_keys=True), flush=True)
        return
    if not record.get("found"):
        print(f"  Community: no NMS Almanac record for {record['address']}.", flush=True)
        return
    system = record.get("system") or {}
    print(f"  Community (NMS Almanac): {system.get('name') or '(unnamed)'}; "
          f"suns={system.get('suns') if system.get('suns') is not None else 'unknown'}; "
          f"{len(record.get('planets', []))} planet record(s).", flush=True)
    for planet in record.get("planets", []):
        print(f"    {planet.get('portal', '')}  {planet.get('name') or '(unnamed)'}  "
              f"biome={planet.get('biome') or 'unknown'}  weather={planet.get('weather') or 'unknown'}",
              flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.configure_community_key:
        return _configure_key()
    try:
        config = config_from_args(args)
        do_community = bool(config.community_api_key) if args.community_lookup is None else args.community_lookup
        if do_community and not config.community_api_key:
            parser.error("Community lookup requires an API key. Run `python cli.py --configure-community-key` or set NMS_ALMANAC_API_KEY.")
        cache = SQLiteSystemCache(config.cache_path) if config.cache_enabled else None
        try:
            with JSBridge(args.bridge, args.node) as bridge:
                results = search_systems(config, bridge, cache)
        finally:
            if cache is not None:
                cache.close()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))

    # Always print generated matches before making any optional community calls.
    _print_generated(results, args.json)
    if not do_community:
        return 0
    if not results:
        print("No generated matches to look up in the community database.", file=sys.stderr, flush=True)
        return 0

    print("Looking up generated matches in NMS Almanac (cached records are free; uncached requests are paced and rate-limited)...",
          file=sys.stderr, flush=True)
    try:
        with CommunityClient(config) as client:
            for result in results:
                try:
                    record = client.lookup(result.portal_address, result.galaxy)
                    _print_community(record, args.json)
                except CommunityRateLimit as exc:
                    message = str(exc)
                    if exc.retry_after:
                        message += f" Retry after approximately {exc.retry_after} seconds."
                    print(f"Community lookups stopped: {message}", file=sys.stderr, flush=True)
                    break
                except CommunityLookupError as exc:
                    print(f"Community lookup failed for {result.portal_address}: {exc}", file=sys.stderr, flush=True)
                    if "API key" in str(exc):
                        break
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Community lookup unavailable: {exc}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
