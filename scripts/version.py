"""Sync generated release metadata from VERSION, or fail CI on drift."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def metadata(version: str) -> dict[Path, str]:
    result: dict[Path, str] = {}
    for name in (
        "desktop/package.json",
        "desktop/package-lock.json",
        "desktop/src-tauri/tauri.conf.json",
    ):
        path = ROOT / name
        value = json.loads(path.read_text())
        value["version"] = version
        if "packages" in value:
            value["packages"][""]["version"] = version
        result[path] = json.dumps(value, indent=2) + "\n"
    for name, pattern in (
        ("core/pyproject.toml", r'(?m)^version = "[^"]+"'),
        ("desktop/src-tauri/Cargo.toml", r'(?m)^version = "[^"]+"'),
        ("core/uv.lock", r'(name = "kat-core"\n)version = "[^"]+"'),
        ("desktop/src-tauri/Cargo.lock", r'(name = "kat-desktop"\n)version = "[^"]+"'),
        ("core/src/kat_core/__init__.py", r'(?m)^__version__ = "[^"]+"'),
    ):
        path = ROOT / name
        result[path] = re.sub(
            pattern,
            lambda m, name=name: (
                (m[1] if m.lastindex else "")
                + ("__version__" if "__init__" in name else "version")
                + f' = "{version}"'
            ),
            path.read_text(),
            count=1,
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("VERSION must contain a stable semantic version")
    drift = []
    for path, expected in metadata(version).items():
        # JSON formatting belongs to Prettier; compare content rather than whitespace.
        current = path.read_text()
        same = (
            json.loads(current) == json.loads(expected)
            if path.suffix == ".json"
            else current == expected
        )
        if not same:
            drift.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(expected)
    if args.check and drift:
        raise SystemExit("Version drift: " + ", ".join(drift))
    print(f"KAT {version}: metadata {'checked' if args.check else 'synchronized'}")


if __name__ == "__main__":
    main()
