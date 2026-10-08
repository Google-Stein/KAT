from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from kat_core.tools import (
    ApplicationAllowlist,
    ApplicationDefinition,
    OpenApplicationArgs,
    ToolExecutionError,
    ToolRisk,
    _validate_native_executable,
    build_tool_registry,
)


@pytest.fixture
def application(tmp_path: Path) -> ApplicationDefinition:
    executable = tmp_path / "safe-editor.exe"
    executable.write_text("fixture executable\n")
    executable.chmod(0o755)
    return ApplicationDefinition(
        id="editor", label="Safe Editor", executable=str(executable), arguments=["--new-window"]
    )


def test_builtin_tools_have_explicit_risk_and_strict_schemas() -> None:
    registry = build_tool_registry(ApplicationAllowlist([]))
    assert {spec.name: spec.risk for spec in registry.specs()} == {
        "get_local_time": ToolRisk.LOW,
        "open_application": ToolRisk.MEDIUM,
    }
    for spec in registry.specs():
        assert spec.description
        assert spec.arguments_model.model_json_schema()["additionalProperties"] is False


def test_current_time_is_local_timezone_aware() -> None:
    registry = build_tool_registry(ApplicationAllowlist([]))
    before = datetime.now().astimezone()
    result = registry.execute("get_local_time", {})
    after = datetime.now().astimezone()
    assert before <= datetime.fromisoformat(result["iso"]) <= after
    assert result["timezone"]


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"application_id": 1},
        {"application_id": "editor", "command": "dangerous"},
        {"application_id": "editor; rm -rf /"},
        {"application_id": "../../bin/bash"},
        {"application_id": "a" * 49},
        {"application_id": "editor\n"},
    ],
)
def test_open_application_rejects_malformed_model_arguments(arguments: dict[str, Any]) -> None:
    registry = build_tool_registry(ApplicationAllowlist([]))
    with pytest.raises(ValidationError):
        registry.execute("open_application", arguments)


def test_time_rejects_extra_arguments() -> None:
    registry = build_tool_registry(ApplicationAllowlist([]))
    with pytest.raises(ValidationError):
        registry.execute("get_local_time", {"shell": "echo no"})


def test_unknown_tools_and_applications_cannot_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    process = Mock()
    monkeypatch.setattr("kat_core.tools.subprocess.Popen", process)
    registry = build_tool_registry(ApplicationAllowlist([]))
    with pytest.raises(ValueError, match="Unknown tool"):
        registry.execute("shell", {})
    with pytest.raises(ValueError, match="allowlist"):
        registry.execute("open_application", {"application_id": "missing"})
    process.assert_not_called()


def test_unknown_application_rejected_during_validation_before_approval() -> None:
    registry = build_tool_registry(ApplicationAllowlist([]))
    with pytest.raises(ValueError, match="allowlist"):
        registry.validate_args("open_application", {"application_id": "missing"})


