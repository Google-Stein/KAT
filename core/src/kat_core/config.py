"""Runtime configuration. Credentials are injected, never persisted in SQLite."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CoreConfig:
    data_dir: Path
    api_token: str = field(repr=False)
    openai_api_key: str | None = field(default=None, repr=False)
    default_model: str = "gpt-4.1-mini"

    def __post_init__(self) -> None:
        if (
            len(self.api_token) < 32
            or not self.api_token.isascii()
            or any(char.isspace() for char in self.api_token)
        ):
            raise ValueError("KAT_API_TOKEN must contain at least 32 non-whitespace characters")

    @classmethod
    def from_environment(cls, *, token: str, data_dir: Path) -> "CoreConfig":
        return cls(
            data_dir=data_dir,
            api_token=token,
            openai_api_key=os.environ.get("KAT_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or None,
            default_model=os.environ.get("KAT_MODEL", "gpt-4.1-mini"),
        )


def default_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "KAT"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "kat"
