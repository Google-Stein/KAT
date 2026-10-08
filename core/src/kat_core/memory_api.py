"""Authenticated memory management; mounted under Core's global auth dependency."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from kat_core.memory_retrieval import fts_query
from kat_core.memory_schemas import (
    MemoryCreate,
    MemoryEdit,
    MemoryKind,
    MemoryRecord,
    MemoryStatus,
    MemoryStatusChange,
    MemorySupersede,
    MemoryToggle,
    MemoryUsage,
    Project,
    ProjectCreate,
    SessionScope,
)
from kat_core.memory_store import MemoryStore
from kat_core.schemas import Session
from kat_core.service import ChatService
from kat_core.storage import Store, timestamp


def memory_router(store: Store, service: ChatService) -> APIRouter:
    router = APIRouter()
    memories = MemoryStore(store)

    @router.get("/projects", response_model=list[Project])
    def projects() -> list[Project]:
        return memories.projects()

    @router.post("/projects", response_model=Project, status_code=201)
    def create_project(body: ProjectCreate) -> Project:
        return memories.create_project(body)

    @router.put("/sessions/{session_id}/scope", response_model=Session)
    def scope(session_id: str, body: SessionScope) -> Session:
        if service.lock(session_id).locked():
            raise HTTPException(409, "Wait for the active conversation request to finish")
        return memories.set_session_project(session_id, body.project_id)

    @router.put("/memory/settings")
    def toggle(body: MemoryToggle) -> dict[str, bool]:
        with store.transaction():
            settings = store.settings().model_copy(update={"memory_enabled": body.enabled})
            store.save_settings(settings)
            store.add_audit("memory_setting_changed", details={"enabled": body.enabled})
        return {"enabled": body.enabled}

    @router.get("/memories", response_model=list[MemoryRecord])
    def listing(
        q: Annotated[str, Query(max_length=2000)] = "",
        kind: MemoryKind | None = None,
        scope: Annotated[str | None, Query(pattern="^(personal|project)$")] = None,
        project_id: str | None = None,
        status: MemoryStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[MemoryRecord]:
        conditions, parameters = [], []
        for field, value in (("kind", kind), ("scope", scope), ("project_id", project_id)):
            if value is not None:
                conditions.append(f"m.{field}=?")
                parameters.append(value)
        if status == "expired":
            conditions.append("(m.status='expired' OR (m.status='confirmed' AND m.expires_at<=?))")
            parameters.append(timestamp())
        elif status:
            conditions.append("m.status=?")
            parameters.append(status)
            if status == "confirmed":
                conditions.append("(m.expires_at IS NULL OR m.expires_at>?)")
                parameters.append(timestamp())
        match = fts_query(q)
        if q.strip() and not match:
            return []
        source = "memory_items m"
        if match:
            source += " JOIN memory_fts ON m.rowid=memory_fts.rowid"
            conditions.append("memory_fts MATCH ?")
            parameters.append(match)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with store.transaction() as db:
            rows = db.execute(
                "SELECT m.* FROM "
                + source
                + where
                + " ORDER BY m.pinned DESC,m.updated_at DESC,m.id LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            )
            return [memories.record(db, row) for row in rows]

    @router.post("/memories", response_model=MemoryRecord, status_code=201)
    def create(body: MemoryCreate) -> MemoryRecord:
        return memories.create(body)

    @router.get("/memories/{memory_id}", response_model=MemoryRecord)
    def get(memory_id: str) -> MemoryRecord:
        return memories.get(memory_id)

    @router.put("/memories/{memory_id}", response_model=MemoryRecord)
    def edit(memory_id: str, body: MemoryEdit) -> MemoryRecord:
        return memories.edit(memory_id, body)

    @router.post("/memories/{memory_id}/status", response_model=MemoryRecord)
    def status_change(memory_id: str, body: MemoryStatusChange) -> MemoryRecord:
        return memories.status(memory_id, body)

    @router.post("/memories/{memory_id}/supersede", response_model=MemoryRecord)
    def supersede(memory_id: str, body: MemorySupersede) -> MemoryRecord:
        return memories.supersede(memory_id, body)

    @router.post("/memories/{memory_id}/forget")
    def forget(memory_id: str) -> dict[str, str]:
        memories.forget(memory_id)
        return {"status": "forgotten"}

    @router.get("/memories/{memory_id}/revisions", response_model=list[MemoryRecord])
    def revisions(memory_id: str) -> list[MemoryRecord]:
        return memories.revisions(memory_id)

    @router.get("/memories/{memory_id}/usage", response_model=list[MemoryUsage])
    def usage(memory_id: str) -> list[MemoryUsage]:
        memories.get(memory_id)
        return memories.usage(memory_id=memory_id)

    @router.get("/sessions/{session_id}/memory-usage", response_model=list[MemoryUsage])
    def session_usage(session_id: str) -> list[MemoryUsage]:
        if store.session(session_id) is None:
            raise HTTPException(404, "Conversation not found")
        return memories.usage(session_id=session_id)

    return router