def test_launch_uses_only_fixed_argv_without_shell_or_core_secrets(
    application: ApplicationDefinition, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock(return_value=Mock(pid=4321))
    monkeypatch.setattr("kat_core.tools.subprocess.Popen", process)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-child")
    monkeypatch.setenv("KAT_CORE_TOKEN", "must-not-reach-child")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-reach-child")
    registry = build_tool_registry(ApplicationAllowlist([application]))

    result = registry.execute("open_application", OpenApplicationArgs(application_id="editor"))

    assert result == {
        "application_id": "editor",
        "label": "Safe Editor",
        "pid": 4321,
        "status": "launched",
    }
    assert process.call_args.args == (application.command,)
    options = process.call_args.kwargs
    assert options["shell"] is False
    assert options["close_fds"] is True
    assert options["creationflags"] == (0x01000000 if os.name == "nt" else 0)
    assert options["cwd"] == str(Path(application.executable).parent)
    assert "OPENAI_API_KEY" not in options["env"]
    assert "KAT_CORE_TOKEN" not in options["env"]
    assert "GITHUB_TOKEN" not in options["env"]
    assert "must-not-reach-child" not in options["env"].values()


def test_launch_reports_os_failure(
    application: ApplicationDefinition, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kat_core.tools.subprocess.Popen", Mock(side_effect=OSError("failure")))
    registry = build_tool_registry(ApplicationAllowlist([application]))
    with pytest.raises(ToolExecutionError, match="could not be launched"):
        registry.execute("open_application", {"application_id": "editor"})


def test_removed_application_is_hidden_and_cannot_launch(
    application: ApplicationDefinition,
) -> None:
    registry = build_tool_registry(ApplicationAllowlist([application]))
    assert registry.public_applications() == [{"id": "editor", "label": "Safe Editor"}]
    Path(application.executable).unlink()
    assert registry.public_applications() == []
    with pytest.raises(ToolExecutionError, match="no longer available"):
        registry.execute("open_application", {"application_id": "editor"})


def test_environment_allowlist_replaces_defaults(application: ApplicationDefinition) -> None:
    allowlist = ApplicationAllowlist.from_environment(
        {"KAT_APPLICATION_ALLOWLIST_JSON": json.dumps([application.model_dump()])}
    )
    assert allowlist.public_entries() == [{"id": "editor", "label": "Safe Editor"}]
    assert (
        ApplicationAllowlist.from_environment(
            {"KAT_APPLICATION_ALLOWLIST_JSON": "[]"}
        ).public_entries()
        == []
    )


@pytest.mark.parametrize("raw", ["not json", "{}", "null", '[{"id":"editor"}]'])
def test_environment_allowlist_invalid_configuration_fails_closed(raw: str) -> None:
    with pytest.raises(ValueError):
        ApplicationAllowlist.from_environment({"KAT_APPLICATION_ALLOWLIST_JSON": raw})


@pytest.mark.parametrize(
    "executable", ["relative.exe", "//host/share/app.exe", "\\\\host\\app.exe"]
)
def test_executable_must_be_local_absolute_path(executable: str) -> None:
    with pytest.raises(ValidationError):
        ApplicationDefinition(id="editor", label="Editor", executable=executable)


@pytest.mark.parametrize(
    "name", ["bash.exe", "cmd.exe", "powershell.exe", "python3.12.exe", "node.exe"]
)
def test_shells_and_interpreters_are_never_allowlisted(tmp_path: Path, name: str) -> None:
    executable = tmp_path / name
    executable.write_text("test")
    executable.chmod(0o755)
    with pytest.raises(ValidationError, match="Shells, interpreters"):
        ApplicationDefinition(id="unsafe", label="Unsafe", executable=str(executable))


def test_interpreter_symlink_cannot_bypass_allowlist_validation(tmp_path: Path) -> None:
    executable = tmp_path / "bash.exe"
    executable.write_text("test")
    executable.chmod(0o755)
    alias = tmp_path / "editor.exe"
    try:
        alias.symlink_to(executable)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this platform")
    with pytest.raises(ValidationError, match="Shells, interpreters"):
        ApplicationDefinition(id="editor", label="Editor", executable=str(alias))


@pytest.mark.parametrize("name", ["editor.bat", "editor.cmd", "editor.ps1", "powershell.cmd"])
def test_windows_batch_and_script_launches_are_forbidden(name: str) -> None:
    path = Path(name)
    with pytest.raises(ValueError, match="native .exe"):
        _validate_native_executable(path, path, windows=True)


def test_windows_native_path_checks_both_original_and_resolved_names() -> None:
    executable = Path("editor.exe")
    _validate_native_executable(executable, executable, windows=True)
    with pytest.raises(ValueError, match="native .exe"):
        _validate_native_executable(executable, Path("editor.cmd"), windows=True)
    with pytest.raises(ValueError, match="native .exe"):
        _validate_native_executable(Path("editor.bat"), executable, windows=True)


def test_windows_script_rejected_by_application_definition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "editor.cmd"
    executable.write_text("test")
    executable.chmod(0o755)
    monkeypatch.setattr("kat_core.tools.sys.platform", "win32")
    with pytest.raises(ValidationError, match="native .exe"):
        ApplicationDefinition(id="editor", label="Editor", executable=str(executable))


def test_fixed_arguments_are_validated(application: ApplicationDefinition) -> None:
    values = application.model_dump()
    values["arguments"] = ["bad\x00argument"]
    with pytest.raises(ValidationError):
        ApplicationDefinition.model_validate(values)
    values["arguments"] = [123]
    with pytest.raises(ValidationError):
        ApplicationDefinition.model_validate(values)


def test_nonexecutable_and_missing_files_cannot_be_allowlisted(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX execute bit check")
    executable = tmp_path / "editor"
    executable.write_text("test")
    executable.chmod(0o600)
    with pytest.raises(ValidationError, match="existing executable file"):
        ApplicationDefinition(id="editor", label="Editor", executable=str(executable))


def test_duplicate_application_ids_and_tool_names_are_rejected(
    application: ApplicationDefinition,
) -> None:
    with pytest.raises(ValueError, match="unique"):
        ApplicationAllowlist([application, application])
    registry = build_tool_registry(ApplicationAllowlist([]))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(registry.get("get_local_time"))
