from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Sequence

from config import SearchConfig, normalize_portal_address, galaxy_to_generator_index


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
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
        return _stringify(self.payload.get("starType") or self.payload.get("star_type"))

    @property
    def race(self) -> str | None:
        return _stringify(self.payload.get("race"))

    @property
    def economy(self) -> str | None:
        return _stringify(self.payload.get("economy"))

    @property
    def conflict(self) -> str | None:
        return _stringify(self.payload.get("conflict"))

    @property
    def pirate(self) -> bool | None:
        return _coerce_bool(self.payload.get("pirate", self.payload.get("outlaw")))

    @property
    def abandoned(self) -> bool | None:
        return _coerce_bool(self.payload.get("abandoned"))

    @property
    def uncharted(self) -> bool | None:
        return _coerce_bool(self.payload.get("uncharted"))

    @property
    def black_hole(self) -> bool | None:
        return _coerce_bool(self.payload.get("isBlackHole", self.payload.get("black_hole")))

    @property
    def atlas_system(self) -> bool | None:
        return _coerce_bool(self.payload.get("isAtlas", self.payload.get("atlas_system")))

    @property
    def suns(self) -> int | None:
        return _coerce_int(self.payload.get("suns", self.payload.get("sunCount", self.payload.get("sun_count"))))

    @property
    def planets(self) -> int | None:
        return _coerce_int(self.payload.get("planets", self.payload.get("planetCount", self.payload.get("planet_count"))))

    @property
    def moons(self) -> int | None:
        return _coerce_int(self.payload.get("moons"))

    @property
    def lush_planets(self) -> int | None:
        return _coerce_int(self.payload.get("lushPlanets", self.payload.get("lush_planets")))

    @property
    def economy_tier(self) -> int | None:
        value = self.payload.get("economyTier")
        if value is None:
            value = self.payload.get("economy_tier")
        if value is None:
            value = self.payload.get("econTier")
        if value is None:
            return None
        tier = _coerce_int(value)
        return tier if tier is not None else None

    @property
    def conflict_tier(self) -> int | None:
        value = self.payload.get("conflictTier")
        if value is None:
            value = self.payload.get("conflict_tier")
        if value is None:
            value = self.payload.get("conTier")
        if value is None:
            return None
        tier = _coerce_int(value)
        return tier if tier is not None else None

    @property
    def core_distance(self) -> float | None:
        coords = self.payload.get("coords")
        if not isinstance(coords, dict):
            return None

        x = _coerce_float(coords.get("x"))
        y = _coerce_float(coords.get("y"))
        z = _coerce_float(coords.get("z"))

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


class JSBridge:
    """Thin wrapper around the Node bridge used by the submodule."""

    def __init__(
        self,
        bridge_path: str = "js/bridge.mjs",
        node_bin: str = "node",
    ) -> None:
        self.bridge_path = bridge_path
        self.node_bin = node_bin

        self.process = __import__("subprocess").Popen(
            [self.node_bin, self.bridge_path],
            stdin=__import__("subprocess").PIPE,
            stdout=__import__("subprocess").PIPE,
            stderr=__import__("subprocess").PIPE,
            text=True,
            bufsize=1,
        )

    def _send(self, payload: dict[str, Any]) -> Any:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("Bridge process I/O is not available.")

        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

        raw = self.process.stdout.readline()
        if not raw:
            error_text = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"Bridge closed unexpectedly: {error_text}")

        response = json.loads(raw)
        if not response.get("success"):
            raise RuntimeError(response.get("error", "Bridge call failed"))

        return response.get("data")

    def lookup(self, portal_address: str, galaxy: int = 0) -> dict[str, Any]:
        address = normalize_portal_address(portal_address)
        result = self._send({"action": "lookup", "portal_code": address, "galaxy": galaxy})
        if isinstance(result, dict):
            return result
        raise TypeError("Bridge lookup returned a non-object result.")

    def batch(self, portal_addresses: Sequence[str], galaxy: int = 0) -> list[dict[str, Any]]:
        if not portal_addresses:
            return []

        normalized = [normalize_portal_address(address) for address in portal_addresses]
        result = self._send(
            {
                "action": "batch",
                "systems": [{"portal_code": address, "galaxy": galaxy} for address in normalized],
            }
        )

        if result is None:
            return []
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            return [result]
        raise TypeError("Bridge batch returned an unexpected payload type.")

    def close(self) -> None:
        try:
            if self.process.stdin is not None:
                self.process.stdin.close()
        except Exception:
            pass

        try:
            if self.process.stdout is not None:
                self.process.stdout.close()
        except Exception:
            pass

        try:
            if self.process.stderr is not None:
                self.process.stderr.close()
        except Exception:
            pass

        try:
            self.process.wait(timeout=2)
        except Exception:
            pass


