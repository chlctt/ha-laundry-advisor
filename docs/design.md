# Design – Laundry Advisor integration

A Home Assistant custom integration that recommends the best place to dry
laundry. One `DataUpdateCoordinator`, one sensor, all detail in attributes.

## History

- **v0.1–v0.2.1** – a template blueprint (`template:` `use_blueprint:`). It
  proved the scoring model but was painful to operate: chunked base64 deploy over
  SSH, restart + `template.reload` for every change, no config UI, five fixed
  room slots, the state trigger watched only room 1, ~800 lines of inline Jinja.
- **v0.3** – rewritten as this custom integration. The blueprint stayed in the
  repo as a frozen legacy copy.
- **v0.4** – blueprint removed from the repo entirely (last copy: git tag
  `v0.3.1`); `integration_type` changed from `helper` to `service` so the config
  subentry UI ("Add drying room") is reachable; optional per-room window/door
  contact sensor.

## Why an integration

HACS one-click install and updates, a config flow, reload without restart,
dynamic rooms as config subentries, a coordinator that listens to every
configured sensor, native HA translations, and the scoring logic as testable
pure Python (`drying.py`, no `hass` import).

`integration_type` is `service`: the entry shows on its own page under
*Settings → Devices & Services*, where the subentry "Add drying room" button
lives. (`helper` would hide it in the Helpers tab, whose row only opens the
options dialog.)

## Repo layout

```
custom_components/laundry_advisor/
  __init__.py       # config-entry setup / unload / reload
  manifest.json     # integration_type: service, iot_class: calculated, dependencies: [weather]
  config_flow.py    # user + options + room-subentry flows
  coordinator.py    # DataUpdateCoordinator: fetch forecasts, read sensors, run drying.evaluate
  drying.py         # PURE: psychrometrics, hour score, room score, state machine
  sensor.py         # the one ENUM sensor
  const.py          # DOMAIN, CONF_* keys, DEFAULTS
  l10n.py           # localised headline + reasons (HA UI language, en fallback)
  strings.json + translations/{en,de}.json + icons.json
tests/
  test_drying.py           # pure unit tests, run anywhere
  integration/             # pytest-homeassistant-custom-component (Linux/WSL)
docs/{design.md, logic.md}
.github/workflows/validate.yml   # examples yamllint · ruff · pytest (pure + integration) · hassfest
```

## Config flow

### `user` step (main entry)

| Field | Notes |
|---|---|
| `weather_entity` | required, `EntitySelector(domain="weather")` |
| `precip_prob_entity` | optional – second weather entity, precipitation probability only |
| `outdoor_temp` / `outdoor_humidity` | optional – fall back to the weather entity attributes |
| `dryer_entity` | optional – any entity, presence flag only |
| `already_washed_boolean` | optional – `input_boolean`, switches `wait_for_tomorrow` vs `defer_wash` |

`async_step_user` aborts only on a duplicate `weather_entity`; a second entry
with a different weather entity is allowed.

### Rooms – config subentries (`subentry_type="room"`)

Add / edit / remove from the entry's page, no slot limit.

| Field | Notes |
|---|---|
| `name` | required |
| `temp_entity` | required, `EntitySelector(domain="sensor")` – no `device_class` filter (group/template/min-max helpers carry none in the registry) |
| `humidity_entity` | required, same selector |
| `wall_temp_entity` | optional – precise mould guard (else the room RH is used) |
| `window_entity` | optional `binary_sensor` – **presence = the room can be aired**; state only picks the wording. No contact → `room_ventilate` and the airing bonus are never applied to that room |
| `fan_entity` / `dehumidifier_entity` | optional `fan`/`switch`/`humidifier` |

With zero rooms the integration still works in outdoor-only mode.

### Options flow

