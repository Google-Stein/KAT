"""Memory schema and a rebuildable external-content FTS index."""

import json
import sqlite3

from kat_core.memory_lexical import MEMORY_TOKENIZER


def create_memory_index(db: sqlite3.Connection, tokenizer: str) -> None:
    # Tokenizer is a code-owned migration constant, never owner/model SQL input.
    db.execute(
        "CREATE VIRTUAL TABLE memory_fts USING fts5(content, content=memory_items, "
        f"content_rowid=rowid, tokenize='{tokenizer}')"
    )
    for statement in (
        """CREATE TRIGGER memory_insert AFTER INSERT ON memory_items BEGIN
            INSERT INTO memory_fts(rowid,content) VALUES(new.rowid,new.content); END""",
        """CREATE TRIGGER memory_delete AFTER DELETE ON memory_items BEGIN
            INSERT INTO memory_fts(memory_fts,rowid,content)
            VALUES('delete',old.rowid,old.content); END""",
        """CREATE TRIGGER memory_update AFTER UPDATE OF content ON memory_items BEGIN
            INSERT INTO memory_fts(memory_fts,rowid,content)
            VALUES('delete',old.rowid,old.content);
            INSERT INTO memory_fts(rowid,content) VALUES(new.rowid,new.content); END""",
    ):
        db.execute(statement)


def stemmed_memory_index(db: sqlite3.Connection) -> None:
    for trigger in ("memory_insert", "memory_delete", "memory_update"):
        db.execute(f"DROP TRIGGER {trigger}")
    db.execute("DROP TABLE memory_fts")
    create_memory_index(db, MEMORY_TOKENIZER)
    db.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")


def memory_schema(db: sqlite3.Connection) -> None:
    statements = (
        "CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "ALTER TABLE sessions ADD COLUMN project_id TEXT REFERENCES projects(id)",
        """CREATE TABLE memory_items (
            id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, content TEXT NOT NULL,
            scope TEXT NOT NULL, project_id TEXT REFERENCES projects(id),
            sensitivity TEXT NOT NULL, pinned INTEGER NOT NULL, importance INTEGER NOT NULL,
            effective_at TEXT, expires_at TEXT, status TEXT NOT NULL, origin TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_reviewed_at TEXT NOT NULL,
            revision INTEGER NOT NULL, superseded_by TEXT,
            source_session_id TEXT, source_message_id TEXT, source_role TEXT)""",
        "CREATE INDEX memory_eligibility ON memory_items(status,scope,project_id,expires_at)",
        "CREATE TABLE memory_revisions (memory_id TEXT NOT NULL REFERENCES memory_items(id) "
        "ON DELETE CASCADE, revision INTEGER NOT NULL, snapshot TEXT NOT NULL, "
        "PRIMARY KEY(memory_id,revision))",
        """CREATE TABLE memory_usage (
            memory_id TEXT NOT NULL, revision INTEGER NOT NULL,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            assistant_message_id TEXT NOT NULL REFERENCES messages(id),
            provider TEXT NOT NULL, used_at TEXT NOT NULL,
            PRIMARY KEY(memory_id,assistant_message_id))""",
        "CREATE INDEX memory_usage_session ON memory_usage(session_id,assistant_message_id)",
    )
    for statement in statements:
        db.execute(statement)
    # Preserve the historical schema-3 definition; migration 4 rebuilds it.
    create_memory_index(db, "unicode61")
    row = db.execute("SELECT value FROM settings WHERE id=1").fetchone()
    if row:
        settings = json.loads(row[0])
        settings.setdefault("memory_enabled", False)
        db.execute("UPDATE settings SET value=? WHERE id=1", (json.dumps(settings),))
