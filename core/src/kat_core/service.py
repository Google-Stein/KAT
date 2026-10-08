"""Conversation orchestration, permission gates, and durable tool outcomes."""

import asyncio
import json
import logging
from typing import Any

from kat_core.errors import ProviderErrorCode, ProviderFailure
from kat_core.permissions import PermissionPolicy
from kat_core.provider import ModelRuntime, ProviderUnavailableError
from kat_core.schemas import Approval, ChatResponse
from kat_core.storage import Store
from kat_core.tools import ToolExecutionError, ToolRegistry

logger = logging.getLogger("kat_core.service")


class SessionBusyError(RuntimeError):
    pass


class ApprovalConflictError(RuntimeError):
    pass


class ChatService:
    def __init__(self, store: Store, runtime: ModelRuntime, registry: ToolRegistry) -> None:
        self.store, self.runtime, self.registry = store, runtime, registry
        self._session_locks: dict[str, asyncio.Lock] = {}

    def lock(self, session_id: str) -> asyncio.Lock:
        return self._session_locks.setdefault(session_id, asyncio.Lock())

    async def chat(self, session_id: str, content: str) -> ChatResponse:
        if not self.runtime.ready:
            raise ProviderUnavailableError()
        lock = self.lock(session_id)
        if lock.locked():
            raise SessionBusyError("This conversation already has a request in progress")
        async with lock:
            settings = self.store.settings()
            user_message = self.store.add_message(session_id, "user", content)
            created_approvals: list[str] = []

            async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                try:
                    spec = self.registry.get(name)
                    validated = self.registry.validate_args(name, arguments)
                except (ValueError, TypeError, ToolExecutionError):
                    self.store.add_audit(
                        "tool_rejected",
                        session_id=session_id,
                        tool_name=name
                        if name in {item.name for item in self.registry.specs()}
                        else None,
                        details={"reason": "invalid_or_disallowed_request"},
                        error="Invalid or disallowed tool request",
                    )
                    return {"status": "failed", "error": "Invalid or disallowed tool arguments"}
                clean_arguments = validated.model_dump()
                self.store.add_audit(
                    "tool_requested",
                    session_id=session_id,
                    tool_name=name,
                    details={"arguments": clean_arguments, "risk": spec.risk.value},
                )
                policy = PermissionPolicy(settings.require_approval_for_low_risk)
                if policy.requires_approval(spec.risk):
                    approval = self.store.create_approval(
                        session_id,
                        name,
                        clean_arguments,
                        spec.risk.value,
                    )
                    created_approvals.append(approval.id)
                    self.store.add_audit(
                        "approval_requested",
                        session_id=session_id,
                        tool_name=name,
                        approval_id=approval.id,
                        details={"risk": spec.risk.value},
                    )
                    return {
                        "status": "pending_approval",
                        "approval_id": approval.id,
                        "tool_name": name,
                        "arguments": clean_arguments,
                    }
                self.store.add_audit(
                    "approval_decision",
                    session_id=session_id,
                    tool_name=name,
                    details={"approved": True, "source": "low_risk_policy"},
                )
                outcome = await self._execute(name, clean_arguments)
                self.store.add_audit(
                    "tool_result",
                    session_id=session_id,
                    tool_name=name,
                    details=outcome,
                    error=outcome.get("error"),
                )
                self.store.add_message(
                    session_id, "tool", json.dumps({"tool_name": name, **outcome})
                )
                return outcome

            try:
                async with asyncio.timeout(120):
                    text = await self.runtime.respond(
                        self.store.messages(session_id), settings, self.registry, dispatch
                    )
            except Exception as error:
                failure = (
                    error
                    if isinstance(error, ProviderFailure)
                    else ProviderFailure(
                        ProviderErrorCode.TIMEOUT
                        if isinstance(error, TimeoutError)
                        else ProviderErrorCode.FAILED
                    )
                )
                logger.warning(
                    "model_request_failed session_id=%s category=%s", session_id, failure.code.value
                )
                self.store.add_audit(
                    "provider_error",
                    session_id=session_id,
                    error=str(failure),
                    details={"code": failure.code.value, "provider": settings.provider},
                )
                raise failure from None
            assistant = self.store.add_message(session_id, "assistant", text)
            approvals = [self.store.approval(approval_id) for approval_id in created_approvals]
            return ChatResponse(
                user_message=user_message,
                assistant_message=assistant,
                approvals=[item for item in approvals if item is not None],
            )

    async def _execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            # Work is fixed and bounded: local clock or one fixed process launch.
            result = await asyncio.to_thread(self.registry.execute, name, arguments)
            return {"status": "completed", "result": result}
        except Exception as error:
            logger.warning(
                "tool_execution_failed tool=%s exception_type=%s", name, type(error).__name__
            )
            return {"status": "failed", "error": "The configured tool could not be executed"}

    async def decide(self, approval: Approval, approved: bool) -> Approval:
        lock = self.lock(approval.session_id)
        if lock.locked():
            raise SessionBusyError("Wait for the active conversation request to finish")
        async with lock:
            if not self.store.claim_approval(approval.id, approved):
                raise ApprovalConflictError("This approval has already been decided")
            if approved:
                outcome = await self._execute(approval.tool_name, approval.arguments)
                self.store.complete_approval(
                    approval.id, result=outcome.get("result"), error=outcome.get("error")
                )
            updated = self.store.approval(approval.id)
            assert updated is not None
            return updated
