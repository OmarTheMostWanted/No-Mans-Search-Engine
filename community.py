from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from config import AppConfig, canonical_system_address, normalize_address, validate_galaxy
from database import SQLiteStore


class AlmanacError(RuntimeError):
    """NMS Almanac request, response or local rate-limit failure."""


class AlmanacClient:
    """Read-only client for the raw NMS Almanac API; separate from generation."""

    def __init__(self, config: AppConfig, store: SQLiteStore | None = None, *, timeout: float = 15):
        self.config = config
        self._own_store = store is None
        self.store = store or SQLiteStore(config.db_path)
        self.timeout = timeout
        if not config.almanac_api_key:
            if self._own_store:
                self.store.close()
            raise ValueError("Add almanac_api_key to config.local.json before Almanac lookups")

    def close(self) -> None:
        if self._own_store:
            self.store.close()

    def __enter__(self) -> "AlmanacClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get_json(self, path: str) -> Any:
        cache_key = "almanac:" + path
        cache_hit, cached_value = self.store.get_cache(cache_key)
        if cache_hit:
            if isinstance(cached_value, dict) and cached_value.get("__not_found__") is True:
                return None
            return cached_value

        self.store.reserve_api_request(self.config.almanac_requests_per_hour)
        headers = {"Accept": "application/json", "User-Agent": "NMS-System-Search/1.0"}
        if self.config.almanac_api_key:
            headers["Authorization"] = "Bearer " + self.config.almanac_api_key
        try:
            with urlopen(Request(self.config.almanac_base_url + path, headers=headers), timeout=self.timeout) as response:
                value = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                self.store.set_cache(cache_key, {"__not_found__": True}, 86400)
                return None
            if exc.code == 429:
                retry = exc.headers.get("Retry-After", "unknown") if exc.headers else "unknown"
                raise AlmanacError(f"Almanac returned HTTP 429; Retry-After: {retry}") from exc
            if exc.code in (401, 403):
                raise AlmanacError(f"Almanac rejected the API key (HTTP {exc.code})") from exc
            raise AlmanacError(f"Almanac HTTP error {exc.code}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AlmanacError(f"Almanac request failed: {exc}") from exc
        if not isinstance(value, (dict, list)):
            raise AlmanacError("Almanac returned JSON with an unexpected top-level type")
        self.store.set_cache(cache_key, value, 30 * 86400)
        return value

    def lookup_system(self, address: str, galaxy: int = 0, *, use_cache: bool = True) -> dict[str, Any]:
        """Input: address (12 hex), galaxy (upstream index 0..255). Output includes parsed data and raw responses.

        System records use a canonical address with planet glyph zero, matching
        Almanac's system-level identity and sharing cached records across body
        portal-address variants.
        """
        address = canonical_system_address(address)
        galaxy = validate_galaxy(galaxy)
        if use_cache:
            cached = self.store.get_almanac(address, galaxy)
            if cached is not None:
                return cached
        raw = self._get_json(f"systems/{quote(address)}?galaxy={galaxy + 1}")
        if raw is None:
            result = {"found": False, "source": "nmsalmanac", "address": address, "galaxy": galaxy,
                      "system": None, "bodies": [], "raw": {"system": None, "bodies": []}}
            self.store.save_almanac(result)
            return result
        system = raw.get("system") if isinstance(raw.get("system"), dict) else raw
        bodies = []
        for item in system.get("bodies", raw.get("bodies", [])) or []:
            if not isinstance(item, dict) or not item.get("portal"):
                continue
            portal = normalize_address(str(item["portal"]))
            planet = self._get_json(f"planets/{quote(portal)}?galaxy={galaxy + 1}")
            if planet is None:
                planet = item
            elif isinstance(planet.get("planet"), dict):
                planet = planet["planet"]
            names = planet.get("names") if isinstance(planet.get("names"), dict) else {}
            bodies.append({
                "portal": portal, "index": int(portal[0], 16),
                "name": names.get("given") or names.get("game") or item.get("name"),
                "game_name": names.get("game"), "biome": planet.get("biome"), "size": planet.get("size"),
                "weather": planet.get("weather"), "sentinels": planet.get("sentinels"), "water": planet.get("water"),
                "moon_of": (planet.get("body") or {}).get("moon_of") if isinstance(planet.get("body"), dict) else None,
                "fauna": planet.get("fauna"), "flora": planet.get("flora"), "resources": planet.get("resources"),
                "pictures": planet.get("pictures"), "colours": planet.get("colours"), "raw": planet,
            })
        names = system.get("names") if isinstance(system.get("names"), dict) else {}
        trade = system.get("trade") if isinstance(system.get("trade"), dict) else {}
        discovery = system.get("discovery") if isinstance(system.get("discovery"), dict) else {}
        result = {
            "found": True, "source": "nmsalmanac", "address": address, "galaxy": galaxy,
            "system": {"portal": system.get("portal"), "name": names.get("given") or names.get("game"),
                       "game_name": names.get("game"), "region": system.get("region"), "star": system.get("star"),
                       "spectral_class": system.get("spectral_class"), "suns": system.get("suns"), "race": system.get("race"),
                       "economy": system.get("economy"), "wealth": system.get("wealth"), "conflict": system.get("conflict"),
                       "abandoned": system.get("abandoned"), "discovery": discovery, "trade": trade,
                       "pictures": system.get("pictures"), "raw": system},
            "bodies": bodies, "raw": {"system": raw, "bodies": [body["raw"] for body in bodies]},
        }
        self.store.save_almanac(result)
        return result


__all__ = ["AlmanacClient", "AlmanacError"]
