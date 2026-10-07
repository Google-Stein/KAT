import asyncio
from pathlib import Path
from typing import Any

import pytest

from kat_core.permissions import PermissionPolicy
from kat_core.provider import ToolDispatcher
from kat_core.schemas import Message, SettingsUpdate
from kat_core.service import ChatService, SessionBusyError
from kat_core.storage import Store
from kat_core.tools import ToolRegistry, ToolRisk


@pytest.mark.parametrize("low_risk_approval", [False, True])
def test_permission_matrix(low_risk_approval: bool) -> None:
    policy = PermissionPolicy(low_risk_approval)
    assert policy.requires_approval(ToolRisk.LOW) is low_risk_approval
    assert policy.requires_approval(ToolRisk.MEDIUM)
    assert policy.requires_approval(ToolRisk.HIGH)


class PausedRuntime:
    ready = True

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.resume = asyncio.Event()
        self.settings: SettingsUpdate | None = None

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str:
        self.settings = settings
        self.entered.set()
        await self.resume.wait()
        return "resumed"


@pytest.mark.asyncio
async def test_concurrent_turn_rejected_and_settings_snapshot_safe(
    tmp_path: Path, registry: ToolRegistry
) -> None:
    store = Store(tmp_path / "test.sqlite3")
    runtime = PausedRuntime()
    service = ChatService(store, runtime, registry)
    session = store.create_session("Concurrent")
    first = asyncio.create_task(service.chat(session.id, "First"))
    await runtime.entered.wait()
    with pytest.raises(SessionBusyError):
        await service.chat(session.id, "Duplicate")
    store.save_settings(SettingsUpdate(model="gpt-4.1", require_approval_for_low_risk=True))
    assert runtime.settings is not None
    assert runtime.settings.model == "gpt-4.1-mini"
    runtime.resume.set()
    result = await first
    assert result.assistant_message.content == "resumed"
    assert [message.content for message in store.messages(session.id)] == ["First", "resumed"]
    store.close()


def test_interrupted_approved_tool_fails_without_replay(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    store = Store(path)
    session = store.create_session("Interrupted")
    approval = store.create_approval(
        session.id, "open_application", {"application_id": "demo"}, "medium"
    )
    assert store.claim_approval(approval.id, True)
    store.close()
    restarted = Store(path)
    recovered = restarted.approval(approval.id)
    assert recovered is not None
    assert recovered.status == "failed"
    assert "unknown" in str(recovered.error)
    assert not restarted.claim_approval(approval.id, True)
    assert len(restarted.messages(session.id)) == 1
    events = [event.event for event in restarted.audit(100)]
    assert events == ["tool_interrupted", "tool_result", "approval_decision"]
    restarted.close()


@pytest.mark.asyncio
async def test_failed_tool_execution_durable(
    tmp_path: Path, registry: ToolRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "fail.sqlite3")
    session = store.create_session("Failure")
    approval = store.create_approval(
        session.id, "open_application", {"application_id": "demo"}, "medium"
    )

    def fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("internal-secret")

    monkeypatch.setattr(registry, "execute", fail)
    service = ChatService(store, PausedRuntime(), registry)
    result = await service.decide(approval, True)
    assert result.status == "failed"
    assert "internal-secret" not in str(result.error)
    assert len(store.messages(session.id)) == 1
    assert store.audit(1)[0].event == "tool_result"
    store.close()
