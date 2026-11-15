from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppConfig:
    """Application settings. API keys are intentionally absent from CLI arguments."""

    db_path: Path
    almanac_api_key: str
    almanac_requests_per_hour: int
    almanac_base_url: str
    node_command: str
    bridge_path: Path


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load settings from `config.local.json`; environment overrides key and limit.

    JSON keys: `almanac_api_key` (string), `almanac_requests_per_hour` (positive integer),
    `database` (optional path), `almanac_base_url` (optional URL), `node` (optional executable).
    Environment overrides: `NMS_ALMANAC_API_KEY`, `NMS_ALMANAC_REQUESTS_PER_HOUR`.
    Missing rate limit defaults to 500 requests in a rolling hour.
    """
    path = Path(config_path) if config_path else ROOT / "config.local.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read configuration {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("config.local.json must contain a JSON object")
    else:
        data = {}
    raw_limit = os.getenv("NMS_ALMANAC_REQUESTS_PER_HOUR", data.get("almanac_requests_per_hour", 500))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("almanac_requests_per_hour must be an integer") from exc
    if limit < 1:
        raise ValueError("almanac_requests_per_hour must be at least 1")
    db_path = Path(data.get("database", "data/nms_search.sqlite3"))
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    return AppConfig(
        db_path=db_path,
        almanac_api_key=os.getenv("NMS_ALMANAC_API_KEY", str(data.get("almanac_api_key", ""))).strip(),
        almanac_requests_per_hour=limit,
        almanac_base_url=str(data.get("almanac_base_url", "https://nmsalmanac.com/api/")).rstrip("/") + "/",
        node_command=str(data.get("node", "node")),
        bridge_path=ROOT / "js" / "bridge.mjs",
    )


def normalize_address(address: str) -> str:
    """Validate and uppercase a portal address: input/output is 12 hex characters."""
    value = str(address).strip().upper()
    if len(value) != 12 or any(char not in "0123456789ABCDEF" for char in value):
        raise ValueError("Portal address must be exactly 12 hexadecimal characters")
    return value


def canonical_system_address(address: str) -> str:
    """Return a system-level address with planet glyph zero.

    The first portal glyph identifies a body within the system. The other eleven
    glyphs identify the system, so body variants share one system cache/API lookup.
    """
    return "0" + normalize_address(address)[1:]


def validate_galaxy(galaxy: int) -> int:
    """Validate and return the upstream zero-based galaxy index (integer 0..255)."""
    if isinstance(galaxy, bool) or not isinstance(galaxy, int) or not 0 <= galaxy <= 255:
        raise ValueError("Galaxy index must be an integer from 0 to 255 (Euclid is 0)")
    return galaxy
