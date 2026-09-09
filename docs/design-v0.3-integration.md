# v0.3 – Custom integration

Status: **concept, for review.** Replaces the template blueprint with a proper
Home Assistant custom integration.

## Why

The template blueprint proved the logic, but its operation is painful:
deployment needs chunked base64 over SSH, every change needs a restart plus
`template.reload` twice, there is no configuration UI, rooms are limited to five
fixed slots, the state trigger only watches room 1, and the ~800 lines of inline
Jinja (with `.format()` string hacks for i18n) are hard to test.

An integration fixes all of that: HACS one-click install and updates, a config
flow, reload without restart, dynamic rooms, a coordinator that listens to every
room sensor, native HA translations, and the scoring logic as testable Python.

## Scope of this version

- Custom integration `laundry_advisor` living in the **same repo**
  (`chlctt/ha-laundry-advisor`), `hacs.json` switched to type `integration`.
- The **template blueprint stays** in `blueprints/` marked as legacy (v0.2.x),
  so existing users are not broken; the README points new users at the
  integration.
- One main sensor `sensor.laundry_advisor` – state = recommendation, everything
  else as attributes (identical contract to v0.2.1, so the card needs only
  minimal changes).
- Language is taken automatically from the Home Assistant UI language (native
  `translations/`), no `language` option.

## Repo layout

```
ha-laundry-advisor/
├── custom_components/
│   └── laundry_advisor/
│       ├── __init__.py            # setup/unload/reload of the config entry + subentries
│       ├── manifest.json          # domain, name, version, iot_class: calculated, dependencies: [weather]
│       ├── config_flow.py         # user + options + room subentry flows
│       ├── coordinator.py         # DataUpdateCoordinator: fetch forecasts, read rooms, compute
│       ├── drying.py              # PURE functions: psychrometrics, hour score, room score, state machine
│       ├── sensor.py              # the one sensor entity
│       ├── const.py               # DOMAIN, defaults, STATES, REASON_CODES
│       ├── strings.json           # config-flow + entity strings (source of translations)
│       └── translations/
│           ├── en.json
│           └── de.json
├── tests/
│   ├── test_drying.py            # unit tests for every scoring path
│   └── conftest.py
├── blueprints/template/laundry_advisor.yaml   # LEGACY (v0.2.x, frozen)
├── hacs.json                     # {"name": "...", "render_readme": true}  (type integration)
├── docs/
│   ├── design-v0.3-integration.md  (this file)
│   └── logic.md
└── .github/workflows/
    ├── validate.yml              # hassfest + HACS action + ruff + pytest
    └── release.yml
```

## Configuration (config flow)

### Step 1 – `user` (the main entry)
| Field | Notes |
|---|---|
| `weather_entity` | required, `EntitySelector(domain="weather")` |
| `precip_prob_entity` | optional – second weather entity, precipitation probability only |
| `outdoor_temp` / `outdoor_humidity` | optional – fall back to the weather entity |
| `dryer_entity` | optional – any entity, presence flag |
| `already_washed_boolean` | optional – `input_boolean` |

Title of the entry = "Laundry Advisor" (editable). A second entry is allowed
(`async_step_user` does not abort on `_async_current_entries`).

### Rooms – **config subentries**
Each drying room is a **subentry** of the main entry (`ConfigSubentryFlow`,
`subentry_type="room"`). Add / edit / remove rooms from the entry's page, no
5-slot limit.

| Field | Notes |
|---|---|
| `name` | required |
| `temp_entity` | required, `EntitySelector(domain="sensor", device_class="temperature")` |
| `humidity_entity` | required, `device_class="humidity"` |
| `wall_temp_entity` | optional – precise mould guard (else room RH is used) |
| `fan_entity` | optional |
| `dehumidifier_entity` | optional |

At least one room is required for indoor recommendations; with zero rooms the
integration still works in outdoor-only mode.

### Options flow (reconfigure without re-adding)
All of the fine-tuning lives here: `block_hours`, `day_start_hour`,
`day_end_hour`, `score_hang` (70), `score_marginal` (55), `wait_delta` (20),
`weight_wind/humidity/sun/temperature` (35/30/20/15), `room_rh_max` (65),
`room_temp_min` (15), `vent_dewpoint_margin` (5), `update_interval_minutes` (15).

Changing options calls `async_reload_entry` – **no HA restart**.

## Coordinator

