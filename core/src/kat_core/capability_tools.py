"""Narrow capability definitions sharing the existing approval dispatcher."""

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from kat_core.capability_schemas import CapabilityFailure
from kat_core.capability_store import CapabilityStore
from kat_core.file_access import (
    directory_entries,
    read_text,
    relative_parts,
    search_names,
    validate_text_target,
)
from kat_core.system_status import system_status
from kat_core.tools import ToolArguments, ToolRegistry, ToolRisk, ToolSpec
from kat_core.weather import OpenMeteo, WeatherAdapter

RootId = Annotated[str, StringConstraints(pattern=r"^root-[a-f0-9]{24}$")]


class EmptyArgs(ToolArguments):
    pass


class SystemArgs(ToolArguments):
    metric: Literal["all", "ram", "cpu", "disks", "gpu", "os"] = "all"


class FileArgs(ToolArguments):
    root_id: RootId = Field(description="Exact registered root ID from the available roots.")
    relative_path: str = Field(
        min_length=1,
        max_length=240,
        description=(
            "Path INSIDE the root, excluding the root folder name or label. "
            "For a file named notes.txt at its top level, use notes.txt, never '.'. "
            "Only list_directory uses '.' to list the root itself."
        ),
    )

    @field_validator("relative_path")
    @classmethod
    def safe_relative(cls, value: str) -> str:
        relative_parts(value)
        return value


class SearchArgs(ToolArguments):
    root_id: RootId
    query: str = Field(min_length=1, max_length=80)

    @field_validator("query")
    @classmethod
    def literal_query(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("Search text must not contain controls")
        return value


class BoundedCapabilities:
    def __init__(self, store: CapabilityStore, weather: WeatherAdapter | None = None) -> None:
        self.store = store
        self.weather = weather or OpenMeteo()

    def register(self, registry: ToolRegistry) -> None:
        registry.approval_context = self.approval_context
        registry.read_roots = lambda: [
            {"id": r.id, "label": r.label} for r in self.store.configuration().read_roots
        ]
        for name, description, risk, schema, execute, external in (
            (
                "get_weather",
                "Get fresh weather at the owner's configured location. "
                "Uses external Open-Meteo HTTPS, independent of AI. "
                "Takes no arguments: call with an empty object {}.",
                ToolRisk.LOW,
                EmptyArgs,
                self.get_weather,
                True,
            ),
            (
                "get_system_status",
                "Get fresh read-only information about this PC. Choose metric 'ram' for RAM "
                "usage, 'cpu', 'disks', 'gpu', 'os', or 'all' for an overview. No shell.",
                ToolRisk.LOW,
                SystemArgs,
                self.get_system,
                False,
            ),
            (
                "list_directory",
                "List one directory in an approved root. relative_path '.' means its top level. "
                "Maximum 100 entries.",
                ToolRisk.LOW,
                FileArgs,
                self.list_directory,
                False,
            ),
            (
                "read_text_file",
                "Read a UTF-8 text file in an approved root after one-time approval. "
                "Copy the requested relative filename exactly, including its extension. "
                "Maximum 64 KiB and 12000 returned characters.",
                ToolRisk.MEDIUM,
                FileArgs,
                self.read_file,
                False,
            ),
            (
                "search_files",
                "Search literal filenames in an approved root, never file bodies. "
                "Maximum 1000 entries, depth 4 and 50 matches.",
                ToolRisk.LOW,
                SearchArgs,
                self.search_files,
                False,
            ),
        ):
            registry.register(
                ToolSpec(
                    name=name,
                    description=description,
                    risk=risk,
                    arguments_model=schema,
                    execute=execute,
                    external_network=external,
                    approval_required=risk != ToolRisk.LOW,
                    transient=True,
                    continuation_policy="local_result" if name == "read_text_file" else "none",
                ),
                replace=True,
            )

    def get_weather(self, _arguments: BaseModel) -> dict[str, Any]:
        location = self.store.configuration().weather_location
        if location is None:
            raise CapabilityFailure(
                "weather_not_configured",
                "Choose and confirm a weather location in Settings → Capabilities.",
            )
        return self.weather.current(location)

    def approval_context(self, name: str, arguments: dict[str, Any]) -> str | None:
        if name in {"read_text_file", "list_directory", "search_files"}:
            root = self.store.root(arguments["root_id"])
            if name == "read_text_file":
                validate_text_target(Path(root.path), arguments["relative_path"])
            return "Read-only folder: " + root.label
        return None

    @staticmethod
    def get_system(arguments: BaseModel) -> dict[str, Any]:
        metric = SystemArgs.model_validate(arguments.model_dump()).metric
        result = system_status()
        if metric == "all":
            return result
        fields = {
            "ram": {"ram"},
            "cpu": {
                "cpu_architecture",
                "cpu_model",
                "logical_cpus",
                "physical_cpus",
                "cpu_percent",
            },
            "disks": {"disks"},
            "gpu": {"gpus"},
            "os": {"os_version", "uptime_seconds"},
        }[metric] | {"os", "collected_at", "unavailable_metrics"}
        return {key: value for key, value in result.items() if key in fields}

    def list_directory(self, arguments: BaseModel) -> dict[str, Any]:
        args = FileArgs.model_validate(arguments.model_dump())
        root = self.store.root(args.root_id)
        return {
            "root_id": root.id,
            "root_label": root.label,
            **directory_entries(Path(root.path), args.relative_path),
        }

    def read_file(self, arguments: BaseModel) -> dict[str, Any]:
        args = FileArgs.model_validate(arguments.model_dump())
        root = self.store.root(args.root_id)
        return {
            "root_id": root.id,
            "root_label": root.label,
            **read_text(Path(root.path), args.relative_path),
        }

    def search_files(self, arguments: BaseModel) -> dict[str, Any]:
        args = SearchArgs.model_validate(arguments.model_dump())
        root = self.store.root(args.root_id)
        return {
            "root_id": root.id,
            "root_label": root.label,
            **search_names(Path(root.path), args.query),
        }
