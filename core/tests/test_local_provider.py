import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.endpoints import local_endpoint
from kat_core.local_provider import OllamaRuntime
from kat_core.schemas import SettingsUpdate
from kat_core.storage import Store
from kat_core.tools import ToolRegistry


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.168.1.1:11434",
        "http://127.0.0.1.evil:11434",
        "http://user:password@localhost:11434",
        "http://localhost:11434/api",
        "http://localhost:11434?x=1",
        "http://localhost:11434#x",
        "file:///tmp/model",
        "http://127.1:11434",
        "http://localhost:42800",
        "http://localhost:0",
        "http://localhost:99999",
    ],
)
def test_local_endpoint_rejects_remote_and_ambiguous_urls(url: str) -> None:
    with pytest.raises(ValueError):
        local_endpoint(url)


def test_local_endpoint_normalizes_dns_and_accepts_loopback_ipv6() -> None:
    assert local_endpoint("http://localhost:11434/") == "http://127.0.0.1:11434"
    assert local_endpoint("http://[::1]:11435") == "http://[::1]:11435"


@pytest.mark.parametrize(
    "tool,args,approval,event",
    [
        ("get_local_time", {}, False, "tool_result"),
        ("get_local_time", {}, True, "approval_requested"),
        ("open_application", {"application_id": "demo"}, True, "approval_requested"),
        (
            "open_application",
            {"application_id": "demo", "command": "shell"},
            False,
            "tool_rejected",
        ),
        ("arbitrary_shell", {"command": "echo private"}, False, "tool_rejected"),
        ("get_local_time", "malformed", False, "tool_rejected"),
    ],
)
def test_native_local_tool_protocol_uses_existing_permissions_and_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    args: Any,
    approval: bool,
    event: str,
    registry: ToolRegistry,
) -> None:
    requests: list[dict[str, Any]] = []

    def backend(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        assert "authorization" not in request.headers
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "tools"]})
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        requests.append(body)
        assert body["stream"] is False
        assert {item["function"]["name"] for item in body["tools"]} == {
            "get_local_time",
            "open_application",
        }
        message = {"role": "assistant", "content": "Please review the action."}
        if len(requests) == 1:
            message["tool_calls"] = [{"function": {"name": tool, "arguments": args}}]
        else:
            outcome = json.loads(body["messages"][-1]["content"])
            assert outcome["status"] == (
                "failed"
                if event == "tool_rejected"
                else "pending_approval"
                if approval
                else "completed"
            )
        return httpx.Response(200, json={"message": message})

    monkeypatch.setattr(
        OllamaRuntime,
        "client",
        lambda self, timeout=60: httpx.AsyncClient(
            transport=httpx.MockTransport(backend), base_url=self.endpoint, trust_env=False
        ),
    )
    monkeypatch.setenv("HTTP_PROXY", "http://should-never-be-used.invalid")
    token = "local-test-token-at-least-32-characters"
    # No OpenAI credential exists. Fail loudly if the cloud client is ever constructed.
    with patch("kat_core.provider.AsyncOpenAI", side_effect=AssertionError("Cloud fallback")):
        app = create_app(CoreConfig(data_dir=tmp_path, api_token=token), registry=registry)
        with TestClient(
            app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {token}"}
        ) as client:
            client.put(
                "/settings",
                json={
                    "provider": "ollama",
                    "model": "qwen3:1.7b",
                    "require_approval_for_low_risk": approval,
                },
            )
            session = client.post("/sessions", json={}).json()["id"]
            result = client.post(
                f"/sessions/{session}/messages", json={"content": "Please handle this request"}
            )
            assert result.status_code == 200, result.text
            assert event in [entry["event"] for entry in client.get("/audit").json()]
            if approval and event != "tool_rejected":
                pending = result.json()["approvals"][0]
                assert pending["status"] == "pending"
                denied = client.post(
                    f"/approvals/{pending['id']}/decision", json={"approved": False}
                )
                assert denied.json()["status"] == "denied"
            assert client.get("/settings").json()["api_key_configured"] is False
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "installed,tools,status",
    [(False, False, "model_missing"), (True, False, "ready"), (True, True, "ready")],
)
async def test_probe_distinguishes_model_missing_and_tool_support(
    monkeypatch: pytest.MonkeyPatch, installed: bool, tools: bool, status: str
) -> None:
    def backend(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "qwen3:1.7b"}] if installed else []}
            )
        return httpx.Response(200, json={"capabilities": ["tools"] if tools else []})

    monkeypatch.setattr(
        OllamaRuntime,
        "client",
        lambda self, timeout=60: httpx.AsyncClient(
            transport=httpx.MockTransport(backend), base_url=self.endpoint
        ),
    )
    result = await OllamaRuntime("http://127.0.0.1:11434").probe(
        SettingsUpdate(provider="ollama", model="qwen3:1.7b")
    )
    assert result.status == status
    assert result.tool_calling == tools


