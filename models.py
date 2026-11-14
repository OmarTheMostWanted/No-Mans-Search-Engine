from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from config import AppConfig, load_config
from database import SQLiteStore


class AlmanacRateLimitError(RuntimeError):
    """Raised when the local hourly request budget is exhausted."""


class AlmanacLookupError(RuntimeError):
    """Raised when the Almanac endpoint cannot be used successfully."""


@dataclass(frozen=True)
class AlmanacSystem:
    """Parsed system object returned by the Almanac API."""

    address: str
    galaxy: int
    found: bool
    system: dict[str, Any] | None
    planets: list[dict[str, Any]]
    raw: dict[str, Any]


class AlmanacClient:
    """Minimal, documented NMS Almanac API client.

    This client intentionally stays separate from generator logic. The key is
    expected to exist on disk in `config.local.json` or in the environment, and
    this class does not prompt for credentials.
    """

    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()
        if not self.config.almanac_api_key:
            raise ValueError("No Almanac API key found. Put it in config.local.json or set NMS_ALMANAC_API_KEY.")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.almanac_api_key}",
            "User-Agent": "No-Mans-Search-Engine/1.0",
        })
        self.store = SQLiteStore(self.config.db_path)
        self._timestamps: list[float] = []

    def close(self) -> None:
        self.store.close()
        self.session.close()

    def _prune_request_history(self) -> None:
        cutoff = time.monotonic() - 3600
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

    def _reserve_request_slot(self) -> None:
        self._prune_request_history()
        if len(self._timestamps) >= self.config.almanac_requests_per_hour:
            oldest = min(self._timestamps)
            wait_seconds = max(1, int(3600 - (time.monotonic() - oldest)))
            raise AlmanacRateLimitError(
                f"NMS Almanac request budget exhausted ({len(self._timestamps)}/{self.config.almanac_requests_per_hour} in the last hour). Retry in {wait_seconds} seconds."
            )
        self._timestamps.append(time.monotonic())

    def _get(self, path: str) -> dict[str, Any] | None:
        """Raw GET helper with rate-limit enforcement and caching."""

        cache_key = f"almanac:{path}"
        cached = self.store.get_cache(cache_key)
        if cached is not None:
            return cached

        self._reserve_request_slot()
        url = f"{self.config.almanac_base_url}{path.lstrip('/')}"
        try:
            response = self.session.get(url, timeout=20)
        except requests.RequestException as exc:
            raise AlmanacLookupError(f"Could not reach NMS Almanac: {exc}") from exc

        if response.status_code == 404:
            return None
        if response.status_code == 429:
            raise AlmanacRateLimitError("NMS Almanac reported a 429 rate limit response.")
        if response.status_code in (401, 403):
            raise AlmanacLookupError("The Almanac API key was rejected or the endpoint is forbidden.")
        if response.status_code >= 500:
            raise AlmanacLookupError(f"NMS Almanac server error {response.status_code}.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AlmanacLookupError("NMS Almanac returned non-JSON content.") from exc

        self.store.set_cache(cache_key, payload, ttl_seconds=3600 * 24)
        return payload

    def _flatten_system(self, raw: dict[str, Any], address: str, galaxy: int) -> dict[str, Any]:
        system = raw.get("system") if isinstance(raw, dict) else None
        if not isinstance(system, dict):
            system = raw if isinstance(raw, dict) else {}

        payload = {
            "name": (system.get("names") or {}).get("given") or (system.get("names") or {}).get("game"),
            "game_name": (system.get("names") or {}).get("game"),
            "star": system.get("star"),
            "spectral_class": system.get("spectral_class"),
            "suns": system.get("suns"),
            "race": system.get("race"),
            "economy": (system.get("economy") or {}).get("name") if isinstance(system.get("economy"), dict) else system.get("economy"),
            "wealth": (system.get("wealth") or {}).get("name") if isinstance(system.get("wealth"), dict) else system.get("wealth"),
            "conflict": (system.get("conflict") or {}).get("name") if isinstance(system.get("conflict"), dict) else system.get("conflict"),
            "discoverer": (system.get("discovery") or {}).get("discoverer") if isinstance(system.get("discovery"), dict) else None,
            "platform": (system.get("discovery") or {}).get("platform") if isinstance(system.get("discovery"), dict) else None,
            "discovered": (system.get("discovery") or {}).get("discovered") if isinstance(system.get("discovery"), dict) else None,
            "sell": ((system.get("trade") or {}).get("sell_percent")),
            "buy": ((system.get("trade") or {}).get("buy_percent")),
            "demand": (system.get("trade") or {}).get("demand"),
            "raw": system,
        }
        return payload

    def _flatten_planets(self, record: dict[str, Any], galaxy: int, parent_address: str) -> list[dict[str, Any]]:
        planets: list[dict[str, Any]] = []
        bodies = record.get("bodies") or []
        for body in bodies:
            if not isinstance(body, dict) or not body.get("portal"):
                continue
            portal = str(body["portal"]).upper()
            planet_data = {
                "portal": portal,
                "name": (body.get("names") or {}).get("given") or (body.get("names") or {}).get("game") or body.get("name"),
                "biome": body.get("biome"),
                "weather": body.get("weather"),
                "water": body.get("water"),
                "moon_of": (body.get("body") or {}).get("moon_of") if isinstance(body.get("body"), dict) else None,
                "raw": body,
                "system_address": parent_address,
                "galaxy": galaxy,
            }
            self.store.save_almanac_planet(portal, galaxy, parent_address, planet_data)
            planets.append(planet_data)
        return planets

    def lookup_system(self, address: str, galaxy: int = 0, *, use_cache: bool = True) -> dict[str, Any]:
        """Look up one system in the NMS Almanac.

        Input shape:
        - address: 12-char portal address
        - galaxy: 0-based galaxy index

        Output shape:
        - dict with `found`, `source`, `address`, `galaxy`, `system`, `planets`, `raw`
        """

        normalized = address.strip().upper()
        if len(normalized) != 12:
            raise ValueError("Almanac lookup requires a 12-character portal address")

        if use_cache:
            cached = self.store.get_almanac_system(normalized, galaxy)
            if cached is not None:
                return cached

        query = f"systems/{quote(normalized)}?galaxy={galaxy + 1}"
        payload = self._get(query)

        if payload is None:
            result = {
                "found": False,
                "source": "nmsalmanac",
                "address": normalized,
                "galaxy": galaxy,
                "system": None,
                "planets": [],
                "raw": {},
            }
            self.store.save_almanac_system(normalized, galaxy, result)
            return result

        system = self._flatten_system(payload, normalized, galaxy)
        body_items = self._flatten_planets(payload, galaxy, normalized)

        result = {
            "found": bool(payload.get("found", True)),
            "source": "nmsalmanac",
            "address": normalized,
            "galaxy": galaxy,
            "system": system,
            "planets": body_items,
            "raw": payload,
        }

        self.store.save_almanac_system(normalized, galaxy, result)
        return result


def _main() -> None:
    config = load_config()
    client = AlmanacClient(config)
    try:
        result = client.lookup_system("0807F07FFFFF", galaxy=0)
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        client.close()


if __name__ == "__main__":
    _main()
