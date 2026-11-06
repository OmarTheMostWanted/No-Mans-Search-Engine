from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from typing import Any

from config import SearchConfig
from generator import search_systems
from cache import SQLiteSystemCache
from js_bridge import JSBridge


def _bool_arg(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"true", "yes", "1", "on"}:
        return True
    if lowered in {"false", "no", "0", "off"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search No Man's Sky systems using nms-galactic-map.")
    parser.add_argument("--galaxy", type=int, default=1, help="Human-friendly galaxy number (1-255).")
    parser.add_argument("--star-color", choices=("yellow", "red", "green", "blue"))
    parser.add_argument("--min-suns", type=int)
    parser.add_argument("--exact-suns", type=int)
    parser.add_argument("--min-planets", type=int)
    parser.add_argument("--exact-planets", type=int)
    parser.add_argument("--min-moons", type=int)
    parser.add_argument("--max-moons", type=int)
    parser.add_argument("--min-lush-planets", type=int)
    parser.add_argument("--exact-lush-planets", type=int)
    parser.add_argument("--economy")
    parser.add_argument("--economy-tier", type=int, choices=(1, 2, 3))
    parser.add_argument("--conflict")
    parser.add_argument("--conflict-tier", type=int, choices=(1, 2, 3))
    parser.add_argument("--race", choices=("gek", "vy'keen", "korvax", "uninhabited"))
    for flag in ("pirate", "abandoned", "uncharted", "black-hole", "atlas-system"):
        parser.add_argument(f"--{flag}", type=_bool_arg, metavar="BOOL", help=f"Filter by {flag.replace('-', ' ')} status.")
    parser.add_argument("--min-core-distance", type=float)
    parser.add_argument("--max-core-distance", type=float)
    parser.add_argument("--mode", dest="search_mode", choices=("random", "sequential"), default="random")
    parser.add_argument("--start-address")
    parser.add_argument("--seed", dest="random_seed", type=int)
    parser.add_argument("--duration", dest="duration_seconds", type=int, default=3600)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-systems", type=int)
    parser.add_argument("--max-matches", type=int)
    parser.add_argument("--cache", dest="cache_enabled", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cache-path", default="data/systems.sqlite3")
    parser.add_argument("--bridge", default="js/bridge.mjs")
    parser.add_argument("--node", default="node")
    parser.add_argument("--json", action="store_true", help="Print JSON lines instead of a human-readable summary.")
    return parser


def config_from_args(args: argparse.Namespace) -> SearchConfig:
    values: dict[str, Any] = vars(args).copy()
    values.pop("bridge", None)
    values.pop("node", None)
    values.pop("json", None)
    values["black_hole"] = values.pop("black_hole", None)
    values["atlas_system"] = values.pop("atlas_system", None)
    values["cache_path"] = values.get("cache_path", "data/systems.sqlite3")
    config = SearchConfig(**values)
    config.validate()
    return config


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
        bridge = JSBridge(args.bridge, args.node)
        cache_context = SQLiteSystemCache(config.cache_path) if config.cache_enabled else None
        try:
            results = search_systems(config, bridge, cache_context)
        finally:
            bridge.close()
            if cache_context is not None:
                cache_context.close()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))

    if args.json:
        for result in results:
            print(json.dumps({"address": result.address, "galaxy": result.galaxy, **result.payload}, sort_keys=True))
    else:
        print(f"Found {len(results)} matching system(s).")
        for result in results:
            print(f"{result.address}  {result.payload.get('name') or '(unnamed)'}  {result.star_type or '?'}  {result.race or '?'}  {result.economy or '?'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
