"""Explicit task identity and bounded current-task data; never ordinary history."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ContinuationState = Literal[
    "running", "waiting", "result_available", "completed", "suppressed", "failed"
]
ContinuationPolicy = Literal["none", "local_result"]


class ContinuationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    origin_user_message_id: str
    provider: Literal["openai", "ollama"]
    state: ContinuationState
    reason: str | None = None
    count: int = 0
    assistant_message_id: str | None = None


class ApprovedToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approval_id: str
    tool_name: str
    arguments: dict[str, Any]
    outcome: dict[str, Any]


class ContinuationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    origin_user_message_id: str
    results: list[ApprovedToolResult] = Field(min_length=1, max_length=6)


class TurnRecord(ContinuationInfo):
    session_id: str
    model: str
    local_endpoint: str
    route_revision: int
    project_id: str | None
    approvals_created: int = 0
    spent_seconds: float = 0.0


MAX_CONTINUATIONS = 3
MAX_APPROVALS = 6
MODEL_BUDGET_SECONDS = 120.0
MAX_RESULT_CONTEXT_CHARS = 28000
