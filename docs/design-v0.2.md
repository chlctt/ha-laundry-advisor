# v0.2 – Design

Status: implemented and merged.

## Goals

1. **Multiple drying rooms** instead of one fixed cellar.
2. **Ranking**: the blueprint scores "outside" + every room and recommends the
   **single best place by name**. The card shows the ranking.
3. **Bilingual** (en/de): `language` input in the blueprint (for notifications),
   the card additionally localises via `hass.language`.
4. New options: **tumble-dryer entity**, **per-room fan + dehumidifier**.

## Breaking changes vs. v0.1

- Inputs `cellar_temp` / `cellar_humidity` / `cellar_wall_temp` **removed** →
  replaced by 5 room slots.
- Attribute `cellar` (object) **removed** → replaced by `rooms` (list).
- New states (below). `outdoor_score*`, `forecast_days`, `best_window_*` stay.
- The `configuration.yaml` `use_blueprint` block must be migrated (note in README).

## Inputs

### Section "Data sources"
| Input | Required | Default |
|---|---|---|
| `weather_entity` | ✅ | – |
| `precip_prob_entity` | – | – |
| `outdoor_temp` / `outdoor_humidity` | – | from the weather entity |
| `already_washed_boolean` | – | – |

### Section "Language & output"
| Input | Default |
|---|---|
| `language` (select `en`/`de`) | `en` |
| `dryer_entity` (optional) | – |

`dryer_entity` set → state `dryer_recommended` possible. Not set → the least-bad
room is recommended instead (`best_effort`).

### Sections "Room 1"…"Room 5" (rooms 2–5 collapsed)
| Input | Required for an active room |
|---|---|
| `room_N_name` (text) | ✅ (empty = slot unused) |
| `room_N_temp` (sensor/temperature) | ✅ |
| `room_N_humidity` (sensor/humidity) | ✅ |
| `room_N_fan` (entity, optional) | – |
| `room_N_dehumidifier` (entity, optional) | – |

A room counts only when `name` + `temp` + `humidity` are all set.

### Section "Fine-tuning" (collapsed)
`block_hours`, `day_start_hour`, `day_end_hour`, `score_hang` (70),
`score_marginal` (55 – at/above it the outside recommendation is still made),
`wait_delta`, `weight_wind/humidity/sun/temperature`,
`room_rh_max` (65), `room_temp_min` (15), `vent_dewpoint_margin` (5).

## Room score (per room, 0–100)

From live sensors:

```
td_room      = dew_point(T_room, rh_room)
ah_room      = absolute humidity
vent_useful  = td_outdoor <= td_room - vent_dewpoint_margin
vpd_room     = E_s(T_room) * (1 - rh_room/100)          # drying driver
mold_risk    = rh_room > 80
suitable     = rh_room < room_rh_max AND T_room >= room_temp_min AND not mold_risk

room_score:
  start = ramp(vpd_room, 2, 12) * 100          # 0 at 2 hPa, 100 at 12 hPa
  + 10  if a dehumidifier is configured
  + 8   if vent_useful (airing helps)
  + 5   if a fan is configured
  − 25  if rh_room >= room_rh_max
  ~2    if mold_risk
  clamped 0..100
```

## Recommendation

"Outside" enters the recommendation via absolute `score_hang` / `score_marginal`
thresholds (see [`docs/logic.md`](logic.md#bands-outdoor)); the rooms are ranked
only among each other, and the best usable one is offered when outside is out. A
unified ranking is [#8](https://github.com/chlctt/ha-laundry-advisor/issues/8).

## States (enum)

`hang_outside_now`, `hang_outside_later`, `outside_marginal`,
`wait_for_tomorrow`, `defer_wash`,
`room_ok`, `room_ventilate`, `room_dehumidify`,
`dryer_recommended`, `best_effort`, `mold_risk`, `unknown`

## Sensor attributes

```yaml
state: <one of the states>
attributes:
  language: en
  headline: "<localised>"
  reasons: ["<localised>", ...]
  reason_codes:                       # for the card's i18n
    - {code: room_best, n: "Basement", s: 27}
  recommended_room: "Basement"        # or null (outside / dryer)
  recommended_fan: fan.basement       # entity of the recommended room, or null
  recommended_dehumidifier: null
  outdoor_score: 42
  outdoor_score_tomorrow: 68
  outdoor_score_day_after: 55
  forecast_days: [...]
  best_window_start_hour: 11
  best_window_end_hour: 16
  daylight_left_h: 5
  rooms:                              # sorted by score
    - name: "Basement"
      score: 34
      status: too_humid               # ok | too_humid | too_cold | mold_risk
      temperature: 20.9
      humidity: 71.9
      dewpoint: 15.6
      vpd: 7.1
      ventilation_useful: false
      has_fan: true
      has_dehumidifier: false
      suitable: false
      mold_risk: false
      recommended: false
```

## i18n

Blueprint: an internal table `T[language]` with `headlines` + `reason` templates.
The `language` input drives `headline`/`reasons`. `reason_codes` stay
language-neutral.

Card: `src/localize/{en,de}.json`, chosen via `hass.locale.language` /
`hass.language`, fallback `en`. Translates states, status chips, `reason_codes`.

## Card v0.2

- 3 score rings stay (today / tomorrow / day after).
- New **room list**: one row per room with name, score, status chip,
  airing/fan/dehumidifier hints; the recommended room is highlighted.
- `cellar` row removed.
- Config: `show_rooms` instead of `show_cellar`.

## v0.2.1 fixes

- New state `room_ok`: a suitable room that needs no airing and has no
  dehumidifier is no longer forced into the contradictory `room_ventilate`
  ("air it out" + "airing does nothing").
- `score_marginal` is wired up (was a dead input); `hang_outside_later` needs
  ≥ 1 daylight hour; `no_forecast` → `unknown` instead of unavailable;
  `advisor_name` / `advisor_unique_id` inputs; `continue_on_error` on the
  forecast calls; recompute every 10 min.

Open: [#8](https://github.com/chlctt/ha-laundry-advisor/issues/8) unified ranking,
[#9](https://github.com/chlctt/ha-laundry-advisor/issues/9) forecast interval,
[#10](https://github.com/chlctt/ha-laundry-advisor/issues/10) room-2..5 trigger.
