"""Cross-layer security checks with the real API, storage, permissions, and tools.

The model runtime is deterministic in these tests; production always uses its
configured provider. These checks deliberately do not require credentials.
"""

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.provider import ToolDispatcher
from kat_core.schemas import Message, SettingsUpdate
from kat_core.tools import ApplicationAllowlist, ToolRegistry

TOKEN = "integration-test-token-with-at-least-32-characters"
SECRET_SENTINEL = "private-provider-error-sentinel"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class RequestingRuntime:
    ready = True

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str:
        command = messages[-1].content
        if command == "provider-failure":
            raise RuntimeError(f"Sensitive provider response: {SECRET_SENTINEL}")
        arguments = {"shell": "forbidden"} if command == "invalid-tool" else {}
        outcome = await dispatch("get_local_time", arguments)
        return json.dumps(outcome)


def application(path: Path, registry: ToolRegistry | None = None) -> FastAPI:
    return create_app(
        CoreConfig(data_dir=path, api_token=TOKEN),
        runtime=RequestingRuntime(),
        registry=registry or ToolRegistry(ApplicationAllowlist([])),
    )


def client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:42800"
    )


@pytest.mark.asyncio
async def test_http_rejects_untrusted_origins_hosts_and_credentials(tmp_path: Path) -> None:
    app = application(tmp_path)
    try:
        async with client(app) as http:
            for endpoint in ("/health", "/sessions", "/settings", "/approvals", "/audit"):
                assert (await http.get(endpoint)).status_code == 401
            assert (await http.get("/health", headers=AUTH)).status_code == 200
            assert (
                await http.get("/health", headers={**AUTH, "Host": "rebind.attacker.example"})
            ).status_code == 400
            for origin in ("null", "https://attacker.example", "http://127.0.0.1:1420.evil"):
                response = await http.get("/health", headers={**AUTH, "Origin": origin})
                assert response.status_code == 403
                assert "access-control-allow-origin" not in response.headers
            malformed = await http.get("/health", headers={b"Authorization": b"Bearer \xff"})
            assert malformed.status_code == 401
            allowed = await http.options(
                "/settings",
                headers={
                    "Origin": "http://127.0.0.1:1420",
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            assert allowed.status_code == 200
            assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:1420"
            assert "access-control-allow-credentials" not in allowed.headers
    finally:
        app.state.store.close()


@pytest.mark.asyncio
async def test_pending_approval_survives_restart_and_competing_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = application(tmp_path)
    async with client(app) as http:
        settings = {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "require_approval_for_low_risk": True,
        }
        assert (await http.put("/settings", headers=AUTH, json=settings)).status_code == 200
        session = (await http.post("/sessions", headers=AUTH, json={"title": "Durable"})).json()
        response = await http.post(
            f"/sessions/{session['id']}/messages", headers=AUTH, json={"content": "request-time"}
        )
        assert response.status_code == 200
        approval = response.json()["approvals"][0]
        assert approval["status"] == "pending"
        before = (await http.get(f"/sessions/{session['id']}/messages", headers=AUTH)).json()
    app.state.store.close()

    registry = ToolRegistry(ApplicationAllowlist([]))
    restarted = application(tmp_path, registry)
    entered, release = threading.Event(), threading.Event()
    executed: list[str] = []
    original_execute = registry.execute

    def execute(name: str, arguments: Any) -> dict[str, Any]:
        executed.append(name)
        entered.set()
        assert release.wait(timeout=10), "The integration test failed to release the tool"
        return original_execute(name, arguments)

    monkeypatch.setattr(registry, "execute", execute)
    try:
        async with client(restarted) as http:
            assert (
                await http.get(f"/sessions/{session['id']}/messages", headers=AUTH)
            ).json() == before
            pending = (await http.get("/approvals", headers=AUTH)).json()
            assert pending == [approval]
            endpoint = f"/approvals/{approval['id']}/decision"
            first = asyncio.create_task(http.post(endpoint, headers=AUTH, json={"approved": True}))
            try:
                assert await asyncio.to_thread(entered.wait, 5), "Tool execution never started"
                competing = await http.post(endpoint, headers=AUTH, json={"approved": True})
                assert competing.status_code == 409
            finally:
                release.set()
            completed = await first
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            assert (
                await http.post(endpoint, headers=AUTH, json={"approved": True})
            ).status_code == 409
            assert executed == ["get_local_time"]
            audit = (await http.get("/audit", headers=AUTH)).json()
            relevant = [event for event in audit if event["approval_id"] == approval["id"]]
            assert {event["event"] for event in relevant} >= {
                "approval_requested",
                "approval_decision",
                "tool_result",
            }
            messages = (await http.get(f"/sessions/{session['id']}/messages", headers=AUTH)).json()
            assert len(messages) == len(before) + 1
            assert messages[-1]["role"] == "tool"
            assert "completed" in messages[-1]["content"]
    finally:
        release.set()
        restarted.state.store.close()


@pytest.mark.asyncio
async def test_invalid_model_arguments_are_audited_without_execution(tmp_path: Path) -> None:
    app = application(tmp_path)
    try:
        async with client(app) as http:
            session_id = (await http.post("/sessions", headers=AUTH, json={})).json()["id"]
            response = await http.post(
                f"/sessions/{session_id}/messages", headers=AUTH, json={"content": "invalid-tool"}
            )
            assert response.status_code == 200
            assert json.loads(response.json()["assistant_message"]["content"])["status"] == "failed"
            assert response.json()["approvals"] == []
            audit = (await http.get("/audit", headers=AUTH)).json()
            assert [event["event"] for event in audit] == ["tool_rejected"]
            assert audit[0]["tool_name"] == "get_local_time"
    finally:
        app.state.store.close()


@pytest.mark.asyncio
async def test_provider_failures_never_echo_private_exception_data(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = application(tmp_path)
    try:
        with caplog.at_level(logging.WARNING):
            async with client(app) as http:
                session_id = (await http.post("/sessions", headers=AUTH, json={})).json()["id"]
                response = await http.post(
                    f"/sessions/{session_id}/messages",
                    headers=AUTH,
                    json={"content": "provider-failure"},
                )
                assert response.status_code == 503
                assert SECRET_SENTINEL not in response.text
                assert SECRET_SENTINEL not in (await http.get("/audit", headers=AUTH)).text
                assert SECRET_SENTINEL not in caplog.text
    finally:
        app.state.store.close()
