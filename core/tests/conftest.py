from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.provider import ToolDispatcher
from kat_core.schemas import Message, SettingsUpdate
from kat_core.tools import ApplicationAllowlist, ApplicationDefinition, ToolRegistry

TOKEN = "test-private-core-token-32-characters"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


class FakeRuntime:
    ready = True

    def __init__(self) -> None:
        self.requests: list[tuple[list[Message], SettingsUpdate]] = []
        self.tool_requests: list[tuple[str, dict[str, Any]]] = []
        self.outcomes: list[dict[str, Any]] = []
        self.failure: Exception | None = None

    async def respond(
        self,
        messages: list[Message],
        settings: SettingsUpdate,
        registry: ToolRegistry,
        dispatch: ToolDispatcher,
    ) -> str:
        self.requests.append((messages, settings))
        if self.failure:
            raise self.failure
        self.outcomes = [await dispatch(name, args) for name, args in self.tool_requests]
        return "KAT response"


@pytest.fixture
def config(tmp_path: Path) -> CoreConfig:
    return CoreConfig(data_dir=tmp_path, api_token=TOKEN)


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    executable = tmp_path / "safe-demo.exe"
    executable.write_text("Mocked process fixture")
    executable.chmod(0o755)
    return ToolRegistry(
        ApplicationAllowlist(
            [ApplicationDefinition(id="demo", label="Demo application", executable=str(executable))]
        )
    )


@pytest.fixture
def client(
    config: CoreConfig, runtime: FakeRuntime, registry: ToolRegistry
) -> Iterator[TestClient]:
    app = create_app(config, runtime=runtime, registry=registry)
    with TestClient(app, base_url="http://127.0.0.1", headers=HEADERS) as active:
        yield active
