import os
import subprocess
import sys
from pathlib import Path

import pytest

from kat_core.__main__ import acquire_data_lock, token_from_file
from kat_core.config import CoreConfig


def test_private_token_file_generated_and_reused(tmp_path: Path) -> None:
    path = tmp_path / "private" / "token"
    first = token_from_file(path)
    assert len(first) >= 32
    assert token_from_file(path) == first
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0
        path.chmod(0o644)
        with pytest.raises(ValueError, match="private"):
            token_from_file(path)


def test_symlink_token_file_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("a" * 32)
    link = tmp_path / "token"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this platform")
    with pytest.raises(ValueError, match="symbolic"):
        token_from_file(link)


def test_cli_refuses_nonloopback_host_without_exposing_credentials(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "kat_core", "--data-dir", str(tmp_path)],
        env={**os.environ, "KAT_HOST": "0.0.0.0", "KAT_API_TOKEN": "secret-token-for-test" * 2},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "secret-token-for-test" not in result.stderr


def test_data_directory_has_one_runtime_owner(tmp_path: Path) -> None:
    held = acquire_data_lock(tmp_path)
    try:
        with pytest.raises(ValueError, match="Another"):
            acquire_data_lock(tmp_path)
    finally:
        held.close()
    acquire_data_lock(tmp_path).close()


@pytest.mark.parametrize("token", ["short", "a" * 32 + " ", "é" * 32])
def test_config_invalid_token_rejected(token: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        CoreConfig(data_dir=tmp_path, api_token=token)


def test_provider_key_alias_takes_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fallback")
    monkeypatch.setenv("KAT_OPENAI_API_KEY", "preferred")
    config = CoreConfig.from_environment(token="a" * 32, data_dir=tmp_path)
    assert config.openai_api_key == "preferred"
    assert "preferred" not in repr(config)
    monkeypatch.delenv("KAT_OPENAI_API_KEY")
    assert (
        CoreConfig.from_environment(token="a" * 32, data_dir=tmp_path).openai_api_key == "fallback"
    )