`LaundryCoordinator(DataUpdateCoordinator)`:

- `update_interval = timedelta(minutes=options["update_interval_minutes"])`.
- `_async_update_data()`:
  1. `hass.services.async_call("weather", "get_forecasts", {...}, blocking=True,
     return_response=True)` for hourly + daily on the primary entity, and hourly
     on the precip-prob entity if set. Wrapped in try/except → on failure the
     coordinator keeps the last good data and the sensor still renders (or
     `unknown` on first run).
  2. Read current room sensor states + outdoor state.
  3. Call `drying.evaluate(...)` (pure) → a `Result` dataclass.
- **Push updates**: `async_track_state_change_event` for every room temp/humidity
  entity + the weather entity + the outdoor sensors → `coordinator.async_request_refresh()`
  (debounced). This replaces the "only room 1" trigger limitation.
- Forecast interval is derived from two consecutive `datetime` values and used to
  scale `daylight_left`, the window length and the `precipitation` threshold
  (fixes the hourly / mm-h assumption, blueprint #9).

## `drying.py` – pure logic (ported from the reviewed Jinja)

Stateless functions, fully unit-tested, no `hass` import:

```python
def dew_point(t: float, rh: float) -> float          # Alduchov–Eskridge Magnus
def abs_humidity(t: float, rh: float) -> float
def sat_vp(t: float) -> float
def hour_score(h: HourFc, weights: Weights) -> float  # 0..100, rain gate
def best_block(hours: list[HourFc], win: int, day_range) -> tuple[float, Window]
def room_score(room: RoomState, outdoor_dew: float | None, cfg: Config) -> RoomScore
def evaluate(fc_hourly, fc_daily, fc_prob, rooms, outdoor, cfg, washed, has_dryer) -> Result
```

`Result` mirrors the v0.2.1 attribute set. The state machine is the same cascade
(`no_forecast → mold_risk → hang_outside_* → outside_marginal → wait/defer →
room_ok/ventilate/dehumidify → dryer → best_effort`).

## Sensor & attribute contract (unchanged from v0.2.1)

```
sensor.laundry_advisor
  state: <recommendation state>            # translated for display via translations/
  attributes:
    headline                               # localised (HA UI language)
    reasons: []                            # localised
    reason_codes: []                       # language-neutral, for the card
    recommended_room / _fan / _dehumidifier
    outdoor_score / _tomorrow / _day_after
    best_window_start_hour / _end_hour
    daylight_left_h
    forecast_days: []
    rooms: []
```

State translation: the raw state is one of the enum keys; HA renders it through
`translations/<lang>.json → entity.sensor.<key>.state.<state>`. `headline` and
`reasons` are built in Python from the same translation strings so notifications
are localised too.

## What changes for the card

- Entity id and attribute names stay the same → the card mostly works unchanged.
- The card can **drop its own state/headline localisation** and use the
  integration's translated `state` + `headline` directly (keeps `reason_codes`
  rendering and its own UI-label localisation). Optional simplification, not
  required for v0.3.
- `room_status` values (`ok/too_humid/too_cold/mold_risk`) unchanged.

## Migration from the template blueprint

1. Install the integration via HACS, add it, configure the same weather entity +
   rooms.
2. It creates `sensor.laundry_advisor` – if the old template sensor still exists
   there is an id clash, so either remove the `use_blueprint:` block from
   `configuration.yaml` first, or let the new entity take
   `sensor.laundry_advisor_2` and rename.
3. Update dashboard card + notify automation to the new entity if the id changed.
4. Remove the `template:` block and the blueprint file.

A short migration section goes in the README; the blueprint stays available for
anyone not ready to switch.

## CI

- `hassfest` (HA's integration manifest/structure check)
- `hacs/action` with `category: integration`
- `ruff` + `mypy` on `custom_components/`
- `pytest` on `tests/` (the point of the Python port)

## Open questions / later

- **HA minimum version**: config subentries need ≥ 2025.3 (approx). Confirm and
  pin in `manifest.json`. If too new, fall back to a JSON list of rooms in
  options.
- Blueprint #8 (unified outside-vs-rooms ranking): easy to add in Python later.
- Actually control the fan/dehumidifier from the integration (a switch/number
  entity or a service) instead of leaving it to the example automation.
- Detect "dryer running" from a power sensor if `dryer_entity` is a power sensor.
- Diagnostics download (`diagnostics.py`) dumping the last coordinator payload.
