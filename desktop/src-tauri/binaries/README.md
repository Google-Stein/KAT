This directory is a Tauri resource directory. `scripts/build-windows.ps1` creates
`kat-core/kat-core.exe` and its adjacent runtime files here with PyInstaller
(`--onedir`) before building the desktop installer. Preserve the entire directory.

Generated executables are ignored by Git. Release startup requires the matching
packaged core; development startup uses `core/.venv` from the existing checkout.

The directory bundle keeps the server in the native launcher's direct child.
A one-file bootloader would spawn another process and complicate lifetime ownership.
