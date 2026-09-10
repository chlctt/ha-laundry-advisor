"""Coordinator tests: forecast fetch, state-change refresh, failure handling."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laundry_advisor import drying
from custom_components.laundry_advisor.const import (
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP,
    CONF_ROOM_WINDOW,
    SUBENTRY_TYPE_ROOM,
)
from custom_components.laundry_advisor.coordinator import LaundryCoordinator

from .helpers import (
    DOMAIN,
    MAIN_DATA,
    ROOM_HUM,
    ROOM_SUBENTRY,
    ROOM_TEMP,
    WEATHER_ENTITY,
    register_mock_forecast,
)

WINDOW = "binary_sensor.cellar_window"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data=MAIN_DATA,
        title="Laundry Advisor",
        subentries_data=[ROOM_SUBENTRY],
    )


async def test_update_data_returns_result(hass: HomeAssistant) -> None:
    register_mock_forecast(hass)
    hass.states.async_set(WEATHER_ENTITY, "cloudy", {"temperature": 17, "humidity": 70})
    hass.states.async_set(ROOM_TEMP, "19.5")
    hass.states.async_set(ROOM_HUM, "58")
    entry = _entry()
    entry.add_to_hass(hass)

    coordinator = LaundryCoordinator(hass, entry)
    await coordinator._async_setup()
    result = await coordinator._async_update_data()

    assert isinstance(result, drying.Result)
    assert result.state in drying.STATES
    assert result.rooms and result.rooms[0]["name"] == "Cellar"


async def test_state_change_schedules_refresh(hass: HomeAssistant) -> None:
    register_mock_forecast(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = LaundryCoordinator(hass, entry)
    await coordinator._async_setup()

    calls: list[int] = []

    async def _fake_refresh() -> None:
        calls.append(1)

    coordinator.async_request_refresh = _fake_refresh  # type: ignore[method-assign]

    hass.states.async_set(ROOM_TEMP, "21")
    await hass.async_block_till_done()

    assert calls


async def test_window_contact_flows_into_room(hass: HomeAssistant) -> None:
    register_mock_forecast(hass)
    hass.states.async_set(WEATHER_ENTITY, "cloudy", {"temperature": 5, "humidity": 60})
    hass.states.async_set(ROOM_TEMP, "20")
    hass.states.async_set(ROOM_HUM, "62")
    hass.states.async_set(WINDOW, "on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MAIN_DATA,
        title="Laundry Advisor",
        subentries_data=[
            {
                "subentry_type": SUBENTRY_TYPE_ROOM,
                "title": "Cellar",
                "unique_id": None,
                "data": {
                    CONF_ROOM_NAME: "Cellar",
                    CONF_ROOM_TEMP: ROOM_TEMP,
                    CONF_ROOM_HUMIDITY: ROOM_HUM,
                    CONF_ROOM_WINDOW: WINDOW,
                },
            }
        ],
    )
    entry.add_to_hass(hass)
    coordinator = LaundryCoordinator(hass, entry)
    await coordinator._async_setup()
    result = await coordinator._async_update_data()

    room = result.rooms[0]
    assert room["has_window"] is True
    assert room["window_open"] is True


async def test_window_contact_change_schedules_refresh(hass: HomeAssistant) -> None:
    register_mock_forecast(hass)
    hass.states.async_set(ROOM_TEMP, "20")
    hass.states.async_set(ROOM_HUM, "62")
    hass.states.async_set(WINDOW, "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MAIN_DATA,
        title="Laundry Advisor",
        subentries_data=[
            {
                "subentry_type": SUBENTRY_TYPE_ROOM,
                "title": "Cellar",
                "unique_id": None,
                "data": {
                    CONF_ROOM_NAME: "Cellar",
                    CONF_ROOM_TEMP: ROOM_TEMP,
                    CONF_ROOM_HUMIDITY: ROOM_HUM,
                    CONF_ROOM_WINDOW: WINDOW,
                },
            }
        ],
    )
    entry.add_to_hass(hass)
    coordinator = LaundryCoordinator(hass, entry)
    await coordinator._async_setup()

    calls: list[int] = []

    async def _fake_refresh() -> None:
        calls.append(1)

    coordinator.async_request_refresh = _fake_refresh  # type: ignore[method-assign]
    hass.states.async_set(WINDOW, "on")
    await hass.async_block_till_done()
    assert calls


async def test_forecast_failure_keeps_last_data(hass: HomeAssistant) -> None:
    counter = register_mock_forecast(hass, fail=True)
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = LaundryCoordinator(hass, entry)
    await coordinator._async_setup()

    sentinel = object()
    coordinator.data = sentinel  # type: ignore[assignment]
    result = await coordinator._async_update_data()

    assert result is sentinel
    assert counter["calls"] >= 1


async def test_forecast_failure_without_prior_data_raises(hass: HomeAssistant) -> None:
    register_mock_forecast(hass, fail=True)
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = LaundryCoordinator(hass, entry)
    await coordinator._async_setup()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
