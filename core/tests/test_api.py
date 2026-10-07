from unittest.mock import MagicMock, patch

import pytest
from conftest import HEADERS, FakeRuntime
from fastapi.testclient import TestClient

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.tools import ToolRegistry


def new_session(client: TestClient) -> str:
    response = client.post("/sessions", json={"title": "First chat"})
    assert response.status_code == 201
    return response.json()["id"]


def test_authentication_required_on_every_endpoint(client: TestClient) -> None:
    for method, path, body in [
        ("GET", "/health", None),
        ("GET", "/openapi.json", None),
        ("GET", "/sessions", None),
        ("POST", "/sessions", {}),
        ("GET", "/sessions/missing/messages", None),
        ("POST", "/sessions/missing/messages", {"content": "hello"}),
        ("GET", "/approvals", None),
        ("POST", "/approvals/missing/decision", {"approved": True}),
        ("GET", "/settings", None),
        ("PUT", "/settings", {}),
        ("GET", "/audit", None),
    ]:
        response = client.request(
            method, path, json=body, headers={"Authorization": "Bearer wrong"}
        )
        assert response.status_code == 401, path


def test_loopback_host_and_origin_enforcement(client: TestClient) -> None:
    assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 400
    assert client.get("/health", headers={"Origin": "https://attacker.example"}).status_code == 403
    for origin in ("http://localhost:1420", "tauri://localhost", "http://tauri.localhost"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    assert client.get("/docs").status_code == 404


def test_health_and_persistent_conversation(
    client: TestClient, runtime: FakeRuntime, config: CoreConfig, registry: ToolRegistry
) -> None:
    assert client.get("/health").json() == {
        "status": "ok",
        "version": "0.1.0",
        "provider_ready": True,
    }
    session_id = new_session(client)
    response = client.post(f"/sessions/{session_id}/messages", json={"content": "Remember Ada"})
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == "KAT response"
    assert runtime.requests[0][0][0].content == "Remember Ada"
    # A separate app opens persisted data, reconstructing context on the next request.
    other_runtime = FakeRuntime()
    other_app = create_app(config, runtime=other_runtime, registry=registry)
    with TestClient(other_app, base_url="http://127.0.0.1", headers=HEADERS) as other:
        assert other.get("/sessions").json()[0]["id"] == session_id
        assert len(other.get(f"/sessions/{session_id}/messages").json()) == 2
        assert (
            other.post(
                f"/sessions/{session_id}/messages", json={"content": "Who did I mention?"}
            ).status_code
            == 200
        )
        assert [item.content for item in other_runtime.requests[0][0]] == [
            "Remember Ada",
            "KAT response",
            "Who did I mention?",
        ]


def test_time_tool_executes_and_records_audit(client: TestClient, runtime: FakeRuntime) -> None:
    runtime.tool_requests = [("get_local_time", {})]
    session_id = new_session(client)
    result = client.post(f"/sessions/{session_id}/messages", json={"content": "What time is it?"})
    assert result.status_code == 200
    assert result.json()["approvals"] == []
    assert runtime.outcomes[0]["status"] == "completed"
    assert "iso" in runtime.outcomes[0]["result"]
    events = [item["event"] for item in client.get("/audit").json()]
    assert events == ["tool_result", "approval_decision", "tool_requested"]
    assert [item["role"] for item in client.get(f"/sessions/{session_id}/messages").json()] == [
        "user",
        "tool",
        "assistant",
    ]


def test_approval_is_durable_and_executes_once(
    client: TestClient, runtime: FakeRuntime, config: CoreConfig, registry: ToolRegistry
) -> None:
    runtime.tool_requests = [("open_application", {"application_id": "demo"})]
    session_id = new_session(client)
    result = client.post(f"/sessions/{session_id}/messages", json={"content": "Open demo"})
    approval = result.json()["approvals"][0]
    assert approval["status"] == "pending"
    assert runtime.outcomes[0]["status"] == "pending_approval"
    assert approval["risk"] == "medium"
    another_app = create_app(config, runtime=FakeRuntime(), registry=registry)
    with TestClient(another_app, base_url="http://127.0.0.1", headers=HEADERS) as another:
        assert another.get("/approvals", params={"session_id": session_id}).json()[0] == approval
        with patch("kat_core.tools.subprocess.Popen", return_value=MagicMock(pid=987)) as launch:
            completed = another.post(
                f"/approvals/{approval['id']}/decision", json={"approved": True}
            )
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            assert completed.json()["result"]["pid"] == 987
            assert (
                another.post(
                    f"/approvals/{approval['id']}/decision", json={"approved": True}
                ).status_code
                == 409
            )
            launch.assert_called_once()
        tool_messages = [
            item
            for item in another.get(f"/sessions/{session_id}/messages").json()
            if item["role"] == "tool"
        ]
        assert len(tool_messages) == 1
        assert "completed" in tool_messages[0]["content"]
        events = [item["event"] for item in another.get("/audit").json()]
        assert events[:2] == ["tool_result", "approval_decision"]


def test_denied_approval_never_executes(client: TestClient, runtime: FakeRuntime) -> None:
    runtime.tool_requests = [("open_application", {"application_id": "demo"})]
    session_id = new_session(client)
    approval = client.post(
        f"/sessions/{session_id}/messages", json={"content": "Open demo"}
    ).json()["approvals"][0]
    with patch("kat_core.tools.subprocess.Popen") as launch:
        response = client.post(f"/approvals/{approval['id']}/decision", json={"approved": False})
        assert response.json()["status"] == "denied"
        assert (
            client.post(
                f"/approvals/{approval['id']}/decision", json={"approved": True}
            ).status_code
            == 409
        )
        launch.assert_not_called()
    assert "denied" in client.get(f"/sessions/{session_id}/messages").json()[-1]["content"]


def test_low_risk_approval_policy_persists(
    client: TestClient, runtime: FakeRuntime, config: CoreConfig, registry: ToolRegistry
) -> None:
    settings = {"provider": "openai", "model": "gpt-4.1", "require_approval_for_low_risk": True}
    assert client.put("/settings", json=settings).status_code == 200
    with TestClient(
        create_app(config, runtime=FakeRuntime(), registry=registry),
        base_url="http://127.0.0.1",
        headers=HEADERS,
    ) as restarted:
        assert restarted.get("/settings").json()["require_approval_for_low_risk"] is True
        assert restarted.get("/settings").json()["model"] == "gpt-4.1"
    runtime.tool_requests = [("get_local_time", {})]
    session_id = new_session(client)
    result = client.post(f"/sessions/{session_id}/messages", json={"content": "Time?"})
    approval = result.json()["approvals"][0]
    assert approval["risk"] == "low"
    assert approval["status"] == "pending"
    assert (
        client.post(f"/approvals/{approval['id']}/decision", json={"approved": True}).json()[
            "status"
        ]
        == "completed"
    )


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("arbitrary_shell", {"command": "rm -rf /"}),
        ("get_local_time", {"unexpected": "secret-input"}),
        ("open_application", {"application_id": "demo;cmd"}),
        ("open_application", {"application_id": "unconfigured"}),
        ("open_application", {"application_id": "demo", "executable": "/bin/sh"}),
        ("open_application", {"application_id": 123}),
    ],
)
def test_untrusted_tool_arguments_rejected_and_audited(
    client: TestClient, runtime: FakeRuntime, name: str, arguments: dict[str, object]
) -> None:
    runtime.tool_requests = [(name, arguments)]
    session_id = new_session(client)
    response = client.post(f"/sessions/{session_id}/messages", json={"content": "Tool request"})
    assert response.status_code == 200
    assert response.json()["approvals"] == []
    assert runtime.outcomes[0]["status"] == "failed"
    audit = client.get("/audit").json()
    assert audit[0]["event"] == "tool_rejected"
    assert "secret-input" not in str(audit)


