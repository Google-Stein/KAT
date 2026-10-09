"""Validated, explicitly allowed tools and their security metadata.

The model selects an application ID, never an executable, command line, or shell
command. Application definitions are local administrator configuration.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class ToolRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolExecutionError(RuntimeError):
    """A validated tool request could not be completed."""


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


ApplicationId = Annotated[
    str, StringConstraints(min_length=1, max_length=48, pattern=r"^[a-z][a-z0-9_-]*$")
]


class GetLocalTimeArgs(ToolArguments):
    pass


class OpenApplicationArgs(ToolArguments):
    application_id: ApplicationId


class ApplicationDefinition(BaseModel):
    """A fixed launch definition; values must never come from model output."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: ApplicationId
    label: str = Field(min_length=1, max_length=80)
    executable: str = Field(min_length=1, max_length=4096)
    arguments: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError(
                "Application label must not contain surrounding whitespace or controls"
            )
        return value

    @field_validator("executable")
    @classmethod
    def validate_executable(cls, value: str) -> str:
        path = Path(value)
        if "\x00" in value or value.startswith(("\\\\", "//")) or not path.is_absolute():
            raise ValueError("Application executable must be a local absolute path")
        resolved = path.resolve()
        _validate_native_executable(path, resolved, windows=sys.platform == "win32")
        if any(
            item.suffix.casefold() in {".bat", ".cmd", ".ps1", ".vbs", ".js", ".sh", ".py"}
            for item in (path, resolved)
        ):
            raise ValueError("Shell scripts and interpreted files cannot be allowed applications")
        blocked = {
            "sh",
            "bash",
            "dash",
            "zsh",
            "ksh",
            "fish",
            "csh",
            "tcsh",
            "cmd",
            "powershell",
            "pwsh",
            "wscript",
            "cscript",
            "mshta",
            "rundll32",
            "regsvr32",
            "node",
            "nodejs",
            "ruby",
            "perl",
        }
        names = {path.name.casefold(), resolved.name.casefold()}
        stems = {name.removesuffix(".exe") for name in names}
        if any(stem in blocked or stem.startswith(("python", "pypy")) for stem in stems):
            raise ValueError(
                "Shells, interpreters, and command hosts cannot be allowed applications"
            )
        if not path.is_file() or (os.name != "nt" and not os.access(path, os.X_OK)):
            raise ValueError("Application executable must be an existing executable file")
        return str(resolved)

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, values: list[str]) -> list[str]:
        if any("\x00" in value or len(value) > 1024 for value in values):
            raise ValueError("Fixed arguments must contain no NULs and be at most 1024 characters")
        return values

    @property
    def command(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)

    @property
    def available(self) -> bool:
        path = Path(self.executable)
        return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def _validate_native_executable(path: Path, resolved: Path, *, windows: bool) -> None:
    # Windows may invoke a command interpreter for batch files even with shell=False.
    if windows and any(candidate.suffix.casefold() != ".exe" for candidate in (path, resolved)):
        raise ValueError("Windows applications must be native .exe executables")


def _windows_directory() -> Path:
    """Ask Windows for its directory rather than trust mutable environment variables."""
    buffer = ctypes.create_unicode_buffer(32768)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    get_directory = kernel32.GetWindowsDirectoryW
    get_directory.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    get_directory.restype = ctypes.c_uint
    length = get_directory(buffer, len(buffer))
    if length == 0 or length >= len(buffer):
        raise ToolExecutionError("Windows system directory could not be determined")
    return Path(buffer.value)


def _default_applications() -> list[ApplicationDefinition]:
    candidates: list[tuple[str, str, Path]] = []
    if sys.platform == "win32":
        system = _windows_directory() / "System32"
        candidates = [
            ("notepad", "Notepad", system / "notepad.exe"),
            ("calculator", "Calculator", system / "calc.exe"),
        ]
    elif sys.platform.startswith("linux"):
        candidates = [
            ("text-editor", "Text Editor", Path("/usr/bin/gnome-text-editor")),
            ("text-editor", "Text Editor", Path("/usr/bin/gedit")),
            ("text-editor", "Text Editor", Path("/usr/bin/kate")),
        ]
    definitions: list[ApplicationDefinition] = []
    for application_id, label, path in candidates:
        if (
            path.is_file()
            and (os.name == "nt" or os.access(path, os.X_OK))
            and not any(item.id == application_id for item in definitions)
        ):
            definitions.append(
                ApplicationDefinition(id=application_id, label=label, executable=str(path))
            )
    return definitions


