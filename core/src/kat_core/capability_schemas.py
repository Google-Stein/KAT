"""Owner configuration and bounded external/local data contracts."""

from typing import Literal

from pydantic import Field, field_validator

from kat_core.schemas import StrictModel


class CapabilityFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class Location(StrictModel):
    label: str = Field(min_length=1, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=80)


class LocationQuery(StrictModel):
    query: str = Field(min_length=2, max_length=100)

    @field_validator("query")
    @classmethod
    def safe_query(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("Location must contain no controls")
        return value.strip()


class WeatherConfiguration(StrictModel):
    location: Location | None


class ReadRoot(StrictModel):
    id: str
    label: str
    path: str


class RootCreate(StrictModel):
    label: str = Field(min_length=1, max_length=80)
    path: str = Field(min_length=1, max_length=240)

    @field_validator("label")
    @classmethod
    def safe_label(cls, value: str) -> str:
        if value != value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Folder label must have no controls or surrounding spaces")
        return value


class Capabilities(StrictModel):
    weather_provider: Literal["open-meteo"] = "open-meteo"
    weather_location: Location | None
    system_available: bool = True
    read_roots: list[ReadRoot]
