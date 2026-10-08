import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from kat_core.provider import OpenAIAgentsRuntime
from kat_core.schemas import Message, SettingsUpdate
from kat_core.tools import ToolRegistry

pytestmark = pytest.mark.asyncio


async def test_actual_sdk_wrapper_constructs_agent_with_privacy_and_tools(
    registry: ToolRegistry,
) -> None:
    runtime = OpenAIAgentsRuntime("test-key-never-networked")
    dispatch = AsyncMock(return_value={"status": "pending_approval", "approval_id": "example"})
    message = Message(id="m", session_id="s", role="user", content="Hello", created_at="now")
    with patch(
        "kat_core.provider.Runner.run",
        new=AsyncMock(return_value=SimpleNamespace(final_output="A real SDK-constructed response")),
    ) as run:
        answer = await runtime.respond([message], SettingsUpdate(), registry, dispatch)
    assert answer == "A real SDK-constructed response"
    agent = run.call_args.args[0]
    assert agent.model_settings.store is False
    assert agent.model_settings.parallel_tool_calls is False
    config = run.call_args.kwargs["run_config"]
    assert config.tracing_disabled is True
    assert config.trace_include_sensitive_data is False
    assert run.call_args.kwargs["input"][0] == {"role": "user", "content": "Hello"}
    tools = {tool.name: tool for tool in agent.tools}
    result = json.loads(
        await tools["open_application"].on_invoke_tool(None, '{"application_id":"demo"}')
    )
    assert result["status"] == "pending_approval"
    dispatch.assert_awaited_once_with("open_application", {"application_id": "demo"})


async def test_sdk_malformed_json_reaches_audit_boundary(registry: ToolRegistry) -> None:
    dispatch = AsyncMock(return_value={"status": "failed"})
    tools = OpenAIAgentsRuntime._sdk_tools(registry, dispatch)
    for payload in ("not-json", "null", "[]", "42"):
        await tools[0].on_invoke_tool(None, payload)
        dispatch.assert_awaited_with("get_local_time", {"__invalid_arguments__": True})


async def test_sdk_context_excludes_historical_tools_without_external_conversation_id(
    registry: ToolRegistry,
) -> None:
    messages = [
        Message(
            id=str(index),
            session_id="s",
            role="tool" if index == 103 else "user",
            content=f"message-{index}",
            created_at="now",
        )
        for index in range(105)
    ]
    with patch(
        "kat_core.provider.Runner.run",
        new=AsyncMock(return_value=SimpleNamespace(final_output="response")),
    ) as run:
        await OpenAIAgentsRuntime("test-key").respond(
            messages, SettingsUpdate(), registry, AsyncMock()
        )
    request: dict[str, Any] = run.call_args.kwargs
    assert len(request["input"]) == 99
    assert request["input"][0]["content"] == "message-5"
    assert [item["content"] for item in request["input"]] == [
        f"message-{index}" for index in range(5, 105) if index != 103
    ]
    assert "conversation_id" not in request
    assert "session" not in request
