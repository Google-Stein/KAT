"""Preserve actual schema-3 owner data while replacing only the derived index."""

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest

from kat_core import migrations
from kat_core.memory_migration import memory_schema, stemmed_memory_index
from kat_core.memory_retrieval import MemoryRetrieval
from kat_core.memory_schemas import MemoryCreate, MemoryEdit, ProjectCreate
from kat_core.memory_store import MemoryStore
from kat_core.migrations import foundation, local_provider_settings, migrate
from kat_core.schemas import Message, SettingsUpdate
from kat_core.storage import Store, timestamp

BASELINE = {1: foundation, 2: local_provider_settings, 3: memory_schema}
AUTHORITATIVE = (
    "projects",
    "sessions",
    "messages",
    "settings",
    "approvals",
    "audit",
    "memory_items",
    "memory_revisions",
    "memory_usage",
)


class Schema3Fixture(Store):
    """Frozen historical writer: current Store rightly requires schema 6."""

    def __init__(self, path: Path) -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        migrate(self._db, path, BASELINE)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("INSERT INTO settings VALUES(1,?)", (SettingsUpdate().model_dump_json(),))
        self._db.commit()

    def add_message(self, session_id, role, content):
        message = Message(
            id=str(uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=timestamp(),
        )
        with self.transaction() as db:
            db.execute(
                "INSERT INTO messages(id,session_id,role,content,created_at) VALUES(?,?,?,?,?)",
                (message.id, session_id, role, content, message.created_at),
            )
        return message

    def save_settings(self, settings):
        with self.transaction() as db:
            db.execute("UPDATE settings SET value=? WHERE id=1", (settings.model_dump_json(),))


def snapshot(db: sqlite3.Connection):
    return {
        table: [tuple(row) for row in db.execute(f"SELECT * FROM {table}")]
        for table in AUTHORITATIVE
    }


def test_upgrade_preserves_representative_030_database_and_wal_backup(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "kat.sqlite3"
    with monkeypatch.context() as baseline:
        baseline.setattr(migrations, "MIGRATIONS", BASELINE)
        store = Schema3Fixture(path)
        memories = MemoryStore(store)
        project = memories.create_project(ProjectCreate(name="Owner project"))
        session = store.create_session("Existing conversation")
        memories.set_session_project(session.id, project.id)
        message = store.add_message(session.id, "user", "Original source text")
        assistant = store.add_message(session.id, "assistant", "Original assistant text")
        item = memories.create(MemoryCreate(content="main user is named Luis", confirmed=True))
        memories.edit(item.id, MemoryEdit(content=item.content, expected_revision=1, pinned=True))
        memories.create(
            MemoryCreate(
                content="The project uses copper sensors",
                confirmed=True,
                scope="project",
                project_id=project.id,
                origin="conversation_selection",
                source_session_id=session.id,
                source_message_id=message.id,
            )
        )
        store.save_settings(
            store.settings().model_copy(
                update={"memory_enabled": True, "provider": "ollama", "model": "qwen3:8b"}
            )
        )
        with store.transaction() as db:
            db.execute(
                "INSERT INTO memory_usage VALUES (?,?,?,?,?,?)",
                (item.id, 1, session.id, assistant.id, "ollama", "then"),
            )
            db.execute(
                "INSERT INTO approvals VALUES "
                "('pending',?,'open_application','{}','medium','pending','then',NULL,NULL)",
                (session.id,),
            )
            assert db.execute("PRAGMA user_version").fetchone()[0] == 3
            assert (
                db.execute(
                    "SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'name'"
                ).fetchone()[0]
                == 0
            )
        # Commit an extra WAL-only row while the connection stays open, then
        # migrate without changing authoritative records or startup recovery.
        store.add_message(session.id, "user", "Committed WAL transcript")
        with store.transaction() as db:
            before = snapshot(db)
        # Migration needs its own explicit transaction, outside Store's context.
        with closing(sqlite3.connect(path)) as upgrade:
            migrate(upgrade, path, BASELINE | {4: stemmed_memory_index})
            assert snapshot(upgrade) == before
            assert upgrade.execute("PRAGMA user_version").fetchone()[0] == 4
            assert (
                "porter unicode61"
                in upgrade.execute(
                    "SELECT sql FROM sqlite_master WHERE name='memory_fts'"
                ).fetchone()[0]
            )
        with store.transaction() as db:
            assert snapshot(db) == before
        results = MemoryRetrieval(memories).retrieve("What is my name?", None)
        assert [(r.id, r.revision) for r in results] == [(item.id, 2)]
        memories.rebuild()
        assert MemoryRetrieval(memories).retrieve("What am I named?", None)[0].id == item.id
        store.close()
    with closing(sqlite3.connect(next(tmp_path.glob("*.backup-v3-*")))) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 3
        assert snapshot(backup) == before
        assert (
            "porter"
            not in backup.execute(
                "SELECT sql FROM sqlite_master WHERE name='memory_fts'"
            ).fetchone()[0]
        )
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    restarted = Store(path)
    try:
        assert restarted.settings().memory_enabled is True
        assert MemoryStore(restarted).get(item.id).revision == 2
        assert restarted.approval("pending").status == "pending"
    finally:
        restarted.close()


def test_index_migration_failure_restores_original_fts_and_version(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "kat.sqlite3"
    with monkeypatch.context() as baseline:
        baseline.setattr(migrations, "MIGRATIONS", BASELINE)
        store = Schema3Fixture(path)
        try:
            MemoryStore(store).create(
                MemoryCreate(content="main user is named Luis", confirmed=True)
            )
        finally:
            store.close()
    with closing(sqlite3.connect(path)) as db:
        original_data = snapshot(db)
        original_sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE name='memory_fts'"
        ).fetchone()[0]

        def broken(connection: sqlite3.Connection) -> None:
            stemmed_memory_index(connection)
            connection.execute("UPDATE settings SET value='changed'")
            raise RuntimeError("index migration fixture failure")

        with pytest.raises(RuntimeError, match="fixture failure"):
            migrate(db, path, BASELINE | {4: broken})
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert (
            db.execute("SELECT sql FROM sqlite_master WHERE name='memory_fts'").fetchone()[0]
            == original_sql
        )
        assert snapshot(db) == original_data
        assert (
            json.loads(db.execute("SELECT value FROM settings").fetchone()[0])["memory_enabled"]
            is False
        )
        assert len(list(db.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))) == 3
        assert (
            db.execute("SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'name'").fetchone()[
                0
            ]
            == 0
        )
        assert (
            db.execute("SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'named'").fetchone()[
                0
            ]
            == 1
        )