def _child_environment() -> dict[str, str]:
    """Only OS/session variables reach launched apps; Core credentials never do."""
    home = str(Path.home())
    if sys.platform == "win32":
        windows = _windows_directory()
        return {
            "SYSTEMROOT": str(windows),
            "WINDIR": str(windows),
            "PATH": str(windows / "System32"),
            "USERPROFILE": home,
            "APPDATA": str(Path(home) / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(Path(home) / "AppData" / "Local"),
            "TEMP": str(Path(home) / "AppData" / "Local" / "Temp"),
            "TMP": str(Path(home) / "AppData" / "Local" / "Temp"),
        }
    environment = {"HOME": home, "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        if value := os.environ.get(name):
            environment[name] = value
    return environment


class ApplicationAllowlist:
    def __init__(self, applications: Sequence[ApplicationDefinition] | None = None) -> None:
        entries = list(applications) if applications is not None else _default_applications()
        if len({entry.id for entry in entries}) != len(entries):
            raise ValueError("Application IDs must be unique")
        self._applications = {entry.id: entry for entry in entries}

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ApplicationAllowlist:
        source = os.environ if environment is None else environment
        raw = source.get("KAT_APPLICATION_ALLOWLIST_JSON")
        if raw is None or raw == "":
            return cls()
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("KAT_APPLICATION_ALLOWLIST_JSON must be a JSON array") from error
        if not isinstance(entries, list):
            raise ValueError("KAT_APPLICATION_ALLOWLIST_JSON must be a JSON array")
        return cls([ApplicationDefinition.model_validate(entry) for entry in entries])

    def public_entries(self) -> list[dict[str, str]]:
        return [
            {"id": entry.id, "label": entry.label}
            for entry in self._applications.values()
            if entry.available
        ]

    def launch(self, application_id: str) -> dict[str, Any]:
        definition = self._available_definition(application_id)
        try:
            process = subprocess.Popen(
                definition.command,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                # Only approved, fixed application definitions escape Core lifetime.
                creationflags=0x01000000 if sys.platform == "win32" else 0,
                cwd=str(Path(definition.executable).parent),
                env=_child_environment(),
            )
        except OSError as error:
            raise ToolExecutionError("Configured application could not be launched") from error
        return {
            "application_id": definition.id,
            "label": definition.label,
            "pid": process.pid,
            "status": "launched",
        }

    def validate_id(self, application_id: str) -> None:
        self._available_definition(application_id)

    def _available_definition(self, application_id: str) -> ApplicationDefinition:
        definition = self._applications.get(application_id)
        if definition is None:
            raise ValueError("Application ID is not in the configured allowlist")
        if not definition.available:
            raise ToolExecutionError("Configured application is no longer available")
        return definition


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    arguments_model: type[BaseModel]
    execute: Callable[[BaseModel], dict[str, Any]]
    approval_required: bool = False
    transient: bool = True
    external_network: bool = False

    def validate_args(self, arguments: Mapping[str, Any]) -> BaseModel:
        return self.arguments_model.model_validate(dict(arguments))


class ToolRegistry:
    def __init__(self, allowlist: ApplicationAllowlist | None = None) -> None:
        self.allowlist = (
            allowlist if allowlist is not None else ApplicationAllowlist.from_environment()
        )
        self._specs: dict[str, ToolSpec] = {}
        self.read_roots: Callable[[], list[dict[str, str]]] = lambda: []
        self.approval_context: Callable[[str, dict[str, Any]], str | None] = lambda _name, _args: (
            None
        )
        self.register(
            ToolSpec(
                name="get_local_time",
                description="Get the current local system date, time, and timezone. "
                "Takes no arguments: call with an empty object {}.",
                risk=ToolRisk.LOW,
                arguments_model=GetLocalTimeArgs,
                execute=self._get_local_time,
            )
        )
        self.register(
            ToolSpec(
                name="open_application",
                description="Open an application by its configured allowlist ID after approval.",
                risk=ToolRisk.MEDIUM,
                arguments_model=OpenApplicationArgs,
                execute=self._open_application,
                approval_required=True,
            )
        )

    def register(self, spec: ToolSpec, *, replace: bool = False) -> None:
        if spec.name in self._specs and not replace:
            raise ValueError(f"Tool already registered: {spec.name}")
        if not issubclass(spec.arguments_model, ToolArguments):
            raise ValueError("Tool argument models must inherit strict ToolArguments")
        self._specs[spec.name] = spec

    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def model_specs(self) -> list[ToolSpec]:
        """Advertise file capabilities only after explicit owner registration."""
        unavailable = (
            {"list_directory", "read_text_file", "search_files"} if not self.read_roots() else set()
        )
        return [spec for spec in self.specs() if spec.name not in unavailable]

    def get(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError as error:
            raise ValueError(f"Unknown tool: {name}") from error

    def validate_args(self, name: str, arguments: Mapping[str, Any]) -> BaseModel:
        validated = self.get(name).validate_args(arguments)
        if isinstance(validated, OpenApplicationArgs):
            self.allowlist.validate_id(validated.application_id)
        return validated

    def execute(self, name: str, arguments: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
        raw = arguments.model_dump() if isinstance(arguments, BaseModel) else arguments
        spec = self.get(name)
        return spec.execute(self.validate_args(name, raw))

    def public_applications(self) -> list[dict[str, str]]:
        return self.allowlist.public_entries()

    @staticmethod
    def audit_outcome(name: str, outcome: dict[str, Any]) -> dict[str, Any]:
        if name not in {"list_directory", "read_text_file", "search_files"}:
            return outcome
        result = outcome.get("result") or {}
        metadata = {
            key: result[key]
            for key in ("root_id", "relative_path", "bytes_returned", "file_bytes", "truncated")
            if key in result
        }
        return {
            "status": outcome.get("status"),
            "result": metadata,
            "error_code": outcome.get("error_code"),
        }

    @staticmethod
    def _get_local_time(arguments: BaseModel) -> dict[str, Any]:
        GetLocalTimeArgs.model_validate(arguments.model_dump())
        now = datetime.now().astimezone()
        return {"iso": now.isoformat(), "timezone": now.tzname() or str(now.utcoffset())}

    def _open_application(self, arguments: BaseModel) -> dict[str, Any]:
        validated = OpenApplicationArgs.model_validate(arguments.model_dump())
        return self.allowlist.launch(validated.application_id)


def build_tool_registry(allowlist: ApplicationAllowlist | None = None) -> ToolRegistry:
    return ToolRegistry(allowlist)
