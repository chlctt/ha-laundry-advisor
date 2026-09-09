# Changelog

All notable changes to this project. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning per
[SemVer](https://semver.org/).

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
