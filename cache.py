from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config import normalize_portal_address


class SQLiteSystemCache:
    """Persistent JSON cache keyed by generator galaxy index and portal code."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS systems (
                galaxy INTEGER NOT NULL,
                address TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (galaxy, address)
            )"""
        )
        self.connection.commit()

    def get(self, address: str, galaxy: int) -> dict[str, Any] | None:
        address = normalize_portal_address(address)
        row = self.connection.execute(
            "SELECT payload FROM systems WHERE galaxy = ? AND address = ?",
            (galaxy, address),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, address: str, galaxy: int, payload: dict[str, Any]) -> None:
        address = normalize_portal_address(address)
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self.connection.execute(
            """INSERT INTO systems (galaxy, address, payload, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(galaxy, address) DO UPDATE SET
                 payload=excluded.payload, updated_at=CURRENT_TIMESTAMP""",
            (galaxy, address, encoded),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteSystemCache":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