def test_keyless_and_provider_failures_have_clear_safe_errors(
    config: CoreConfig, registry: ToolRegistry, client: TestClient, runtime: FakeRuntime
) -> None:
    with TestClient(
        create_app(config, registry=registry), base_url="http://127.0.0.1", headers=HEADERS
    ) as keyless:
        session_id = new_session(keyless)
        response = keyless.post(f"/sessions/{session_id}/messages", json={"content": "Hello"})
        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]
        assert keyless.get(f"/sessions/{session_id}/messages").json() == []
    runtime.failure = RuntimeError("super-secret-key private-prompt")
    session_id = new_session(client)
    response = client.post(f"/sessions/{session_id}/messages", json={"content": "Hello"})
    assert response.status_code == 503
    assert "super-secret-key" not in response.text
    assert "super-secret-key" not in client.get("/audit").text
    assert client.get("/audit").json()[0]["event"] == "provider_error"


@pytest.mark.parametrize(
    "body",
    [
        {"provider": "other"},
        {"model": "../../invalid"},
        {"model": ""},
        {"model": "a" * 121},
        {"api_key": "must-not-store"},
        {"require_approval_for_low_risk": "false"},
    ],
)
def test_settings_validation(client: TestClient, body: dict[str, object]) -> None:
    assert client.put("/settings", json=body).status_code == 422


def test_missing_blank_and_bounded_inputs(client: TestClient) -> None:
    assert client.get("/sessions/missing/messages").status_code == 404
    assert client.get("/approvals", params={"session_id": "missing"}).status_code == 404
    assert client.post("/approvals/missing/decision", json={"approved": True}).status_code == 404
    assert client.post("/sessions", json={"title": "  "}).status_code == 422
    session_id = new_session(client)
    for content in ("", " ", "a" * 32001):
        assert (
            client.post(f"/sessions/{session_id}/messages", json={"content": content}).status_code
            == 422
        )
    assert client.get("/audit", params={"limit": 1001}).status_code == 422
