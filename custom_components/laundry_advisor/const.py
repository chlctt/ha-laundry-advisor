"""Constants for the Laundry Advisor integration."""

from __future__ import annotations

DOMAIN = "laundry_advisor"

# config entry (main) keys
CONF_WEATHER = "weather_entity"
CONF_PRECIP_PROB = "precip_prob_entity"
CONF_OUTDOOR_TEMP = "outdoor_temp"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"
CONF_DRYER = "dryer_entity"
CONF_WASHED_BOOLEAN = "already_washed_boolean"

# room subentry keys
SUBENTRY_TYPE_ROOM = "room"
CONF_ROOM_NAME = "name"
CONF_ROOM_TEMP = "temp_entity"
CONF_ROOM_HUMIDITY = "humidity_entity"
CONF_ROOM_WALL_TEMP = "wall_temp_entity"
CONF_ROOM_FAN = "fan_entity"
CONF_ROOM_DEHUMIDIFIER = "dehumidifier_entity"

# options
CONF_UPDATE_INTERVAL = "update_interval_minutes"
CONF_BLOCK_HOURS = "block_hours"
CONF_DAY_START = "day_start_hour"
CONF_DAY_END = "day_end_hour"
CONF_SCORE_HANG = "score_hang"
CONF_SCORE_MARGINAL = "score_marginal"
CONF_WAIT_DELTA = "wait_delta"
CONF_W_WIND = "weight_wind"
CONF_W_HUMIDITY = "weight_humidity"
CONF_W_SUN = "weight_sun"
CONF_W_TEMPERATURE = "weight_temperature"
CONF_ROOM_RH_MAX = "room_rh_max"
CONF_ROOM_TEMP_MIN = "room_temp_min"
CONF_VENT_MARGIN = "vent_dewpoint_margin"

DEFAULTS: dict[str, float | int] = {
    CONF_UPDATE_INTERVAL: 15,
    CONF_BLOCK_HOURS: 5,
    CONF_DAY_START: 8,
    CONF_DAY_END: 20,
    CONF_SCORE_HANG: 70,
    CONF_SCORE_MARGINAL: 55,
    CONF_WAIT_DELTA: 20,
    CONF_W_WIND: 35,
    CONF_W_HUMIDITY: 30,
    CONF_W_SUN: 20,
    CONF_W_TEMPERATURE: 15,
    CONF_ROOM_RH_MAX: 65,
    CONF_ROOM_TEMP_MIN: 15,
    CONF_VENT_MARGIN: 5,
}
