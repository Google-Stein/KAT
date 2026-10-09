"""Pin local Windows path components; never read through reparse points.

Directory handles deny write/delete-sharing until the operation completes,
preventing replacement, rename or in-place reparse changes during enumeration. Final
handle paths and volume types are verified before enumeration or reading.
"""

import ctypes
import ntpath
import os
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Any

from kat_core.capability_schemas import CapabilityFailure


@contextmanager
def open_windows_path(path: Path, *, directory: bool) -> Iterator[Any]:
    api: Any = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    api.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    api.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    api.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    api.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    api.GetFileType.argtypes = [wintypes.HANDLE]
    handles = []
    original = ntpath.normcase(str(path))
    drive, _ = ntpath.splitdrive(original)
    if api.GetDriveTypeW(drive + "\\") != 3:
        raise CapabilityFailure(
            "path_outside_root", "Only local fixed-drive folders are supported."
        )
    try:
        parts = path.parts
        for index in range(len(parts)):
            component = Path(*parts[: index + 1])
            is_directory = index < len(parts) - 1 or directory
            # OPEN_REPARSE_POINT + BACKUP_SEMANTICS, read sharing only. Write
            # sharing would allow an in-place reparse update before os.scandir.
            handle = api.CreateFileW(
                str(component),
                # LIST_DIRECTORY participates in Windows sharing locks;
                # READ_ATTRIBUTES alone does not enforce write/delete exclusion.
                0x81 if is_directory else 0x80000000,
                1,
                None,
                3,
                0x02200000,
                None,
            )
            if handle == ctypes.c_void_p(-1).value:
                code = ctypes.get_last_error()  # type: ignore[attr-defined]
                raise CapabilityFailure(
                    "file_not_found" if code in (2, 3) else "filesystem_access_failed",
                    "File or folder was not found."
                    if code in (2, 3)
                    else "The local filesystem could not be accessed.",
                )
            handles.append(handle)
            tag = (wintypes.DWORD * 2)()
            if not api.GetFileInformationByHandleEx(
                handle, 9, ctypes.byref(tag), ctypes.sizeof(tag)
            ):
                raise CapabilityFailure(
                    "filesystem_access_failed", "File attributes could not be verified."
                )
            if (
                tag[0] & 0x400
                or bool(tag[0] & 0x10) != is_directory
                or api.GetFileType(handle) != 1
            ):
                raise CapabilityFailure(
                    "path_outside_root",
                    "Symlinks, reparse points and special files are not allowed.",
                )
            buffer = ctypes.create_unicode_buffer(32768)
            size = api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
            if not size or size >= len(buffer):
                raise CapabilityFailure(
                    "filesystem_access_failed", "The file location could not be verified."
                )
            final = ntpath.normcase(buffer.value.removeprefix("\\\\?\\"))
            if final.rstrip("\\") != ntpath.normcase(str(component)).rstrip("\\"):
                raise CapabilityFailure(
                    "path_outside_root", "The file resolved outside its approved location."
                )
        if directory:
            yield path
        else:
            import msvcrt

            fd = msvcrt.open_osfhandle(handles[-1], os.O_RDONLY | os.O_BINARY)  # type: ignore[attr-defined]
            handles.pop()
            with os.fdopen(fd, "rb") as stream:
                yield stream
    finally:
        for handle in reversed(handles):
            api.CloseHandle(handle)
