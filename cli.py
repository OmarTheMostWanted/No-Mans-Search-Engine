from __future__ import annotations

import argparse
import json

from cache import SQLiteSystemCache
from config import SearchConfig
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
    return parser


def config_from_args(args: argparse.Namespace) -> SearchConfig:
    values = vars(args).copy()
    for key in ("bridge", "node", "json"):
        values.pop(key)
    values["black_hole"] = values.pop("black_hole", None)
    values["atlas_system"] = values.pop("atlas_system", None)
    config = SearchConfig(**values)
    config.validate()
    return config


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
        cache = SQLiteSystemCache(config.cache_path) if config.cache_enabled else None
        try:
            with JSBridge(args.bridge, args.node) as bridge:
                results = search_systems(config, bridge, cache)
        finally:
            if cache is not None:
                cache.close()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    if args.json:
        for result in results:
            print(json.dumps({"address": result.portal_address, **result.data}, sort_keys=True))
    else:
        print(f"Found {len(results)} matching system(s).")
        for result in results:
            data = result.data
            print(f"{result.portal_address}  {data.get('name') or '(unnamed)'}  {result.star_color or '?'}  "
                  f"{result.planets} planets/{result.moons} moons  {result.race or '?'}  {result.economy or '?'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