def test_actual_v1_settings_upgrade_preserves_provider_and_transcript(tmp_path: Path) -> None:
    import sqlite3

    from kat_core.migrations import foundation, migrate

    path = tmp_path / "kat.sqlite3"
    db = sqlite3.connect(path)
    migrate(db, path, {1: foundation})
    db.execute(
        "INSERT INTO settings VALUES (1,?)",
        ('{"provider":"openai","model":"gpt-4.1-mini","require_approval_for_low_risk":true}',),
    )
    db.execute("INSERT INTO sessions VALUES ('old','Owner conversation','then','now')")
    db.execute(
        "INSERT INTO messages(id,session_id,role,content,created_at) "
        "VALUES ('msg','old','user','Preserve me','then')"
    )
    db.commit()
    db.close()
    store = Store(path)
    assert store.settings().provider == "openai"
    assert store.settings().require_approval_for_low_risk is True
    assert store.settings().local_endpoint == "http://127.0.0.1:11434"
    assert store.messages("old")[0].content == "Preserve me"
    store.close()


@pytest.mark.parametrize(
    "failure,code",
    [
        ("connect", "provider_network"),
        ("timeout", "provider_timeout"),
        ("redirect", "provider_failed"),
        ("malformed", "provider_malformed_response"),
        ("missing", "provider_model_unavailable"),
    ],
)
def test_local_failures_are_safe_and_never_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, code: str
) -> None:
    def backend(request: httpx.Request) -> httpx.Response:
        if failure == "connect":
            raise httpx.ConnectError("private-provider-payload", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private-provider-payload", request=request)
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://api.openai.com/v1/responses"})
        if failure == "missing":
            return httpx.Response(404, json={"error": "private-provider-payload"})
        return httpx.Response(200, content="private-provider-payload")

    monkeypatch.setattr(
        OllamaRuntime,
        "client",
        lambda self, timeout=60: httpx.AsyncClient(
            transport=httpx.MockTransport(backend), base_url=self.endpoint, follow_redirects=False
        ),
    )
    token = "test-local-failure-token-at-least-32"
    with patch("kat_core.provider.AsyncOpenAI", side_effect=AssertionError("Cloud fallback")):
        app = create_app(
            CoreConfig(
                data_dir=tmp_path, api_token=token, openai_api_key="configured-but-never-used"
            )
        )
        with TestClient(
            app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {token}"}
        ) as client:
            client.put("/settings", json={"provider": "ollama", "model": "qwen3:1.7b"})
            session = client.post("/sessions", json={}).json()["id"]
            response = client.post(f"/sessions/{session}/messages", json={"content": "hello"})
            assert response.json()["error"]["code"] == code
            assert "private-provider-payload" not in response.text + client.get("/audit").text


@pytest.mark.parametrize(
    "metadata,name",
    [
        ({"remote_host": "https://ollama.com"}, "innocent-alias"),
        ({"remote_model": "remote-secret-model"}, "innocent-alias"),
        ({"capabilities": ["cloud", "tools"]}, "model"),
        ({"manifests": [{"remote_host": "https://ollama.com"}]}, "model"),
        ({}, "model:cloud"),
        ({}, "model-cloud"),
    ],
)
@pytest.mark.asyncio
async def test_cloud_backed_ollama_models_are_rejected_before_context_is_sent(
    monkeypatch: pytest.MonkeyPatch, metadata: dict[str, Any], name: str
) -> None:
    from kat_core.errors import ProviderFailure
    from kat_core.tools import ApplicationAllowlist

    calls = []

    def backend(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.path == "/api/show", (
            "Conversation must never reach a cloud-backed Ollama model"
        )
        return httpx.Response(200, json=metadata)

    monkeypatch.setattr(
        OllamaRuntime,
        "client",
        lambda self, timeout=60: httpx.AsyncClient(
            transport=httpx.MockTransport(backend), base_url=self.endpoint
        ),
    )

    async def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("Must not dispatch a tool")

    with pytest.raises(ProviderFailure) as caught:
        await OllamaRuntime("http://127.0.0.1:11434").respond(
            [],
            SettingsUpdate(provider="ollama", model=name),
            ToolRegistry(ApplicationAllowlist([])),
            dispatch,
        )
    assert caught.value.code.value == "provider_local_model_required"
    assert calls == ["/api/show"]
