"""Ollama native chat adapter: loopback, bounded outputs, shared tool dispatcher."""

import json
from typing import Any

import httpx

from kat_core.endpoints import local_endpoint
from kat_core.errors import ProviderErrorCode, ProviderFailure
from kat_core.model_context import history, instructions
from kat_core.provider import ToolDispatcher
from kat_core.schemas import Message, ProviderStatus, SettingsUpdate
from kat_core.tools import ToolRegistry


class OllamaRuntime:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = local_endpoint(endpoint)

    @property
    def ready(self) -> bool:
        # Configured is distinct from connectivity; probe reports actual backend/model status.
        return True

    def client(self, timeout: float = 60) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.endpoint, trust_env=False, follow_redirects=False, timeout=timeout
        )

    @staticmethod
    async def request(
        client: httpx.AsyncClient, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with client.stream(method, path, json=body) as response:
                if response.status_code == 404:
                    raise ProviderFailure(ProviderErrorCode.MODEL_UNAVAILABLE)
                if response.status_code == 429:
                    raise ProviderFailure(ProviderErrorCode.RATE_LIMITED)
                if response.status_code != 200:
                    raise ProviderFailure(ProviderErrorCode.FAILED)
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 2_000_000:
                        raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                payload = json.loads(chunks)
                if not isinstance(payload, dict) or "error" in payload:
                    raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                return payload
        except httpx.TimeoutException:
            raise ProviderFailure(ProviderErrorCode.TIMEOUT) from None
        except httpx.RequestError:
            raise ProviderFailure(ProviderErrorCode.NETWORK) from None
        except (ValueError, TypeError):
            raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE) from None

    async def probe(self, settings: SettingsUpdate) -> ProviderStatus:
        async with self.client(5) as client:
            tags = await self.request(client, "GET", "/api/tags")
            items = tags.get("models")
            if not isinstance(items, list):
                raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
            models = sorted(
                {
                    item["name"]
                    for item in items
                    if isinstance(item, dict) and isinstance(item.get("name"), str)
                }
            )[:200]
            installed = settings.model in models or settings.model + ":latest" in models
            if not installed:
                return ProviderStatus(
                    provider="ollama",
                    status="model_missing",
                    message="Backend is running. Install the selected model, then refresh.",
                    models=models,
                )
            info = await self.request(client, "POST", "/api/show", {"model": settings.model})
            capabilities = info.get("capabilities", [])
            tools = isinstance(capabilities, list) and "tools" in capabilities
            return ProviderStatus(
                provider="ollama",
                status="ready",
                message="Local backend and selected model are ready."
                if tools
                else "Model is available for chat; it does not advertise tool support.",
                models=models,
                tool_calling=tools,
            )

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str:
        context: list[dict[str, Any]] = [
            {"role": "system", "content": instructions(registry)},
            *history(messages, budget=18000),
        ]
        async with self.client() as client:
            info = await self.request(client, "POST", "/api/show", {"model": settings.model})
            capabilities = info.get("capabilities", [])
            if not isinstance(capabilities, list):
                raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
            supports_tools = "tools" in capabilities
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.arguments_model.model_json_schema(),
                    },
                }
                for spec in registry.specs()
            ]
            for _ in range(6):
                body: dict[str, Any] = {
                    "model": settings.model,
                    "messages": context,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0, "num_predict": 1024, "num_ctx": 8192},
                }
                if supports_tools:
                    body["tools"] = tools
                response = await self.request(client, "POST", "/api/chat", body)
                message = response.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                content = message.get("content", "")
                calls = message.get("tool_calls", [])
                if not isinstance(content, str) or not isinstance(calls, list) or len(calls) > 8:
                    raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                if not calls:
                    if not content.strip() or len(content) > 32000:
                        raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                    return content
                if not supports_tools:
                    raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                context.append({"role": "assistant", "content": content, "tool_calls": calls})
                for call in calls:
                    function = call.get("function") if isinstance(call, dict) else None
                    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
                        raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
                    arguments = function.get("arguments")
                    if not isinstance(arguments, dict):
                        arguments = {"__invalid_arguments__": True}
                    name = function["name"]
                    outcome = await dispatch(name, arguments)
                    context.append(
                        {"role": "tool", "tool_name": name, "content": json.dumps(outcome)}
                    )
        raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