All fine-tuning: `update_interval_minutes` (15), `block_hours` (5),
`day_start_hour` (8), `day_end_hour` (20), `score_hang` (70),
`score_marginal` (55), `wait_delta` (20), `weight_wind/humidity/sun/temperature`
(35/30/20/15), `room_rh_max` (65), `room_dehumidify_rh` (55), `room_temp_min`
(15), `vent_dewpoint_margin` (5). Changing an option reloads the entry – no
restart. The main entry's entities are edited via **Reconfigure**.

## Coordinator

- `update_interval = timedelta(minutes=update_interval_minutes)`.
- `async_setup()` registers `async_track_state_change_event` for the weather
  entity, the precip-prob entity, the optional outdoor / dryer / washed
  entities, and every room's temp / humidity / wall-temp / window entity. A
  change schedules `async_request_refresh()` (itself debounced).
- `_async_update_data()`:
  1. `weather.get_forecasts` (hourly + daily on the primary entity, hourly on the
     precip-prob entity if set) via `blocking=True, return_response=True`. A
     forecast failure keeps the last good `Result` (or raises `UpdateFailed` on
     the first run).
  2. Resolve room sensor states; `window_open` is `True` / `False` / `None`
     (unknown / unavailable / missing).
  3. Outdoor dew point from the optional sensors, else the weather entity
     attributes.
  4. `drying.evaluate(...)` → a `Result` dataclass.
- The forecast interval is the median spacing of two consecutive `datetime`
  values; it scales `daylight_left_h`, the window length and the
  `precipitation` mm/h gate, so multi-hourly and sub-hourly providers are
  handled correctly.

## `drying.py`

```python
def dew_point(t, rh) -> float          # Alduchov–Eskridge Magnus, b=17.625 c=243.04
def abs_humidity(t, rh) -> float
def sat_vp(t) -> float
def vpd(t, rh) -> float
def hour_score(h: HourFc, w: Weights, interval_h=1.0) -> float   # 0..100, rain gate
def best_block(hours, block_hours) -> tuple[float, Window | None] # best daylight window
def room_score(room: RoomState, outdoor_dew, cfg: Config) -> RoomScore | None
def evaluate(*, hourly, daily, prob, rooms, outdoor, cfg, now, washed, has_dryer) -> Result
```

`evaluate()` does not mutate its inputs. State-machine cascade:

```
no_forecast → mold_risk (all rooms) → hang_outside_now / _later →
outside_marginal → wait_for_tomorrow / defer_wash →
room_ventilate / room_dehumidify / room_ok → dryer_recommended →
best_effort → unknown
```

`room_ventilate` requires the candidate room to have a window/door contact
configured *and* the outdoor dew point ≥ `vent_dewpoint_margin` below the room's.

## Sensor & attribute contract

```
sensor.laundry_advisor
  state: <recommendation>                 # ENUM, translated via translations/
  attributes:
    headline                              # localised one-liner (HA UI language)
    reasons: []  /  reason_codes: []      # localised / language-neutral
    recommended_room / _fan / _dehumidifier
    outdoor_score / _tomorrow / _day_after
    best_window_start_hour / _end_hour
    daylight_left_h
    forecast_days: []
    rooms: []                             # per room: score, status, dewpoint,
                                          # abs_humidity, vpd, ventilation_useful,
                                          # has_window, window_open, has_fan,
                                          # has_dehumidifier, suitable, mold_risk,
                                          # recommended
```

`"unknown"` is not advertised as an ENUM option (HA rejects it); the sensor
reports `None` for that state.

## Verified

Built and tested against **Home Assistant 2026.9.1** – `hassfest` clean, pure +
integration tests green, every HA API used checked against that version.
`hacs.json` pins `homeassistant: 2026.9.0`.

## Later

- Unified outside-vs-rooms ranking (issue #8).
- Optional Open-Meteo solar source (#5) and finer wind source (#4).
- Fog/dew window start (#2), aggregated sub-scores attribute (#1).
- Actually drive the fan/dehumidifier from the integration instead of the
  example automation; `diagnostics.py` dumping the last coordinator payload.