def _batched(items: Sequence[str], batch_size: int) -> Iterator[list[str]]:
    for index in range(0, len(items), batch_size):
        yield list(items[index : index + batch_size])


def _iter_random_addresses(config: SearchConfig, limit: int | None = None) -> Iterator[str]:
    rng = __import__("random").Random(config.random_seed)
    produced = 0

    while True:
        if limit is not None and produced >= limit:
            break

        yield format(rng.getrandbits(48), "012X")
        produced += 1


def _iter_sequential_addresses(start_address: str, limit: int | None = None) -> Iterator[str]:
    start = int(normalize_portal_address(start_address), 16)
    produced = 0

    while True:
        if limit is not None and produced >= limit:
            break

        yield format(start, "012X")
        start += 1
        produced += 1


def _iter_addresses(config: SearchConfig, limit: int | None = None) -> Iterator[str]:
    if config.search_mode == "random":
        yield from _iter_random_addresses(config, limit=limit)
        return

    if config.search_mode == "sequential":
        if config.start_address is None:
            raise ValueError("Sequential search requires a starting portal address.")
        yield from _iter_sequential_addresses(config.start_address, limit=limit)
        return

    raise ValueError(f"Unsupported search mode: {config.search_mode}")


def search_systems(config: SearchConfig, bridge: JSBridge | None = None) -> list[SearchResult]:
    config.validate()

    if bridge is None:
        bridge = JSBridge()

    addresses: list[str]
    if config.search_mode == "random":
        limit = config.max_systems
        addresses = list(_iter_addresses(config, limit=limit))
    else:
        limit = config.max_systems
        addresses = list(_iter_addresses(config, limit=limit))

    galaxy_index = galaxy_to_generator_index(config.galaxy)
    checked = 0
    matches: list[SearchResult] = []

    for batch in _batched(addresses, config.batch_size):
        batch_data = bridge.batch(batch, galaxy=galaxy_index)
        if not isinstance(batch_data, list):
            batch_data = [batch_data]

        for payload in batch_data:
            checked += 1

            if not isinstance(payload, dict):
                continue

            result = SearchResult(
                address=str(payload.get("address") or payload.get("portal_code") or ""),
                galaxy=config.galaxy,
                payload=payload,
            )

            if result.matches(config):
                matches.append(result)

            if config.max_matches is not None and len(matches) >= config.max_matches:
                return matches

            if config.max_systems is not None and checked >= config.max_systems:
                return matches

    return matches


__all__ = [
    "SearchResult",
    "JSBridge",
    "search_systems",
    "_iter_random_addresses",
    "_iter_sequential_addresses",
]


if __name__ == "__main__":
    cfg = SearchConfig(
        galaxy=1,
        star_color="yellow",
        min_planets=3,
        max_moons=2,
        search_mode="random",
        random_seed=42,
        batch_size=10,
        max_systems=20,
        max_matches=5,
    )
    results = search_systems(cfg)
    for result in results:
        print(result.address, result.race, result.economy, result.conflict)
"path":"models.py