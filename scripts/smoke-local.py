"""Exercise actual local inference through production Core with no OpenAI access.

Does not download/start a backend. On Windows, approves real application launches.
On other platforms, validates the application approval but does not launch it.
"""

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.tools import ApplicationAllowlist, ApplicationDefinition, ToolRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b-instruct")
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
            validate = app.state.service.registry.validate_args

            def diagnose_arguments(name: str, arguments: dict):
                try:
                    return validate(name, arguments)
                except ValueError:
                    if os.environ.get("GITHUB_ACTIONS") == "true":
                        # Types/counts only: never print argument values or arbitrary keys.
                        print(
                            json.dumps(
                                {
                                    "test": "rejected-argument-shape",
                                    "tool": name
                                    if name in {s.name for s in app.state.service.registry.specs()}
                                    else "unknown",
                                    "argument_count": len(arguments),
                                    "value_types": sorted(
                                        type(v).__name__ for v in arguments.values()
                                    ),
                                }
                            ),
                            flush=True,
                        )
                    raise

            app.state.service.registry.validate_args = diagnose_arguments
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

                def time_results() -> list[dict]:
                    return [
                        event
                        for event in client.get("/audit").json()
                        if event["event"] == "tool_result"
                        and event["tool_name"] == "get_local_time"
                    ]

                timestamps = []
                for attempt in range(1, 3):
                    previous = {event["id"] for event in time_results()}
                    response = chat("Tell me the time.")
                    fresh = [event for event in time_results() if event["id"] not in previous]
                    if len(fresh) != 1 and os.environ.get("GITHUB_ACTIONS") == "true":
                        # Disposable, self-created test session: never owner chat,
                        # credentials or raw HTTP headers. JSON escapes control text.
                        print(
                            json.dumps(
                                {
                                    "test": "fresh-time",
                                    "attempt": attempt,
                                    "fresh_results": len(fresh),
                                    "safe_tool_events": [
                                        {
                                            "event": event["event"],
                                            "tool": event["tool_name"],
                                            "reason": event["details"].get("reason"),
                                            "status": event["details"].get("status"),
                                        }
                                        for event in client.get("/audit").json()
                                        if event["session_id"] == session
                                        and event["event"].startswith("tool_")
                                    ],
                                    "assistant_reply": response["assistant_message"]["content"][
                                        :1000
                                    ],
                                }
                            ),
                            flush=True,
                        )
                    assert len(fresh) == 1, "Repeated time request did not invoke a fresh tool"
                    assert fresh[0]["details"]["status"] == "completed"
                    timestamps.append(datetime.fromisoformat(fresh[0]["details"]["result"]["iso"]))
                assert timestamps[1] > timestamps[0], "Second time result was stale"
                print(
                    "PASS: repeated real local time requests invoke fresh tools with newer results."
                )
                approval_ids = set()
                applications = (
                    ("notepad", "notepad", "calculator", "calculator")
                    if os.name == "nt"
                    else ("notepad", "notepad")
                )
                for application_id in applications:
                    previous_results = len(
                        [
                            event
                            for event in client.get("/audit").json()
                            if event["event"] == "tool_result"
                            and event["tool_name"] == "open_application"
                        ]
                    )
                    result = chat(f"Open {application_id.title()}.")
                    pending = [
                        item
                        for item in result["approvals"]
                        if item["tool_name"] == "open_application"
                        and item["arguments"] == {"application_id": application_id}
                    ]
                    assert len(pending) == 1 and pending[0]["status"] == "pending", (
                        f"Model selection failed: no new {application_id} approval"
                    )
                    assert pending[0]["id"] not in approval_ids
                    approval_ids.add(pending[0]["id"])
                    assert (
                        len(
                            [
                                event
                                for event in client.get("/audit").json()
                                if event["event"] == "tool_result"
                                and event["tool_name"] == "open_application"
                            ]
                        )
                        == previous_results
                    ), "Application ran before approval"
                    approved = client.post(
                        f"/approvals/{pending[0]['id']}/decision",
                        json={"approved": os.name == "nt"},
                    ).json()
                    if os.name == "nt":
                        assert approved["status"] == "completed", approved["error"]
                        print(
                            f"PASS: fresh {application_id} selection, explicit approval, "
                            "fixed native launch and audit."
                        )
                        # GUI creation is separately asserted by the installed UI test.
                        from contextlib import suppress

                        import win32api

                        with suppress(Exception):
                            handle = win32api.OpenProcess(1, False, approved["result"]["pid"])
                            win32api.TerminateProcess(handle, 0)
                            win32api.CloseHandle(handle)
                    else:
                        assert approved["status"] == "denied"
                        print(
                            "PASS: repeated local approval/denial; "
                            "Windows launch untested on Linux."
                        )
                session = client.post("/sessions", json={}).json()["id"]
                response = chat("How much RAM am I using?")
                events = [e for e in client.get("/audit").json() if e["session_id"] == session]
                results = [
                    e
                    for e in events
                    if e["event"] == "tool_result" and e["tool_name"] == "get_system_status"
                ]
                if len(results) != 1 and os.environ.get("GITHUB_ACTIONS") == "true":
                    print(
                        json.dumps(
                            {
                                "test": "fresh-system",
                                "result_count": len(results),
                                "safe_tool_events": [
                                    {
                                        "event": e["event"],
                                        "tool": e["tool_name"],
                                        "reason": e["details"].get("reason"),
                                    }
                                    for e in events
                                    if e["event"].startswith("tool_")
                                ],
                                "assistant_reply": response["assistant_message"]["content"][:1000],
                            }
                        ),
                        flush=True,
                    )
                assert len(results) == 1, "RAM request did not invoke one fresh system tool"
                assert results[0]["details"]["status"] == "completed"
                assert results[0]["details"]["result"]["ram"]["total_bytes"] > 0
                print(
                    "PASS: real local current RAM request executes fresh read-only system metrics."
                )


if __name__ == "__main__":
    main()
