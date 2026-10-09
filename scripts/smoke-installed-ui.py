"""Drive the production Windows UI through accessibility, never a debugging port.

Disposable CI account only. Uses synthetic native credential input and real local
inference. Database inspection is read-only; all mutations use actual UI controls.
"""

import argparse
import ctypes
import json
import os
import sqlite3
import subprocess
import time
import traceback
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

TARGET = "KAT/OpenAI"
FIXTURE = "sk-proj-ci_synthetic_not_a_real_api_key_1234"
REPLACEMENT = "sk-proj-ci_synthetic_replacement_key_5678"


def wait_for(check: Any, timeout: float = 20) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.2)
    raise RuntimeError("Expected test condition did not become ready")


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("Synthetic credential test requires a disposable Windows CI account.")
    import win32cred
    import win32gui
    from pywinauto import Application, mouse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--credentials-only", action="store_true")
    args = parser.parse_args()
    try:
        win32cred.CredRead(TARGET, win32cred.CRED_TYPE_GENERIC)
    except Exception as error:
        if getattr(error, "winerror", None) != 1168:
            raise SystemExit("Cannot establish empty disposable credential vault.") from None
    else:
        raise SystemExit("Refusing to modify an existing KAT credential.")

    database = Path(os.environ["LOCALAPPDATA"]) / "com.kat.assistant/kat.sqlite3"
    environment = os.environ.copy()
    for name in (
        "OPENAI_API_KEY",
        "KAT_OPENAI_API_KEY",
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "WEBVIEW2_USER_DATA_FOLDER",
    ):
        environment.pop(name, None)
    process = None
    window = None
    application_windows: list[int] = []
    stage = "installed-startup"

    def rows(query: str, parameters: tuple = ()) -> list[dict[str, Any]]:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(query, parameters)]
        finally:
            connection.close()

    def reveal(control: Any) -> None:
        # Chromium does not expose ScrollItem on every HTML form control. Scroll
        # the actual Settings pane with normal mouse input when it is offscreen.
        if control.is_visible():
            return
        window.set_focus()
        rect = window.rectangle()
        coords = (rect.left + rect.width() * 3 // 4, rect.top + rect.height() // 2)
        mouse.scroll(coords=coords, wheel_dist=40)
        for _ in range(40):
            if control.is_visible():
                return
            mouse.scroll(coords=coords, wheel_dist=-2)
            time.sleep(0.1)
        raise RuntimeError("Settings control could not be scrolled into view")

    def button(name: str) -> Any:
        control = window.child_window(title=name, control_type="Button", visible_only=False)
        control.wait("exists", timeout=20)
        with suppress(Exception):
            control.wrapper_object().iface_scroll_item.ScrollIntoView()
        reveal(control)
        control.wait("visible enabled", timeout=20)
        return control

    def visible_text(text: str) -> bool:
        return any(control.window_text() == text for control in window.descendants())

    def launch() -> None:
        nonlocal process, window
        process = subprocess.Popen([str(args.executable)], env=environment)
        app = Application(backend="uia").connect(process=process.pid, timeout=30)
        window = app.window(title="KAT")
        window.wait("visible", timeout=45)
        # Hosted desktops can be smaller than KAT's restored window size. Use
        # the real maximize action so mouse input stays inside the work area.
        window.maximize()
        window.set_focus()
        button("Settings")

    def close() -> None:
        nonlocal process
        window.close()
        assert process.wait(timeout=15) == 0
        process = None

    def dialog() -> Any:
        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user32.FindWindowW.restype = ctypes.c_void_p
        handle = wait_for(lambda: user32.FindWindowW(None, "KAT — OpenAI API key"), 10)
        return Application(backend="win32").connect(handle=handle).window(handle=handle)

    def configure_key(value: str, replace: bool = False) -> None:
        button("Replace saved key" if replace else "Set API key").click_input()
        prompt = dialog()
        password = next(
            control
            for control in prompt.descendants(class_name="Edit")
            if win32gui.GetWindowLong(control.handle, -16) & 0x20
        )
        password.set_edit_text(value)
        prompt.child_window(title="OK", class_name="Button").click()
        wait_for(lambda: visible_text("API key saved. Local Core restarted."))
        assert (
            win32cred.CredRead(TARGET, win32cred.CRED_TYPE_GENERIC)["CredentialBlob"]
            == value.encode()
        )
        assert not visible_text(value)

    try:
        launch()
        stage = "native-credential-entry"
        button("Settings").click_input()
        button("Set API key").click_input()
        dialog().close()
        wait_for(lambda: visible_text("API key setup cancelled."))
        configure_key(FIXTURE)
        configure_key(REPLACEMENT, replace=True)
        close()
        launch()
        button("Settings").click_input()
        wait_for(lambda: visible_text("API key configured"))
        button("Replace saved key")
        button("Remove saved key").click_input()
        wait_for(lambda: visible_text("Saved key removed. Local Core restarted."))
        wait_for(lambda: visible_text("API key required"))
        print(
            "PASS: installed native key entry/cancel/save/replace, vault "
            "restart persistence and UI removal; no renderer key exposure.",
            flush=True,
        )

        if args.credentials_only:
            close()
            return

        stage = "local-provider-selection"
        provider = window.child_window(
            title="Provider", control_type="ComboBox", visible_only=False
        )
        provider.wait("exists enabled", timeout=20)
        reveal(provider)
        provider.set_focus()
        provider.type_keys("{HOME}{DOWN}{ENTER}")
        stage = "local-model-selection"
        # An input with a datalist is exposed as a ComboBox rather than Edit.
        model = window.child_window(title="Model", control_type="ComboBox", visible_only=False)
        model.wait("exists enabled", timeout=20)
        reveal(model)
        model.set_focus()
        model.type_keys("^a" + args.model, with_spaces=True)
        wait_for(lambda: visible_text("Local backend and selected model are ready."), 30)
        button("Save settings").click_input()
        wait_for(lambda: visible_text("Settings saved"))
        assert (
            json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])["provider"]
            == "ollama"
        )
        # Button's accessible name includes the decorative plus; locate by prefix.
        new = next(
            control
            for control in window.descendants(control_type="Button")
            if control.window_text().startswith("New conversation")
        )
        previous_sessions = {row["id"] for row in rows("SELECT id FROM sessions")}
        new.click_input()
        session_id = wait_for(
            lambda: [
                row for row in rows("SELECT id FROM sessions") if row["id"] not in previous_sessions
            ]
        )[0]["id"]

        def composer() -> Any:
            textarea = window.child_window(title="Message KAT", control_type="Edit")
            textarea.wait("visible enabled", timeout=20)
            return textarea

        def send(text: str, *, needs_approval: bool = False) -> None:
            previous_answers = len(
                rows(
                    "SELECT id FROM messages WHERE session_id=? AND role='assistant'", (session_id,)
                )
            )
            textarea = composer()
            textarea.set_focus()
            textarea.type_keys(text, with_spaces=True)
            button("Send message").click_input()
            # Send stays disabled after success because the draft is empty.
            # Wait for the actual stored reply and re-enabled composer instead.
            wait_for(
                lambda: (
                    len(
                        rows(
                            "SELECT id FROM messages WHERE session_id=? AND role='assistant'",
                            (session_id,),
                        )
                    )
                    > previous_answers
                    and (
                        any(
                            control.window_text() == "Allow once"
                            for control in window.descendants(control_type="Button")
                        )
                        if needs_approval
                        else textarea.is_enabled()
                    )
                ),
                180,
            )

        stage = "real-local-chat"
        send("Hello, KAT.")
        assert rows(
            "SELECT id FROM messages WHERE session_id=? AND role='assistant'", (session_id,)
        )

        def time_results() -> list[dict[str, Any]]:
            return rows(
                "SELECT id,details FROM audit WHERE session_id=? AND event='tool_result' "
                "AND tool_name='get_local_time'",
                (session_id,),
            )

        timestamps = []
        for _ in range(2):
            previous = {event["id"] for event in time_results()}
            send("Tell me the time.")
            fresh = [event for event in time_results() if event["id"] not in previous]
            assert len(fresh) == 1, "Repeated time request did not invoke a fresh tool"
            outcome = json.loads(fresh[0]["details"])
            assert outcome["status"] == "completed"
            timestamps.append(datetime.fromisoformat(outcome["result"]["iso"]))
        assert timestamps[1] > timestamps[0], "Second installed time result was stale"
        print(
            "PASS: installed production UI generates real local conversation "
            "and executes/audits a fresh time tool on each identical request.",
            flush=True,
        )

        approval_ids = set()
        for application_id in ("notepad", "notepad", "calculator"):
            stage = f"{application_id}-selection-and-approval"
            previous_windows = set()
            win32gui.EnumWindows(lambda hwnd, _, seen=previous_windows: seen.add(hwnd), None)
            send(f"Open {application_id.title()}.", needs_approval=True)
            pending = rows(
                "SELECT * FROM approvals WHERE session_id=? AND status='pending' "
                "AND tool_name='open_application'",
                (session_id,),
            )
            if len(pending) != 1:
                print(
                    json.dumps(
                        {
                            "test": "application-selection",
                            "application_id": application_id,
                            "pending_arguments": [
                                json.loads(item["arguments"]) for item in pending
                            ],
                        }
                    ),
                    flush=True,
                )
            assert len(pending) == 1, (
                f"Expected one {application_id} approval; received "
                + json.dumps([json.loads(item["arguments"]) for item in pending])
            )
            assert json.loads(pending[0]["arguments"]) == {"application_id": application_id}
            assert pending[0]["id"] not in approval_ids
            approval_ids.add(pending[0]["id"])
            assert not rows(
                "SELECT id FROM audit WHERE approval_id=? AND event='tool_result'",
                (pending[0]["id"],),
            ), "Application ran before UI approval"
            button("Allow once").click_input()
            stage = f"{application_id}-native-execution"
            wait_for(
                lambda approval=pending[0]["id"]: rows(
                    "SELECT id FROM approvals WHERE id=? AND status='completed'", (approval,)
                )
            )

            def find_application(seen: set = previous_windows, app_id: str = application_id) -> Any:
                found = []
                win32gui.EnumWindows(
                    lambda hwnd, _: (
                        found.append(hwnd)
                        if hwnd not in seen
                        and win32gui.IsWindowVisible(hwnd)
                        and (
                            win32gui.GetClassName(hwnd) == "Notepad"
                            if app_id == "notepad"
                            else win32gui.GetWindowText(hwnd) == "Calculator"
                        )
                        else None
                    ),
                    None,
                )
                return found[0] if found else None

            stage = f"{application_id}-window-creation"
            application_windows.append(wait_for(find_application, 10))
            print(f"PASS: new {application_id} approval and actual application window.", flush=True)

        tools = rows(
            "SELECT content FROM messages WHERE session_id=? AND role='tool'", (session_id,)
        )
        assert len(tools) == 5, "Historical outcomes disappeared from the installed transcript"
        close()
        assert all(win32gui.IsWindow(hwnd) for hwnd in application_windows), (
            "Approved app was killed on KAT close"
        )
        for hwnd in application_windows:
            win32gui.PostMessage(hwnd, 0x0010, 0, 0)
        application_windows.clear()
        print(
            "PASS: both Notepad windows and Calculator survive normal KAT close; "
            "historical outcomes persist.",
            flush=True,
        )

        stage = "installed-relaunch-persistence"
        launch()
        settings = json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])
        assert settings["provider"] == "ollama" and settings["model"] == args.model
        assert rows(
            "SELECT id FROM messages WHERE session_id=? AND content='Hello, KAT.'", (session_id,)
        )
        print(
            "PASS: installed local routing, real conversation and audit "
            "survive close/relaunch with no cloud key.",
            flush=True,
        )

        def fresh_conversation() -> str:
            nonlocal stage
            source_stage = stage
            stage = source_stage + ":review-close"
            # A committed SQLite write precedes the renderer's save acknowledgement.
            # Wait for the review overlay to close before clicking navigation beneath it.
            wait_for(
                lambda: (
                    not any(
                        control.window_text() == "Close memory review"
                        for control in window.descendants(control_type="Button")
                    )
                )
            )
            print("PASS: memory review closed before navigation.", flush=True)
            before = {r["id"] for r in rows("SELECT id FROM sessions")}
            stage = source_stage + ":new-session-control"
            control = next(
                c
                for c in window.descendants(control_type="Button")
                if c.window_text().startswith("New conversation")
            )
            control_rect = control.rectangle()
            window_rect = window.rectangle()
            print(
                json.dumps(
                    {
                        "test": "new-conversation-navigation",
                        "visible": control.is_visible(),
                        "enabled": control.is_enabled(),
                        "button_rectangle": [
                            control_rect.left,
                            control_rect.top,
                            control_rect.right,
                            control_rect.bottom,
                        ],
                        "window_rectangle": [
                            window_rect.left,
                            window_rect.top,
                            window_rect.right,
                            window_rect.bottom,
                        ],
                    }
                ),
                flush=True,
            )
            assert control.is_visible() and control.is_enabled(), (
                "Memory focus/scroll moved or disabled workspace navigation"
            )
            stage = source_stage + ":new-session-click"
            control.click_input()
            stage = source_stage + ":new-session-commit"
            return wait_for(
                lambda: [r for r in rows("SELECT id FROM sessions") if r["id"] not in before]
            )[0]["id"]

        def inspect_memory(text: str) -> None:
            wait_for(
                lambda: (
                    not any(
                        control.window_text() == "Close memory review"
                        for control in window.descendants(control_type="Button")
                    )
                )
            )
            button("Memory").click_input()
            button("Inspect memory: " + text).click_input()

        local_preference = "KAT should prefer local models when practical."
        cloud_preference = "KAT should prefer cloud models when practical."
        question = "Do I prefer local or cloud models for KAT?"
        stage = "memory-explicit-create-and-enable"
        button("Memory").click_input()
        assert (
            json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])["memory_enabled"]
            is False
        )
        checkbox = window.child_window(
            title="Enable local memory retrieval", control_type="CheckBox", visible_only=False
        )
        checkbox.wait("exists enabled", timeout=20)
        reveal(checkbox)
        checkbox.click_input()
        wait_for(
            lambda: json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])[
                "memory_enabled"
            ]
        )
        button("Add memory").click_input()
        wording = window.child_window(title="Memory wording", control_type="Edit")
        wording.wait("visible enabled", timeout=20)
        wording.type_keys(local_preference, with_spaces=True)
        assert not rows("SELECT id FROM memory_items WHERE content=?", (local_preference,))
        button("Confirm & save memory").click_input()
        memory_id = wait_for(
            lambda: rows("SELECT id FROM memory_items WHERE content=?", (local_preference,))
        )[0]["id"]
        stage = "memory-close-and-relaunch"
        close()
        launch()
        assert (
            json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])["memory_enabled"]
            is True
        )
        assert rows("SELECT id FROM memory_items WHERE id=?", (memory_id,))
        session_id = fresh_conversation()
        stage = "memory-real-local-answer-and-inspector"
        send(question)
        used = rows("SELECT * FROM memory_usage WHERE session_id=?", (session_id,))
        assert len(used) == 1 and used[0]["memory_id"] == memory_id and used[0]["revision"] == 1
        answer = rows(
            "SELECT content FROM messages WHERE id=?", (used[0]["assistant_message_id"],)
        )[0]["content"].lower()
        assert "local" in answer and any(
            word in answer for word in ("prefer", "practical", "favor", "priorit")
        ), "Real model did not reflect the local preference"
        summary = wait_for(
            lambda: next(
                (c for c in window.descendants() if c.window_text() == "Memories used · 1"), None
            )
        )
        summary.click_input()
        wait_for(lambda: visible_text(local_preference))
        print(
            "PASS: installed explicit memory survives restart, informs a new local "
            "conversation and appears in the exact-revision inspector.",
            flush=True,
        )

        stage = "memory-owner-edit-current-revision"
        inspect_memory(local_preference)
        wait_for(lambda: visible_text("Entered and confirmed by you in Memory."))
        button("Edit memory").click_input()
        wording = window.child_window(title="Memory wording", control_type="Edit")
        wording.wait("visible enabled", timeout=20)
        wording.type_keys("^a" + cloud_preference, with_spaces=True)
        button("Save revision").click_input()
        wait_for(
            lambda: rows("SELECT id FROM memory_items WHERE id=? AND revision=2", (memory_id,))
        )
        stage = "memory-updated-new-conversation"
        session_id = fresh_conversation()
        send(question)
        used = rows("SELECT * FROM memory_usage WHERE session_id=?", (session_id,))
        assert len(used) == 1 and used[0]["memory_id"] == memory_id and used[0]["revision"] == 2
        answer = rows(
            "SELECT content FROM messages WHERE id=?", (used[0]["assistant_message_id"],)
        )[0]["content"].lower()
        assert "cloud" in answer and any(
            word in answer for word in ("prefer", "practical", "favor", "priorit")
        ), "Real model did not reflect the revised cloud preference"
        assert (
            len(rows("SELECT revision FROM memory_revisions WHERE memory_id=?", (memory_id,))) == 2
        )
        print(
            "PASS: installed owner edit creates a revision; a new real local response "
            "uses only the current revision.",
            flush=True,
        )

        stage = "memory-forget-and-new-conversation"
        inspect_memory(cloud_preference)
        stage = "memory-forget-open-confirmation"
        button("Forget memory").click_input()
        stage = "memory-forget-notice"
        wait_for(
            lambda: visible_text(
                "Forgetting this memory does not automatically delete the original "
                "conversation or older database backups that may contain the original text."
            )
        )
        stage = "memory-forget-explicit-confirmation"
        button("Confirm forget").click_input()
        stage = "memory-forget-commit"
        wait_for(lambda: not rows("SELECT id FROM memory_items WHERE id=?", (memory_id,)))
        assert not rows("SELECT revision FROM memory_revisions WHERE memory_id=?", (memory_id,))
        assert not rows("SELECT rowid FROM memory_fts WHERE memory_fts MATCH 'prefer'")
        session_id = fresh_conversation()
        send(question)
        assert not rows("SELECT * FROM memory_usage WHERE session_id=?", (session_id,))
        assert not visible_text("Memories used · 1")
        stage = "memory-explicit-conversation-selection"
        remember = next(
            control
            for control in window.descendants(control_type="Button")
            if control.window_text() == "Remember"
        )
        with suppress(Exception):
            remember.iface_scroll_item.ScrollIntoView()
        reveal(remember)
        remember.click_input()
        wording = window.child_window(title="Memory wording", control_type="Edit")
        wording.wait("visible enabled", timeout=20)
        selected_wording = "KAT memory source came from an explicitly reviewed conversation."
        wording.type_keys("^a" + selected_wording, with_spaces=True)
        button("Confirm & save memory").click_input()
        selected_memory = wait_for(
            lambda: rows("SELECT * FROM memory_items WHERE content=?", (selected_wording,))
        )[0]
        assert selected_memory["origin"] == "conversation_selection"
        assert selected_memory["source_session_id"] == session_id
        assert selected_memory["source_role"] == "user"
        inspect_memory(selected_wording)
        button("View source conversation").click_input()
        composer()
        print(
            "PASS: installed Remember requires review and retains a navigable "
            "selected-message source.",
            flush=True,
        )
        stage = "memory-name-explicit-create"
        name_memory = "main user is named Luis"
        button("Memory").click_input()
        button("Add memory").click_input()
        wording = window.child_window(title="Memory wording", control_type="Edit")
        wording.wait("visible enabled", timeout=20)
        wording.type_keys(name_memory, with_spaces=True)
        button("Confirm & save memory").click_input()
        name_id = wait_for(
            lambda: rows("SELECT id FROM memory_items WHERE content=?", (name_memory,))
        )[0]["id"]
        stage = "memory-name-close-and-relaunch"
        close()
        launch()
        assert (
            json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])["memory_enabled"]
            is True
        )
        for index, name_question in enumerate(("What is my name?", "What am I named?"), start=1):
            stage = f"memory-name-new-conversation-{index}"
            session_id = fresh_conversation()
            assert not rows("SELECT id FROM messages WHERE session_id=?", (session_id,))
            stage = f"memory-name-real-local-answer-{index}"
            send(name_question)
            used = rows("SELECT * FROM memory_usage WHERE session_id=?", (session_id,))
            assert (
                len(used) == 1 and used[0]["memory_id"] == name_id and used[0]["revision"] == 1
            ), "Name recall did not use exactly the confirmed memory/revision"
            answer = rows(
                "SELECT content FROM messages WHERE id=?", (used[0]["assistant_message_id"],)
            )[0]["content"]
            assert "luis" in answer.lower(), "Real local model did not answer the remembered name"
            summary = wait_for(
                lambda: next(
                    (c for c in window.descendants() if c.window_text() == "Memories used · 1"),
                    None,
                )
            )
            summary.click_input()
            wait_for(lambda: visible_text(name_memory))
            print(
                f"PASS: installed name recall variant {index} uses the confirmed ID/revision "
                "in a brand-new conversation after restart; real Ollama answers Luis "
                "and Memories used shows the wording.",
                flush=True,
            )
        stage = "memory-name-unrelated-new-conversation"
        session_id = fresh_conversation()
        stage = "memory-name-weather-abstention"
        send("What is the weather in Oslo?")
        assert not rows("SELECT * FROM memory_usage WHERE session_id=?", (session_id,))
        assert not visible_text("Memories used · 1")
        print(
            "PASS: unrelated Oslo weather question retrieves no name memory or other record; "
            "usage and response inspector are empty.",
            flush=True,
        )
        stage = "capabilities-weather-owner-configuration"
        button("Settings").click_input()
        place = window.child_window(
            title="Weather location", control_type="Edit", visible_only=False
        )
        place.wait("exists enabled", timeout=20)
        reveal(place)
        place.type_keys("Thornton, Colorado", with_spaces=True)
        button("Find locations").click_input()
        choice = wait_for(
            lambda: next(
                (
                    c
                    for c in window.descendants(control_type="Button")
                    if c.window_text().startswith("Use Thornton, Colorado")
                ),
                None,
            )
        )
        reveal(choice)
        choice.click_input()
        wait_for(lambda: visible_text("Weather location saved"))
        weather_configuration = json.loads(
            rows("SELECT weather FROM capabilities WHERE id=1")[0]["weather"]
        )
        assert weather_configuration["label"].startswith("Thornton, Colorado")
        stage = "capabilities-live-weather-with-local-ai"
        session_id = fresh_conversation()
        for _ in range(2):
            before = {
                r["id"]
                for r in rows(
                    "SELECT id FROM audit WHERE tool_name='get_weather' AND event='tool_result'"
                )
            }
            send("What's the weather?")
            fresh = [
                r
                for r in rows(
                    "SELECT id,details FROM audit WHERE tool_name='get_weather' "
                    "AND event='tool_result'"
                )
                if r["id"] not in before
            ]
            assert len(fresh) == 1, "Weather request did not perform one fresh lookup"
            result = json.loads(fresh[0]["details"])
            assert result["status"] == "completed", "Live weather lookup failed"
            assert (
                result["result"]["provider"] == "open-meteo" and "temperature_c" in result["result"]
            )
            assert result["result"]["observed_at"]
        print(
            "PASS: installed owner-selected location and two fresh external Open-Meteo "
            "lookups through real Ollama, no OpenAI key.",
            flush=True,
        )
        stage = "capabilities-fresh-system-status"
        session_id = fresh_conversation()
        send("How much RAM am I using?")
        status = rows(
            "SELECT details FROM audit WHERE session_id=? AND tool_name='get_system_status' "
            "AND event='tool_result'",
            (session_id,),
        )
        if len(status) != 1:
            print(
                json.dumps(
                    {
                        "test": "installed-fresh-system",
                        "result_count": len(status),
                        "safe_tool_events": [
                            {
                                "event": e["event"],
                                "tool": e["tool_name"],
                                "reason": json.loads(e["details"]).get("reason"),
                            }
                            for e in rows(
                                "SELECT event,tool_name,details FROM audit WHERE session_id=?",
                                (session_id,),
                            )
                            if e["event"].startswith("tool_")
                        ],
                    }
                ),
                flush=True,
            )
        assert len(status) == 1
        system = json.loads(status[0]["details"])
        assert system["status"] == "completed" and system["result"]["ram"]["total_bytes"] > 0
        assert system["result"]["os"] == "Windows" and system["result"]["collected_at"] > 0
        print(
            "PASS: installed real Ollama requests current Windows/RAM metrics "
            "from read-only system APIs.",
            flush=True,
        )

        stage = "capabilities-native-folder-selection"
        fixture_root = Path(os.environ["RUNNER_TEMP"]) / "KAT Read Fixtures"
        fixture_root.mkdir(exist_ok=True)
        fixture_text = "The disposable test project's release color is cobalt blue."
        (fixture_root / "release.txt").write_text(fixture_text, encoding="utf-8")
        button("Settings").click_input()
        label = window.child_window(title="Folder label", control_type="Edit", visible_only=False)
        label.wait("exists enabled", timeout=20)
        reveal(label)
        label.type_keys("Test folder", with_spaces=True)
        button("Choose folder").click_input()
        picker = wait_for(
            lambda: next(
                (
                    w
                    for w in Application(backend="win32").connect(process=process.pid).windows()
                    if w.class_name() == "#32770"
                ),
                None,
            )
        )
        edit = next(c for c in picker.descendants(class_name="Edit") if c.is_visible())
        edit.set_edit_text(str(fixture_root))
        picker.child_window(title="OK", class_name="Button").click()
        wait_for(
            lambda: (
                window.child_window(
                    title="Read-only folder", control_type="Edit", visible_only=False
                ).get_value()
                == str(fixture_root)
            )
        )
        assert not rows("SELECT id FROM read_roots"), (
            "Picker selection registered scope without explicit Add"
        )
        button("Add read-only folder").click_input()
        registered = wait_for(lambda: rows("SELECT * FROM read_roots WHERE label='Test folder'"))[0]
        assert Path(registered["path"]) == fixture_root
        print(
            "PASS: installed native folder selection and explicit owner confirmation "
            "register only a disposable local read root.",
            flush=True,
        )
        stage = "capabilities-local-directory-listing"
        session_id = fresh_conversation()
        send("What files are in my test folder?")
        listing = rows(
            "SELECT content FROM messages WHERE session_id=? AND role='tool'", (session_id,)
        )
        outcomes = [json.loads(r["content"]) for r in listing]
        assert any(
            o["tool_name"] == "list_directory"
            and o["status"] == "completed"
            and any(e["name"] == "release.txt" for e in o["result"]["entries"])
            for o in outcomes
        )
        stage = "capabilities-file-content-approval"
        send("Read release.txt from my test folder.", needs_approval=True)
        approval = wait_for(
            lambda: rows(
                "SELECT * FROM approvals WHERE session_id=? AND tool_name='read_text_file' "
                "AND status='pending'",
                (session_id,),
            )
        )[0]
        assert json.loads(approval["arguments"]) == {
            "root_id": registered["id"],
            "relative_path": "release.txt",
        }
        assert approval["display_context"] == "Read-only folder: Test folder"
        assert not rows(
            "SELECT id FROM messages WHERE session_id=? AND role='tool' "
            "AND content LIKE '%cobalt blue%'",
            (session_id,),
        )
        assert visible_text("Read-only folder: Test folder")
        button("Allow once").click_input()
        completed = wait_for(
            lambda: rows(
                "SELECT * FROM approvals WHERE id=? AND status='completed'", (approval["id"],)
            )
        )[0]
        assert json.loads(completed["result"])["content"] == fixture_text
        wait_for(lambda: visible_text(fixture_text))
        assert not rows("SELECT id FROM audit WHERE details LIKE '%cobalt blue%'")
        print(
            "PASS: installed file-content approval precedes the read; exact text returns "
            "in the production UI/transcript and never in audit.",
            flush=True,
        )
        stage = "capabilities-traversal-rejection"
        # A model traversal proposal exercises the actual installed dispatcher.
        # No webview debugging or token extraction is used.
        session_id = fresh_conversation()
        send(
            "Use read_text_file with root_id "
            + registered["id"]
            + " and relative_path ../outside.txt exactly."
        )
        rejected = rows(
            "SELECT details FROM audit WHERE session_id=? AND tool_name='read_text_file' "
            "AND event='tool_rejected'",
            (session_id,),
        )
        assert rejected and any(
            json.loads(r["details"])["reason"] == "path_outside_root" for r in rejected
        ), "Model did not exercise trusted traversal rejection"
        assert not rows(
            "SELECT id FROM approvals WHERE session_id=? AND tool_name='read_text_file'",
            (session_id,),
        )
        print(
            "PASS: installed traversal proposal is rejected by trusted validation "
            "before approval or content access.",
            flush=True,
        )
        stage = "capabilities-relaunch-persistence"
        close()
        launch()
        button("Settings").click_input()
        assert (
            json.loads(rows("SELECT weather FROM capabilities WHERE id=1")[0]["weather"])
            == weather_configuration
        )
        assert rows("SELECT id FROM read_roots WHERE id=?", (registered["id"],))
        button("Remove Test folder").click_input()
        wait_for(lambda: not rows("SELECT id FROM read_roots WHERE id=?", (registered["id"],)))
        print(
            "PASS: installed weather/read-root configuration survives relaunch; "
            "local provider and prior memory/tool checks remain passing.",
            flush=True,
        )
        close()
        print(
            "PASS: installed Forget removes wording/revisions/FTS; a new local conversation "
            "records zero memory usage. Original transcripts remain separate.",
            flush=True,
        )
    except Exception as error:
        print(f"FAIL: installed UI stage={stage} exception_type={type(error).__name__}", flush=True)
        # Keep diagnostics actionable without printing exception messages, code
        # lines, local variables, transcript contents or credential dialog text.
        print(
            json.dumps(
                {
                    "test": "installed-ui-failure-stack",
                    "frames": [
                        {
                            "file": Path(frame.filename).name,
                            "function": frame.name,
                            "line": frame.lineno,
                        }
                        for frame in traceback.extract_tb(error.__traceback__)
                    ],
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
    finally:
        for hwnd in application_windows:
            with suppress(Exception):
                win32gui.PostMessage(hwnd, 0x0010, 0, 0)
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=15)
        with suppress(Exception):
            win32cred.CredDelete(TARGET, win32cred.CRED_TYPE_GENERIC)


if __name__ == "__main__":
    main()
