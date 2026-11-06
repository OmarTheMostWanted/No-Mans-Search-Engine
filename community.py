from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from config import SearchConfig, normalize_portal_address

ALMANAC_API = "https://nmsalmanac.com/api/"


class CommunityLookupError(RuntimeError):
    """The community service could not provide a usable lookup."""


class CommunityRateLimit(RuntimeError):
    """Lookups stopped before exhausting the conservative local API budget."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class CommunityClient:
    """Read-only client for the NMS Almanac community database.

    It follows the dependency project's documented API shape: GET /systems/{address}
    and, for charted systems, GET /planets/{portal}. API requests are sequential,
    cached locally, paced, and counted in a persistent rolling hourly budget.
    """

    def __init__(self, config: SearchConfig, timeout: float = 10.0) -> None:
        if not config.community_api_key:
            raise ValueError("Set NMS_ALMANAC_API_KEY before enabling community lookups.")
        self.config = config
        self.timeout = timeout
        self.path = Path(config.community_cache_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS community_cache (
            galaxy INTEGER NOT NULL, address TEXT NOT NULL, expires_at REAL NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(galaxy,address))""")
        self.db.execute("CREATE TABLE IF NOT EXISTS api_requests (requested_at REAL NOT NULL)")
        self.db.commit()
        self._last_request_at = 0.0

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "CommunityClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _cached(self, address: str, galaxy: int) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT expires_at,payload FROM community_cache WHERE galaxy=? AND address=?",
            (galaxy, address),
        ).fetchone()
        if row is None:
            return None
        if row[0] <= time.time():
            self.db.execute("DELETE FROM community_cache WHERE galaxy=? AND address=?", (galaxy, address))
            self.db.commit()
            return None
        return json.loads(row[1])

    def _cache(self, address: str, galaxy: int, payload: dict[str, Any]) -> None:
        # Hits are refreshed daily; misses are retried after six hours.
        ttl = 24 * 3600 if payload.get("found") else 6 * 3600
        self.db.execute("""INSERT INTO community_cache(galaxy,address,expires_at,payload)
            VALUES(?,?,?,?) ON CONFLICT(galaxy,address) DO UPDATE SET
            expires_at=excluded.expires_at,payload=excluded.payload""",
            (galaxy, address, time.time() + ttl, json.dumps(payload, separators=(",", ":"))))
        self.db.commit()

    def _reserve_request(self) -> None:
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("DELETE FROM api_requests WHERE requested_at <= ?", (now - 3600,))
            count = self.db.execute("SELECT COUNT(*) FROM api_requests").fetchone()[0]
            if count >= self.config.community_hourly_request_limit:
                oldest = self.db.execute("SELECT MIN(requested_at) FROM api_requests").fetchone()[0]
                retry = max(1, int(oldest + 3600 - now)) if oldest is not None else 3600
                raise CommunityRateLimit(
                    f"Local community API budget reached ({count}/{self.config.community_hourly_request_limit} requests in the last hour).",
                    retry,
                )
            self.db.execute("INSERT INTO api_requests(requested_at) VALUES(?)", (now,))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        wait = self.config.community_min_request_interval - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _get_json(self, path: str) -> dict[str, Any] | None:
        self._reserve_request()
        request = Request(
            ALMANAC_API + path,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.config.community_api_key}",
                "User-Agent": "No-Mans-Search-Engine/1.0 (community lookup)",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code == 429:
                value = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    retry = max(1, int(value)) if value else None
                except ValueError:
                    retry = None
                raise CommunityRateLimit(
                    "NMS Almanac returned HTTP 429; stopping community lookups to respect its rate limit.", retry
                ) from exc
            if exc.code in (401, 403):
                raise CommunityLookupError(
                    f"NMS Almanac rejected the API key (HTTP {exc.code}); verify NMS_ALMANAC_API_KEY."
                ) from exc
            if exc.code >= 500:
                raise CommunityLookupError(f"NMS Almanac server error (HTTP {exc.code}).") from exc
            raise CommunityLookupError(f"NMS Almanac request failed (HTTP {exc.code}).") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CommunityLookupError(f"Could not reach NMS Almanac: {exc}.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommunityLookupError("NMS Almanac returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise CommunityLookupError("NMS Almanac returned an unexpected response.")
        return data

    @staticmethod
    def _system_data(response: dict[str, Any] | None) -> dict[str, Any] | None:
        if response is None:
            return None
        inner = response.get("system")
        if isinstance(inner, dict):
            return inner
        return response

    def lookup(self, address: str, galaxy_number: int) -> dict[str, Any]:
        """Look up one generated match and its recorded body data, if available."""
        address = normalize_portal_address(address)
        galaxy_index = galaxy_number - 1
        cached = self._cached(address, galaxy_index)
        if cached is not None:
            return cached

        query = urlencode({"galaxy": galaxy_number})
        try:
            response = self._get_json(f"systems/{quote(address)}?{query}")
            system = self._system_data(response)
            if system is None or response.get("found") is False:
                result = {"found": False, "source": "NMS Almanac", "address": address,
                          "galaxy": galaxy_number, "system": None, "planets": []}
                self._cache(address, galaxy_index, result)
                return result

            bodies = system.get("bodies") or response.get("bodies") or []
            planets: list[dict[str, Any]] = []
            for body in bodies[:8]:
                if not isinstance(body, dict) or not body.get("portal"):
                    continue
                portal = normalize_portal_address(str(body["portal"]))
                planet_response = self._get_json(
                    f"planets/{quote(portal)}?{query}"
                )
                if planet_response is None:
                    continue
                planet = planet_response.get("planet")
                planet = planet if isinstance(planet, dict) else planet_response
                planets.append({
                    "portal": portal,
                    "name": (planet.get("names") or {}).get("given") or
                            (planet.get("names") or {}).get("game") or body.get("name"),
                    "biome": planet.get("biome"),
                    "weather": planet.get("weather"),
                    "water": planet.get("water"),
                    "moon_of": (planet.get("body") or {}).get("moon_of"),
                    # Preserve the upstream record as returned; API attributes
                    # may evolve and callers may need fields not normalized here.
                    "record": planet,
                })
            result = {
                "found": True,
                "source": "NMS Almanac",
                "address": address,
                "galaxy": galaxy_number,
                "system": {
                    "name": (system.get("names") or {}).get("given") or
                            (system.get("names") or {}).get("game"),
                    "suns": system.get("suns"),
                    "star": system.get("star"),
                    "spectral_class": system.get("spectral_class"),
                    "economy": system.get("economy"),
                    "wealth": system.get("wealth"),
                    "conflict": system.get("conflict"),
                    "record": system,
                },
                "planets": planets,
            }
            self._cache(address, galaxy_index, result)
            return result
        except CommunityRateLimit:
            raise
        except CommunityLookupError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise CommunityLookupError(f"Could not parse NMS Almanac data for {address}: {exc}.") from exc


__all__ = ["CommunityClient", "CommunityLookupError", "CommunityRateLimit"]
