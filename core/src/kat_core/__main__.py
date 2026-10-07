"""CLI used by desktop supervision and local development."""

import argparse
import logging
import logging.handlers
import os
import secrets
import stat
import time
from pathlib import Path
from typing import IO

import uvicorn
from dotenv import load_dotenv

from kat_core.app import create_app
from kat_core.config import CoreConfig, default_data_dir


def token_from_file(path: Path) -> str:
    """Create a private token once, then reuse it without printing its contents."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("Token file must not be a symbolic link")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if not path.is_file():
            raise ValueError("Token path must be a regular file") from None
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError("Token file must be private (chmod 600)") from None
        return path.read_text(encoding="utf-8").strip()
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        token = secrets.token_urlsafe(32)
        output.write(token + "\n")
        return token


def acquire_data_lock(data_dir: Path) -> IO[bytes]:
    """Ensure one owner for a database; a released OS lock survives crashes safely."""
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_file = (data_dir / "core.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        raise ValueError("Another KAT Core process owns this data directory") from None
    return lock_file


def configure_logging(data_dir: Path) -> None:
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    formatter.converter = time.gmtime
    file_handler = logging.handlers.RotatingFileHandler(
        logs / "core.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    stream_handler = logging.StreamHandler()
    for handler in (file_handler, stream_handler):
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)
    # HTTP libraries may emit request URLs; keep routine provider network metadata out of logs.
    for name in ("openai", "httpx", "httpcore", "openai.agents"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run authenticated local KAT Core")
    parser.add_argument("--port", type=int, help="Loopback port (default KAT_PORT or 42800)")
    parser.add_argument("--data-dir", type=Path, help="Local data directory (or KAT_DATA_DIR)")
    parser.add_argument("--token-file", type=Path, help="Read/create a private bearer token file")
    parser.add_argument(
        "--env-file", type=Path, help="Explicit local dotenv file; never overrides env"
    )
    args = parser.parse_args()
    if os.name != "nt":
        os.umask(0o077)
    if args.env_file:
        if not args.env_file.is_file():
            parser.error("The requested --env-file does not exist")
        load_dotenv(args.env_file, override=False)
    data_dir = args.data_dir or Path(os.environ.get("KAT_DATA_DIR", str(default_data_dir())))
    data_dir = data_dir.expanduser().resolve()
    try:
        port = args.port if args.port is not None else int(os.environ.get("KAT_PORT", "42800"))
        if not 1024 <= port <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        if os.environ.get("KAT_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
            raise ValueError("KAT Core can only bind to loopback")
        token = os.environ.get("KAT_API_TOKEN") or token_from_file(
            args.token_file or data_dir / "api-token"
        )
        config = CoreConfig.from_environment(token=token, data_dir=data_dir)
        data_lock = acquire_data_lock(data_dir)
        configure_logging(data_dir)
        app = create_app(config)
    except (ValueError, OSError):
        # Configuration validation can include original secret-bearing input. Never echo it.
        parser.error(
            "Invalid or unavailable Core configuration. "
            "Check token, data path, port, and allowlist."
        )
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, access_log=False, log_config=None)
    finally:
        data_lock.close()


if __name__ == "__main__":
    main()
