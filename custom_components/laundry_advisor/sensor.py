"""The single Laundry Advisor sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import drying, l10n
from .coordinator import LaundryConfigEntry, LaundryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([LaundryAdvisorSensor(entry.runtime_data)])


class LaundryAdvisorSensor(CoordinatorEntity[LaundryCoordinator], SensorEntity):
    """State = recommendation, everything else as attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "recommendation"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(drying.STATES)

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.state if self.coordinator.data else None

    @property
    def icon(self) -> str:
        state = self.native_value
        return {
            "hang_outside_now": "mdi:weather-sunny",
            "hang_outside_later": "mdi:weather-sunset",
            "outside_marginal": "mdi:weather-partly-cloudy",
            "wait_for_tomorrow": "mdi:timer-sand",
            "defer_wash": "mdi:washing-machine-off",
            "room_ok": "mdi:tshirt-crew",
            "room_ventilate": "mdi:window-open-variant",
            "room_dehumidify": "mdi:air-humidifier",
            "dryer_recommended": "mdi:tumble-dryer",
            "best_effort": "mdi:home-alert",
            "mold_risk": "mdi:alert",
        }.get(state or "", "mdi:tshirt-crew")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        r: drying.Result | None = self.coordinator.data
        if r is None:
            return None
        lang = self.hass.config.language
        return {
            "headline": l10n.headline(lang, r.state, r.recommended_room),
            "reasons": l10n.reasons(lang, r.reason_codes),
            "reason_codes": r.reason_codes,
            "recommended_room": r.recommended_room,
            "recommended_fan": r.recommended_fan,
            "recommended_dehumidifier": r.recommended_dehumidifier,
            "outdoor_score": r.outdoor_score,
            "outdoor_score_tomorrow": r.outdoor_score_tomorrow,
            "outdoor_score_day_after": r.outdoor_score_day_after,
            "daylight_left_h": r.daylight_left_h,
            "best_window_start_hour": r.best_window_start_hour,
            "best_window_end_hour": r.best_window_end_hour,
            "forecast_days": r.forecast_days,
            "rooms": r.rooms,
        }
