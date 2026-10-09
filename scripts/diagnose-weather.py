"""Bounded timing of fixed public weather endpoints; synthetic location only."""

import json
import socket
import time

import httpx

from kat_core.weather import FORECAST, MAX_RESPONSE


def main() -> None:
    started = time.monotonic()
    addresses = socket.getaddrinfo("api.open-meteo.com", 443, type=socket.SOCK_STREAM)
    print(
        json.dumps(
            {
                "test": "weather-dns",
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "families": sorted(
                    {"ipv4" if a[0] == socket.AF_INET else "ipv6" for a in addresses}
                ),
            }
        ),
        flush=True,
    )
    for attempt in range(2):
        started = time.monotonic()
        evidence = {"test": "weather-fixed-endpoint-timing", "attempt": attempt + 1}
        try:
            with (
                httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client,
                client.stream(
                    "GET",
                    FORECAST,
                    headers={"Accept-Encoding": "identity"},
                    params={
                        "latitude": 39.86804,
                        "longitude": -104.97199,
                        "timezone": "auto",
                        "current": "temperature_2m,apparent_temperature,"
                        "weather_code,wind_speed_10m",
                        "daily": "temperature_2m_max,temperature_2m_min,"
                        "precipitation_probability_max",
                        "forecast_days": 1,
                    },
                ) as response,
            ):
                evidence["status"] = response.status_code
                evidence["headers_ms"] = int((time.monotonic() - started) * 1000)
                evidence["compressed"] = (
                    response.headers.get("content-encoding", "identity") != "identity"
                )
                size = 0
                for chunk in response.iter_bytes(chunk_size=4096):
                    size += len(chunk)
                    if size > MAX_RESPONSE or time.monotonic() - started > 20:
                        raise ValueError("Timing probe exceeded its bound")
                evidence["bytes"] = size
        except Exception as error:
            evidence["exception_type"] = type(error).__name__
        evidence["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
