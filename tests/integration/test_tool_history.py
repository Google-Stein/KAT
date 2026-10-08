"""Actual provider protocols: past outcomes cannot substitute for a new action.

Model decisions are deterministic HTTP fixtures; registry, clock, permission,
approval and SQLite orchestration run normally. Only process creation is mocked.
"""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.local_provider import OllamaRuntime
from kat_core.tools import ApplicationAllowlist, ApplicationDefinition, ToolRegistry

TOKEN = "history-regression-token-at-least-32-characters"
TIMES = [
    datetime.fromisoformat(value).astimezone().isoformat()
    for value in ["2026-10-08T09:54:00+00:00", "2026-10-08T09:55:00+00:00"]
]


@pytest.mark.parametrize("provider", ["openai", "ollama"])
def test_repeated_time_and_application_requests_use_new_tools_and_keep_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    definitions = []
    for name in ("notepad", "calculator"):
        executable = tmp_path / f"{name}-fixture.exe"
        executable.write_text("Process creation is mocked")
        executable.chmod(0o755)
        definitions.append(
            ApplicationDefinition(id=name, label=name.title(), executable=str(executable))
        )
    registry = ToolRegistry(ApplicationAllowlist(definitions))
    clock = iter(datetime.fromisoformat(value) for value in TIMES)

    class Clock:
        @staticmethod
        def now() -> datetime:
            return next(clock)

    monkeypatch.setattr("kat_core.tools.datetime", Clock)
    launch = Mock(side_effect=[Mock(pid=101), Mock(pid=102), Mock(pid=103), Mock(pid=104)])
    # Patch this module's process interface, not the shared subprocess module:
    # SDK/platform discovery may also start unrelated processes.
    monkeypatch.setattr("kat_core.tools.subprocess", SimpleNamespace(Popen=launch, DEVNULL=-3))
    starts: list[list[dict[str, Any]]] = []
    active_outcomes: list[dict[str, Any]] = []
    sequence = 0

    def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal sequence
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["tools"]})
        body = json.loads(request.content)
        context = body["input"] if provider == "openai" else body["messages"][1:]
        final = context[-1]
        active = final.get("type") == "function_call_output" or final.get("role") == "tool"
        if active:
            outcome = json.loads(final["output"] if provider == "openai" else final["content"])
            active_outcomes.append(outcome)
            text = (
                outcome["result"]["iso"]
                if outcome["status"] == "completed"
                else "Review the new approval card."
            )
            output = {"role": "assistant", "content": text}
        else:
            starts.append(context)
            # Reproduce the owner's stale-evidence failure when old tool data is
            # presented as a user assertion rather than an active tool response.
            contaminated = any(
                item.get("role") == "user"
                and str(item.get("content", "")).startswith("KAT recorded tool outcome")
                for item in context
            )
            if contaminated:
                output = {"role": "assistant", "content": TIMES[0]}
            else:
                prompt = final["content"]
                name = "get_local_time" if "time" in prompt else "open_application"
                arguments = (
                    {}
                    if name == "get_local_time"
                    else {"application_id": "calculator" if "Calculator" in prompt else "notepad"}
                )
                output = {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
                }
        if provider == "ollama":
            return httpx.Response(200, json={"message": output})
        sequence += 1
        if output.get("tool_calls"):
            function = output["tool_calls"][0]["function"]
            items = [
                {
                    "id": f"fc_{sequence}",
                    "type": "function_call",
                    "call_id": f"call_{sequence}",
                    "name": function["name"],
                    "arguments": json.dumps(function["arguments"]),
                    "status": "completed",
                }
            ]
        else:
            items = [
                {
                    "id": f"msg_{sequence}",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": output["content"],
                            "annotations": [],
                            "logprobs": [],
                        }
                    ],
                }
            ]
        return httpx.Response(
            200,
            json={
                "id": f"resp_{sequence}",
                "object": "response",
                "created_at": 1700000000,
                "status": "completed",
                "model": "gpt-4.1-mini",
                "output": items,
                "parallel_tool_calls": False,
                "usage": {"input_tokens": 8, "output_tokens": 8, "total_tokens": 16},
            },
        )

    if provider == "openai":
        monkeypatch.setattr(
            "kat_core.provider.AsyncOpenAI",
            lambda **kwargs: AsyncOpenAI(
                **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint))
            ),
        )
    else:
        monkeypatch.setattr(
            "kat_core.provider.AsyncOpenAI",
            Mock(side_effect=AssertionError("Local must not contact OpenAI")),
        )
        monkeypatch.setattr(
            OllamaRuntime,
            "client",
            lambda self, timeout=60: httpx.AsyncClient(
                base_url=self.endpoint, transport=httpx.MockTransport(endpoint)
            ),
        )
    app = create_app(
        CoreConfig(
            data_dir=tmp_path, api_token=TOKEN, openai_api_key="synthetic-mocked-transport-key"
        ),
        registry=registry,
    )
    with TestClient(
        app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {TOKEN}"}
    ) as client:
        client.put("/settings", json={"provider": provider})
        session = client.post("/sessions", json={}).json()["id"]

        def chat(prompt: str) -> dict[str, Any]:
            response = client.post(f"/sessions/{session}/messages", json={"content": prompt})
            assert response.status_code == 200, response.text
            return response.json()

        assert chat("Tell me the time")["assistant_message"]["content"] == TIMES[0]
        second = chat("Tell me the time")
        assert second["assistant_message"]["content"] == TIMES[1], (
            "Historical time was reused instead of invoking the clock again"
        )
        approvals = []
        for application in ("Notepad", "Notepad", "Calculator", "Calculator"):
            result = chat(f"Open {application}.")
            assert len(result["approvals"]) == 1, "New action was treated as historically completed"
            approval = result["approvals"][0]
            assert approval["status"] == "pending"
            assert approval["arguments"] == {"application_id": application.lower()}
            assert launch.call_count == len(approvals), "Application ran before approval"
            approvals.append(approval["id"])
            decision = client.post(f"/approvals/{approval['id']}/decision", json={"approved": True})
            assert decision.json()["status"] == "completed"
            assert decision.json()["result"]["application_id"] == application.lower()
        assert len(set(approvals)) == 4 and launch.call_count == 4
        for call, definition in zip(
            launch.call_args_list,
            [definitions[0], definitions[0], definitions[1], definitions[1]],
            strict=True,
        ):
            assert call.args == (definition.command,)
            assert call.kwargs["shell"] is False
        transcript = client.get(f"/sessions/{session}/messages").json()
        tools = [json.loads(item["content"]) for item in transcript if item["role"] == "tool"]
        assert len(tools) == 6
        assert [item["result"]["iso"] for item in tools[:2]] == TIMES
        assert [item["approval_id"] for item in tools[2:]] == approvals
        audit = client.get("/audit", params={"session_id": session}).json()
        outcomes = [item for item in audit if item["event"] == "tool_result"]
        assert len(outcomes) == 6
        assert all(item["details"]["status"] == "completed" for item in outcomes)
        assert len([item for item in audit if item["event"] == "tool_requested"]) == 6
    assert len(starts) == 6 and len(active_outcomes) == 6
    assert [item["result"]["iso"] for item in active_outcomes[:2]] == TIMES
    assert all(item["status"] == "pending_approval" for item in active_outcomes[2:])
    for context in starts:
        assert all(item["role"] in {"user", "assistant"} for item in context)
        assert "KAT recorded tool outcome" not in json.dumps(context)
        assert '"tool_name"' not in json.dumps(context)
