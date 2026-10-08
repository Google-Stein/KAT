"""Exercise actual local inference through production Core with no OpenAI access.

Does not download/start a backend. On Windows, approves and opens real Notepad.
On other platforms, validates the application approval but does not launch it.
"""

import argparse
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.tools import ApplicationAllowlist, ApplicationDefinition, ToolRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:1.7b")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="kat-local-smoke-") as directory:
        config = CoreConfig(
            data_dir=Path(directory), api_token="real-local-smoke-token-at-least-32-characters"
        )
        registry = None
        if os.name != "nt":
            # Linux validation cannot claim a Windows Notepad execution.
            registry = ToolRegistry(
                ApplicationAllowlist(
                    [
                        ApplicationDefinition(
                            id="notepad",
                            label="Approval-only Linux fixture",
                            executable="/usr/bin/true",
                        )
                    ]
                )
            )
        with patch(
            "kat_core.provider.AsyncOpenAI",
            side_effect=AssertionError("Local path tried to contact OpenAI"),
        ):
            app = create_app(config, registry=registry)
            with TestClient(
                app,
                base_url="http://127.0.0.1",
                headers={"Authorization": f"Bearer {config.api_token}"},
            ) as client:
                settings = {"provider": "ollama", "model": args.model}
                assert client.put("/settings", json=settings).status_code == 200
                status = client.post("/providers/probe", json=settings).json()
                assert status["status"] == "ready" and status["tool_calling"], status["message"]
                session = client.post("/sessions", json={}).json()["id"]

                def chat(prompt: str) -> dict:
                    response = client.post(
                        f"/sessions/{session}/messages", json={"content": prompt}
                    )
                    assert response.status_code == 200, response.text
                    assert response.json()["assistant_message"]["content"].strip()
                    return response.json()

                chat("Hello, KAT.")
                print("PASS: real local conversation, OpenAI unavailable.")
                chat("What time is it? Use the current local system time.")
                audit = client.get("/audit").json()
                assert any(
                    event["event"] == "tool_result"
                    and event["tool_name"] == "get_local_time"
                    and event["details"]["status"] == "completed"
                    for event in audit
                )
                print("PASS: real local model chose the time tool; execution audited.")
                result = chat("Open Notepad.")
                pending = [
                    item
                    for item in result["approvals"]
                    if item["tool_name"] == "open_application"
                    and item["arguments"] == {"application_id": "notepad"}
                ]
                assert len(pending) == 1 and pending[0]["status"] == "pending"
                assert not any(
                    event["tool_name"] == "open_application" and event["event"] == "tool_result"
                    for event in client.get("/audit").json()
                )
                approved = client.post(
                    f"/approvals/{pending[0]['id']}/decision", json={"approved": os.name == "nt"}
                ).json()
                if os.name == "nt":
                    assert approved["status"] == "completed", approved["error"]
                    print(
                        "PASS: real local Notepad request, explicit approval, native launch "
                        "and audit."
                    )
                    # This disposable test closes only the PID returned by its own approved tool.
                    from contextlib import suppress

                    import win32api

                    with suppress(Exception):
                        handle = win32api.OpenProcess(1, False, approved["result"]["pid"])
                        win32api.TerminateProcess(handle, 0)
                        win32api.CloseHandle(handle)
                else:
                    assert approved["status"] == "denied"
                    print(
                        "PASS: local application approval/denial; Windows launch not tested on "
                        "Linux."
                    )


if __name__ == "__main__":
    main()
