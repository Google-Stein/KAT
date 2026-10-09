"""Read-only fresh metrics; no process command lines, environment or shell."""

import ctypes
import os
import platform
import time
from typing import Any

import psutil


def gpu_information() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    # EnumDisplayDevices returns display adapter names through a fixed Win32 API.
    from ctypes import wintypes

    class DisplayDevice(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("name", wintypes.WCHAR * 32),
            ("description", wintypes.WCHAR * 128),
            ("flags", wintypes.DWORD),
            ("id", wintypes.WCHAR * 128),
            ("key", wintypes.WCHAR * 128),
        ]

    api: Any = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
    api.EnumDisplayDevicesW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(DisplayDevice),
        wintypes.DWORD,
    ]
    entries = []
    for index in range(8):
        device = DisplayDevice()
        device.cb = ctypes.sizeof(device)
        if not api.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        entries.append({"name": device.description, "vram_bytes": None})
    return entries


def system_status() -> dict[str, Any]:
    unavailable = []
    result: dict[str, Any] = {
        "collected_at": time.time(),
        "os": platform.system(),
        "os_version": platform.version()[:120],
        "cpu_architecture": platform.machine()[:80],
        "cpu_model": None,
        "logical_cpus": psutil.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False),
    }
    try:
        result["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        result["ram"] = {
            "total_bytes": ram.total,
            "used_bytes": ram.total - ram.available,
            "available_bytes": ram.available,
            "percent": ram.percent,
        }
        result["uptime_seconds"] = max(0, int(time.time() - psutil.boot_time()))
    except (OSError, psutil.Error):
        unavailable.append("utilization")
    disks: list[dict[str, Any]] = []
    for partition in psutil.disk_partitions(all=False)[:16]:
        if len(disks) >= 8:
            break
        if os.name == "nt" and (
            partition.mountpoint.startswith("\\\\") or "fixed" not in partition.opts
        ):
            continue
        if os.name != "nt" and (
            partition.fstype.lower() in {"nfs", "nfs4", "cifs", "smbfs", "sshfs", "fuse.sshfs"}
            or not partition.device.startswith("/dev/")
        ):
            continue
        try:
            disk = psutil.disk_usage(partition.mountpoint)
            disks.append(
                {
                    "volume": partition.mountpoint,
                    "total_bytes": disk.total,
                    "used_bytes": disk.used,
                    "free_bytes": disk.free,
                    "percent": disk.percent,
                }
            )
        except (OSError, psutil.Error):
            unavailable.append("disk")
    result["disks"] = disks
    try:
        result["gpus"] = gpu_information()
        if not result["gpus"]:
            unavailable.append("gpu")
    except (OSError, AttributeError):
        result["gpus"] = []
        unavailable.append("gpu")
    result["unavailable_metrics"] = unavailable
    return result
