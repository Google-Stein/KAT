"""Owner-controlled memory, revision and provenance persistence."""

import sqlite3
from uuid import uuid4

from kat_core.memory_schemas import (
    MemoryCreate,
    MemoryEdit,
    MemoryRecord,
    MemoryStatusChange,
    MemorySupersede,
    MemoryUsage,
    Project,
    ProjectCreate,
)
from kat_core.schemas import AuditEntry, Session
from kat_core.storage import Store, timestamp


class MemoryError(ValueError):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


class MemoryStore:
    def __init__(self, store: Store) -> None:
        self.store = store

    @staticmethod
    def audit(db: sqlite3.Connection, event: str, memory_id: str, revision: int = 0) -> None:
        Store._insert_audit(
            db,
            AuditEntry(
                id=str(uuid4()),
                timestamp=timestamp(),
                event=event,
                details={"memory_id": memory_id, "revision": revision, "outcome": "completed"},
            ),
        )

    @staticmethod
    def record(db: sqlite3.Connection, row: sqlite3.Row) -> MemoryRecord:
        data = dict(row)
        data.pop("rowid", None)
        data["pinned"] = bool(data["pinned"])
        source = data["source_message_id"]
        data["source_available"] = (
            source is None
            or db.execute(
                "SELECT 1 FROM messages WHERE id=? AND session_id=?",
                (source, data["source_session_id"]),
            ).fetchone()
            is not None
        )
        return MemoryRecord(**data)

    def _get(self, db: sqlite3.Connection, memory_id: str) -> MemoryRecord:
        row = db.execute("SELECT * FROM memory_items WHERE id=?", (memory_id,)).fetchone()
        if row is None:
            raise MemoryError("Memory not found", 404)
        return self.record(db, row)

    def get(self, memory_id: str) -> MemoryRecord:
        with self.store.transaction() as db:
            return self._get(db, memory_id)

    @staticmethod
    def _project(db: sqlite3.Connection, project_id: str | None) -> None:
        if (
            project_id is not None
            and db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None
        ):
            raise MemoryError("Project not found", 404)

    def projects(self) -> list[Project]:
        with self.store.transaction() as db:
            return [
                Project(**dict(row))
                for row in db.execute("SELECT * FROM projects ORDER BY name,id")
            ]

    def create_project(self, body: ProjectCreate) -> Project:
        project = Project(
            id=str(uuid4()), name=body.name, created_at=timestamp(), updated_at=timestamp()
        )
        with self.store.transaction() as db:
            db.execute(
                "INSERT INTO projects VALUES (?,?,?,?)", tuple(project.model_dump().values())
            )
            Store._insert_audit(
                db,
                AuditEntry(
                    id=str(uuid4()),
                    timestamp=timestamp(),
                    event="project_created",
                    details={"project_id": project.id},
                ),
            )
        return project

    def set_session_project(self, session_id: str, project_id: str | None) -> Session:
        with self.store.transaction() as db:
            self._project(db, project_id)
            if (
                db.execute(
                    "UPDATE sessions SET project_id=? WHERE id=?", (project_id, session_id)
                ).rowcount
                != 1
            ):
                raise MemoryError("Conversation not found", 404)
        session = self.store.session(session_id)
        assert session is not None
        return session

    @staticmethod
    def _write(db: sqlite3.Connection, record: MemoryRecord, *, create: bool = False) -> None:
        fields = record.model_dump(exclude={"source_available"})
        fields["pinned"] = int(record.pinned)
        if create:
            db.execute(
                "INSERT INTO memory_items("
                + ",".join(fields)
                + ") VALUES ("
                + ",".join("?" for _ in fields)
                + ")",
                tuple(fields.values()),
            )
        else:
            db.execute(
                "UPDATE memory_items SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?",
                (*fields.values(), record.id),
            )
        db.execute(
            "INSERT INTO memory_revisions VALUES (?,?,?)",
            (record.id, record.revision, record.model_dump_json()),
        )

    def create(self, body: MemoryCreate) -> MemoryRecord:
        with self.store.transaction() as db:
            self._project(db, body.project_id)
            source_role = None
            if body.source_message_id:
                source = db.execute(
                    "SELECT role FROM messages WHERE id=? AND session_id=?",
                    (body.source_message_id, body.source_session_id),
                ).fetchone()
                if source is None or source["role"] not in {"user", "assistant"}:
                    raise MemoryError("Choose an existing user or assistant message as the source")
                source_role = source["role"]
            now = timestamp()
            record = MemoryRecord(
                **body.model_dump(exclude={"confirmed"}),
                id=str(uuid4()),
                status="confirmed",
                created_at=now,
                updated_at=now,
                last_reviewed_at=now,
                revision=1,
                source_role=source_role,
            )
            self._write(db, record, create=True)
            self.audit(db, "memory_created", record.id, record.revision)
            return record

    @staticmethod
    def _expected(record: MemoryRecord, expected: int) -> None:
        if record.revision != expected:
            raise MemoryError("This memory changed. Refresh before saving your review.", 409)

    def edit(self, memory_id: str, body: MemoryEdit) -> MemoryRecord:
        with self.store.transaction() as db:
            record = self._get(db, memory_id)
            self._expected(record, body.expected_revision)
            self._project(db, body.project_id)
            # Scope is immutable; an explicit new item avoids moving private project
            # evidence into a broader personal retrieval scope through an ordinary edit.
            if (body.scope, body.project_id) != (record.scope, record.project_id):
                raise MemoryError("Create a new memory to change its scope")
            data = record.model_dump() | body.model_dump(exclude={"expected_revision"})
            data.update(
                revision=record.revision + 1, updated_at=timestamp(), last_reviewed_at=timestamp()
            )
            updated = MemoryRecord(**data)
            self._write(db, updated)
            self.audit(db, "memory_edited", memory_id, updated.revision)
            return updated

    def status(self, memory_id: str, body: MemoryStatusChange) -> MemoryRecord:
        with self.store.transaction() as db:
            record = self._get(db, memory_id)
            self._expected(record, body.expected_revision)
            if record.status == "superseded":
                raise MemoryError("A superseded memory stays historical; review its replacement")
            data = record.model_dump() | {
                "status": body.status,
                "revision": record.revision + 1,
                "updated_at": timestamp(),
                "last_reviewed_at": timestamp(),
            }
            updated = MemoryRecord(**data)
            self._write(db, updated)
            self.audit(db, "memory_status_changed", memory_id, updated.revision)
            return updated

    def supersede(self, memory_id: str, body: MemorySupersede) -> MemoryRecord:
        with self.store.transaction() as db:
            record, replacement = self._get(db, memory_id), self._get(db, body.replacement_id)
            self._expected(record, body.expected_revision)
            if (
                record.id == replacement.id
                or replacement.status != "confirmed"
                or record.status == "superseded"
            ):
                raise MemoryError("Choose a different current confirmed replacement")
            if (record.scope, record.project_id) != (replacement.scope, replacement.project_id):
                raise MemoryError("Replacement must have the same scope")
            updated = MemoryRecord(
                **(
                    record.model_dump()
                    | {
                        "status": "superseded",
                        "superseded_by": replacement.id,
                        "revision": record.revision + 1,
                        "updated_at": timestamp(),
                        "last_reviewed_at": timestamp(),
                    }
                )
            )
            self._write(db, updated)
            self.audit(db, "memory_superseded", memory_id, updated.revision)
            return updated

    def forget(self, memory_id: str) -> None:
        with self.store.transaction() as db:
            self._get(db, memory_id)
            db.execute("DELETE FROM memory_items WHERE id=?", (memory_id,))
            # Merge away deleted FTS postings, including its shadow segment copies.
            # secure_delete clears main-table cells; old backups/transcripts remain separate.
            db.execute("INSERT INTO memory_fts(memory_fts) VALUES ('rebuild')")
            self.audit(db, "memory_forgotten", memory_id)

    def revisions(self, memory_id: str) -> list[MemoryRecord]:
        with self.store.transaction() as db:
            current = self._get(db, memory_id)
            return [
                MemoryRecord.model_validate_json(row[0]).model_copy(
                    update={"source_available": current.source_available}
                )
                for row in db.execute(
                    "SELECT snapshot FROM memory_revisions "
                    "WHERE memory_id=? ORDER BY revision DESC",
                    (memory_id,),
                )
            ]

    def rebuild(self) -> None:
        with self.store.transaction() as db:
            db.execute("INSERT INTO memory_fts(memory_fts) VALUES ('rebuild')")

    def usage(
        self, *, memory_id: str | None = None, session_id: str | None = None
    ) -> list[MemoryUsage]:
        with self.store.transaction() as db:
            where, values = (
                ("u.memory_id=?", (memory_id,)) if memory_id else ("u.session_id=?", (session_id,))
            )
            rows = db.execute(
                "SELECT u.*,r.snapshot FROM memory_usage u LEFT JOIN memory_revisions r "
                "ON r.memory_id=u.memory_id AND r.revision=u.revision WHERE "
                + where
                + " ORDER BY u.used_at DESC LIMIT 1000",
                values,
            )
            result = []
            for row in rows:
                data = dict(row)
                snapshot = data.pop("snapshot")
                result.append(
                    MemoryUsage(
                        **data,
                        forgotten=snapshot is None,
                        content=MemoryRecord.model_validate_json(snapshot).content
                        if snapshot
                        else None,
                    )
                )
            return result
