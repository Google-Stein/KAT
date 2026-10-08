"""Ordered atomic schema upgrades. Never silently downgrade or replay scripts."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

Migration = Callable[[sqlite3.Connection], None]


def foundation(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS messages (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE, session_id TEXT NOT NULL REFERENCES sessions(id),
                    role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)""")
    db.execute("""CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, sequence)""")
    db.execute("""CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1),
                    value TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    tool_name TEXT NOT NULL, arguments TEXT NOT NULL, risk TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT, error TEXT)""")
    db.execute(
        """CREATE INDEX IF NOT EXISTS approvals_session ON approvals(session_id, created_at)"""
    )
    db.execute("""CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE, timestamp TEXT NOT NULL, event TEXT NOT NULL,
                    session_id TEXT, tool_name TEXT, approval_id TEXT,
                    details TEXT NOT NULL, error TEXT)""")


MIGRATIONS: dict[int, Migration] = {1: foundation}


def migrate(
    db: sqlite3.Connection, path: Path, migrations: dict[int, Migration] | None = None
) -> None:
    steps = MIGRATIONS if migrations is None else migrations
    target = max(steps)
    current = int(db.execute("PRAGMA user_version").fetchone()[0])
    if current > target:
        raise RuntimeError("This database requires a newer KAT version; it was not modified.")
    if current == target:
        return
    if any(version not in steps for version in range(current + 1, target + 1)):
        raise RuntimeError("Missing ordered KAT database migration; database was not modified.")
    if current:
        backup_path = path.with_name(f"{path.name}.backup-v{current}-{uuid4().hex}")
        # SQLite backup includes committed WAL data; raw file copies do not.
        backup = sqlite3.connect(backup_path)
        try:
            db.backup(backup)
            backup.execute("PRAGMA journal_mode=DELETE")
        finally:
            backup.close()
        backup_path.chmod(0o600)
    try:
        db.execute("BEGIN EXCLUSIVE")
        actual = int(db.execute("PRAGMA user_version").fetchone()[0])
        if actual > target:
            raise RuntimeError("Database version changed; restart with a compatible KAT version.")
        for version in range(actual + 1, target + 1):
            steps[version](db)
            db.execute(f"PRAGMA user_version={version}")
        db.commit()
    except BaseException:
        db.rollback()
        raise
