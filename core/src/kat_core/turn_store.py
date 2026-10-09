"""Transactional task bookkeeping. Private tool bodies stay in approval storage."""

import sqlite3
from typing import TYPE_CHECKING

from kat_core.continuation_schemas import (
    MAX_CONTINUATIONS,
    MODEL_BUDGET_SECONDS,
    ContinuationInfo,
    ContinuationState,
    TurnRecord,
)
from kat_core.schemas import Approval, Message, SettingsUpdate

if TYPE_CHECKING:
    from kat_core.storage import Store


class TurnStore:
    def __init__(self, store: "Store") -> None:
        self.store = store

    def create(self, user: Message, project_id: str | None) -> TurnRecord:
        with self.store.transaction() as db:
            route = db.execute("SELECT value,route_revision FROM settings WHERE id=1").fetchone()
            settings = SettingsUpdate.model_validate_json(route["value"])
            db.execute(
                "INSERT INTO continuations(origin_user_message_id,session_id,provider,model,"
                "local_endpoint,route_revision,project_id,state) VALUES(?,?,?,?,?,?,?,'running')",
                (
                    user.id,
                    user.session_id,
                    settings.provider,
                    settings.model,
                    settings.local_endpoint,
                    route["route_revision"],
                    project_id,
                ),
            )
        result = self.get(user.id)
        assert result is not None
        return result

    def get(self, origin: str) -> TurnRecord | None:
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT * FROM continuations WHERE origin_user_message_id=?", (origin,)
            ).fetchone()
            return TurnRecord(**dict(row)) if row else None

    def info(self, origin: str | None) -> ContinuationInfo | None:
        record = self.get(origin) if origin else None
        return (
            ContinuationInfo.model_validate(
                record.model_dump(include=set(ContinuationInfo.model_fields))
            )
            if record
            else None
        )

    def approvals(self, turn: TurnRecord) -> list[Approval]:
        return [
            a
            for a in self.store.approvals(turn.session_id)
            if a.origin_user_message_id == turn.origin_user_message_id
        ]

    def suppression(self, turn: TurnRecord) -> str | None:
        if turn.provider != "ollama":
            return "cloud_policy"
        settings = self.store.settings()
        with self.store.transaction() as db:
            revision = db.execute("SELECT route_revision FROM settings WHERE id=1").fetchone()[0]
        if (
            revision != turn.route_revision
            or settings.provider != turn.provider
            or settings.model != turn.model
            or settings.local_endpoint != turn.local_endpoint
        ):
            return "provider_changed"
        users = [m for m in self.store.messages(turn.session_id) if m.role == "user"]
        if not users or users[-1].id != turn.origin_user_message_id:
            return "conversation_advanced"
        session = self.store.session(turn.session_id)
        if session is None or session.project_id != turn.project_id:
            return "scope_changed"
        if turn.count >= MAX_CONTINUATIONS or turn.spent_seconds >= MODEL_BUDGET_SECONDS:
            return "budget_exhausted"
        return None

    def state(
        self,
        origin: str,
        state: ContinuationState,
        reason: str | None = None,
        assistant_message_id: str | None = None,
        db: sqlite3.Connection | None = None,
    ) -> None:
        if db is None:
            with self.store.transaction() as connection:
                self.state(origin, state, reason, assistant_message_id, connection)
            return
        db.execute(
            "UPDATE continuations SET state=?,reason=?,assistant_message_id=? "
            "WHERE origin_user_message_id=?",
            (state, reason, assistant_message_id, origin),
        )

    def add_time(self, origin: str, seconds: float) -> None:
        with self.store.transaction() as db:
            db.execute(
                "UPDATE continuations SET spent_seconds=spent_seconds+? "
                "WHERE origin_user_message_id=?",
                (seconds, origin),
            )

    def claim_continuation(self, origin: str) -> bool:
        with self.store.transaction() as db:
            return (
                db.execute(
                    "UPDATE continuations SET state='running',count=count+1,reason=NULL "
                    "WHERE origin_user_message_id=? AND state IN ('waiting','result_available') "
                    "AND count<? AND spent_seconds<?",
                    (origin, MAX_CONTINUATIONS, MODEL_BUDGET_SECONDS),
                ).rowcount
                == 1
            )

    def recover(self) -> None:
        with self.store.transaction() as db:
            rows = db.execute(
                "SELECT origin_user_message_id,session_id,provider FROM continuations "
                "WHERE state IN ('running','result_available')"
            ).fetchall()
            for row in rows:
                self.state(row["origin_user_message_id"], "failed", "core_restarted", db=db)
                self.store.add_audit(
                    "continuation_recovered",
                    session_id=row["session_id"],
                    details={
                        "origin_user_message_id": row["origin_user_message_id"],
                        "provider": row["provider"],
                        "reason": "core_restarted",
                    },
                )
