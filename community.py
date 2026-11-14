from __future__ import annotations

from pathlib import Path
from typing import Any

from config import AppConfig, load_config
from js_bridge import NodeBridge


class NMSMapClient:
    """Gateway to the upstream JavaScript generator.

    The upstream logic is not reimplemented here. This class calls the upstream
    module and normalizes its results for Python.
    """

    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()
        repo_root = Path(__file__).resolve().parent
        bridge_path = repo_root / self.config.map_bridge_path
        core_path = repo_root / self.config.map_core_path
        self.bridge = NodeBridge(bridge_path, core_path)

    def lookup_system(self, address: str, galaxy: int = 0) -> dict[str, Any]:
        """Look up one generated system by portal address.

        Input:
        - address: 12-char portal address
        - galaxy: integer galaxy index, 0 = Euclid

        Output:
        - exact JS result from the upstream library, normalized to Python types
        """

        raw = self.bridge.lookup(str(address).upper(), galaxy)
        return self._normalize(raw)

    def _normalize(self, item: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise TypeError(f"Expected dict from generator but got {type(item)!r}")
        normalized = dict(item)
        normalized["address"] = str(normalized.get("address") or "").upper()
        normalized["galaxy"] = int(normalized.get("galaxy", 0))
        normalized["planets"] = int(normalized.get("planets", 0))
        normalized["moons"] = int(normalized.get("moons", 0))
        normalized["star_type"] = str(normalized.get("starType") or normalized.get("star_type") or "unknown").lower()
        normalized["name"] = normalized.get("name")
        normalized["region"] = normalized.get("region")
        normalized["race"] = normalized.get("race")
        normalized["economy"] = normalized.get("economy")
        normalized["economy_type"] = normalized.get("econType")
        normalized["economy_tier"] = int(normalized.get("econTier", 0))
        normalized["economy_desc"] = normalized.get("econDesc")
        normalized["sell"] = normalized.get("sell")
        normalized["buy"] = normalized.get("buy")
        normalized["conflict"] = normalized.get("conflict")
        normalized["conflict_tier"] = int(normalized.get("conTier", 0))
        normalized["abandoned"] = bool(normalized.get("abandoned", False))
        normalized["uncharted"] = bool(normalized.get("uncharted", False))
        normalized["outlaw"] = bool(normalized.get("outlaw", False))
        normalized["is_black_hole"] = bool(normalized.get("isBlackHole", False))
        normalized["is_atlas"] = bool(normalized.get("isAtlas", False))
        normalized["coords"] = normalized.get("coords") or {}
        normalized["planet_names"] = normalized.get("planetNames") or []
        normalized["raw"] = normalized.copy()
        return normalized


__all__ = ["NMSMapClient"]
