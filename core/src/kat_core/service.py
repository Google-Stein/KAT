"""Conversation orchestration, permission gates, and durable tool outcomes."""

import asyncio
import logging
import sqlite3
import time
from typing import Any

from kat_core.capability_schemas import CapabilityFailure
from kat_core.continuation_schemas import (
    MAX_RESULT_CONTEXT_CHARS,
    MODEL_BUDGET_SECONDS,
    ApprovedToolResult,
    ContinuationContext,
    TurnRecord,
)
from kat_core.errors import ProviderErrorCode, ProviderFailure
from kat_core.memory_retrieval import MemoryRetrieval
from kat_core.memory_store import MemoryStore
from kat_core.provider import ModelRuntime, ProviderUnavailableError
from kat_core.schemas import Approval, ApprovalDecisionResponse, ChatResponse, Message
from kat_core.storage import Store
from kat_core.tool_dispatch import TaskDispatcher
from kat_core.tools import ToolRegistry
from kat_core.turn_store import TurnStore

logger = logging.getLogger("kat_core.service")


class SessionBusyError(RuntimeError):
    pass


class ApprovalConflictError(RuntimeError):
    pass


class ChatService:
    def __init__(self, store: Store, runtime: ModelRuntime, registry: ToolRegistry) -> None:
        self.store, self.runtime, self.registry = store, runtime, registry
        self.turns = TurnStore(store)
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
            user = self.store.add_message(session_id, "user", content)
            session = self.store.session(session_id)
            turn = self.turns.create(user, session.project_id if session else None)
            assistant, approvals = await self._model_step(turn)
            return ChatResponse(user_message=user, assistant_message=assistant, approvals=approvals)

    async def _model_step(
        self, turn: TurnRecord, continuation: ContinuationContext | None = None
    ) -> tuple[Message, list[Approval]]:
        settings = self.store.settings()
        messages = self.store.messages(turn.session_id)
        origin_index = next(
            i for i, m in enumerate(messages) if m.id == turn.origin_user_message_id
        )
        messages = messages[: origin_index + 1]
        retrieval = MemoryRetrieval(MemoryStore(self.store))
        memory = (
            retrieval.retrieve(messages[-1].content, turn.project_id)
            if settings.memory_enabled and turn.provider == "ollama"
            else []
        )
        # Fix the original route even if owner Settings changes while inference runs.
        settings = settings.model_copy(
            update={
                "provider": turn.provider,
                "model": turn.model,
                "local_endpoint": turn.local_endpoint,
            }
        )
        dispatch = TaskDispatcher(self.store, self.registry, turn, self._execute)
        started = time.monotonic()
        try:
            remaining = MODEL_BUDGET_SECONDS - turn.spent_seconds
            if remaining <= 0:
                raise TimeoutError()
            async with asyncio.timeout(remaining):
                if continuation is not None:
                    text = await self.runtime.respond(
                        messages,
                        settings,
                        self.registry,
                        dispatch,
                        memory,
                        continuation=continuation,
                    )
                elif memory:
                    text = await self.runtime.respond(
                        messages, settings, self.registry, dispatch, memory
                    )
                else:
                    text = await self.runtime.respond(messages, settings, self.registry, dispatch)
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                self.turns.state(turn.origin_user_message_id, "failed", "request_interrupted")
                raise
            failure = (
                error
                if isinstance(error, ProviderFailure)
                else ProviderFailure(
                    ProviderErrorCode.TIMEOUT
                    if isinstance(error, TimeoutError)
                    else ProviderErrorCode.FAILED
                )
            )
            self.turns.state(turn.origin_user_message_id, "failed", failure.code.value)
            logger.warning(
                "model_request_failed session_id=%s category=%s",
                turn.session_id,
                failure.code.value,
            )
            self.store.add_audit(
                "provider_error",
                session_id=turn.session_id,
                error=str(failure),
                details={"code": failure.code.value, "provider": turn.provider},
            )
            raise failure from None
        finally:
            self.turns.add_time(turn.origin_user_message_id, time.monotonic() - started)
        pending = [a for a in self.turns.approvals(turn) if a.status == "pending"]

        def commit_reply(db: sqlite3.Connection, message: Message) -> None:
            retrieval.record_usage(memory, turn.session_id, message.id, db=db)
            self.turns.state(
                turn.origin_user_message_id,
                "waiting" if pending else "completed",
                assistant_message_id=message.id,
                db=db,
            )

        assistant = self.store.add_message(
            turn.session_id,
            "assistant",
            text,
            origin_user_message_id=turn.origin_user_message_id,
            transient_tool_context=continuation is not None,
            after_insert=commit_reply,
        )
        approvals = [self.store.approval(a) for a in dispatch.created_approvals]
        return assistant, [a for a in approvals if a is not None]

    def _decision_response(self, approval_id: str) -> ApprovalDecisionResponse:
        approval = self.store.approval(approval_id)
        assert approval is not None
        info = approval.continuation
        assistant = None
        if info and info.count > 0 and info.assistant_message_id:
            assistant = next(
                (
                    m
                    for m in self.store.messages(approval.session_id)
                    if m.id == info.assistant_message_id
                ),
                None,
            )
        pending = [
            a
            for a in self.store.approvals(approval.session_id)
            if a.origin_user_message_id == approval.origin_user_message_id and a.status == "pending"
        ]
        return ApprovalDecisionResponse(
            **approval.model_dump(), assistant_message=assistant, new_approvals=pending
        )

    def _audit_continuation(self, approval: Approval) -> None:
        info = self.turns.info(approval.origin_user_message_id)
        if info is not None:
            self.store.add_audit(
                "continuation_status",
                session_id=approval.session_id,
                tool_name=approval.tool_name,
                approval_id=approval.id,
                details=info.model_dump(),
            )

    async def _continue(self, approval: Approval) -> None:
        turn = (
            self.turns.get(approval.origin_user_message_id)
            if approval.origin_user_message_id
            else None
        )
        if turn is None or turn.state in {"completed", "suppressed", "failed"}:
            return
        approvals = self.turns.approvals(turn)
        eligible = [a for a in approvals if a.continuation_policy == "local_result"]
        if not eligible:
            if not any(a.status == "pending" for a in approvals):
                self.turns.state(turn.origin_user_message_id, "completed")
            return
        reason = self.turns.suppression(turn)
        if any(a.status == "denied" for a in approvals):
            reason = "approval_denied"
        elif any(a.status == "failed" for a in approvals):
            reason = "tool_failed"
        if reason:
            self.turns.state(turn.origin_user_message_id, "suppressed", reason)
            self._audit_continuation(approval)
            return
        if any(a.status in {"pending", "approved"} for a in approvals):
            self._audit_continuation(approval)
            return
        context = ContinuationContext(
            origin_user_message_id=turn.origin_user_message_id,
            results=[
                ApprovedToolResult(
                    approval_id=a.id,
                    tool_name=a.tool_name,
                    arguments=a.arguments,
                    outcome={"status": "completed", "result": a.result},
                )
                for a in eligible
                if a.status == "completed"
            ],
        )
        if len(context.model_dump_json()) > MAX_RESULT_CONTEXT_CHARS:
            self.turns.state(turn.origin_user_message_id, "suppressed", "result_context_limit")
            self._audit_continuation(approval)
            return
        if not self.turns.claim_continuation(turn.origin_user_message_id):
            return
        self._audit_continuation(approval)
        try:
            await self._model_step(turn, context)
        except ProviderFailure:
            # Execution remains completed; continuation failure can never unclaim it.
            pass
        finally:
            self._audit_continuation(approval)

    async def _execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            # Each capability owns its explicit I/O and output bounds.
            async with asyncio.timeout(12):
                result = await asyncio.to_thread(self.registry.execute, name, arguments)
            return {"status": "completed", "result": result}
        except TimeoutError:
            return {
                "status": "failed",
                "error_code": "tool_timeout",
                "error": "The tool exceeded its 12-second execution deadline.",
            }
        except CapabilityFailure as error:
            return {"status": "failed", "error_code": error.code, "error": str(error)}
        except Exception as error:
            logger.warning(
                "tool_execution_failed tool=%s exception_type=%s", name, type(error).__name__
            )
            return {"status": "failed", "error": "The configured tool could not be executed"}

    async def decide(self, approval: Approval, approved: bool) -> ApprovalDecisionResponse:
        # One owner for execution + continuation. Do not recursively acquire this lock.
        async with self.lock(approval.session_id):
            current = self.store.approval(approval.id)
            assert current is not None
            if current.status != "pending":
                if (current.status == "denied") == approved:
                    raise ApprovalConflictError("This approval has a different recorded decision")
                return self._decision_response(approval.id)
            if not self.store.claim_approval(approval.id, approved):
                return self._decision_response(approval.id)
            if approved:
                outcome = await self._execute(current.tool_name, current.arguments)
                self.store.complete_approval(
                    current.id,
                    result=outcome.get("result"),
                    error=outcome.get("error"),
                    audit_result=self.registry.audit_outcome(current.tool_name, outcome).get(
                        "result"
                    ),
                )
            await self._continue(current)
            return self._decision_response(current.id)
