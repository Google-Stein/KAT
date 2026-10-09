"""Validated public API and persistent data schemas."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from kat_core.endpoints import local_endpoint


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Session(StrictModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    project_id: str | None = None


class SessionCreate(StrictModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class Message(StrictModel):
    id: str
    session_id: str
    role: Literal["user", "assistant", "tool"]
    content: str
    created_at: str


class MessageCreate(StrictModel):
    content: str = Field(min_length=1, max_length=32000)


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    COMPLETED = "completed"
    FAILED = "failed"


class Approval(StrictModel):
    id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk: Literal["low", "medium", "high"]
    status: Literal["pending", "approved", "denied", "completed", "failed"]
    created_at: str
    result: dict[str, Any] | None = None
    error: str | None = None
    display_context: str | None = None


class ApprovalDecision(StrictModel):
    approved: bool


class ChatResponse(StrictModel):
    user_message: Message
    assistant_message: Message
    approvals: list[Approval]


class SettingsUpdate(StrictModel):
    provider: Literal["openai", "ollama"] = "openai"
    model: str = Field(default="gpt-4.1-mini", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,119}$")
    require_approval_for_low_risk: bool = False
    local_endpoint: str = "http://127.0.0.1:11434"
    memory_enabled: bool = False

    @field_validator("local_endpoint")
    @classmethod
    def validate_local_endpoint(cls, value: str) -> str:
        return local_endpoint(value)


class Settings(SettingsUpdate):
    api_key_configured: bool
    application_allowlist: list[dict[str, str]]


class ProviderCapabilities(StrictModel):
    chat: bool = True
    tool_calling: bool
    structured_output: bool = False
    streaming: bool = False
    context_limit: int | None = None


class ProviderDescriptor(StrictModel):
    id: Literal["openai", "ollama"]
    label: str
    local: bool
    capabilities: ProviderCapabilities


class ProviderStatus(StrictModel):
    provider: Literal["openai", "ollama"]
    status: Literal[
        "ready", "configured", "not_configured", "model_missing", "unreachable", "error"
    ]
    message: str
    models: list[str] = Field(default_factory=list)
    tool_calling: bool = False
    error_code: str | None = None


class AuditEntry(StrictModel):
    id: str
    timestamp: str
    event: str
    session_id: str | None = None
    tool_name: str | None = None
    approval_id: str | None = None
    details: dict[str, Any]
    error: str | None = None
