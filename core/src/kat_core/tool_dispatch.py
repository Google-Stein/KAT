"""One trusted dispatcher used by initial turns and approval continuations."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from kat_core.capability_schemas import CapabilityFailure
from kat_core.continuation_schemas import MAX_APPROVALS, TurnRecord
from kat_core.permissions import PermissionPolicy
from kat_core.storage import Store
from kat_core.tools import ToolExecutionError, ToolRegistry
from kat_core.turn_store import TurnStore


class TaskDispatcher:
    def __init__(
        self,
        store: Store,
        registry: ToolRegistry,
        turn: TurnRecord,
        execute: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        self.store, self.registry, self.turn, self._execute = store, registry, turn, execute
        self.created_approvals: list[str] = []

    async def __call__(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        session_id = self.turn.session_id
        settings = self.store.settings()
        try:
            spec = self.registry.get(name)
            validated = self.registry.validate_args(name, arguments)
            display_context = await asyncio.wait_for(
                asyncio.to_thread(self.registry.approval_context, name, validated.model_dump()),
                timeout=12,
            )
        except TimeoutError:
            self.store.add_audit(
                "tool_rejected",
                session_id=session_id,
                tool_name=name,
                details={"reason": "tool_timeout"},
                error="Tool request validation timed out.",
            )
            return {
                "status": "failed",
                "error_code": "tool_timeout",
                "error": "Tool request validation timed out.",
            }
        except CapabilityFailure as error:
            self.store.add_audit(
                "tool_rejected",
                session_id=session_id,
                tool_name=name,
                details={"reason": error.code},
                error=str(error),
            )
            capability_failure = {
                "status": "failed",
                "error_code": error.code,
                "error": str(error),
            }
            if name == "read_text_file" and error.code == "file_not_found":
                capability_failure["retry_hint"] = (
                    "Fetch a fresh list_directory for this root with relative_path '.'; "
                    "use the matching entry's relative_path exactly, "
                    "without the root label. "
                    "A corrected read still requires its own owner approval."
                )
            return capability_failure
        except (ValueError, TypeError, ToolExecutionError) as error:
            known = name in {item.name for item in self.registry.specs()}
            feedback = self.registry.get(name).validation_feedback(error) if known else []
            self.store.add_audit(
                "tool_rejected",
                session_id=session_id,
                tool_name=name if known else None,
                details={
                    "reason": "invalid_or_disallowed_request",
                    "field_errors": feedback,
                    "argument_count": len(arguments),
                    "value_types": sorted(type(value).__name__ for value in arguments.values()),
                },
                error="Invalid or disallowed tool request",
            )
            failure: dict[str, Any] = {
                "status": "failed",
                "error": "Invalid or disallowed tool arguments",
            }
            if known:
                fields = list(self.registry.get(name).arguments_model.model_fields)
                failure.update(
                    error_code="invalid_tool_arguments",
                    expected_arguments=fields,
                    field_errors=feedback,
                    error="Invalid tool arguments. Retry using only the declared fields: "
                    + (", ".join(fields) if fields else "none; pass an empty object {}"),
                )
                if any(item["field"] == "root_id" for item in feedback):
                    failure["retry_hint"] = (
                        "Copy the exact root_id from the approved roots, including its "
                        "hyphen and all hexadecimal characters. Preserve the requested "
                        "relative_path. Retry once; never substitute another file."
                    )
            return failure
        clean_arguments = validated.model_dump()
        self.store.add_audit(
            "tool_requested",
            session_id=session_id,
            tool_name=name,
            details={"arguments": clean_arguments, "risk": spec.risk.value},
        )
        policy = PermissionPolicy(settings.require_approval_for_low_risk)
        if spec.approval_required or policy.requires_approval(spec.risk):
            # Some local models repeat the same proposal after receiving a
            # pending result. One unresolved read of the exact same file in this
            # task needs one decision, not several duplicate cards. Completed
            # reads and other owner turns are never reused here.
            if name == "read_text_file":
                existing = next(
                    (
                        a
                        for a in TurnStore(self.store).approvals(self.turn)
                        if a.status == "pending"
                        and a.tool_name == name
                        and a.arguments == clean_arguments
                    ),
                    None,
                )
                if existing is not None:
                    self.store.add_audit(
                        "approval_proposal_repeated",
                        session_id=session_id,
                        tool_name=name,
                        approval_id=existing.id,
                        details={"origin_user_message_id": self.turn.origin_user_message_id},
                    )
                    return {
                        "status": "pending_approval",
                        "approval_id": existing.id,
                        "tool_name": name,
                        "arguments": clean_arguments,
                    }
            current = TurnStore(self.store).get(self.turn.origin_user_message_id)
            if current is None or current.approvals_created >= MAX_APPROVALS:
                return {
                    "status": "failed",
                    "error_code": "approval_budget_exhausted",
                    "error": "This request reached its individual approval limit.",
                }
            approval = self.store.create_approval(
                session_id,
                name,
                clean_arguments,
                spec.risk.value,
                display_context=display_context,
                origin_user_message_id=self.turn.origin_user_message_id,
                continuation_policy=spec.continuation_policy,
            )
            self.created_approvals.append(approval.id)
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
            details=self.registry.audit_outcome(name, outcome),
            error=outcome.get("error"),
        )
        self.store.add_message(
            session_id,
            "tool",
            json.dumps({"tool_name": name, **outcome}),
            origin_user_message_id=self.turn.origin_user_message_id,
        )
        return outcome
