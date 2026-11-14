from __future__ import annotations

import random
from collections.abc import Iterator
from typing import Any

from config import AppConfig, normalize_address, validate_galaxy
from database import SQLiteStore
from nms_map_client import NMSMapClient


class SearchFilters:
    """Optional exact/range filters supported by `search_systems`.

    Fields: star_type, race, economy, conflict (case-insensitive exact strings);
    min_planets, max_planets, min_moons, max_moons (inclusive integer bounds);
    abandoned, uncharted, outlaw, is_black_hole, is_atlas (optional booleans).
    """
    def __init__(self, *, star_type: str|None=None, race: str|None=None, economy: str|None=None,
                 conflict: str|None=None, min_planets: int|None=None,max_planets: int|None=None,
                 min_moons: int|None=None,max_moons: int|None=None,abandoned: bool|None=None,
                 uncharted: bool|None=None,outlaw: bool|None=None,is_black_hole: bool|None=None,is_atlas: bool|None=None):
        self.values=locals().copy(); self.values.pop("self")

    def matches(self, record: dict[str,Any]) -> bool:
        for field in ("star_type","race","economy","conflict"):
            expected=self.values[field]
            if expected is not None and str(record.get(field) or "").casefold()!=expected.casefold(): return False
        for field,op in (("min_planets","min"),("max_planets","max"),("min_moons","min"),("max_moons","max")):
            expected=self.values[field]
            if expected is not None:
                value=record.get("planets" if "planets" in field else "moons")
                if value is None or (op=="min" and value<expected) or (op=="max" and value>expected): return False
        for field in ("abandoned","uncharted","outlaw","is_black_hole","is_atlas"):
            expected=self.values[field]
            if expected is not None and record.get(field) is not expected: return False
        return True


def iter_addresses(mode: str="random", *, seed: int|None=None,start_address: str|None=None) -> Iterator[str]:
    """Yield canonical system portal codes (leading planet glyph zero); mode random or sequential."""
    if mode=="random":
        rng=random.Random(seed)
        while True: yield f"0{rng.getrandbits(44):011X}"
    elif mode=="sequential":
        if start_address is None: raise ValueError("Sequential mode requires start_address")
        value=int(normalize_address(start_address),16)&0xFFFFFFFFFFF
        while True:
            yield f"0{value:011X}"; value=(value+1)&0xFFFFFFFFFFF
    else: raise ValueError("mode must be 'random' or 'sequential'")


def lookup_system(address: str, galaxy: int=0, *, config: AppConfig|None=None, store: SQLiteStore|None=None, use_cache: bool=True) -> dict[str,Any]:
    """Input: portal address and zero-based galaxy. Output: full normalized system dict; cached in SQLite."""
    config=config or __import__("config").load_config(); own=store is None; store=store or SQLiteStore(config.db_path)
    client=NMSMapClient(config,store)
    try: return client.lookup_system(address,validate_galaxy(galaxy),use_cache=use_cache)
    finally:
        client.close()
        if own: store.close()


def search_systems(galaxy: int=0, *, filters: SearchFilters|None=None, mode: str="random", seed: int|None=None,
                   start_address: str|None=None,max_results: int=20,max_checks: int=2000,
                   config: AppConfig|None=None,store: SQLiteStore|None=None) -> list[dict[str,Any]]:
    """Search address candidates. Input limits must be positive; output is a list of full system dicts."""
    validate_galaxy(galaxy)
    if max_results<1 or max_checks<1: raise ValueError("max_results and max_checks must be positive")
    config=config or __import__("config").load_config(); own=store is None; store=store or SQLiteStore(config.db_path)
    results=[]
    try:
        with NMSMapClient(config,store) as client:
            for i,address in enumerate(iter_addresses(mode,seed=seed,start_address=start_address)):
                if i>=max_checks or len(results)>=max_results: break
                record=client.lookup_system(address,galaxy)
                if filters is None or filters.matches(record): results.append(record)
        return results
    finally:
        if own: store.close()

__all__=["SearchFilters","iter_addresses","lookup_system","search_systems"]
