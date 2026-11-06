from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config import normalize_portal_address


class SQLiteSystemCache:
    """Persistent cache of exact generated system payloads."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.execute("""CREATE TABLE IF NOT EXISTS systems (
            galaxy INTEGER NOT NULL, address TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (galaxy, address))""")
        self.connection.commit()

    def get(self, address: str, galaxy: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT payload FROM systems WHERE galaxy=? AND address=?",
                                      (galaxy, normalize_portal_address(address))).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, address: str, galaxy: int, payload: dict[str, Any]) -> None:
        self.connection.execute("""INSERT INTO systems(galaxy,address,payload) VALUES(?,?,?)
            ON CONFLICT(galaxy,address) DO UPDATE SET payload=excluded.payload""",
            (galaxy, normalize_portal_address(address), json.dumps(payload, separators=(",", ":"))))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteSystemCache":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
