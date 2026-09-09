# Laundry Advisor

A Home Assistant **template blueprint** that recommends the **best place to dry
laundry** – outside on the line, in one of up to five indoor rooms, in the tumble
dryer – or tells you to wait until tomorrow to wash.

Matching Lovelace card: **[laundry-advisor-card](https://github.com/chlctt/laundry-advisor-card)**.

> Status: **v0.2**. English is the primary language; the runtime output is
> available in English and German (`language` input + the card's own
> localisation).

---

## What it produces

One sensor (`sensor.laundry_advisor`): **state** = the recommendation, everything
else as **attributes**.

| Value | Where |
|---|---|
| Recommendation state | `state` |
| Localised one-liner | `attributes.headline` |
| Localised reasons | `attributes.reasons` |
| Reason codes (language-neutral, for the card) | `attributes.reason_codes` |
| Recommended room (name) / fan / dehumidifier | `attributes.recommended_room` / `_fan` / `_dehumidifier` |
| Outdoor score today / tomorrow / day after (0–100) | `attributes.outdoor_score` / `_tomorrow` / `_day_after` |
| Best drying window today | `attributes.best_window_start_hour` / `_end_hour` |
| Day preview (up to 6 days) | `attributes.forecast_days` |
| Rooms, sorted by drying suitability | `attributes.rooms` |
| Remaining daylight | `attributes.daylight_left_h` |
| Active language | `attributes.language` |

### Recommendation states

| State | Meaning |
|---|---|
| `hang_outside_now` | Hang it outside now |
| `hang_outside_later` | Still today, but the window is tight |
| `outside_marginal` | Outside works, keep an eye on it |
| `wait_for_tomorrow` | Onto a **rack** today, outside tomorrow (laundry is already washed) |
| `defer_wash` | Postpone **washing** until tomorrow |
| `room_ok` | Best room – warm & dry enough, just hang it there |
| `room_ventilate` | Best room (`recommended_room`) – air it out + fan |
| `room_dehumidify` | Best room – dehumidifier only (airing does nothing) |
| `dryer_recommended` | Tumble dryer (only when `dryer_entity` is set) |
| `best_effort` | No room below the humidity limit, no dryer – least-bad room + warning |
| `mold_risk` | Every room too humid – do not hang anything wet |

### `rooms` object (per room)

```yaml
- name: "Basement"
  score: 29                    # 0–100 drying suitability
  status: too_humid            # ok | too_humid | too_cold | mold_risk
  temperature: 20.9
  humidity: 72.0
  dewpoint: 15.6
  vpd: 6.9                     # vapour-pressure deficit, hPa
  ventilation_useful: false    # is outdoor air drier in absolute terms? (5-K rule)
  has_fan: true
  has_dehumidifier: false
  suitable: false
  mold_risk: false
  recommended: false
```

---

## Installation

Requires Home Assistant **≥ 2024.11**.

> ⚠️ **Template blueprints have no UI import / "create" dialog.** The
> *Settings → Automations & Scenes → Blueprints → Import* button only handles
> automation and script blueprints and will error on this one. Install it the
> YAML way instead.

1. **Add the blueprint file** to your config:
   `config/blueprints/template/chilcott/laundry_advisor.yaml`
   (copy the [raw file](https://github.com/chlctt/ha-laundry-advisor/blob/main/blueprints/template/laundry_advisor.yaml)).

2. **Optional helper:** an `input_boolean` (e.g. `input_boolean.laundry_washed`)
   that indicates fresh laundry is waiting – switches `wait_for_tomorrow` vs.
   `defer_wash`.

3. **Instantiate it** in `configuration.yaml`:

   ```yaml
   template:
     - use_blueprint:
         path: chilcott/laundry_advisor.yaml
         input:
           weather_entity: weather.home
           precip_prob_entity: weather.metno            # optional
           language: en                                 # en | de
           dryer_entity: switch.tumble_dryer_plug       # optional
           already_washed_boolean: input_boolean.laundry_washed
           room_1_name: Basement
           room_1_temp: sensor.basement_temperature
           room_1_humidity: sensor.basement_humidity
           room_1_fan: fan.basement_fan                 # optional
           room_2_name: Boiler room
           room_2_temp: sensor.boiler_room_temperature
           room_2_humidity: sensor.boiler_room_humidity
   ```

4. Reload: *Developer Tools → YAML → Template entities*.

> ⚠️ **After changing the blueprint file _or_ the `use_blueprint` inputs:
> restart HA, wait for the boot to finish, then run `template.reload`.**
> A plain "Reload template entities" does not re-read the blueprint or new
> inputs; a restart does, but the trigger-based entity then restores its
> previous state and only recomputes on the next trigger – `template.reload`
> right after the restart forces it (occasionally twice).

### Data source notes

- **Primary weather:** any `weather` entity with an hourly **and** daily
  forecast. Germany's DWD (`dwd_weather`) additionally exposes `dew_point`,
  `humidity_absolute`, `sun_irradiance`, `fog_probability` – used when present.
- **Precipitation probability:** the DWD does not provide it in hourly mode – add
  a second entity (e.g. Met.no) as `precip_prob_entity`; it is matched hour by
  hour.
- **Each active room needs a temperature and a humidity sensor.** A room without
  a name or sensors is ignored. Room 1 is required.
- **Outdoor sensors are optional** (fall back to the weather entity).
- **Assumes an hourly forecast in mm/h.** `daylight_left_h` and `block_hours`
  count forecast entries, and `precipitation > 0.1` is read as mm/h – with a
  3-hourly provider both are off by ~3× ([#9](https://github.com/chlctt/ha-laundry-advisor/issues/9)).
- Sensor changes in rooms 2–5 are picked up on the next 10-minute tick, not
  immediately ([#10](https://github.com/chlctt/ha-laundry-advisor/issues/10)).

---

## Fine-tuning

Section *Fine-tuning* (collapsed). Research-based defaults:

| Factor | Weight |
|---|---:|
| Wind | 35 |
| Humidity / vapour-pressure deficit | 30 |
| Sun | 20 |
| Temperature | 15 |

Rain > 0.1 mm/h → score 0. `indoor_score_bias` (default 15) penalises indoor
rooms in the ranking so "outside" wins on a tie. A room is "usable" below
`room_rh_max` (65 %) and at/above `room_temp_min` (15 °C). Airing is recommended
when the outdoor dew point is at least `vent_dewpoint_margin` (5 K) below the
room's dew point.

Derivation & sources: [`docs/logic.md`](docs/logic.md). v0.2 model:
[`docs/design-v0.2.md`](docs/design-v0.2.md).

---

## Notifications

Example: [`examples/notify_automation.yaml`](examples/notify_automation.yaml) –
notifies on a state change and optionally switches the recommended room's fan /
dehumidifier (`recommended_fan` / `recommended_dehumidifier`).

---

## Credits / prior art

- [GSW Smart Ventilation Suite](https://community.home-assistant.io/t/gsw-smart-ventilation-suite-absolute-humidity-dew-point-logic/995338) – dew-point ventilation logic
- [Thermal Comfort](https://github.com/dolezsa/thermal_comfort) – dew point / absolute humidity sensors
- Forum: *[To line dry or not to line dry?](https://community.home-assistant.io/t/to-line-dry-or-not-to-line-dry/235079)*, *[Laundry Drying Outside / Drying Index](https://community.home-assistant.io/t/laundry-drying-outside-drying-index-schedule/149311)*
- [hackitu.de/drynow](https://www.hackitu.de/drynow/) – Penman over DWD MOSMIX

## Licence

MIT – see [LICENSE](LICENSE).
