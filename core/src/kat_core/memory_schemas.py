"""Typed owner-controlled memory contracts; no extraction or action capabilities."""

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MemoryKind = Literal["semantic", "episodic", "project_state", "commitment", "procedure"]
MemoryStatus = Literal["confirmed", "superseded", "disputed", "expired"]


class MemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def safe_wording(value: str) -> str:
    value = value.strip()
    patterns = (
        r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}",
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----",
        r"\b(?:password|passwd|api[_ -]?key|access[_ -]?token|auth[_ -]?token|"
        r"client[_ -]?secret|secret[_ -]?key|token)\s*[:=]\s*\S+",
    )
    if not value or any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
        raise ValueError("Memory must contain normal information, never credentials or secrets")
    return value


class Project(MemoryModel):
    id: str
    name: str
    created_at: str
    updated_at: str


class ProjectCreate(MemoryModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return safe_wording(value)


class MemoryFields(MemoryModel):
    kind: MemoryKind = "semantic"
    content: str = Field(min_length=1, max_length=2000)
    scope: Literal["personal", "project"] = "personal"
    project_id: str | None = None
    sensitivity: Literal["normal"] = "normal"
    pinned: bool = False
    importance: int = Field(default=0, ge=0, le=3)
    effective_at: str | None = None
    expires_at: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return safe_wording(value)

    @field_validator("effective_at", "expires_at")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError
            return parsed.astimezone(UTC).isoformat()
        except ValueError:
            raise ValueError("Memory dates require an ISO timestamp with a timezone") from None

    @model_validator(mode="after")
    def validate_scope(self) -> "MemoryFields":
        if (self.scope == "project") != (self.project_id is not None):
            raise ValueError("Project scope requires a project ID; personal scope has none")
        if self.effective_at and self.expires_at and self.expires_at <= self.effective_at:
            raise ValueError("Expiry must follow the effective timestamp")
        return self


class MemoryCreate(MemoryFields):
    confirmed: Literal[True]
    origin: Literal["owner_explicit", "conversation_selection"] = "owner_explicit"
    source_session_id: str | None = None
    source_message_id: str | None = None

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("Explicit owner confirmation is required")
        return value

    @model_validator(mode="after")
    def validate_source(self) -> "MemoryCreate":
        has_source = self.source_session_id is not None and self.source_message_id is not None
        if self.origin == "conversation_selection" and not has_source:
            raise ValueError("Conversation selection requires a source session and message")
        if self.origin == "owner_explicit" and (
            self.source_session_id is not None or self.source_message_id is not None
        ):
            raise ValueError("Direct owner entry does not have a conversation source")
        return self


class MemoryEdit(MemoryFields):
    expected_revision: int = Field(ge=1)


class MemoryStatusChange(MemoryModel):
    status: Literal["confirmed", "disputed", "expired"]
    expected_revision: int = Field(ge=1)


class MemorySupersede(MemoryModel):
    replacement_id: str
    expected_revision: int = Field(ge=1)


class MemoryRecord(MemoryFields):
    id: str
    status: MemoryStatus
    origin: Literal["owner_explicit", "conversation_selection"]
    created_at: str
    updated_at: str
    last_reviewed_at: str
    revision: int
    superseded_by: str | None = None
    source_session_id: str | None = None
    source_message_id: str | None = None
    source_role: Literal["user", "assistant"] | None = None
    source_available: bool = True


class MemoryContextItem(MemoryModel):
    id: str
    revision: int
    kind: MemoryKind
    scope: Literal["personal", "project"]
    project_id: str | None
    content: str
    origin: Literal["owner_explicit", "conversation_selection"]


class MemoryUsage(MemoryModel):
    memory_id: str
    revision: int
    session_id: str
    assistant_message_id: str
    provider: Literal["ollama"]
    used_at: str
    content: str | None = None
    forgotten: bool = False


class MemoryToggle(MemoryModel):
    enabled: bool


class SessionScope(MemoryModel):
    project_id: str | None = None
