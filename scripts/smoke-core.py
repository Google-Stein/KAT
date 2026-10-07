"""Exercise real CLI startup, authenticated HTTP, restart persistence, and shutdown.

This is intentionally keyless: it validates service plumbing, not live model access.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def request(
    base: str, token: str, path: str, body: dict[str, Any] | None = None, method: str | None = None
) -> Any:
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + path,
        data=payload,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


def start(executable: Path, data: Path, token_file: Path, port: int) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    for name in (
        "OPENAI_API_KEY",
        "KAT_OPENAI_API_KEY",
        "KAT_API_TOKEN",
        "KAT_HOST",
        "KAT_APPLICATION_ALLOWLIST_JSON",
        "KAT_MODEL",
        "KAT_PORT",
    ):
        environment.pop(name, None)
    args = [str(executable)]
    if executable.name.lower().startswith("python"):
        args += ["-m", "kat_core"]
    process = subprocess.Popen(
        [*args, "--data-dir", str(data), "--token-file", str(token_file), "--port", str(port)],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Core exited during startup (exit {process.returncode})")
        if token_file.exists():
            try:
                health = request(
                    f"http://127.0.0.1:{port}", token_file.read_text().strip(), "/health"
                )
                if health["status"] == "ok":
                    return process
            except (OSError, urllib.error.URLError):
                pass
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError("Core did not become ready")


def stop(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise RuntimeError("Core required forced shutdown") from None
    if process.returncode not in (0, -15):
        raise RuntimeError(f"Core shutdown failed (exit {process.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default = (
        Path(__file__).resolve().parent.parent
        / "core/.venv"
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    parser.add_argument("--executable", type=Path, default=default)
    # Preserve the venv launcher path: resolving its symlink would use global packages.
    executable = parser.parse_args().executable.absolute()
    if not executable.is_file():
        parser.error("Core executable is missing; install locked dependencies first")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="kat-smoke-") as directory:
        root = Path(directory)
        token_file = root / "token"
        process = start(executable, root / "data", token_file, port)
        base = f"http://127.0.0.1:{port}"
        try:
            token = token_file.read_text().strip()
            assert request(base, token, "/health")["provider_ready"] is False
            try:
                request(base, "incorrect-token", "/sessions")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError("Unauthenticated access succeeded")
            session = request(base, token, "/sessions", {"title": "Restart smoke check"})
            request(
                base,
                token,
                "/settings",
                {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "require_approval_for_low_risk": True,
                },
                method="PUT",
            )
            try:
                request(base, token, f"/sessions/{session['id']}/messages", {"content": "Hello"})
            except urllib.error.HTTPError as error:
                assert error.code == 503
            else:
                raise AssertionError("Keyless conversation reported success")
            assert request(base, token, "/openapi.json")["info"]["title"] == "KAT Core"
        finally:
            stop(process)
        process = start(executable, root / "data", token_file, port)
        try:
            sessions = request(base, token, "/sessions")
            assert sessions[0]["id"] == session["id"]
            assert request(base, token, "/settings")["require_approval_for_low_risk"] is True
        finally:
            stop(process)
    print(
        "PASS: real Core startup, authenticated API, keyless error, "
        "persistence after restart, shutdown"
    )


if __name__ == "__main__":
    main()
