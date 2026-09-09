"""Shared helpers for the HA-dependent Laundry Advisor tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import dt as dt_util

from custom_components.laundry_advisor.const import (
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP,
    CONF_WEATHER,
    DOMAIN,
    SUBENTRY_TYPE_ROOM,
)

WEATHER_ENTITY = "weather.home"
ROOM_TEMP = "sensor.cellar_temp"
ROOM_HUM = "sensor.cellar_humidity"

MAIN_DATA = {CONF_WEATHER: WEATHER_ENTITY}

ROOM_SUBENTRY = {
    "subentry_type": SUBENTRY_TYPE_ROOM,
    "title": "Cellar",
    "unique_id": None,
    "data": {
        CONF_ROOM_NAME: "Cellar",
        CONF_ROOM_TEMP: ROOM_TEMP,
        CONF_ROOM_HUMIDITY: ROOM_HUM,
    },
}


def make_forecast(hours: int = 30) -> list[dict[str, Any]]:
    """A minimal, well-formed hourly forecast starting at the current local hour."""
    start = dt_util.now().replace(minute=0, second=0, microsecond=0)
    return [
        {
            "datetime": (start + timedelta(hours=i)).isoformat(),
            "temperature": 18.0,
            "humidity": 55.0,
            "wind_speed": 15.0,
            "cloud_coverage": 20.0,
            "precipitation": 0.0,
            "precipitation_probability": 5.0,
        }
        for i in range(hours)
    ]


def register_mock_forecast(
    hass: HomeAssistant,
    forecast: list[dict[str, Any]] | None = None,
    *,
    fail: bool = False,
) -> dict[str, int]:
    """Register a stand-in weather.get_forecasts service. Returns a call counter."""
    counter = {"calls": 0}
    fc = forecast if forecast is not None else make_forecast()

    async def _handler(call: ServiceCall) -> dict[str, Any]:
        counter["calls"] += 1
        if fail:
            raise RuntimeError("boom")
        entity_id = call.data["entity_id"]
        ids = entity_id if isinstance(entity_id, list) else [entity_id]
        return {eid: {"forecast": fc} for eid in ids}

    hass.services.async_register(
        "weather",
        "get_forecasts",
        _handler,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return counter


__all__ = [
    "DOMAIN",
    "MAIN_DATA",
    "ROOM_HUM",
    "ROOM_SUBENTRY",
    "ROOM_TEMP",
    "WEATHER_ENTITY",
    "make_forecast",
    "register_mock_forecast",
]
