"""The single Laundry Advisor sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import drying, l10n
from .const import DOMAIN
from .coordinator import LaundryConfigEntry, LaundryCoordinator

PARALLEL_UPDATES = 0

# ENUM options must not contain "unknown" (HA rejects it); it maps to None instead.
_OPTIONS = [s for s in drying.STATES if s != "unknown"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([LaundryAdvisorSensor(entry.runtime_data)])


class LaundryAdvisorSensor(CoordinatorEntity[LaundryCoordinator], SensorEntity):
    """State = recommendation, everything else as attributes."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "recommendation"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _OPTIONS

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attrs: dict[str, Any] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        r: drying.Result | None = self.coordinator.data
        if r is None:
            self._attrs = None
            return
        lang = self.hass.config.language
        self._attrs = {
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

    @property
    def native_value(self) -> str | None:
        state = self.coordinator.data.state if self.coordinator.data else None
        return state if state in _OPTIONS else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._attrs
