"""Small transactional SQLite store; conversation data stays on the local machine."""

import json
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from kat_core.migrations import migrate
from kat_core.schemas import Approval, AuditEntry, Message, Session, SettingsUpdate


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path, default_model: str = "gpt-4.1-mini") -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA secure_delete=ON")
            try:
                migrate(self._db, path)
                self._db.execute("PRAGMA journal_mode=WAL")
            except BaseException:
                self._db.close()
                raise
            initial = SettingsUpdate(model=default_model)
            self._db.execute(
                "INSERT OR IGNORE INTO settings(id,value) VALUES (1,?)",
                (initial.model_dump_json(),),
            )
            self._db.commit()
        if path.exists():
            path.chmod(0o600)
        # A process crash can leave a claimed action with an unknown external outcome.
        # Never replay it automatically: at-most-once dispatch is safer than duplicate launching.
        for approval in self.approvals(status="approved"):
            error = "Core stopped during execution; outcome is unknown. The action will not replay."
            self.complete_approval(approval.id, error=error)
            self.add_audit(
                "tool_interrupted",
                session_id=approval.session_id,
                tool_name=approval.tool_name,
                approval_id=approval.id,
                error=error,
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._db:
            yield self._db

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def sessions(self) -> list[Session]:
        with self._lock:
            return [
                Session(**dict(row))
                for row in self._db.execute("SELECT * FROM sessions ORDER BY updated_at DESC, id")
            ]

    def session(self, session_id: str) -> Session | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            return Session(**dict(row)) if row else None

    def create_session(self, title: str) -> Session:
        session = Session(
            id=str(uuid4()), title=title, created_at=timestamp(), updated_at=timestamp()
        )
        with self.transaction() as db:
            db.execute(
                "INSERT INTO sessions(id,title,created_at,updated_at,project_id) "
                "VALUES (?,?,?,?,?)",
                tuple(session.model_dump().values()),
            )
        return session

    def messages(self, session_id: str) -> list[Message]:
        with self._lock:
            return [
                Message(**dict(row))
                for row in self._db.execute(
                    "SELECT id,session_id,role,content,created_at FROM messages "
                    "WHERE session_id=? ORDER BY sequence",
                    (session_id,),
                )
            ]

    def add_message(
        self,
        session_id: str,
        role: Literal["user", "assistant", "tool"],
        content: str,
        *,
        after_insert: Callable[[sqlite3.Connection, Message], None] | None = None,
    ) -> Message:
        message = Message(
            id=str(uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=timestamp(),
        )
        with self.transaction() as db:
            db.execute(
                "INSERT INTO messages(id,session_id,role,content,created_at) VALUES (?,?,?,?,?)",
                tuple(message.model_dump().values()),
            )
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (timestamp(), session_id))
            if after_insert is not None:
                after_insert(db, message)
        return message

    def settings(self) -> SettingsUpdate:
        with self._lock:
            row = self._db.execute("SELECT value FROM settings WHERE id=1").fetchone()
            assert row is not None
            return SettingsUpdate.model_validate_json(row[0])

    def save_settings(self, settings: SettingsUpdate) -> None:
        with self.transaction() as db:
            db.execute("UPDATE settings SET value=? WHERE id=1", (settings.model_dump_json(),))

    @staticmethod
    def _approval(row: sqlite3.Row) -> Approval:
        data = dict(row)
        data["arguments"] = json.loads(data["arguments"])
        data["result"] = json.loads(data["result"]) if data["result"] else None
        return Approval(**data)

    def approval(self, approval_id: str) -> Approval | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            return self._approval(row) if row else None

    def approvals(self, session_id: str | None = None, status: str | None = None) -> list[Approval]:
        conditions, values = [], []
        if session_id is not None:
            conditions.append("session_id=?")
            values.append(session_id)
        if status is not None:
            conditions.append("status=?")
            values.append(status)
        clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._lock:
            return [
                self._approval(row)
                for row in self._db.execute(
                    "SELECT * FROM approvals" + clause + " ORDER BY created_at,id", values
                )
            ]

    def create_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        risk: Literal["low", "medium", "high"],
        display_context: str | None = None,
    ) -> Approval:
        approval = Approval(
            id=str(uuid4()),
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            risk=risk,
            status="pending",
            created_at=timestamp(),
            display_context=display_context,
        )
        with self.transaction() as db:
            db.execute(
                "INSERT INTO approvals(id,session_id,tool_name,arguments,risk,status,"
                "created_at,display_context) VALUES (?,?,?,?,?,?,?,?)",
                (
                    approval.id,
                    session_id,
                    tool_name,
                    json.dumps(arguments),
                    risk,
                    approval.status,
                    approval.created_at,
                    display_context,
                ),
            )
        return approval

    def claim_approval(self, approval_id: str, approved: bool) -> bool:
        with self.transaction() as db:
            cursor = db.execute(
                "UPDATE approvals SET status=? WHERE id=? AND status='pending'",
                ("approved" if approved else "denied", approval_id),
            )
            if cursor.rowcount != 1:
                return False
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            assert row is not None
            self._insert_audit(
                db,
                AuditEntry(
                    id=str(uuid4()),
                    timestamp=timestamp(),
                    event="approval_decision",
                    session_id=row["session_id"],
                    tool_name=row["tool_name"],
                    approval_id=approval_id,
                    details={"approved": approved},
                ),
            )
            if not approved:
                self._insert_tool_message(
                    db,
                    row["session_id"],
                    {
                        "tool_name": row["tool_name"],
                        "approval_id": approval_id,
                        "status": "denied",
                    },
                )
            return True

    @staticmethod
    def _insert_tool_message(
        db: sqlite3.Connection, session_id: str, result: dict[str, Any]
    ) -> None:
        now = timestamp()
        db.execute(
            "INSERT INTO messages(id,session_id,role,content,created_at) VALUES (?,?,?,?,?)",
            (str(uuid4()), session_id, "tool", json.dumps(result), now),
        )
        db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))

    def complete_approval(
        self,
        approval_id: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        audit_result: dict[str, Any] | None = None,
    ) -> None:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            cursor = db.execute(
                "UPDATE approvals SET status=?,result=?,error=? WHERE id=? AND status='approved'",
                (
                    "failed" if error else "completed",
                    json.dumps(result) if result is not None else None,
                    error,
                    approval_id,
                ),
            )
            if cursor.rowcount == 1 and row is not None:
                status = "failed" if error else "completed"
                self._insert_audit(
                    db,
                    AuditEntry(
                        id=str(uuid4()),
                        timestamp=timestamp(),
                        event="tool_result",
                        session_id=row["session_id"],
                        tool_name=row["tool_name"],
                        approval_id=approval_id,
                        details={
                            "status": status,
                            "result": audit_result if audit_result is not None else result,
                        },
                        error=error,
                    ),
                )
                self._insert_tool_message(
                    db,
                    row["session_id"],
                    {
                        "tool_name": row["tool_name"],
                        "approval_id": approval_id,
                        "status": status,
                        "result": result,
                        "error": error,
                    },
                )

    @staticmethod
    def _insert_audit(db: sqlite3.Connection, entry: AuditEntry) -> None:
        db.execute(
            "INSERT INTO audit(id,timestamp,event,session_id,tool_name,approval_id,details,error) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                entry.id,
                entry.timestamp,
                entry.event,
                entry.session_id,
                entry.tool_name,
                entry.approval_id,
                json.dumps(entry.details),
                entry.error,
            ),
        )

    def add_audit(
        self,
        event: str,
        *,
        session_id: str | None = None,
        tool_name: str | None = None,
        approval_id: str | None = None,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            id=str(uuid4()),
            timestamp=timestamp(),
            event=event,
            session_id=session_id,
            tool_name=tool_name,
            approval_id=approval_id,
            details=details or {},
            error=error,
        )
        with self.transaction() as db:
            self._insert_audit(db, entry)
        return entry

    def audit(self, limit: int) -> list[AuditEntry]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id,timestamp,event,session_id,tool_name,approval_id,details,error "
                "FROM audit ORDER BY sequence DESC LIMIT ?",
                (limit,),
            )
            entries = []
            for row in rows:
                data = dict(row)
                data["details"] = json.loads(data["details"])
                entries.append(AuditEntry(**data))
            return entries
