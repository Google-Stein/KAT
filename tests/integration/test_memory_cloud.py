"""Production SDK HTTP serialization excludes memory, preserves ordinary transcript."""

import json
from typing import Any

import httpx
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.memory_retrieval import MemoryRetrieval
from kat_core.tools import ApplicationAllowlist, ToolRegistry


def test_sdk_cloud_request_contains_zero_memory_and_usage(tmp_path, monkeypatch):
    requests = []
    private = "private_memory_marker KAT should prefer local models when practical."
    ordinary = "This normal transcript discusses local models."

    def endpoint(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        requests.append(body)
        assert private not in request.content.decode()
        assert "KAT MEMORY DATA" not in request.content.decode()
        assert ordinary in request.content.decode()
        return httpx.Response(
            200,
            json={
                "id": "resp_memory_cloud",
                "object": "response",
                "created_at": 1700000000,
                "status": "completed",
                "model": "gpt-4.1-mini",
                "parallel_tool_calls": False,
                "output": [
                    {
                        "id": "msg_reply",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Ordinary cloud reply",
                                "annotations": [],
                                "logprobs": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 8, "output_tokens": 8, "total_tokens": 16},
            },
        )

    def client_factory(**kwargs: Any):
        return AsyncOpenAI(
            **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint))
        )

    monkeypatch.setattr("kat_core.provider.AsyncOpenAI", client_factory)
    # Any retrieval in the cloud route is a defect, even if its payload is discarded.
    monkeypatch.setattr(
        MemoryRetrieval,
        "retrieve",
        lambda *a: (_ for _ in ()).throw(AssertionError("Cloud retrieval")),
    )
    config = CoreConfig(
        data_dir=tmp_path,
        api_token="cloud-memory-test-token-at-least-32-characters",
        openai_api_key="synthetic-never-networked",
    )
    app = create_app(config, registry=ToolRegistry(ApplicationAllowlist([])))
    with TestClient(
        app, base_url="http://127.0.0.1", headers={"Authorization": "Bearer " + config.api_token}
    ) as client:
        client.put("/settings", json={"provider": "openai", "memory_enabled": True})
        client.post("/memories", json={"confirmed": True, "content": private})
        session = client.post("/sessions", json={}).json()["id"]
        app.state.store.add_message(session, "user", ordinary)
        response = client.post(
            f"/sessions/{session}/messages",
            json={"content": "Do I prefer local or cloud models for KAT?"},
        )
        assert response.status_code == 200
        assert client.get(f"/sessions/{session}/memory-usage").json() == []
        assert not any(e["event"] == "memory_retrieved" for e in client.get("/audit").json())
        assert len(requests) == 1
