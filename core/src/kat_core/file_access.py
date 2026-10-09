"""Anchored local read-only file access with explicit bounded traversal."""

import os
import re
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Any

from kat_core.capability_schemas import CapabilityFailure

MAX_BYTES = 65536
MAX_CHARACTERS = 12000
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".xml",
    ".log",
    ".py",
    ".rs",
    ".ts",
    ".tsx",
    ".css",
    ".html",
    ".ini",
}
DEVICES = re.compile(r"^(CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])(?:\.|$)", re.I)


def relative_parts(value: str) -> tuple[str, ...]:
    if (
        not value
        or len(value) > 240
        or value.startswith(("/", "\\"))
        or PureWindowsPath(value).drive
    ):
        raise CapabilityFailure(
            "path_outside_root", "Use a relative path inside the registered folder."
        )
    if value == ".":
        return ()
    parts = tuple(value.replace("\\", "/").split("/"))
    if any(
        p in ("", ".", "..")
        or p.endswith((".", " "))
        or DEVICES.match(p)
        or any(ord(c) < 32 or c in ':*?"<>|' for c in p)
        for p in parts
    ):
        raise CapabilityFailure(
            "path_outside_root", "This path is outside the allowed file-access syntax."
        )
    return parts


@contextmanager
def opened(path: Path, *, directory: bool) -> Iterator[Any]:
    if os.name == "nt":
        from kat_core.windows_files import open_windows_path

        with open_windows_path(path, directory=directory) as handle:
            yield handle
        return
    descriptors: list[int] = []
    try:
        for index, part in enumerate(path.parts):
            is_directory = index < len(path.parts) - 1 or directory
            flags = (
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | (os.O_DIRECTORY if is_directory else 0)
            )
            fd = os.open(part, flags, dir_fd=descriptors[-1] if descriptors else None)
            descriptors.append(fd)
            if not (
                stat.S_ISDIR(os.fstat(fd).st_mode)
                if is_directory
                else stat.S_ISREG(os.fstat(fd).st_mode)
            ):
                raise CapabilityFailure(
                    "path_outside_root", "Special files and links are not supported."
                )
        if directory:
            yield descriptors[-1]
        else:
            with os.fdopen(descriptors.pop(), "rb") as stream:
                yield stream
    except OSError as error:
        raise CapabilityFailure(
            "file_not_found" if error.errno == 2 else "filesystem_access_failed",
            "File or folder was not found."
            if error.errno == 2
            else "The filesystem is unavailable or this path contains a link.",
        ) from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def validate_root(value: str) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or value.startswith(("\\\\", "//"))
        or (os.name == "nt" and (not re.match(r"^[A-Za-z]:[\\/]", value) or len(path.parts) < 2))
    ):
        raise CapabilityFailure(
            "path_outside_root", "Choose a local folder, not a network, device or drive root."
        )
    # Do not resolve through a symlink, junction or an alias before validating.
    tail = str(path)[len(path.anchor) :]
    relative_parts(tail)
    with opened(path, directory=True):
        return path


def safe_target(root: Path, relative: str) -> Path:
    parts = relative_parts(relative)
    return root.joinpath(*parts)


def read_text(root: Path, relative: str) -> dict[str, Any]:
    path = safe_target(root, relative)
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise CapabilityFailure("unsupported_file", "Only supported UTF-8 text files may be read.")
    with opened(path, directory=False) as stream:
        if os.fstat(stream.fileno()).st_size > MAX_BYTES:
            raise CapabilityFailure("file_too_large", "Text files must be at most 64 KiB.")
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise CapabilityFailure("file_too_large", "Text files must be at most 64 KiB.")
    try:
        text = raw.decode("utf-8-sig")
        if "\x00" in text or any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValueError
    except (UnicodeError, ValueError):
        raise CapabilityFailure(
            "unsupported_file", "The file is binary or is not supported UTF-8 text."
        ) from None
    content = text[:MAX_CHARACTERS]
    return {
        "relative_path": relative,
        "content": content,
        "bytes_returned": len(content.encode("utf-8")),
        "file_bytes": len(raw),
        "truncated": len(text) > MAX_CHARACTERS,
    }


def validate_text_target(root: Path, relative: str) -> None:
    """Check only metadata before approval; never open/read the file body."""
    path = safe_target(root, relative)
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise CapabilityFailure("unsupported_file", "Choose a supported UTF-8 text filename.")
    try:
        with opened(path.parent, directory=True) as parent:
            info = (
                os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                if isinstance(parent, int)
                else os.stat(parent / path.name, follow_symlinks=False)
            )
    except OSError as error:
        raise CapabilityFailure(
            "file_not_found" if error.errno == 2 else "filesystem_access_failed",
            "File or folder was not found."
            if error.errno == 2
            else "The local filesystem could not be accessed.",
        ) from None
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise CapabilityFailure(
            "path_outside_root", "Only ordinary files inside the root are allowed."
        )
    if info.st_size > MAX_BYTES:
        raise CapabilityFailure("file_too_large", "Text files must be at most 64 KiB.")


def directory_entries(root: Path, relative: str) -> dict[str, Any]:
    path = safe_target(root, relative)
    entries: list[dict[str, Any]] = []
    inspected = 0
    with opened(path, directory=True) as handle, os.scandir(handle) as iterator:
        for entry in iterator:
            inspected += 1
            if inspected > 1000 or len(entries) >= 100:
                break
            attributes = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or getattr(attributes, "st_file_attributes", 0) & 0x400:
                continue
            entries.append(
                {"name": entry.name[:240], "directory": stat.S_ISDIR(attributes.st_mode)}
            )
    return {"relative_path": relative, "entries": entries, "truncated": inspected > len(entries)}


def search_names(root: Path, query: str) -> dict[str, Any]:
    pending = [(".", 0)]
    matches: list[dict[str, Any]] = []
    inspected = 0
    deadline = time.monotonic() + 2
    while pending and inspected < 1000 and len(matches) < 50 and time.monotonic() < deadline:
        relative, depth = pending.pop()
        try:
            with (
                opened(safe_target(root, relative), directory=True) as handle,
                os.scandir(handle) as iterator,
            ):
                for entry in iterator:
                    inspected += 1
                    if inspected > 1000 or len(matches) >= 50 or time.monotonic() >= deadline:
                        break
                    info = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                        continue
                    child = entry.name if relative == "." else relative + "/" + entry.name
                    relative_parts(child)
                    directory = stat.S_ISDIR(info.st_mode)
                    if query.casefold() in entry.name.casefold():
                        matches.append({"relative_path": child, "directory": directory})
                    if directory and depth < 4:
                        pending.append((child, depth + 1))
        except CapabilityFailure:
            if relative == ".":
                raise
    return {
        "matches": matches,
        "inspected": min(inspected, 1000),
        "truncated": bool(pending)
        or inspected >= 1000
        or len(matches) >= 50
        or time.monotonic() >= deadline,
    }
