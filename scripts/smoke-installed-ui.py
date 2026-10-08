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
from contextlib import suppress
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
    parser.add_argument("--model", default="qwen3:1.7b")
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
    notepad_window = None
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

        def send(text: str) -> None:
            textarea = window.descendants(control_type="Edit")[0]
            textarea.set_focus()
            textarea.type_keys(text, with_spaces=True)
            button("Send message").click_input()
            wait_for(
                lambda: window.child_window(
                    title="Send message", control_type="Button"
                ).is_enabled(),
                180,
            )

        stage = "real-local-chat"
        send("Hello, KAT.")
        assert rows(
            "SELECT id FROM messages WHERE session_id=? AND role='assistant'", (session_id,)
        )
        send("What time is it?")
        events = rows(
            "SELECT details FROM audit WHERE session_id=? AND event='tool_result' "
            "AND tool_name='get_local_time'",
            (session_id,),
        )
        assert any(json.loads(event["details"])["status"] == "completed" for event in events)
        print(
            "PASS: installed production UI generates real local conversation "
            "and executes/audits the time tool.",
            flush=True,
        )

        stage = "notepad-approval"
        previous_windows = set()
        win32gui.EnumWindows(lambda hwnd, _: previous_windows.add(hwnd), None)
        textarea = window.descendants(control_type="Edit")[0]
        textarea.set_focus()
        textarea.type_keys("Open Notepad.", with_spaces=True)
        button("Send message").click_input()
        wait_for(
            lambda: window.child_window(title="Allow once", control_type="Button").exists(), 180
        )
        pending = rows(
            "SELECT * FROM approvals WHERE session_id=? AND status='pending' "
            "AND tool_name='open_application'",
            (session_id,),
        )
        assert len(pending) == 1 and json.loads(pending[0]["arguments"]) == {
            "application_id": "notepad"
        }
        button("Allow once").click_input()
        wait_for(
            lambda: rows(
                "SELECT id FROM approvals WHERE id=? AND status='completed'", (pending[0]["id"],)
            )
        )

        def find_notepad() -> Any:
            found = []
            win32gui.EnumWindows(
                lambda hwnd, _: (
                    found.append(hwnd)
                    if hwnd not in previous_windows
                    and win32gui.IsWindowVisible(hwnd)
                    and win32gui.GetClassName(hwnd) == "Notepad"
                    else None
                ),
                None,
            )
            return found[0] if found else None

        notepad_window = wait_for(find_notepad, 10)
        close()
        assert win32gui.IsWindow(notepad_window), "Approved Notepad was killed on KAT close"
        win32gui.PostMessage(notepad_window, 0x0010, 0, 0)
        notepad_window = None
        print(
            "PASS: actual Notepad window opens after UI approval and survives normal KAT close.",
            flush=True,
        )

        stage = "installed-relaunch-persistence"
        launch()
        settings = json.loads(rows("SELECT value FROM settings WHERE id=1")[0]["value"])
        assert settings["provider"] == "ollama" and settings["model"] == args.model
        assert rows(
            "SELECT id FROM messages WHERE session_id=? AND content='Hello, KAT.'", (session_id,)
        )
        close()
        print(
            "PASS: installed local routing, real conversation and audit "
            "survive close/relaunch with no cloud key.",
            flush=True,
        )
    except Exception as error:
        print(f"FAIL: installed UI stage={stage} exception_type={type(error).__name__}", flush=True)
        raise SystemExit(1) from None
    finally:
        if notepad_window:
            with suppress(Exception):
                win32gui.PostMessage(notepad_window, 0x0010, 0, 0)
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=15)
        with suppress(Exception):
            win32cred.CredDelete(TARGET, win32cred.CRED_TYPE_GENERIC)


if __name__ == "__main__":
    main()
