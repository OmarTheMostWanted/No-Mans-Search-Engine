from __future__ import annotations

import argparse
import json

from community import AlmanacClient
from config import load_config
from database import SQLiteStore
from generator import SearchFilters, lookup_system, search_systems


def parser() -> argparse.ArgumentParser:
    """Build CLI parser. No key or API rate-limit flags are provided; use config.local.json."""
    root=argparse.ArgumentParser(description="Look up and search NMS systems")
    commands=root.add_subparsers(dest="command",required=True)
    for name in ("lookup","almanac"):
        p=commands.add_parser(name); p.add_argument("address"); p.add_argument("--galaxy",type=int,default=0); p.add_argument("--json",action="store_true")
    p=commands.add_parser("search"); p.add_argument("--galaxy",type=int,default=0); p.add_argument("--mode",choices=("random","sequential"),default="random")
    p.add_argument("--seed",type=int); p.add_argument("--start-address"); p.add_argument("--max-results",type=int,default=20); p.add_argument("--max-checks",type=int,default=2000)
    p.add_argument("--star-type"); p.add_argument("--race"); p.add_argument("--economy"); p.add_argument("--conflict")
    p.add_argument("--min-planets",type=int); p.add_argument("--max-planets",type=int); p.add_argument("--min-moons",type=int); p.add_argument("--max-moons",type=int)
    for flag in ("abandoned","uncharted","outlaw","is-black-hole","is-atlas"): p.add_argument("--"+flag,action="store_true",default=None)
    p.add_argument("--json",action="store_true")
    return root


def main(argv: list[str]|None=None) -> int:
    args=parser().parse_args(argv); config=load_config()
    if args.command=="lookup":
        with SQLiteStore(config.db_path) as store: result=lookup_system(args.address,args.galaxy,config=config,store=store)
    elif args.command=="almanac":
        with SQLiteStore(config.db_path) as store, AlmanacClient(config,store) as client: result=client.lookup_system(args.address,args.galaxy)
    else:
        values={k:getattr(args,k.replace("-","_"),None) for k in ()}
        filters=SearchFilters(star_type=args.star_type,race=args.race,economy=args.economy,conflict=args.conflict,
            min_planets=args.min_planets,max_planets=args.max_planets,min_moons=args.min_moons,max_moons=args.max_moons,
            abandoned=args.abandoned,uncharted=args.uncharted,outlaw=args.outlaw,is_black_hole=args.is_black_hole,is_atlas=args.is_atlas)
        with SQLiteStore(config.db_path) as store: result=search_systems(args.galaxy,filters=filters,mode=args.mode,seed=args.seed,start_address=args.start_address,max_results=args.max_results,max_checks=args.max_checks,config=config,store=store)
    if args.json: print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    else: print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
