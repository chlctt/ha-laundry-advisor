"""Coordinator: fetch forecasts, read sensors, run the pure logic."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import drying
from .const import (
    CONF_BLOCK_HOURS,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_DRYER,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    CONF_PRECIP_PROB,
    CONF_ROOM_DEHUMIDIFIER,
    CONF_ROOM_DEHUMIDIFY_RH,
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
    DEFAULTS,
    DOMAIN,
    SUBENTRY_TYPE_ROOM,
)

_LOGGER = logging.getLogger(__name__)

_FC_KEYS = (
    "temperature",
    "humidity",
    "wind_speed",
    "wind_gust_speed",
    "cloud_coverage",
    "precipitation",
    "precipitation_probability",
    "sun_irradiance",
)

type LaundryConfigEntry = ConfigEntry[LaundryCoordinator]


class LaundryCoordinator(DataUpdateCoordinator[drying.Result]):
    """Polls forecasts on an interval and on relevant state changes."""

    config_entry: LaundryConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LaundryConfigEntry) -> None:
        opts = {**DEFAULTS, **entry.options}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=int(opts[CONF_UPDATE_INTERVAL])),
        )
        self._opts = opts

    # -- lifecycle ------------------------------------------------------------
    async def _async_setup(self) -> None:
        """Wire up state-change listeners for every entity we read.

        The base ``DataUpdateCoordinator`` calls this exactly once, from
        ``async_config_entry_first_refresh()``.
        """
        entry = self.config_entry
        watched: set[str] = set()
        for key in (
            CONF_WEATHER,
            CONF_PRECIP_PROB,
            CONF_OUTDOOR_TEMP,
            CONF_OUTDOOR_HUMIDITY,
            CONF_DRYER,
            CONF_WASHED_BOOLEAN,
        ):
            if v := entry.data.get(key):
                watched.add(v)
        for sub in entry.subentries.values():
            if sub.subentry_type != SUBENTRY_TYPE_ROOM:
                continue
            for key in (
                CONF_ROOM_TEMP,
                CONF_ROOM_HUMIDITY,
                CONF_ROOM_WALL_TEMP,
                CONF_ROOM_WINDOW,
            ):
                if v := sub.data.get(key):
                    watched.add(v)

        if watched:
            entry.async_on_unload(
                async_track_state_change_event(
                    self.hass, sorted(watched), self._handle_state_change
                )
            )

    @callback
    def _handle_state_change(self, _event: Event[EventStateChangedData]) -> None:
        # DataUpdateCoordinator.async_request_refresh is itself debounced.
        self.config_entry.async_create_task(
            self.hass, self.async_request_refresh(), eager_start=False
        )

    # -- data ---------------------------------------------------------------
    async def _async_update_data(self) -> drying.Result:
        entry = self.config_entry
        weather = entry.data[CONF_WEATHER]

        try:
            hourly = await self._forecast(weather, "hourly")
        except Exception as err:  # a flaky forecast must never kill the coordinator
            if self.data is not None:
                _LOGGER.debug("forecast fetch failed, keeping last result: %s", err)
                return self.data
            raise UpdateFailed(f"forecast fetch failed: {err}") from err

        prob: list[drying.HourFc] = []
        if pe := entry.data.get(CONF_PRECIP_PROB):
            try:
                prob = await self._forecast(pe, "hourly")
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("precip-prob fetch failed: %s", err)

        rooms = [
            drying.RoomState(
                name=sub.data[CONF_ROOM_NAME],
                temp=self._num(sub.data.get(CONF_ROOM_TEMP)),
                humidity=self._num(sub.data.get(CONF_ROOM_HUMIDITY)),
                wall_temp=self._num(sub.data.get(CONF_ROOM_WALL_TEMP)),
                fan_entity=sub.data.get(CONF_ROOM_FAN) or None,
                dehumidifier_entity=sub.data.get(CONF_ROOM_DEHUMIDIFIER) or None,
                window_entity=(we := sub.data.get(CONF_ROOM_WINDOW) or None),
                window_open=self._is_on(we),
            )
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_TYPE_ROOM
        ]

        outdoor = drying.Outdoor(
            temp=self._outdoor_value(CONF_OUTDOOR_TEMP, weather, "temperature"),
            humidity=self._outdoor_value(CONF_OUTDOOR_HUMIDITY, weather, "humidity"),
        )

        washed = False
        if wb := entry.data.get(CONF_WASHED_BOOLEAN):
            washed = (st := self.hass.states.get(wb)) is not None and st.state == "on"

        has_dryer = bool(entry.data.get(CONF_DRYER))

        cfg = drying.Config(
            weights=drying.Weights(
                wind=float(self._opts[CONF_W_WIND]),
                humidity=float(self._opts[CONF_W_HUMIDITY]),
                sun=float(self._opts[CONF_W_SUN]),
                temperature=float(self._opts[CONF_W_TEMPERATURE]),
            ),
            block_hours=int(self._opts[CONF_BLOCK_HOURS]),
            day_start=int(self._opts[CONF_DAY_START]),
            day_end=int(self._opts[CONF_DAY_END]),
            score_hang=float(self._opts[CONF_SCORE_HANG]),
            score_marginal=float(self._opts[CONF_SCORE_MARGINAL]),
            wait_delta=float(self._opts[CONF_WAIT_DELTA]),
            room_rh_max=float(self._opts[CONF_ROOM_RH_MAX]),
            room_dehumidify_rh=float(self._opts[CONF_ROOM_DEHUMIDIFY_RH]),
            room_temp_min=float(self._opts[CONF_ROOM_TEMP_MIN]),
            vent_margin=float(self._opts[CONF_VENT_MARGIN]),
        )

        return drying.evaluate(
            hourly=hourly,
            daily=[],  # reserved – evaluate() does not use a daily forecast yet
            prob=prob,
            rooms=rooms,
            outdoor=outdoor,
            cfg=cfg,
            now=dt_util.now(),
            washed=washed,
            has_dryer=has_dryer,
        )

    # -- helpers ----------------------------------------------------------
    async def _forecast(self, entity_id: str, fc_type: str) -> list[drying.HourFc]:
        resp = await self.hass.services.async_call(
            "weather",
            "get_forecasts",
            {"type": fc_type, "entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
        entries = (resp or {}).get(entity_id, {}).get("forecast", [])
        out: list[drying.HourFc] = []
        for e in entries:
            dt = dt_util.parse_datetime(e.get("datetime", ""))
            if dt is None:
                continue
            out.append(
                drying.HourFc(
                    dt=dt_util.as_local(dt),
                    **{k: self._float(e.get(k)) for k in _FC_KEYS},
                )
            )
        return out

    def _outdoor_value(self, conf_key: str, weather: str, attr: str) -> float | None:
        if (eid := self.config_entry.data.get(conf_key)) and (v := self._num(eid)) is not None:
            return v
        st = self.hass.states.get(weather)
        return self._float(st.attributes.get(attr)) if st else None

    def _num(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return self._float(st.state) if st else None

    def _is_on(self, entity_id: str | None) -> bool | None:
        """True/False for a binary contact, None if unknown/unavailable/missing."""
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if st is None or st.state in ("unknown", "unavailable"):
            return None
        return st.state == "on"

    @staticmethod
    def _float(value: object) -> float | None:
        try:
            f = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return None if f != f else f  # drop NaN
