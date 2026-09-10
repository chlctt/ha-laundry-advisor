# Changelog

All notable changes to this project. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning per
[SemVer](https://semver.org/).

## [0.4.2] – 2026-09-10

### Fixed
- `best_block` now takes the forecast spacing from **each day's own** daylight
  entries. A regularly 3-hourly (or otherwise coarse) day is no longer treated
  as one big gap and scored 0 – the v0.4.1 gap check compared every day against
  the global median interval.
- Window length rounds up on a `.5` ratio (a 2-hourly forecast with the default
  5 h block gets a 3-entry / 6 h window, not 2 / 4 h).
- Example automation: `wait_for_tomorrow` (laundry drying on a rack today) no
  longer triggers the "turn every actuator off" branch.
- Translation-parity test now also fails on stale keys in `de.json`.

## [0.4.1] – 2026-09-10

Follow-up review fixes.

### Added
- **Reconfigure** flow for the main entry: change the weather entity, the
  precipitation source, the outdoor sensors, the dryer entity or the "already
  washed" helper afterwards without deleting the entry (and its rooms).
- New fine-tuning option **`room_dehumidify_rh`** (default 55 %) – the room
  humidity from which a dehumidifier is recommended was previously hard-coded.

### Fixed
- The coordinator's setup hook is now `_async_setup`, invoked once by
  `async_config_entry_first_refresh()`, instead of a separate public method
  called from `__init__`.
- The **daily** forecast is no longer fetched – it was unused, and a weather
  entity that only supports one forecast type made the whole integration fail to
  start.
- Room subentry **reconfigure** form: the window/door contact field now has a
  translated label and description (it was showing the raw key).
- A relative-humidity sensor reading above 100 % no longer produces a dew point
  above the air temperature.
- The best-window search skips a window that spans a gap in the forecast, so the
  reported hours stay honest with an incomplete forecast.
- Duplicate room names no longer flag more than one room as `recommended`.
- `manifest.json`: `dependencies` → `after_dependencies` for `weather`.
- Example notification automation: handles `room_ok`, and turns every known
  room actuator back off when drying moves outside.

## [0.4.0] – 2026-09-10

### Changed / Breaking
- `integration_type` is now `service` (was `helper`). The entry moves from the
  *Helpers* tab to *Settings → Devices & Services → Integrations*, where the
  **Add drying room** button actually renders – the Helpers-tab row only ever
  opened the options dialog, which is why rooms could not be added in the UI.
- The README now states the minimum Home Assistant version as **≥ 2026.9**, to
  match the (unchanged) `hacs.json` floor. HACS will not offer the update on
  older cores.
- **Rooms need a window/door contact to be considered ventilatable.** New
  optional per-room `window_entity` (`binary_sensor`): its presence marks the
  room as airable and its state picks the wording ("open the window there" vs
  "already open"). A room with no contact configured no longer gets
  `room_ventilate` or the airing score bonus. Existing rooms have none set, so
  add one (a `binary_sensor` group works) to keep the airing path.

### Removed
- The template blueprint (`blueprints/`, the `blueprint` CI job, the README
  section, `docs/design-v0.2.md`). The integration is the only supported form.
  The last blueprint release stays at git tag `v0.3.1`.

### Added
- `rooms[]` attribute gains `has_window` and `window_open`.

## [0.3.1] – 2026-09-10

### Fixed
- Integration config flow: dropped the `device_class` filter on the
  temperature / humidity entity pickers. Group / template / min-max helper
  sensors derive `device_class` at runtime and carry none in the entity
  registry, so the filter hid exactly the average sensors this integration is
  meant to use.

## [0.3.0] – 2026-09-09

Custom integration (`custom_components/laundry_advisor/`): config flow, rooms as
config subentries, coordinator, one sensor, en/de. The template blueprint stays
as legacy v0.2.1. See `docs/design-v0.3-integration.md`.

<!-- Everything below is the legacy template blueprint (removed in 0.4.0). -->

## [0.2.1] – 2026-09-09

### Fixed
- `score_marginal` is now actually used for the `outside_marginal` threshold
  (was hard-wired to 55 and the input was dead). Default raised to 55 to match.
- Removed the `indoor_score_bias` input – there is no unified outside-vs-rooms
  ranking (that is a possible v0.3 feature); the docs described one that did
  not exist.
- `hang_outside_later` no longer fires with 0 daylight hours left (needs ≥ 1).
- New state `room_ok`: a room that is suitable, needs no airing and has no
  dehumidifier no longer gets the contradictory "air it out" / "airing does
  nothing" pairing.
- `weather.get_forecasts` calls use `continue_on_error`; if the forecast is
  missing (e.g. the weather entity is not ready at HA start) the sensor reports
  `unknown` with a `no_forecast` reason instead of going unavailable.
- Recompute every 10 min (was 15).

### Added
- `advisor_name` / `advisor_unique_id` inputs – the sensor name and unique_id
  are no longer hard-coded, so a second instance no longer collides.

### Removed
- `custom_templates/laundry_advisor.jinja` (stale v0.1 macros referencing
  removed states). Will return with the package variant (#3).

### Docs
- English is the primary language across README / CHANGELOG / docs and the
  blueprint input labels.
- Documented the hourly-forecast assumption and the room-2..5 trigger delay.

## [0.2.0] – 2026-09-09

### Added
- **Multiple drying rooms** (up to 5 slots: name + temperature + humidity +
  optional fan + dehumidifier).
- **Ranking**: "outside" and every room are scored; the best place is
  recommended by name (`recommended_room`). `rooms` attribute = sorted list.
- Room score from vapour-pressure deficit + bonus for a dehumidifier / when
  airing helps (5-Kelvin dew-point rule) + a fan; penalty above the RH limit;
  ~0 at mould risk.
- **Bilingual**: `language` input (en/de) drives `headline`/`reasons`;
  `reason_codes` stay language-neutral for the card.
- `dryer_entity` input: without it, the least-bad room is recommended
  (`best_effort`) instead of `dryer_recommended`.
- New states: `room_ventilate`, `room_dehumidify`, `best_effort`.
- `indoor_score_bias`, `room_rh_max`, `room_temp_min` (replace `cellar_*`).
- `docs/design-v0.2.md`.

### Changed / Breaking
- Inputs `cellar_temp` / `cellar_humidity` / `cellar_wall_temp` **removed**.
- Attribute `cellar` **removed** → `rooms` (list).
- The `use_blueprint` block in `configuration.yaml` must be updated
  (migration in the README).
- English is now the primary language; `language` default is `en`.

## [0.1.x]

### Added
- Template blueprint (MVP): outdoor score today/tomorrow/day-after,
  9 recommendation states, cellar assessment (dew point / airing / mould guard),
  day preview, best time window – one sensor with attributes.
- Attribute `outdoor_score_day_after`.
- Core macros `custom_templates/laundry_advisor.jinja`.
- `docs/logic.md`, example notification automation.
