"""Config, options and room-subentry flow tests."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laundry_advisor.const import (
    CONF_DRYER,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP,
    CONF_ROOM_WINDOW,
    CONF_UPDATE_INTERVAL,
    CONF_WASHED_BOOLEAN,
    CONF_WEATHER,
    DOMAIN,
    SUBENTRY_TYPE_ROOM,
)

from .helpers import MAIN_DATA, WEATHER_ENTITY


async def test_user_flow_happy_path(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WEATHER: WEATHER_ENTITY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Laundry Advisor"
    assert result["data"] == {CONF_WEATHER: WEATHER_ENTITY}


async def test_user_flow_aborts_on_duplicate_weather_entity(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data=MAIN_DATA, title="Laundry Advisor").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WEATHER: WEATHER_ENTITY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_main_entry_keeps_rooms(hass: HomeAssistant) -> None:
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
                    CONF_ROOM_TEMP: "sensor.cellar_temp",
                    CONF_ROOM_HUMIDITY: "sensor.cellar_humidity",
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_WEATHER: WEATHER_ENTITY,
            CONF_DRYER: "switch.dryer",
            CONF_WASHED_BOOLEAN: "input_boolean.washed",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_DRYER] == "switch.dryer"
    assert entry.data[CONF_WASHED_BOOLEAN] == "input_boolean.washed"
    assert len(entry.subentries) == 1  # rooms untouched


async def test_options_flow_round_trip(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=MAIN_DATA, title="Laundry Advisor")
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == 30


def _room_input(name: str = "Cellar") -> dict:
    return {
        CONF_ROOM_NAME: name,
        CONF_ROOM_TEMP: "sensor.cellar_temp",
        CONF_ROOM_HUMIDITY: "sensor.cellar_humidity",
    }


async def test_room_subentry_create(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=MAIN_DATA, title="Laundry Advisor")
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ROOM),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], _room_input())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cellar"

    assert len(entry.subentries) == 1
    sub = next(iter(entry.subentries.values()))
    assert sub.subentry_type == SUBENTRY_TYPE_ROOM
    assert sub.data[CONF_ROOM_TEMP] == "sensor.cellar_temp"
    # _clean() drops empty optionals
    assert "fan_entity" not in sub.data


async def test_room_subentry_keeps_window_entity(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=MAIN_DATA, title="Laundry Advisor")
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ROOM),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**_room_input(), CONF_ROOM_WINDOW: "binary_sensor.cellar_window"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    sub = next(iter(entry.subentries.values()))
    assert sub.data[CONF_ROOM_WINDOW] == "binary_sensor.cellar_window"


async def test_room_subentry_reconfigure(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MAIN_DATA,
        title="Laundry Advisor",
        subentries_data=[
            {
                "subentry_type": SUBENTRY_TYPE_ROOM,
                "title": "Cellar",
                "unique_id": None,
                "data": _room_input(),
            }
        ],
    )
    entry.add_to_hass(hass)
    sub = next(iter(entry.subentries.values()))

    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _room_input(name="Utility room")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    sub = next(iter(entry.subentries.values()))
    assert sub.title == "Utility room"
    assert sub.data[CONF_ROOM_NAME] == "Utility room"


async def test_supported_subentry_types(hass: HomeAssistant) -> None:
    from custom_components.laundry_advisor.config_flow import (
        LaundryAdvisorConfigFlow,
        RoomSubentryFlowHandler,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=MAIN_DATA)
    entry.add_to_hass(hass)
    types = LaundryAdvisorConfigFlow.async_get_supported_subentry_types(entry)
    assert types == {SUBENTRY_TYPE_ROOM: RoomSubentryFlowHandler}
