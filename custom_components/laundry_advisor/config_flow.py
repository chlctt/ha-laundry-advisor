"""Config, options and room-subentry flows for Laundry Advisor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_BLOCK_HOURS,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_DRYER,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    CONF_PRECIP_PROB,
    CONF_ROOM_DEHUMIDIFIER,
    CONF_ROOM_FAN,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_NAME,
    CONF_ROOM_RH_MAX,
    CONF_ROOM_TEMP,
    CONF_ROOM_TEMP_MIN,
    CONF_ROOM_WALL_TEMP,
    CONF_ROOM_WINDOW,
    CONF_SCORE_HANG,
    CONF_SCORE_MARGINAL,
    CONF_UPDATE_INTERVAL,
    CONF_VENT_MARGIN,
    CONF_W_HUMIDITY,
    CONF_W_SUN,
    CONF_W_TEMPERATURE,
    CONF_W_WIND,
    CONF_WAIT_DELTA,
    CONF_WASHED_BOOLEAN,
    CONF_WEATHER,
    DOMAIN,
    SUBENTRY_TYPE_ROOM,
)

_WEATHER = selector.EntitySelector(selector.EntitySelectorConfig(domain="weather"))
# No device_class filter: group / template / min-max helpers derive device_class
# at runtime and carry none in the entity registry, so a device_class filter
# would hide exactly the average sensors people use here.
_TEMP = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
_HUM = _TEMP
# Any binary_sensor – a door/window group helper carries no registry device_class
# either, so no device_class filter here for the same reason as the sensors above.
_WINDOW = selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor"))
_ANY = selector.EntitySelector(selector.EntitySelectorConfig())
_BOOL = selector.EntitySelector(selector.EntitySelectorConfig(domain="input_boolean"))
_ACTUATOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["fan", "switch", "humidifier"], multiple=False)
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WEATHER): _WEATHER,
        vol.Optional(CONF_PRECIP_PROB): _WEATHER,
        vol.Optional(CONF_OUTDOOR_TEMP): _TEMP,
        vol.Optional(CONF_OUTDOOR_HUMIDITY): _HUM,
        vol.Optional(CONF_DRYER): _ANY,
        vol.Optional(CONF_WASHED_BOOLEAN): _BOOL,
    }
)


def _marker(cls: type, key: str, value: Any) -> Any:
    """A vol.Required/Optional marker that carries a suggested value, not a default.

    ``default=None`` on an EntitySelector key is fed straight into the selector on
    an empty submit and fails validation, so pre-fill via ``suggested_value``.
    """
    if value in (None, ""):
        return cls(key)
    return cls(key, description={"suggested_value": value})


def _room_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            _marker(vol.Required, CONF_ROOM_NAME, d.get(CONF_ROOM_NAME)): selector.TextSelector(),
            _marker(vol.Required, CONF_ROOM_TEMP, d.get(CONF_ROOM_TEMP)): _TEMP,
            _marker(vol.Required, CONF_ROOM_HUMIDITY, d.get(CONF_ROOM_HUMIDITY)): _HUM,
            _marker(vol.Optional, CONF_ROOM_WALL_TEMP, d.get(CONF_ROOM_WALL_TEMP)): _TEMP,
            _marker(vol.Optional, CONF_ROOM_WINDOW, d.get(CONF_ROOM_WINDOW)): _WINDOW,
            _marker(vol.Optional, CONF_ROOM_FAN, d.get(CONF_ROOM_FAN)): _ACTUATOR,
            _marker(vol.Optional, CONF_ROOM_DEHUMIDIFIER, d.get(CONF_ROOM_DEHUMIDIFIER)): _ACTUATOR,
        }
    )


def _num(minimum: float, maximum: float, step: float = 1, unit: str | None = None):
    config: dict[str, Any] = {
        "min": minimum,
        "max": maximum,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(selector.NumberSelectorConfig(config))


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UPDATE_INTERVAL): _num(5, 60, unit="min"),
        vol.Optional(CONF_BLOCK_HOURS): _num(2, 10, unit="h"),
        vol.Optional(CONF_DAY_START): _num(3, 12),
        vol.Optional(CONF_DAY_END): _num(14, 23),
        vol.Optional(CONF_SCORE_HANG): _num(40, 100),
        vol.Optional(CONF_SCORE_MARGINAL): _num(20, 80),
        vol.Optional(CONF_WAIT_DELTA): _num(5, 50),
        vol.Optional(CONF_W_WIND): _num(0, 100),
        vol.Optional(CONF_W_HUMIDITY): _num(0, 100),
        vol.Optional(CONF_W_SUN): _num(0, 100),
        vol.Optional(CONF_W_TEMPERATURE): _num(0, 100),
        vol.Optional(CONF_ROOM_RH_MAX): _num(45, 80, unit="%"),
        vol.Optional(CONF_ROOM_TEMP_MIN): _num(8, 22, unit="°C"),
        vol.Optional(CONF_VENT_MARGIN): _num(1, 9, unit="K"),
    }
)

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class LaundryAdvisorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._async_abort_entries_match({CONF_WEATHER: user_input[CONF_WEATHER]})
            return self.async_create_entry(title="Laundry Advisor", data=user_input)
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_ROOM: RoomSubentryFlowHandler}


class RoomSubentryFlowHandler(ConfigSubentryFlow):
    """Add or edit a drying room."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_ROOM_NAME], data=_clean(user_input)
            )
        return self.async_show_form(step_id="user", data_schema=_room_schema())

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                sub,
                title=user_input[CONF_ROOM_NAME],
                data=_clean(user_input),
            )
        return self.async_show_form(step_id="reconfigure", data_schema=_room_schema(dict(sub.data)))


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Drop optional keys the user left empty."""
    return {k: v for k, v in data.items() if v not in (None, "")}
