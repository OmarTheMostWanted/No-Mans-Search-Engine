from __future__ import annotations

from typing import Any

from config import AppConfig, normalize_address, validate_galaxy
from database import SQLiteStore
from js_bridge import JSBridge


class NMSMapClient:
    """Calls the real upstream generator; it does not reimplement generation."""
    def __init__(self, config: AppConfig, store: SQLiteStore):
        self.config=config; self.store=store; self.bridge=JSBridge(config.bridge_path,config.node_command)

    def close(self) -> None: self.bridge.close()
    def __enter__(self) -> "NMSMapClient": return self
    def __exit__(self,*_: object) -> None: self.close()

    def lookup_system(self, address: str, galaxy: int = 0, *, use_cache: bool = True) -> dict[str, Any]:
        """Input: address (12 hex glyphs), galaxy (zero-based integer 0..255).
        Output: normalized dict containing name/region/star/body/economy/status/coordinates,
        `bodies` as indexed name records, and `raw` with the complete upstream object.
        """
        address=normalize_address(address); galaxy=validate_galaxy(galaxy)
        if use_cache:
            cached=self.store.get_generated(address,galaxy)
            if cached is not None: return cached
        raw=self.bridge.lookup(address,galaxy)
        if raw.get("address","").upper()!=address or raw.get("galaxy")!=galaxy:
            raise ValueError("Generator response address or galaxy does not match the request")
        names=raw.get("planetNames") or []
        bodies=[{"index":i+1,"name":name} for i,name in enumerate(names)]
        record={
            "address":address,"galaxy":galaxy,"name":raw.get("name"),"region":raw.get("region"),
            "star_type":raw.get("starType"),"planets":raw.get("planets"),"moons":raw.get("moons"),
            "gas_giant":raw.get("gasGiant"),"safe_start":raw.get("safeStart"),"planet_index":raw.get("planetIndex"),
            "race":raw.get("race"),"economy":raw.get("economy"),"economy_type":raw.get("econType"),
            "economy_tier":raw.get("econTier"),"economy_description":raw.get("econDesc"),
            "sell":raw.get("sell"),"buy":raw.get("buy"),"conflict":raw.get("conflict"),
            "conflict_tier":raw.get("conTier"),"abandoned":raw.get("abandoned"),"uncharted":raw.get("uncharted"),
            "outlaw":raw.get("outlaw"),"is_black_hole":raw.get("isBlackHole"),"is_atlas":raw.get("isAtlas"),
            "coords":raw.get("coords"),"bodies":bodies,"raw":raw,
        }
        self.store.save_generated(record)
        return record

__all__=["NMSMapClient"]
