from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from config import SearchConfig, normalize_portal_address


def _text(value: Any) -> str | None:
    return str(value).strip().lower() if value is not None and str(value).strip() else None


def _number(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return None
    return None


@dataclass(frozen=True)
class SearchResult:
    """Normalized system record; payload preserves all upstream fields."""

    address: str
    galaxy: int
    payload: dict[str, Any]

    @classmethod
    def from_upstream(cls, payload: dict[str, Any], address: str, galaxy: int) -> "SearchResult":
        if not isinstance(payload, dict):
            raise TypeError("Upstream system must be a JSON object.")
        upstream_address = payload.get("address", address)
        upstream_galaxy = payload.get("galaxy", galaxy)
        normalized = normalize_portal_address(str(upstream_address))
        if normalized != normalize_portal_address(address):
            raise ValueError(f"Bridge address mismatch: requested {address}, received {normalized}.")
        if int(upstream_galaxy) != galaxy - 1:
            raise ValueError(
                f"Bridge galaxy mismatch: expected generator index {galaxy - 1}, got {upstream_galaxy}."
            )
        return cls(normalized, galaxy, payload)

    @property
    def star_type(self) -> str | None:
        return _text(self.payload.get("starType"))

    @property
    def race(self) -> str | None:
        return _text(self.payload.get("race"))

    @property
    def economy(self) -> str | None:
        return _text(self.payload.get("economy"))

    @property
    def conflict(self) -> str | None:
        return _text(self.payload.get("conflict"))

    @property
    def suns(self) -> int | None:
        # nms-lookup.js does not currently return a sun count.
        return _number(self.payload.get("suns"))

    @property
    def planets(self) -> int | None:
        return _number(self.payload.get("planets"))

    @property
    def moons(self) -> int | None:
        return _number(self.payload.get("moons"))

    @property
    def lush_planets(self) -> int | None:
        # Biomes are not part of nms-lookup.js's response, so this is
        # intentionally unknown unless a future/upstream payload supplies it.
        return _number(self.payload.get("lushPlanets"))

    @property
    def economy_tier(self) -> int | None:
        # Upstream econTier is 0=low, 1=medium, 2=high. Config uses 1..3.
        value = _number(self.payload.get("econTier"))
        return value + 1 if value is not None and 0 <= value <= 2 else None

    @property
    def conflict_tier(self) -> int | None:
        value = _number(self.payload.get("conTier"))
        return value + 1 if value is not None and 0 <= value <= 2 else None

    @property
    def pirate(self) -> bool | None:
        return _flag(self.payload.get("outlaw"))

    @property
    def abandoned(self) -> bool | None:
        return _flag(self.payload.get("abandoned"))

    @property
    def uncharted(self) -> bool | None:
        return _flag(self.payload.get("uncharted"))

    @property
    def black_hole(self) -> bool | None:
        return _flag(self.payload.get("isBlackHole"))

    @property
    def atlas_system(self) -> bool | None:
        return _flag(self.payload.get("isAtlas"))

    @property
    def core_distance(self) -> float | None:
        coords = self.payload.get("coords")
        if not isinstance(coords, dict):
            return None
        try:
            x, y, z = (float(coords[axis]) for axis in ("x", "y", "z"))
        except (KeyError, TypeError, ValueError):
            return None
        return math.sqrt(x * x + y * y + z * z)

    def matches(self, config: SearchConfig) -> bool:
        checks = (
            (config.star_color, self.star_type, "eq"),
            (config.economy, self.economy, "eq"),
            (config.conflict, self.conflict, "eq"),
            (config.race, self.race, "eq"),
            (config.exact_suns, self.suns, "eq"),
            (config.exact_planets, self.planets, "eq"),
            (config.exact_lush_planets, self.lush_planets, "eq"),
            (config.economy_tier, self.economy_tier, "eq"),
            (config.conflict_tier, self.conflict_tier, "eq"),
            (config.pirate, self.pirate, "eq"),
            (config.abandoned, self.abandoned, "eq"),
            (config.uncharted, self.uncharted, "eq"),
            (config.black_hole, self.black_hole, "eq"),
            (config.atlas_system, self.atlas_system, "eq"),
            (config.min_suns, self.suns, "min"),
            (config.min_planets, self.planets, "min"),
            (config.min_moons, self.moons, "min"),
            (config.min_lush_planets, self.lush_planets, "min"),
            (config.max_moons, self.moons, "max"),
            (config.min_core_distance, self.core_distance, "min"),
            (config.max_core_distance, self.core_distance, "max"),
        )
        for expected, actual, operation in checks:
            if expected is None:
                continue
            if actual is None:
                return False
            if operation == "eq" and isinstance(expected, str):
                if actual != expected.lower():
                    return False
            elif operation == "eq" and actual != expected:
                return False
            elif operation == "min" and actual < expected:
                return False
            elif operation == "max" and actual > expected:
                return False
        return True


__all__ = ["SearchResult"]
