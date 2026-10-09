"""Metadata-only durable approval origins and model continuation claims."""

import sqlite3


def continuation_schema(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE settings ADD COLUMN route_revision INTEGER NOT NULL DEFAULT 0")
    db.execute(
        "ALTER TABLE messages ADD COLUMN origin_user_message_id TEXT REFERENCES messages(id)"
    )
    db.execute("ALTER TABLE messages ADD COLUMN transient_tool_context INTEGER NOT NULL DEFAULT 0")
    db.execute("""CREATE TABLE continuations (
        origin_user_message_id TEXT PRIMARY KEY REFERENCES messages(id),
        session_id TEXT NOT NULL REFERENCES sessions(id),
        provider TEXT NOT NULL, model TEXT NOT NULL, local_endpoint TEXT NOT NULL,
        route_revision INTEGER NOT NULL, project_id TEXT,
        state TEXT NOT NULL, reason TEXT, count INTEGER NOT NULL DEFAULT 0,
        approvals_created INTEGER NOT NULL DEFAULT 0,
        spent_seconds REAL NOT NULL DEFAULT 0,
        assistant_message_id TEXT REFERENCES messages(id))""")
    db.execute(
        "ALTER TABLE approvals ADD COLUMN origin_user_message_id TEXT "
        "REFERENCES continuations(origin_user_message_id)"
    )
    db.execute("ALTER TABLE approvals ADD COLUMN continuation_policy TEXT NOT NULL DEFAULT 'none'")
    db.execute("CREATE INDEX approvals_origin ON approvals(origin_user_message_id,created_at,id)")
