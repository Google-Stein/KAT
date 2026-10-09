"""Fixed-destination credential-free Open-Meteo adapter, independent of AI."""

import json
import logging
import time
from datetime import datetime
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from kat_core.capability_schemas import CapabilityFailure, Location

MAX_RESPONSE = 128 * 1024
GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
logger = logging.getLogger("kat_core.weather")


class WeatherAdapter(Protocol):
    def resolve(self, query: str) -> list[Location]: ...
    def current(self, location: Location) -> dict[str, Any]: ...


class OpenMeteo:
    def client(self) -> httpx.Client:
        return httpx.Client(timeout=8, follow_redirects=False, trust_env=False)

    def _request(self, endpoint: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        if endpoint not in (GEOCODING, FORECAST):
            raise CapabilityFailure("weather_destination", "Unsupported weather destination.")
        deadline = time.monotonic() + 8
        for attempt in range(2):
            try:
                return self._attempt(endpoint, params, deadline)
            except httpx.RequestError as error:
                timeout = isinstance(error, httpx.TimeoutException)
                if attempt == 0 and deadline - time.monotonic() > 1:
                    logger.info(
                        "weather_transport_retry category=%s", "timeout" if timeout else "network"
                    )
                    continue
                raise CapabilityFailure(
                    "weather_timeout" if timeout else "weather_unavailable",
                    "Weather provider timed out. Try again."
                    if timeout
                    else "Weather provider could not be reached.",
                ) from None
        raise AssertionError("Bounded weather attempts exhausted")

    def _attempt(
        self, endpoint: str, params: dict[str, str | int | float], deadline: float
    ) -> dict[str, Any]:
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CapabilityFailure("weather_timeout", "Weather provider timed out.")
            with (
                self.client() as client,
                client.stream(
                    "GET",
                    endpoint,
                    params=params,
                    headers={"Accept-Encoding": "identity"},
                    timeout=min(3.5, remaining),
                ) as response,
            ):
                logger.info(
                    "weather_response endpoint=%s status=%d encoding=%s",
                    "forecast" if endpoint == FORECAST else "geocoding",
                    response.status_code,
                    "identity"
                    if response.headers.get("content-encoding", "identity").lower() == "identity"
                    else "compressed",
                )
                if response.status_code != 200:
                    raise CapabilityFailure(
                        "weather_unavailable", "Weather provider is unavailable. Try again later."
                    )
                # Avoid unbounded decompression before the decoded-size check.
                # Fixed providers must honor the explicitly uncompressed request.
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise CapabilityFailure(
                        "weather_malformed", "Weather provider returned unsupported compression."
                    )
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    if time.monotonic() > deadline:
                        raise CapabilityFailure("weather_timeout", "Weather provider timed out.")
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE:
                        raise CapabilityFailure(
                            "weather_malformed",
                            "Weather provider response exceeded its size limit.",
                        )
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError
                return result
        except (ValueError, UnicodeError):
            raise CapabilityFailure(
                "weather_malformed", "Weather provider returned unreadable data."
            ) from None

    def resolve(self, query: str) -> list[Location]:
        # The public geocoder accepts city names, not comma-separated addresses.
        body = self._request(
            GEOCODING,
            {
                "name": query.split(",", 1)[0].strip(),
                "count": 5,
                "language": "en",
                "format": "json",
            },
        )
        try:
            rows = body.get("results", [])
            if not isinstance(rows, list) or len(rows) > 5:
                raise ValueError
            return [
                Location(
                    label=", ".join(str(r[k]) for k in ("name", "admin1", "country") if r.get(k))[
                        :160
                    ],
                    latitude=float(r["latitude"]),
                    longitude=float(r["longitude"]),
                    timezone=r["timezone"],
                )
                for r in rows
            ]
        except (KeyError, TypeError, ValueError, ValidationError):
            raise CapabilityFailure(
                "weather_malformed", "Weather provider returned an invalid location."
            ) from None

    def current(self, location: Location) -> dict[str, Any]:
        body = self._request(
            FORECAST,
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timezone": "auto",
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": 1,
            },
        )
        try:
            current, daily = body["current"], body["daily"]
            code = int(current["weather_code"])
            datetime.fromisoformat(current["time"])
            if not 0 <= code <= 99:
                raise ValueError
            condition = (
                "clear"
                if code == 0
                else "cloudy"
                if code <= 3
                else "fog"
                if code <= 48
                else "rain"
                if code <= 67
                else "snow"
                if code <= 77
                else "showers"
                if code <= 86
                else "thunderstorm"
            )
            result: dict[str, Any] = {
                "provider": "open-meteo",
                "source": FORECAST,
                "location": location.label,
                "observed_at": str(current["time"])[:40],
                "timezone": str(body["timezone"])[:80],
                "temperature_c": float(current["temperature_2m"]),
                "feels_like_c": float(current["apparent_temperature"]),
                "condition": condition,
                "wind_kmh": float(current["wind_speed_10m"]),
                "forecast_high_c": float(daily["temperature_2m_max"][0]),
                "forecast_low_c": float(daily["temperature_2m_min"][0]),
                "precipitation_chance_percent": int(daily["precipitation_probability_max"][0]),
            }
            import math

            if (
                not all(
                    math.isfinite(result[k]) and -150 <= result[k] <= 500
                    for k in (
                        "temperature_c",
                        "feels_like_c",
                        "wind_kmh",
                        "forecast_high_c",
                        "forecast_low_c",
                    )
                )
                or not 0 <= result["precipitation_chance_percent"] <= 100
            ):
                raise ValueError
            return result
        except (KeyError, TypeError, ValueError, IndexError):
            raise CapabilityFailure(
                "weather_malformed", "Weather provider returned invalid conditions."
            ) from None
