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
    """Runtime configuration for the local NMS toolchain."""

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
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Local config file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Local config file must contain a JSON object: {path}")
    return data


def load_config() -> AppConfig:
    """Load configuration from JSON and environment.

    Supported keys:
    - almanac_api_key
    - almanac_requests_per_hour

    Supported env vars:
    - NMS_ALMANAC_API_KEY
    - NMS_ALMANAC_REQUESTS_PER_HOUR
    """

    local_data = _read_local_json(LOCAL_CONFIG_PATH)

    key = os.environ.get("NMS_ALMANAC_API_KEY", "").strip()
    if not key:
        key = str(local_data.get("almanac_api_key", "")).strip()

    requests_raw = os.environ.get("NMS_ALMANAC_REQUESTS_PER_HOUR", "").strip()
    if requests_raw:
        try:
            requests_amount = int(requests_raw)
        except ValueError as exc:
            raise ValueError("NMS_ALMANAC_REQUESTS_PER_HOUR must be an integer") from exc
    else:
        raw_value = local_data.get("almanac_requests_per_hour", 500)
        try:
            requests_amount = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("almanac_requests_per_hour must be an integer") from exc

    if requests_amount <= 0:
        raise ValueError("almanac_requests_per_hour must be greater than zero")

    return AppConfig(
        db_path=APP_ROOT / "data" / "nms_search.sqlite3",
        local_config_path=LOCAL_CONFIG_PATH,
        almanac_api_key=key,
        almanac_requests_per_hour=requests_amount,
    )


__all__ = ["AppConfig", "load_config"]
