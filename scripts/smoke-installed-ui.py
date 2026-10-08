"""Disposable Windows CI only: drive the installed WebView with real local inference.

CDP is enabled only in this explicitly invoked test process and closed afterwards.
Never run this credential fixture in a normal owner's Windows account.
"""

import argparse
import ctypes
import os
import subprocess
import time
from contextlib import suppress
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

TARGET = "KAT/OpenAI"
FIXTURE = "sk-proj-ci_synthetic_not_a_real_api_key_1234"


def api(page: Page, path: str, method: str = "GET", body: object = None) -> object:
    # The existing trusted native command returns only the local Core connection.
    # Keep its bearer in the page's execution scope, never in log output.
    return page.evaluate(
        """async ({path,method,body}) => {
      const connection = await window.__TAURI_INTERNALS__.invoke('core_connection');
      const result = await fetch(connection.base_url + path, {
        method, headers: {
          Authorization: 'Bearer ' + connection.token, 'Content-Type':'application/json'
        },
        body: body == null ? undefined : JSON.stringify(body)
      });
      if (!result.ok) throw new Error('Core HTTP ' + result.status);
      return result.json();
    }""",
        {"path": path, "method": method, "body": body},
    )


def close_normally(process: subprocess.Popen[bytes]) -> None:
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def close(window: int, _: int) -> bool:
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(window), ctypes.byref(pid))
        if pid.value == process.pid and user32.IsWindowVisible(ctypes.c_void_p(window)):
            user32.PostMessageW(ctypes.c_void_p(window), 0x0010, 0, 0)  # WM_CLOSE
        return True

    user32.EnumWindows(close, 0)
    assert process.wait(timeout=15) == 0


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit(
            "This synthetic credential and CDP test requires a disposable Windows CI account."
        )
    import win32cred

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:1.7b")
    args = parser.parse_args()
    try:
        win32cred.CredRead(TARGET, win32cred.CRED_TYPE_GENERIC)
    except Exception as error:
        if getattr(error, "winerror", None) != 1168:
            raise SystemExit("Cannot establish empty disposable credential vault.") from None
    else:
        raise SystemExit("Refusing to replace an existing KAT credential.")

    environment = os.environ.copy()
    for name in ("OPENAI_API_KEY", "KAT_OPENAI_API_KEY"):
        environment.pop(name, None)
    environment["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        "--remote-debugging-port=9527 --remote-debugging-address=127.0.0.1"
    )
    process = None
    stage = "installed-startup"
    try:
        with sync_playwright() as playwright:

            def launch() -> Page:
                nonlocal process
                process = subprocess.Popen([str(args.executable)], env=environment)
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    assert process.poll() is None, "Installed desktop exited"
                    try:
                        browser = playwright.chromium.connect_over_cdp(
                            "http://127.0.0.1:9527", timeout=1500
                        )
                        pages = [page for context in browser.contexts for page in context.pages]
                        if pages:
                            page = pages[0]
                            page.set_default_timeout(20000)
                            expect(
                                page.get_by_role("button", name="Settings", exact=True)
                            ).to_be_visible()
                            return page
                    except Exception:
                        time.sleep(0.3)
                raise RuntimeError("Installed WebView debugging session unavailable")

            page = launch()
            stage = "native-credential-dialog"
            page.get_by_role("button", name="Settings", exact=True).click()
            page.get_by_role("button", name="Set API key", exact=True).click()
            user32 = ctypes.windll.user32
            user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
            user32.FindWindowW.restype = ctypes.c_void_p
            deadline = time.monotonic() + 10
            dialog = None
            while time.monotonic() < deadline and not dialog:
                dialog = user32.FindWindowW(None, "KAT — OpenAI API key")
                time.sleep(0.1)
            assert dialog, "Native masked credential dialog did not appear"
            user32.PostMessageW(ctypes.c_void_p(dialog), 0x0010, 0, 0)
            expect(page.get_by_text("API key setup cancelled.", exact=True)).to_be_visible()
            assert process is not None
            close_normally(process)
            process = None
            print(
                "PASS: installed Settings invokes native credential dialog; cancel "
                "preserves no-key state."
            )

            stage = "vault-injection-and-removal"
            win32cred.CredWrite(
                {
                    "Type": win32cred.CRED_TYPE_GENERIC,
                    "TargetName": TARGET,
                    "CredentialBlob": FIXTURE.encode(),
                    "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                    "UserName": "OpenAI",
                }
            )
            page = launch()
            page.get_by_role("button", name="Settings", exact=True).click()
            expect(page.get_by_text("API key configured", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Replace saved key", exact=True)).to_be_visible()
            assert FIXTURE not in page.content()
            page.get_by_role("button", name="Remove saved key", exact=True).click()
            expect(
                page.get_by_text("Saved key removed. Local Core restarted.", exact=True)
            ).to_be_visible()
            expect(page.get_by_text("API key required", exact=True)).to_be_visible()
            print(
                "PASS: actual Windows vault key loads into installed Core; UI removal "
                "restarts Core without revealing it."
            )

            stage = "local-provider-selection"
            page.get_by_label("Provider", exact=True).select_option("ollama")
            page.get_by_label("Model", exact=True).fill(args.model)
            expect(
                page.get_by_text("Local backend and selected model are ready.", exact=True)
            ).to_be_visible(timeout=30000)
            page.get_by_role("button", name="Save settings", exact=True).click()
            expect(page.get_by_text("Settings saved", exact=True)).to_be_visible()
            page.get_by_role("button", name="New conversation", exact=False).click()

            def send(text: str) -> None:
                page.get_by_placeholder("Message KAT…").fill(text)
                page.get_by_role("button", name="Send message", exact=True).click()
                expect(page.get_by_role("button", name="Send message", exact=True)).to_be_enabled(
                    timeout=180000
                )
                assert page.get_by_role("alert").count() == 0, (
                    "Installed UI reported a model failure"
                )

            stage = "real-local-chat"
            send("Hello, KAT.")
            assert page.get_by_label("assistant message", exact=True).count() >= 1
            send("What time is it?")
            events = api(page, "/audit")
            assert any(
                event["event"] == "tool_result"
                and event["tool_name"] == "get_local_time"
                and event["details"]["status"] == "completed"
                for event in events
            )
            print(
                "PASS: installed desktop generates real local chat and executes/audits "
                "the time tool."
            )

            stage = "notepad-approval"
            # Send becomes disabled while an approval is pending; wait for the card instead.
            page.get_by_placeholder("Message KAT…").fill("Open Notepad.")
            page.get_by_role("button", name="Send message", exact=True).click()
            expect(page.get_by_role("button", name="Allow once", exact=True)).to_be_enabled(
                timeout=180000
            )
            pending = api(page, "/approvals")
            request = next(
                item
                for item in pending
                if item["status"] == "pending" and item["tool_name"] == "open_application"
            )
            assert request["arguments"] == {"application_id": "notepad"}
            page.get_by_role("button", name="Allow once", exact=True).click()
            expect(page.get_by_role("button", name="Allow once", exact=True)).not_to_be_visible(
                timeout=20000
            )
            outcome = next(item for item in api(page, "/approvals") if item["id"] == request["id"])
            assert outcome["status"] == "completed"
            print(
                "PASS: installed local model requests Notepad; owner UI approval runs "
                "the audited native tool."
            )

            stage = "installed-relaunch-persistence"
            session_id = request["session_id"]
            assert process is not None
            close_normally(process)
            process = None
            page = launch()
            settings = api(page, "/settings")
            assert settings["provider"] == "ollama" and settings["model"] == args.model
            messages = api(page, f"/sessions/{session_id}/messages")
            assert any(item["role"] == "assistant" for item in messages)
            assert any(item["content"] == "Hello, KAT." for item in messages)
            assert process is not None
            close_normally(process)
            process = None
            print(
                "PASS: installed local routing and real conversation survive normal "
                "close/relaunch; no cloud key exists."
            )
    except Exception as error:
        # Avoid CDP tracebacks/request dumps, which can expose memory-only connection tokens.
        print(f"FAIL: installed UI stage={stage} exception_type={type(error).__name__}")
        raise SystemExit(1) from None
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=15)
        with suppress(Exception):
            win32cred.CredDelete(TARGET, win32cred.CRED_TYPE_GENERIC)


if __name__ == "__main__":
    main()
