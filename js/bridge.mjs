from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from config import SearchConfig


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return bool(value)


@dataclass
class SearchResult:
    address: str
    galaxy: int
    payload: dict[str, Any]

    @property
    def star_type(self) -> str | None:
        return _clean(self.payload.get("starType") or self.payload.get("star_type"))

    @property
    def race(self) -> str | None:
        return _clean(self.payload.get("race"))

    @property
    def economy(self) -> str | None:
        return _clean(self.payload.get("economy"))

    @property
    def conflict(self) -> str | None:
        return _clean(self.payload.get("conflict"))

    @property
    def pirate(self) -> bool | None:
        return _bool(self.payload.get("pirate", self.payload.get("outlaw")))

    @property
    def abandoned(self) -> bool | None:
        return _bool(self.payload.get("abandoned"))

    @property
    def uncharted(self) -> bool | None:
        return _bool(self.payload.get("uncharted"))

    @property
    def black_hole(self) -> bool | None:
        return _bool(self.payload.get("isBlackHole", self.payload.get("black_hole")))

    @property
    def atlas_system(self) -> bool | None:
        return _bool(self.payload.get("isAtlas", self.payload.get("atlas_system")))

    @property
    def suns(self) -> int | None:
        return _int(self.payload.get("suns", self.payload.get("sunCount", self.payload.get("sun_count"))))

    @property
    def planets(self) -> int | None:
        return _int(self.payload.get("planets", self.payload.get("planetCount", self.payload.get("planet_count"))))

    @property
    def moons(self) -> int | None:
        return _int(self.payload.get("moons"))

    @property
    def lush_planets(self) -> int | None:
        return _int(self.payload.get("lushPlanets", self.payload.get("lush_planets")))

    @property
    def economy_tier(self) -> int | None:
        value = self.payload.get("economyTier")
        if value is None:
            value = self.payload.get("economy_tier")
        if value is None:
            value = self.payload.get("econTier")
        if value is None:
            return None
        return _int(value)

    @property
    def conflict_tier(self) -> int | None:
        value = self.payload.get("conflictTier")
        if value is None:
            value = self.payload.get("conflict_tier")
        if value is None:
            value = self.payload.get("conTier")
        if value is None:
            return None
        return _int(value)

    @property
    def core_distance(self) -> float | None:
        coords = self.payload.get("coords")
        if not isinstance(coords, dict):
            return None

        x = _float(coords.get("x"))
        y = _float(coords.get("y"))
        z = _float(coords.get("z"))

        if x is None or y is None or z is None:
            return None

        return math.sqrt((x * x) + (y * y) + (z * z))

    def matches(self, config: SearchConfig) -> bool:
        if config.star_color is not None and self.star_type != config.star_color:
            return False

        if config.min_suns is not None:
            if self.suns is None or self.suns < config.min_suns:
                return False
        if config.exact_suns is not None:
            if self.suns is None or self.suns != config.exact_suns:
                return False

        if config.min_planets is not None:
            if self.planets is None or self.planets < config.min_planets:
                return False
        if config.exact_planets is not None:
            if self.planets is None or self.planets != config.exact_planets:
                return False

        if config.min_moons is not None:
            if self.moons is None or self.moons < config.min_moons:
                return False
        if config.max_moons is not None:
            if self.moons is not None and self.moons > config.max_moons:
                return False

        if config.min_lush_planets is not None:
            if self.lush_planets is None or self.lush_planets < config.min_lush_planets:
                return False
        if config.exact_lush_planets is not None:
            if self.lush_planets is None or self.lush_planets != config.exact_lush_planets:
                return False

        if config.economy is not None:
            if self.economy is None or self.economy != config.economy:
                return False
        if config.economy_tier is not None:
            if self.economy_tier is None or self.economy_tier != config.economy_tier:
                return False

        if config.conflict is not None:
            if self.conflict is None or self.conflict != config.conflict:
                return False
        if config.conflict_tier is not None:
            if self.conflict_tier is None or self.conflict_tier != config.conflict_tier:
                return False

        if config.race is not None:
            if self.race is None or self.race != config.race:
                return False

        if config.pirate is not None:
            if self.pirate is None or self.pirate != config.pirate:
                return False

        if config.abandoned is not None:
            if self.abandoned is None or self.abandoned != config.abandoned:
                return False

        if config.uncharted is not None:
            if self.uncharted is None or self.uncharted != config.uncharted:
                return False

        if config.black_hole is not None:
            if self.black_hole is None or self.black_hole != config.black_hole:
                return False

        if config.atlas_system is not None:
            if self.atlas_system is None or self.atlas_system != config.atlas_system:
                return False

        if config.min_core_distance is not None:
            dist = self.core_distance
            if dist is None or dist < config.min_core_distance:
                return False
        if config.max_core_distance is not None:
            dist = self.core_distance
            if dist is not None and dist > config.max_core_distance:
                return False

        return True


__all__ = ["SearchResult"]
