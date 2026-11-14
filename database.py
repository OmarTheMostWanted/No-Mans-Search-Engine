from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class SQLiteStore:
    """One SQLite database for normalized system/body records, raw payloads and caches."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS generated_systems (
          galaxy INTEGER NOT NULL, address TEXT NOT NULL, name TEXT, region TEXT,
          star_type TEXT, planets INTEGER, moons INTEGER, race TEXT, economy TEXT, conflict TEXT,
          payload_json TEXT NOT NULL, fetched_at REAL NOT NULL, PRIMARY KEY(galaxy,address));
        CREATE TABLE IF NOT EXISTS generated_bodies (
          galaxy INTEGER NOT NULL, address TEXT NOT NULL, body_index INTEGER NOT NULL,
          name TEXT, payload_json TEXT NOT NULL,
          PRIMARY KEY(galaxy,address,body_index),
          FOREIGN KEY(galaxy,address) REFERENCES generated_systems(galaxy,address) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS almanac_systems (
          galaxy INTEGER NOT NULL, address TEXT NOT NULL, found INTEGER NOT NULL,
          name TEXT, region TEXT, star TEXT, race TEXT, economy TEXT, wealth TEXT, conflict TEXT,
          payload_json TEXT NOT NULL, fetched_at REAL NOT NULL, PRIMARY KEY(galaxy,address));
        CREATE TABLE IF NOT EXISTS almanac_bodies (
          galaxy INTEGER NOT NULL, system_address TEXT NOT NULL, portal TEXT NOT NULL,
          body_index INTEGER NOT NULL, name TEXT, biome TEXT, weather TEXT, payload_json TEXT NOT NULL,
          PRIMARY KEY(galaxy,system_address,portal));
        CREATE TABLE IF NOT EXISTS api_cache (
          cache_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS api_requests (requested_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_gen_star ON generated_systems(galaxy,star_type);
        CREATE INDEX IF NOT EXISTS idx_gen_race ON generated_systems(galaxy,race);
        CREATE INDEX IF NOT EXISTS idx_gen_planets ON generated_systems(galaxy,planets);
        CREATE INDEX IF NOT EXISTS idx_alm_biome ON almanac_bodies(galaxy,biome);
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_generated(self, address: str, galaxy: int) -> dict[str, Any] | None:
        row = self.db.execute("SELECT payload_json FROM generated_systems WHERE galaxy=? AND address=?", (galaxy,address)).fetchone()
        return json.loads(row[0]) if row else None

    def save_generated(self, record: dict[str, Any]) -> None:
        now = time.time(); g = record["galaxy"]; addr = record["address"]
        with self.db:
            self.db.execute("""INSERT OR REPLACE INTO generated_systems
              (galaxy,address,name,region,star_type,planets,moons,race,economy,conflict,payload_json,fetched_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (g,addr,record.get("name"),record.get("region"),record.get("star_type"),record.get("planets"),record.get("moons"),record.get("race"),record.get("economy"),record.get("conflict"),json.dumps(record),now))
            self.db.execute("DELETE FROM generated_bodies WHERE galaxy=? AND address=?", (g,addr))
            for i, body in enumerate(record.get("bodies", [])):
                self.db.execute("INSERT INTO generated_bodies VALUES(?,?,?,?,?)", (g,addr,i,body.get("name"),json.dumps(body)))

    def get_almanac(self, address: str, galaxy: int) -> dict[str, Any] | None:
        row = self.db.execute("SELECT payload_json FROM almanac_systems WHERE galaxy=? AND address=?",(galaxy,address)).fetchone()
        return json.loads(row[0]) if row else None

    def save_almanac(self, record: dict[str, Any]) -> None:
        g=record["galaxy"]; addr=record["address"]; system=record.get("system") or {}
        with self.db:
            self.db.execute("""INSERT OR REPLACE INTO almanac_systems
              (galaxy,address,found,name,region,star,race,economy,wealth,conflict,payload_json,fetched_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (g,addr,int(record["found"]),system.get("name"),system.get("region"),system.get("star"),system.get("race"),system.get("economy"),system.get("wealth"),system.get("conflict"),json.dumps(record),time.time()))
            self.db.execute("DELETE FROM almanac_bodies WHERE galaxy=? AND system_address=?",(g,addr))
            for i, body in enumerate(record.get("bodies", [])):
                self.db.execute("INSERT INTO almanac_bodies VALUES(?,?,?,?,?,?,?,?)", (g,addr,body.get("portal",str(i)),i,body.get("name"),body.get("biome"),body.get("weather"),json.dumps(body)))

    def get_cache(self, key: str) -> tuple[bool, Any]:
        row=self.db.execute("SELECT payload_json,expires_at FROM api_cache WHERE cache_key=?",(key,)).fetchone()
        if not row: return False, None
        if row[1] <= time.time():
            self.db.execute("DELETE FROM api_cache WHERE cache_key=?",(key,)); self.db.commit(); return False,None
        return True,json.loads(row[0])

    def set_cache(self, key: str, value: Any, ttl: int) -> None:
        self.db.execute("INSERT OR REPLACE INTO api_cache VALUES(?,?,?)",(key,json.dumps(value),time.time()+ttl)); self.db.commit()

    def reserve_api_request(self, limit: int) -> None:
        """Atomically record one request if fewer than limit occurred in the prior hour."""
        now=time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("DELETE FROM api_requests WHERE requested_at <= ?",(now-3600,))
            row=self.db.execute("SELECT COUNT(*),MIN(requested_at) FROM api_requests").fetchone()
            if row[0] >= limit:
                wait=max(1,int(row[1]+3600-now))
                raise RuntimeError(f"Almanac local rate limit reached ({row[0]}/{limit} requests/hour); retry in {wait}s")
            self.db.execute("INSERT INTO api_requests VALUES(?)",(now,)); self.db.commit()
        except Exception:
            self.db.rollback(); raise
