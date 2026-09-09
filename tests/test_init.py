"""Integration setup / unload / reload tests."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

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


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    await async_setup_component(hass, "weather", {})
    register_mock_forecast(hass)
    hass.states.async_set(WEATHER_ENTITY, "sunny", {"temperature": 18, "humidity": 60})
    hass.states.async_set(ROOM_TEMP, "19")
    hass.states.async_set(ROOM_HUM, "55")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MAIN_DATA,
        title="Laundry Advisor",
        subentries_data=[ROOM_SUBENTRY],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, LaundryCoordinator)
    assert entry.runtime_data.data is not None  # first refresh ran
    # SENSOR platform was forwarded
    assert Platform.SENSOR.value in hass.config.components
    assert hass.states.async_entity_ids("sensor")


async def test_unload_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_update_listener_reloads(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    first = entry.runtime_data

    hass.config_entries.async_update_entry(entry, options={"update_interval_minutes": 45})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not first  # reloaded -> fresh coordinator
