import json
import sqlite3
from pathlib import Path

import pytest

from kat_core.migrations import MIGRATIONS, foundation, migrate
from kat_core.schemas import SettingsUpdate
from kat_core.storage import Store


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


def test_v04_upgrade_preserves_legacy_approval_without_inventing_a_continuation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "kat.sqlite3"
    db = sqlite3.connect(path)
    migrate(db, path, {version: step for version, step in MIGRATIONS.items() if version <= 5})
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        "INSERT INTO sessions(id,title,created_at,updated_at) "
        "VALUES('owner','Original','then','now')"
    )
    db.execute("INSERT INTO settings(id,value) VALUES(1,?)", (SettingsUpdate().model_dump_json(),))
    private = "Private retained file body."
    db.execute(
        "INSERT INTO messages(id,session_id,role,content,created_at) VALUES('tool','owner',"
        "'tool',?,'then')",
        (private,),
    )
    db.execute(
        "INSERT INTO approvals(id,session_id,tool_name,arguments,risk,status,created_at,result) "
        "VALUES('legacy','owner','read_text_file',?,'medium','completed','then',?)",
        (
            json.dumps({"root_id": "old-root", "relative_path": "briefing.txt"}),
            json.dumps({"content": private}),
        ),
    )
    db.commit()
    store = Store(path)
    try:
        approval = store.approval("legacy")
        assert approval is not None and approval.result == {"content": private}
        assert approval.origin_user_message_id is None
        assert approval.continuation is None and approval.continuation_policy == "none"
        assert store.messages("owner")[0].content == private
        with store.transaction() as current:
            assert current.execute("PRAGMA user_version").fetchone()[0] == 6
            assert current.execute("SELECT count(*) FROM continuations").fetchone()[0] == 0
            assert current.execute("PRAGMA foreign_key_check").fetchall() == []
        backup = list(tmp_path.glob("*.backup-v5-*"))
        assert len(backup) == 1
        with sqlite3.connect(backup[0]) as restored:
            assert restored.execute("PRAGMA user_version").fetchone()[0] == 5
            assert restored.execute("SELECT content FROM messages").fetchone()[0] == private
            assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        store.close()
        db.close()
