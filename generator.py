from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import load_config
from generator import SearchFilters, lookup_system, search_systems
from community import AlmanacClient
from database import SQLiteStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No Man's Sky system lookup and search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lookup_parser = subparsers.add_parser("lookup", help="Lookup one system by portal address")
    lookup_parser.add_argument("--address", required=True, help="12-character portal address, e.g. 0807F07FFFFF")
    lookup_parser.add_argument("--galaxy", type=int, default=0, help="Galaxy index (0 = Euclid, 0-255)")
    lookup_parser.add_argument("--json", action="store_true", help="Emit JSON instead of pretty text")

    search_parser = subparsers.add_parser("search", help="Search many systems with filters")
    search_parser.add_argument("--galaxy", type=int, default=0, help="Galaxy index (0 = Euclid, 0-255)")
    search_parser.add_argument("--mode", choices=("random", "sequential"), default="random")
    search_parser.add_argument("--seed", type=int, help="Random seed for reproducible search")
    search_parser.add_argument("--start-address", help="12-character start address when --mode sequential")
    search_parser.add_argument("--max-results", type=int, default=20, help="Number of matches to return")
    search_parser.add_argument("--max-checks", type=int, default=2000, help="Number of systems to inspect")
    search_parser.add_argument("--star-color", choices=("yellow", "green", "blue", "red", "purple"))
    search_parser.add_argument("--min-planets", type=int)
    search_parser.add_argument("--max-planets", type=int)
    search_parser.add_argument("--min-moons", type=int)
    search_parser.add_argument("--max-moons", type=int)
    search_parser.add_argument("--race", choices=("gek", "vy'keen", "korvax", "uninhabited"))
    search_parser.add_argument("--economy")
    search_parser.add_argument("--conflict")
    search_parser.add_argument("--is-black-hole", action="store_true")
    search_parser.add_argument("--is-atlas", action="store_true")
    search_parser.add_argument("--json", action="store_true")

    almanac_parser = subparsers.add_parser("almanac", help="Lookup one system in the NMS Almanac API")
    almanac_parser.add_argument("--address", required=True, help="12-character portal address")
    almanac_parser.add_argument("--galaxy", type=int, default=0, help="Galaxy index (0 = Euclid, 0-255)")
    almanac_parser.add_argument("--json", action="store_true")

    return parser


def _render_system(record: dict) -> str:
    coords = record.get("coords") or {}
    return (
        f"{record.get('address')} | "
        f"{record.get('name') or 'unnamed'} | "
        f"star={record.get('star_type') or '?'} | "
        f"planets={record.get('planets')} | "
        f"moons={record.get('moons')} | "
        f"race={record.get('race') or '?'} | "
        f"economy={record.get('economy') or '?'} | "
        f"coords=({coords.get('x')}, {coords.get('y')}, {coords.get('z')})"
    )


def _run_lookup(args: argparse.Namespace) -> int:
    config = load_config()
    store = SQLiteStore(config.db_path)
    try:
        record = lookup_system(args.address, galaxy=args.galaxy, store=store)
    finally:
        store.close()

    if args.json:
        print(json.dumps(record, sort_keys=True, indent=2))
    else:
        print(_render_system(record))
    return 0


def _run_search(args: argparse.Namespace) -> int:
    filters = SearchFilters(
        star_color=args.star_color,
        min_planets=args.min_planets,
        max_planets=args.max_planets,
        min_moons=args.min_moons,
        max_moons=args.max_moons,
        race=args.race,
        economy=args.economy,
        conflict=args.conflict,
        is_black_hole=args.is_black_hole,
        is_atlas=args.is_atlas,
    )

    config = load_config()
    store = SQLiteStore(config.db_path)
    try:
        results = search_systems(
            galaxy=args.galaxy,
            filters=filters,
            mode=args.mode,
            seed=args.seed,
            start_address=args.start_address,
            max_results=args.max_results,
            max_checks=args.max_checks,
            store=store,
        )
    finally:
        store.close()

    if args.json:
        print(json.dumps(results, sort_keys=True, indent=2))
    else:
        if not results:
            print("No matching systems found.")
            return 0
        for item in results:
            print(_render_system(item))
    return 0


def _run_almanac(args: argparse.Namespace) -> int:
    config = load_config()
    client = AlmanacClient(config)
    try:
        record = client.lookup_system(args.address, galaxy=args.galaxy, use_cache=True)
    finally:
        client.close()

    if args.json:
        print(json.dumps(record, sort_keys=True, indent=2))
    else:
        if record.get("found"):
            system = record.get("system") or {}
            print(f"{record.get('address')} | {system.get('name') or 'unnamed'} | {system.get('star') or '?'}")
            for planet in record.get("planets") or []:
                print(f"  - {planet.get('portal')} | {planet.get('name') or 'unnamed'} | biome={planet.get('biome') or '?'} | weather={planet.get('weather') or '?'}")
        else:
            print(f"No Almanac result found for {args.address} in galaxy {args.galaxy}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "lookup":
        return _run_lookup(args)
    if args.command == "search":
        return _run_search(args)
    if args.command == "almanac":
        return _run_almanac(args)

    parser.error(f"Unsupported command: {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
