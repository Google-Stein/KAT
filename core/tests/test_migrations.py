import sqlite3
from pathlib import Path

import pytest

from kat_core.migrations import foundation, migrate


def test_upgrade_preserves_wal_data_and_has_recoverable_backup(tmp_path: Path) -> None:
    path = tmp_path / "kat.sqlite3"
    db = sqlite3.connect(path)
    migrate(db, path, {1: foundation})
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("INSERT INTO sessions VALUES ('old','Owner data','then','now')")
    db.commit()

    def upgrade(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE upgrade_marker (id INTEGER)")

    migrate(db, path, {1: foundation, 2: upgrade})
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.execute("SELECT title FROM sessions").fetchone()[0] == "Owner data"
    backups = list(tmp_path.glob("*.backup-v1-*"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as restored:
        assert restored.execute("PRAGMA user_version").fetchone()[0] == 1
        assert restored.execute("SELECT title FROM sessions").fetchone()[0] == "Owner data"
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    migrate(db, path, {1: foundation, 2: upgrade})
    assert len(list(tmp_path.glob("*.backup-v1-*"))) == 1
    db.close()


def test_failed_upgrade_rolls_back_ddl_data_and_version(tmp_path: Path) -> None:
    path = tmp_path / "kat.sqlite3"
    db = sqlite3.connect(path)
    migrate(db, path, {1: foundation})

    def broken(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE should_not_exist (id INTEGER)")
        connection.execute("INSERT INTO sessions VALUES ('bad','bad','bad','bad')")
        raise RuntimeError("fixture failure")

    with pytest.raises(RuntimeError, match="fixture failure"):
        migrate(db, path, {1: foundation, 2: broken})
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    assert (
        db.execute("SELECT count(*) FROM sqlite_master WHERE name='should_not_exist'").fetchone()[0]
        == 0
    )
    db.close()


def test_future_database_and_missing_step_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "kat.sqlite3"
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="newer KAT"):
        migrate(db, path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 99
    db.execute("PRAGMA user_version=0")
    with pytest.raises(RuntimeError, match="Missing ordered"):
        migrate(db, path, {2: foundation})
    assert db.execute("PRAGMA user_version").fetchone()[0] == 0
    db.close()
