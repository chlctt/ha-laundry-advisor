"""Sensor entity tests."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laundry_advisor import drying
from custom_components.laundry_advisor.sensor import _OPTIONS, LaundryAdvisorSensor

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
    assert state.state in _OPTIONS
    assert set(state.attributes) >= _DOC_ATTRS


async def test_enum_device_class_and_options(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    state = _sensor_state(hass, entry)

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    # "unknown" must not be advertised as an ENUM option
    assert state.attributes[ATTR_OPTIONS] == _OPTIONS
    assert "unknown" not in state.attributes[ATTR_OPTIONS]


class _FakeCoord:
    class config_entry:
        entry_id = "x"
        title = "Laundry Advisor"

    data: drying.Result | None = None


def _result(state: str) -> drying.Result:
    return drying.Result(
        state=state,
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


def test_native_value_falls_back_to_none_on_unknown() -> None:
    coord = _FakeCoord()
    coord.data = _result("unknown")
    assert LaundryAdvisorSensor(coord).native_value is None  # type: ignore[arg-type]
    coord.data = _result("mold_risk")
    assert LaundryAdvisorSensor(coord).native_value == "mold_risk"  # type: ignore[arg-type]


def test_native_value_none_when_no_data() -> None:
    coord = _FakeCoord()
    coord.data = None
    sensor = LaundryAdvisorSensor(coord)  # type: ignore[arg-type]
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None


_COMPONENT = Path(__file__).resolve().parents[2] / "custom_components" / "laundry_advisor"


def test_icons_json_covers_every_state() -> None:
    icons = json.loads((_COMPONENT / "icons.json").read_text())
    mapped = icons["entity"]["sensor"]["recommendation"]["state"]
    assert set(mapped) == set(_OPTIONS)
    assert icons["entity"]["sensor"]["recommendation"]["default"]


def test_strings_and_translations_cover_every_state() -> None:
    strings = json.loads((_COMPONENT / "strings.json").read_text(encoding="utf-8"))
    en = json.loads((_COMPONENT / "translations" / "en.json").read_text(encoding="utf-8"))
    de = json.loads((_COMPONENT / "translations" / "de.json").read_text(encoding="utf-8"))

    def states(doc: dict) -> set[str]:
        return set(doc["entity"]["sensor"]["recommendation"]["state"])

    assert states(strings) == set(drying.STATES)
    assert states(en) == set(drying.STATES)
    assert states(de) == set(drying.STATES)
    # en.json is kept byte-identical to strings.json
    assert (_COMPONENT / "strings.json").read_bytes() == (
        _COMPONENT / "translations" / "en.json"
    ).read_bytes()


def _flatten(doc: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for k, v in doc.items():
        key = f"{prefix}.{k}" if prefix else k
        out |= _flatten(v, key) if isinstance(v, dict) else {key}
    return out


def test_de_and_en_translations_have_the_same_keys() -> None:
    en = _flatten(json.loads((_COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")))
    de = _flatten(json.loads((_COMPONENT / "translations" / "de.json").read_text(encoding="utf-8")))
    assert not en - de, f"de.json missing: {sorted(en - de)}"
    assert not de - en, f"de.json has stale keys: {sorted(de - en)}"
