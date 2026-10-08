"""Disposable CI diagnostic of the normal installed application's accessibility UI."""

import argparse
import os
import subprocess


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("Disposable Windows CI only")
    from pywinauto import Application

    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    process = subprocess.Popen([args.executable])
    try:
        app = Application(backend="uia").connect(process=process.pid, timeout=30)
        window = app.window(title="KAT")
        window.wait("visible", timeout=45)
        settings = window.child_window(title="Settings", control_type="Button")
        settings.wait("visible enabled", timeout=20)
        settings.click_input()
        key = window.child_window(title="Set API key", control_type="Button")
        key.wait("visible enabled", timeout=20)
        print(
            "PASS: production Settings/key controls work through Windows accessibility."
        )
        window.close()
        assert process.wait(timeout=15) == 0
    except Exception as error:
        print("FAIL accessibility diagnostic:", type(error).__name__)
        raise SystemExit(1) from None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
