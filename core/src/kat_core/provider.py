"""Replaceable model boundary with the first adapter using OpenAI Agents SDK."""

import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    OpenAIResponsesModel,
    RunConfig,
    RunContextWrapper,
    RunHooks,
    Runner,
    Tool,
    set_tracing_disabled,
)
from agents.exceptions import ModelBehaviorError
from agents.items import ModelResponse, TResponseInputItem
from agents.tool_context import ToolContext
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from kat_core.errors import ProviderErrorCode, ProviderFailure
from kat_core.model_context import history, instructions
from kat_core.schemas import Message, SettingsUpdate
from kat_core.tools import ToolRegistry

ToolDispatcher = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class ModelRuntime(Protocol):
    @property
    def ready(self) -> bool: ...

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str: ...


class ProviderUnavailableError(ProviderFailure):
    """Compatibility name for a missing provider configuration."""

    def __init__(self) -> None:
        super().__init__(ProviderErrorCode.NOT_CONFIGURED)


def classify_openai_error(error: Exception) -> ProviderFailure:
    # Inspect only structured status/code fields. Never match exception prose,
    # echo payloads, or keep raw exceptions in the public failure object.
    if isinstance(error, APITimeoutError):
        category = ProviderErrorCode.TIMEOUT
    elif isinstance(error, APIConnectionError):
        category = ProviderErrorCode.NETWORK
    elif isinstance(error, AuthenticationError):
        category = ProviderErrorCode.AUTHENTICATION
    elif isinstance(error, (NotFoundError, PermissionDeniedError)):
        category = ProviderErrorCode.MODEL_UNAVAILABLE
    elif isinstance(error, RateLimitError):
        body = error.body
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            body = body["error"]
        code = body.get("code") if isinstance(body, dict) else None
        category = (
            ProviderErrorCode.QUOTA
            if code in ("insufficient_quota", "billing_hard_limit_reached", "usage_limit_reached")
            else ProviderErrorCode.RATE_LIMITED
        )
    elif isinstance(error, (APIResponseValidationError, ModelBehaviorError)):
        category = ProviderErrorCode.MALFORMED_RESPONSE
    elif isinstance(error, APIStatusError) and error.status_code == 400:
        body = error.body
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            body = body["error"]
        code = body.get("code") if isinstance(body, dict) else None
        category = (
            ProviderErrorCode.MODEL_UNAVAILABLE
            if code in ("model_not_found", "model_not_available")
            else ProviderErrorCode.FAILED
        )
    else:
        category = ProviderErrorCode.FAILED
    return ProviderFailure(category)


class AuditUnknownToolsHook(RunHooks[Any]):
    """The SDK rejects unknown names before callbacks; preserve an audit event too."""

    def __init__(self, registry: ToolRegistry, dispatch: ToolDispatcher) -> None:
        self._known = {spec.name for spec in registry.specs()}
        self._dispatch = dispatch

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: ModelResponse
    ) -> None:
        for item in response.output:
            if item.type == "function_call" and item.name not in self._known:
                await self._dispatch(item.name, {"__invalid_arguments__": True})


class OpenAIAgentsRuntime:
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key
        # Traces may contain conversations and tools. Local logs are the only audit transport.
        set_tracing_disabled(True)

    @property
    def ready(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _sdk_tools(registry: ToolRegistry, dispatch: ToolDispatcher) -> list[FunctionTool]:
        sdk_tools = []
        for spec in registry.specs():

            def make_handler(name: str) -> Callable[[ToolContext[Any], str], Awaitable[str]]:
                async def invoke(_context: ToolContext[Any], raw: str) -> str:
                    try:
                        arguments = json.loads(raw)
                        if not isinstance(arguments, dict):
                            raise ValueError("Tool arguments must be a JSON object")
                    except (ValueError, TypeError):
                        # Pass an invalid sentinel through the same auditable validation boundary.
                        arguments = {"__invalid_arguments__": True}
                    result = await dispatch(name, arguments)
                    return json.dumps(result, ensure_ascii=False)

                return invoke

            sdk_tools.append(
                FunctionTool(
                    name=spec.name,
                    description=spec.description,
                    params_json_schema=spec.arguments_model.model_json_schema(),
                    on_invoke_tool=make_handler(spec.name),
                    strict_json_schema=True,
                )
            )
        return sdk_tools

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str:
        if not self._api_key:
            raise ProviderUnavailableError()
        context = cast(list[TResponseInputItem], history(messages))
        prompt = instructions(registry)
        try:
            async with AsyncOpenAI(api_key=self._api_key, timeout=45.0, max_retries=1) as client:
                agent: Agent[Any] = Agent(
                    name="KAT",
                    instructions=prompt,
                    model=OpenAIResponsesModel(settings.model, client),
                    model_settings=ModelSettings(
                        store=False, parallel_tool_calls=False, max_tokens=4096
                    ),
                    tools=cast(list[Tool], self._sdk_tools(registry, dispatch)),
                )
                result = await Runner.run(
                    agent,
                    input=context,
                    max_turns=6,
                    run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False),
                    hooks=AuditUnknownToolsHook(registry, dispatch),
                )
        except Exception as error:
            raise classify_openai_error(error) from None
        if not isinstance(result.final_output, str) or not result.final_output.strip():
            raise ProviderFailure(ProviderErrorCode.MALFORMED_RESPONSE)
        return result.final_output
