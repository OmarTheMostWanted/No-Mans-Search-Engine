from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class SQLiteStore:
    """Persistent SQLite cache and archive for all generated and Almanac data."""

    def __init__(self, path: str | Path = "data/nms_search.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.conn.close()

    def _initialize(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_systems (
                galaxy INTEGER NOT NULL,
                address TEXT NOT NULL,
                system_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (galaxy, address)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS almanac_systems (
                galaxy INTEGER NOT NULL,
                address TEXT NOT NULL,
                system_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (galaxy, address)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS almanac_planets (
                galaxy INTEGER NOT NULL,
                portal TEXT NOT NULL,
                system_address TEXT NOT NULL,
                planet_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (galaxy, portal)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self.conn.commit()

    def save_generated_system(self, address: str, galaxy: int, payload: dict[str, Any]) -> None:
        row = json.dumps(payload, sort_keys=True)
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO generated_systems (galaxy, address, system_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(galaxy, address)
            DO UPDATE SET system_json = excluded.system_json, created_at = excluded.created_at
            """,
            (int(galaxy), str(address).upper(), row, now),
        )
        self.conn.commit()

    def get_generated_system(self, address: str, galaxy: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT system_json FROM generated_systems WHERE galaxy = ? AND address = ?",
            (int(galaxy), str(address).upper()),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["system_json"])

    def save_almanac_system(self, address: str, galaxy: int, payload: dict[str, Any]) -> None:
        row = json.dumps(payload, sort_keys=True)
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO almanac_systems (galaxy, address, system_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(galaxy, address)
            DO UPDATE SET system_json = excluded.system_json, created_at = excluded.created_at
            """,
            (int(galaxy), str(address).upper(), row, now),
        )
        self.conn.commit()

    def get_almanac_system(self, address: str, galaxy: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT system_json FROM almanac_systems WHERE galaxy = ? AND address = ?",
            (int(galaxy), str(address).upper()),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["system_json"])

    def save_almanac_planet(self, portal: str, galaxy: int, system_address: str, payload: dict[str, Any]) -> None:
        row = json.dumps(payload, sort_keys=True)
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO almanac_planets (galaxy, portal, system_address, planet_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(galaxy, portal)
            DO UPDATE SET system_address = excluded.system_address, planet_json = excluded.planet_json, created_at = excluded.created_at
            """,
            (int(galaxy), str(portal).upper(), str(system_address).upper(), row, now),
        )
        self.conn.commit()

    def get_cache(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload, expires_at FROM cache_entries WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= time.time():
            self.conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
            self.conn.commit()
            return None
        return json.loads(row["payload"])

    def set_cache(self, key: str, payload: Any, ttl_seconds: int = 3600) -> None:
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO cache_entries (cache_key, payload, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key)
            DO UPDATE SET payload = excluded.payload, expires_at = excluded.expires_at, created_at = excluded.created_at
            """,
            (key, json.dumps(payload, sort_keys=True), now + ttl_seconds, now),
        )
        self.conn.commit()


__all__ = ["SQLiteStore"]
