"""Exercise the production Agents runtime against a simulated Responses endpoint.

Only the HTTP transport is replaced. Agent construction, SDK serialization,
function-call dispatch, permission checks, and persistence are production code.
This validates protocol integration without claiming live provider verification.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI as OpenAIClient

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.tools import ApplicationAllowlist, ToolRegistry

TOKEN = "agents-protocol-test-token-at-least-32-characters"


def response_output(output: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return {
        "id": f"resp_{index}",
        "object": "response",
        "created_at": 1700000000,
        "status": "completed",
        "model": "gpt-4.1-mini",
        "output": output,
        "parallel_tool_calls": False,
        "usage": {"input_tokens": 8, "output_tokens": 8, "total_tokens": 16},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,raw_arguments,approval_required,expected_status,expected_event,expected_http_status",
    [
        ("get_local_time", "{}", False, "completed", "tool_result", 200),
        ("get_local_time", "{}", True, "pending_approval", "approval_requested", 200),
        ("get_local_time", "{malformed-json", False, "failed", "tool_rejected", 200),
        (
            "arbitrary_shell",
            '{"command":"private-untrusted-tool-argument"}',
            False,
            "failed",
            "tool_rejected",
            502,
        ),
    ],
)
async def test_actual_agents_tool_round_trip_preserves_local_security_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    raw_arguments: str,
    approval_required: bool,
    expected_status: str,
    expected_event: str,
    expected_http_status: int,
) -> None:
    requests: list[dict[str, Any]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "gpt-4.1-mini"
        assert body["store"] is False
        assert body["parallel_tool_calls"] is False
        assert "conversation" not in body
        assert "previous_response_id" not in body
        if len(requests) == 1:
            tools = {tool["name"]: tool for tool in body["tools"]}
            assert set(tools) == {
                "get_local_time",
                "open_application",
                "get_weather",
                "get_system_status",
            }
            assert tools["get_local_time"]["strict"] is True
            assert tools["get_local_time"]["parameters"]["additionalProperties"] is False
            output = [
                {
                    "id": "fc_time",
                    "type": "function_call",
                    "call_id": "call_time",
                    "name": tool_name,
                    "arguments": raw_arguments,
                    "status": "completed",
                }
            ]
        else:
            assert len(requests) == 2, "The SDK made an unexpected additional request"
            tool_results = [
                item for item in body["input"] if item.get("type") == "function_call_output"
            ]
            assert len(tool_results) == 1
            assert tool_results[0]["call_id"] == "call_time"
            outcome = json.loads(tool_results[0]["output"])
            assert outcome["status"] == expected_status
            output = [
                {
                    "id": "msg_reply",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "The tool request was handled.",
                            "annotations": [],
                            "logprobs": [],
                        }
                    ],
                }
            ]
        return httpx.Response(200, json=response_output(output, len(requests)))

    def make_client(**kwargs: Any) -> OpenAIClient:
        return OpenAIClient(
            **kwargs,
            base_url="https://api.openai.com/v1",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
        )

    monkeypatch.setattr("kat_core.provider.AsyncOpenAI", make_client)
    app = create_app(
        CoreConfig(
            data_dir=tmp_path,
            api_token=TOKEN,
            openai_api_key="protocol-test-key-never-networked",
        ),
        registry=ToolRegistry(ApplicationAllowlist([])),
    )
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:42800"
        ) as http:
            setting_response = await http.put(
                "/settings",
                headers=headers,
                json={"require_approval_for_low_risk": approval_required},
            )
            assert setting_response.status_code == 200
            session_id = (await http.post("/sessions", headers=headers, json={})).json()["id"]
            chat = await http.post(
                f"/sessions/{session_id}/messages",
                headers=headers,
                json={"content": "Please get the current time."},
            )
            assert chat.status_code == expected_http_status, chat.text
            if expected_http_status == 200:
                assert (
                    chat.json()["assistant_message"]["content"] == "The tool request was handled."
                )
                assert len(chat.json()["approvals"]) == int(approval_required)
            else:
                assert "private-untrusted-tool-argument" not in chat.text
                messages = (
                    await http.get(f"/sessions/{session_id}/messages", headers=headers)
                ).json()
                assert [message["role"] for message in messages] == ["user"]
            audit = (await http.get("/audit", headers=headers)).json()
            assert expected_event in {event["event"] for event in audit}
            assert "protocol-test-key-never-networked" not in json.dumps(audit)
            assert "private-untrusted-tool-argument" not in json.dumps(audit)
            assert len(requests) == (2 if expected_http_status == 200 else 1)
            if expected_http_status != 200:
                assert "provider_error" in {event["event"] for event in audit}
    finally:
        app.state.store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,provider_code,expected",
    [
        (401, "invalid_api_key", "provider_authentication"),
        (403, "model_access_denied", "provider_model_unavailable"),
        (404, "model_not_found", "provider_model_unavailable"),
        (400, "model_not_found", "provider_model_unavailable"),
        (429, "insufficient_quota", "provider_quota"),
        (429, "rate_limit_exceeded", "provider_rate_limited"),
        (500, "server_error", "provider_failed"),
    ],
)
async def test_actual_sdk_http_errors_are_classified_without_payload_leaks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
    provider_code: str,
    expected: str,
) -> None:
    private = "private-api-key-and-conversation-payload"

    def endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": provider_code, "message": private}})

    def make_client(**kwargs: Any) -> OpenAIClient:
        kwargs["max_retries"] = 0
        return OpenAIClient(
            **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint))
        )

    monkeypatch.setattr("kat_core.provider.AsyncOpenAI", make_client)
    app = create_app(CoreConfig(data_dir=tmp_path, api_token=TOKEN, openai_api_key=private))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1",
            headers={"Authorization": f"Bearer {TOKEN}"},
        ) as client:
            session = (await client.post("/sessions", json={})).json()["id"]
            response = await client.post(f"/sessions/{session}/messages", json={"content": private})
            audit = await client.get("/audit")
            assert response.json()["error"]["code"] == expected
            assert audit.json()[0]["details"]["code"] == expected
            assert private not in response.text + audit.text + caplog.text
    finally:
        app.state.store.close()
