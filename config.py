from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import json
import os
import re

MAX_GALAXY_NUMBER = 255
STAR_COLORS = {"yellow", "red", "green", "blue", "purple"}
DOMINANT_RACES = {"gek", "vy'keen", "korvax", "uninhabited"}
SEARCH_MODES = {"random", "sequential"}
LOCAL_CONFIG_PATH = Path(__file__).resolve().with_name("config.local.json")


def load_community_api_key(config_path: str | Path = LOCAL_CONFIG_PATH) -> str:
    """Load the Almanac key from the environment or an untracked local JSON config.

    The environment variable takes precedence so deployments and CI can keep
    secrets in their secret store. Local development can save the key with
    save_community_api_key() without putting it into tracked source files.
    """
    environment_key = os.getenv("NMS_ALMANAC_API_KEY", "").strip()
    if environment_key:
        return environment_key
    path = Path(config_path)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read local config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Local config file {path} must contain a JSON object.")
    key = data.get("community_api_key", "")
    if not isinstance(key, str):
        raise ValueError("community_api_key in local config must be a string.")
    return key.strip()


def save_community_api_key(api_key: str, config_path: str | Path = LOCAL_CONFIG_PATH) -> Path:
    """Save the key to config.local.json, which is excluded from Git."""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key cannot be empty.")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot update local config file {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"Local config file {path} must contain a JSON object.")
        existing = loaded
    existing["community_api_key"] = api_key
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows and some mounted filesystems do not support POSIX modes.
        pass
    return path


def galaxy_to_generator_index(galaxy_number: int) -> int:
    return galaxy_number - 1


def normalize_portal_address(address: str) -> str:
    address = address.strip().upper()
    if not re.fullmatch(r"[0-9A-F]{12}", address):
        raise ValueError("Portal address must contain exactly 12 hexadecimal characters.")
    return address


def normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value.lower() if value else None


@dataclass
class SearchConfig:
    galaxy: int = 1
    star_color: str | None = None
    min_planets: int | None = None
    exact_planets: int | None = None
    min_moons: int | None = None
    max_moons: int | None = None
    economy: str | None = None
    economy_tier: int | None = None
    conflict: str | None = None
    conflict_tier: int | None = None
    race: str | None = None
    pirate: bool | None = None
    abandoned: bool | None = None
    uncharted: bool | None = None
    black_hole: bool | None = None
    atlas_system: bool | None = None
    min_core_distance: float | None = None
    max_core_distance: float | None = None
    search_mode: Literal["random", "sequential"] = "random"
    start_address: str | None = None
    random_seed: int | None = None
    duration_seconds: int = 3600
    batch_size: int = 100
    max_systems: int | None = None
    max_matches: int | None = None
    cache_enabled: bool = True
    cache_path: Path = Path("data/systems.sqlite3")
    # Environment variable overrides the ignored local config file.
    community_api_key: str = field(default_factory=load_community_api_key, repr=False, compare=False)
    community_cache_path: Path = Path("data/community.sqlite3")
    community_hourly_request_limit: int = 450
    community_min_request_interval: float = 1.0

    def validate(self) -> None:
        if not 1 <= self.galaxy <= MAX_GALAXY_NUMBER:
            raise ValueError(f"Galaxy must be between 1 and {MAX_GALAXY_NUMBER}.")
        if self.star_color is not None:
            self.star_color = self.star_color.strip().lower()
            if self.star_color not in STAR_COLORS:
                raise ValueError(f"Invalid star colour: {self.star_color}")
        self.economy = normalize_optional_string(self.economy)
        self.conflict = normalize_optional_string(self.conflict)
        self.race = normalize_optional_string(self.race)
        if self.race is not None and self.race not in DOMINANT_RACES:
            raise ValueError(f"Invalid dominant race: {self.race}")
        for name in ("economy_tier", "conflict_tier"):
            value = getattr(self, name)
            if value is not None and value not in (1, 2, 3):
                raise ValueError(f"{name.replace('_', ' ').capitalize()} must be 1, 2 or 3.")
        for name in ("min_planets", "exact_planets", "min_moons", "max_moons"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name.replace('_', ' ').capitalize()} cannot be negative.")
        if self.min_planets is not None and self.exact_planets is not None:
            raise ValueError("Specify either minimum or exact planet count, not both.")
        if self.min_moons is not None and self.max_moons is not None and self.min_moons > self.max_moons:
            raise ValueError("Minimum moon count cannot exceed maximum moon count.")
        for name in ("min_core_distance", "max_core_distance"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name.replace('_', ' ').capitalize()} cannot be negative.")
        if (self.min_core_distance is not None and self.max_core_distance is not None
                and self.min_core_distance > self.max_core_distance):
            raise ValueError("Minimum core distance cannot exceed maximum core distance.")
        if self.search_mode not in SEARCH_MODES:
            raise ValueError(f"Invalid search mode: {self.search_mode}")
        if self.search_mode == "sequential" and self.start_address is None:
            raise ValueError("Sequential search requires a starting portal address.")
        if self.start_address is not None:
            self.start_address = normalize_portal_address(self.start_address)
        if self.duration_seconds <= 0 or self.batch_size <= 0:
            raise ValueError("Duration and batch size must be greater than zero.")
        for name in ("max_systems", "max_matches"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name.replace('_', ' ').capitalize()} must be greater than zero.")
        if not 1 <= self.community_hourly_request_limit <= 450:
            raise ValueError("Community API request limit must be between 1 and 450 per hour (below the documented 500/hour key quota).")
        if self.community_min_request_interval < 0:
            raise ValueError("Community API request interval cannot be negative.")
        self.cache_path = Path(self.cache_path)
        self.community_cache_path = Path(self.community_cache_path)
