"""Sensor entity tests."""

from __future__ import annotations

from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laundry_advisor import drying
from custom_components.laundry_advisor.sensor import LaundryAdvisorSensor

from .helpers import (
    DOMAIN,
    MAIN_DATA,
    ROOM_HUM,
    ROOM_SUBENTRY,
    ROOM_TEMP,
    WEATHER_ENTITY,
    register_mock_forecast,
)

_DOC_ATTRS = {
    "headline",
    "reasons",
    "reason_codes",
    "recommended_room",
    "recommended_fan",
    "recommended_dehumidifier",
    "outdoor_score",
    "outdoor_score_tomorrow",
    "outdoor_score_day_after",
    "daylight_left_h",
    "best_window_start_hour",
    "best_window_end_hour",
    "forecast_days",
    "rooms",
}


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


def _sensor_state(hass: HomeAssistant, entry: MockConfigEntry):
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, entry.entry_id)
    assert entity_id is not None
    return hass.states.get(entity_id)


async def test_native_value_and_attributes(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    state = _sensor_state(hass, entry)

    assert state is not None
    assert state.state == entry.runtime_data.data.state
    assert state.state in drying.STATES
    assert set(state.attributes) >= _DOC_ATTRS


async def test_enum_device_class_and_options(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    state = _sensor_state(hass, entry)

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == list(drying.STATES)


async def test_icon_mapping() -> None:
    class _Coord:
        class config_entry:
            entry_id = "x"

        data = drying.Result(
            state="mold_risk",
            reason_codes=[],
            recommended_room=None,
            recommended_fan=None,
            recommended_dehumidifier=None,
            outdoor_score=0.0,
            outdoor_score_tomorrow=0.0,
            outdoor_score_day_after=0.0,
            daylight_left_h=0.0,
            best_window_start_hour=None,
            best_window_end_hour=None,
            forecast_days=[],
            rooms=[],
        )

    sensor = LaundryAdvisorSensor(_Coord())  # type: ignore[arg-type]
    assert sensor.native_value == "mold_risk"
    assert sensor.icon == "mdi:alert"

    _Coord.data.state = "hang_outside_now"
    assert sensor.icon == "mdi:weather-sunny"
    _Coord.data.state = "totally_unknown_value"
    assert sensor.icon == "mdi:tshirt-crew"


async def test_native_value_none_when_no_data() -> None:
    class _Coord:
        class config_entry:
            entry_id = "x"

        data = None

    sensor = LaundryAdvisorSensor(_Coord())  # type: ignore[arg-type]
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None
