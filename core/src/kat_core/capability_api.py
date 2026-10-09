"""Authenticated owner configuration; no registration tool is exposed to AI."""

import asyncio

from fastapi import APIRouter

from kat_core.capability_schemas import (
    Capabilities,
    Location,
    LocationQuery,
    ReadRoot,
    RootCreate,
    WeatherConfiguration,
)
from kat_core.capability_store import CapabilityStore
from kat_core.weather import WeatherAdapter


def capability_router(store: CapabilityStore, weather: WeatherAdapter) -> APIRouter:
    router = APIRouter(prefix="/capabilities")

    @router.get("")
    def configuration() -> Capabilities:
        return store.configuration()

    @router.post("/weather/locations")
    async def locations(value: LocationQuery) -> list[Location]:
        from kat_core.capability_schemas import CapabilityFailure

        try:
            async with asyncio.timeout(12):
                return await asyncio.to_thread(weather.resolve, value.query)
        except TimeoutError:
            raise CapabilityFailure(
                "weather_timeout", "Weather location lookup timed out."
            ) from None

    @router.put("/weather")
    def set_weather(value: WeatherConfiguration) -> Capabilities:
        return store.set_weather(value.location)

    @router.post("/roots", status_code=201)
    def add_root(value: RootCreate) -> ReadRoot:
        return store.add_root(value)

    @router.delete("/roots/{root_id}")
    def remove_root(root_id: str) -> dict[str, str]:
        store.remove_root(root_id)
        return {"status": "removed"}

    return router
