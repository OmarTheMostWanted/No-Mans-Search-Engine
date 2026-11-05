from __future__ import annotations

import random
import time
from collections.abc import Iterator, Sequence
from typing import Protocol, Any

from config import SearchConfig, galaxy_to_generator_index, normalize_portal_address
from models import SearchResult


class SystemProvider(Protocol):
    def batch(self, portal_addresses: Sequence[str], galaxy: int = 0) -> list[dict[str, Any]]: ...


class SystemCache(Protocol):
    def get(self, address: str, galaxy: int) -> dict[str, Any] | None: ...
    def set(self, address: str, galaxy: int, payload: dict[str, Any]) -> None: ...


def iter_random_addresses(seed: int | None = None) -> Iterator[str]:
    """Yield portal codes from the complete 48-bit address space."""
    rng = random.Random(seed)
    while True:
        yield f"{rng.getrandbits(48):012X}"


def iter_sequential_addresses(start_address: str) -> Iterator[str]:
    """Increment all 12 hexadecimal glyphs, wrapping at FFFFFFFFFFFF."""
    number = int(normalize_portal_address(start_address), 16)
    while True:
        yield f"{number:012X}"
        number = (number + 1) & 0xFFFFFFFFFFFF


def _batches(items: Iterator[str], size: int) -> Iterator[list[str]]:
    while batch := [next(items, None) for _ in range(size)]:
        yield [item for item in batch if item is not None]
        if len(batch) < size or batch[-1] is None:
            return


def search_systems(
    config: SearchConfig,
    bridge: SystemProvider,
    cache: SystemCache | None = None,
) -> list[SearchResult]:
    """Search address candidates via the generator bridge; cache is optional.

    ``max_systems`` counts candidates examined, including cache hits. The
    duration limit is checked between batches. Missing upstream fields never
    count as a match for a filter that requires them.
    """
    config.validate()
    addresses = (
        iter_random_addresses(config.random_seed)
        if config.search_mode == "random"
        else iter_sequential_addresses(config.start_address or "000000000000")
    )
    galaxy_index = galaxy_to_generator_index(config.galaxy)
    started = time.monotonic()
    inspected = 0
    matches: list[SearchResult] = []

    while inspected < (config.max_systems or float("inf")):
        if time.monotonic() - started >= config.duration_seconds:
            break
        take = config.batch_size
        if config.max_systems is not None:
            take = min(take, config.max_systems - inspected)
        candidates = [next(addresses) for _ in range(take)]
        payloads: dict[str, dict[str, Any]] = {}
        missing: list[str] = []

        for address in candidates:
            cached = cache.get(address, galaxy_index) if config.cache_enabled and cache else None
            if cached is None:
                missing.append(address)
            else:
                payloads[address] = cached

        if missing:
            fetched = bridge.batch(missing, galaxy=galaxy_index)
            if len(fetched) != len(missing):
                raise RuntimeError(
                    f"Bridge returned {len(fetched)} systems for {len(missing)} addresses."
                )
            for address, payload in zip(missing, fetched):
                if not isinstance(payload, dict):
                    raise TypeError("Bridge returned a system that is not an object.")
                payloads[address] = payload
                if config.cache_enabled and cache:
                    cache.set(address, galaxy_index, payload)

        for address in candidates:
            inspected += 1
            result = SearchResult.from_upstream(payloads[address], address, config.galaxy)
            if result.matches(config):
                matches.append(result)
                if config.max_matches is not None and len(matches) >= config.max_matches:
                    return matches
        if config.max_systems is not None and inspected >= config.max_systems:
            break

    return matches


__all__ = ["SearchResult", "search_systems", "iter_random_addresses", "iter_sequential_addresses"]
