from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent
LOCAL_CONFIG_PATH = APP_ROOT / "config.local.json"
DEFAULT_DB_PATH = APP_ROOT / "data" / "nms_search.sqlite3"


@dataclass
class AppConfig:
    """Runtime configuration for the local NMS search project.

    This project intentionally keeps secrets in a local json file instead of a
    CLI flag. The idea is simple: the user places a key in a file on disk and
    the program reads it. No prompts, no hidden interactive credential flow.
    """

    db_path: Path = DEFAULT_DB_PATH
    local_config_path: Path = LOCAL_CONFIG_PATH
    almanac_api_key: str = ""
    almanac_requests_per_hour: int = 500
    almanac_base_url: str = "https://nmsalmanac.com/api/"
    map_bridge_path: str | Path = "nms-galactic-map/nms-tools/nms-lookup.js"
    map_core_path: str | Path = "nms-galactic-map/nms-core"


def _read_local_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Local config file is not valid JSON: {path}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"Local config file must contain a JSON object: {path}")
    return loaded


def load_config() -> AppConfig:
    """Load config from environment and a local config file.

    Supported file keys:
    - almanac_api_key
    - almanac_requests_per_hour

    Supported environment variables:
    - NMS_ALMANAC_API_KEY
    - NMS_ALMANAC_REQUESTS_PER_HOUR
    """

    local_data = _read_local_json(LOCAL_CONFIG_PATH)
    key = os.environ.get("NMS_ALMANAC_API_KEY", "").strip()
    if not key:
        key = str(local_data.get("almanac_api_key", "")).strip()

    requests_per_hour = os.environ.get("NMS_ALMANAC_REQUESTS_PER_HOUR", "")
    if requests_per_hour:
        try:
            requests_per_hour_value = int(requests_per_hour)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("NMS_ALMANAC_REQUESTS_PER_HOUR must be an integer") from exc
    else:
        requests_per_hour_value = int(local_data.get("almanac_requests_per_hour", 500))

    if requests_per_hour_value <= 0:
        raise ValueError("almanac_requests_per_hour must be greater than zero")

    return AppConfig(
        db_path=APP_ROOT / "data" / "nms_search.sqlite3",
        local_config_path=LOCAL_CONFIG_PATH,
        almanac_api_key=key,
        almanac_requests_per_hour=requests_per_hour_value,
    )


__all__ = ["AppConfig", "load_config"]
