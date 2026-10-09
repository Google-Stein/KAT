"""Capability configuration upgrade, independent of store initialization."""

import sqlite3


def capability_schema(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE approvals ADD COLUMN display_context TEXT")
    db.execute("CREATE TABLE capabilities (id INTEGER PRIMARY KEY CHECK(id=1), weather TEXT)")
    db.execute("INSERT INTO capabilities VALUES (1,NULL)")
    db.execute(
        "CREATE TABLE read_roots (id TEXT PRIMARY KEY, label TEXT NOT NULL, "
        "path TEXT NOT NULL UNIQUE)"
    )
