"""Explicit provider selection; no automatic fallback or cross-provider data routing."""

from collections.abc import Callable

from kat_core.errors import ProviderFailure
from kat_core.local_provider import OllamaRuntime
from kat_core.provider import ModelRuntime, OpenAIAgentsRuntime, ToolDispatcher
from kat_core.schemas import (
    Message,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderStatus,
    SettingsUpdate,
)
from kat_core.tools import ToolRegistry


class ProviderRegistry:
    def __init__(self, openai_api_key: str | None) -> None:
        self.openai = OpenAIAgentsRuntime(openai_api_key)
        self.factories: dict[str, Callable[[SettingsUpdate], ModelRuntime]] = {
            "openai": lambda _: self.openai,
            "ollama": lambda settings: OllamaRuntime(settings.local_endpoint),
        }

    def get(self, settings: SettingsUpdate) -> ModelRuntime:
        return self.factories[settings.provider](settings)

    @staticmethod
    def descriptors() -> list[ProviderDescriptor]:
        return [
            ProviderDescriptor(
                id="openai",
                label="OpenAI",
                local=False,
                capabilities=ProviderCapabilities(tool_calling=True),
            ),
            ProviderDescriptor(
                id="ollama",
                label="Local · Ollama",
                local=True,
                capabilities=ProviderCapabilities(tool_calling=True, context_limit=8192),
            ),
        ]

    async def probe(self, settings: SettingsUpdate) -> ProviderStatus:
        if settings.provider == "openai":
            return ProviderStatus(
                provider="openai",
                status="configured" if self.openai.ready else "not_configured",
                message="Key configured. Account/model access is checked when you send a message."
                if self.openai.ready
                else "Save an OpenAI API key in Settings to enable cloud conversation.",
                tool_calling=True,
            )
        try:
            return await OllamaRuntime(settings.local_endpoint).probe(settings)
        except ProviderFailure as error:
            return ProviderStatus(
                provider="ollama",
                status="unreachable" if error.code.value == "provider_network" else "error",
                message=str(error),
                error_code=error.code.value,
            )


class SelectedRuntime:
    def __init__(self, registry: ProviderRegistry, settings: Callable[[], SettingsUpdate]) -> None:
        self.registry, self.settings = registry, settings

    @property
    def ready(self) -> bool:
        return self.registry.get(self.settings()).ready

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str:
        return await self.registry.get(settings).respond(messages, settings, registry, dispatch)
