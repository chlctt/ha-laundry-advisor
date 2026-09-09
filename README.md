# Laundry Advisor

Recommends the **best place to dry laundry** – outside on the line, in one of your
indoor rooms, in the tumble dryer – or tells you to wait until tomorrow to wash.

Ships as a **custom integration** (recommended) and, for anyone not ready to
switch, a legacy **template blueprint**.

Matching Lovelace card: **[laundry-advisor-card](https://github.com/chlctt/laundry-advisor-card)**.

---

## What it produces

One sensor (`sensor.laundry_advisor`): **state** = the recommendation, everything
else as **attributes**. Same contract for the integration and the blueprint.

| Value | Where |
|---|---|
| Recommendation state | `state` (translated by HA) |
| Localised one-liner | `attributes.headline` |
| Localised reasons / language-neutral codes | `attributes.reasons` / `reason_codes` |
| Recommended room / fan / dehumidifier | `attributes.recommended_room` / `_fan` / `_dehumidifier` |
| Outdoor score today / tomorrow / day after (0–100) | `attributes.outdoor_score` / `_tomorrow` / `_day_after` |
| Best drying window today | `attributes.best_window_start_hour` / `_end_hour` |
| Day preview (up to 6 days) | `attributes.forecast_days` |
| Rooms, sorted by drying suitability | `attributes.rooms` |
| Remaining daylight (hours) | `attributes.daylight_left_h` |

### Recommendation states

| State | Meaning |
|---|---|
| `hang_outside_now` / `hang_outside_later` | Outside now / while the window lasts |
| `outside_marginal` | Outside works, keep an eye on it |
| `wait_for_tomorrow` | Onto a rack today, outside tomorrow (already washed) |
| `defer_wash` | Postpone washing until tomorrow |
| `room_ok` | Best room – warm & dry enough, just hang it there |
| `room_ventilate` | Best room – air it out + fan |
| `room_dehumidify` | Best room – dehumidifier (airing does nothing) |
| `dryer_recommended` | Tumble dryer (only when a dryer entity is set) |
| `best_effort` | No room below the humidity limit, no dryer – least-bad room + warning |
| `mold_risk` | Every room too humid – do not hang anything wet |

---

## Integration (recommended)

Requires Home Assistant **≥ 2025.6**.

1. **HACS** → ⋮ → *Custom repositories* → `https://github.com/chlctt/ha-laundry-advisor`,
   category **Integration** → download → restart HA.
2. *Settings → Devices & Services → Add Integration → Laundry Advisor.*
   Pick the weather entity (and optionally a second one for precipitation
   probability, outdoor sensors, a dryer entity, an "already washed" boolean).
3. On the integration's page: **Add drying room** for each candidate room
   (name + temperature + humidity sensor; optionally a wall-temperature sensor,
   a fan and a dehumidifier). Any number of rooms.
4. Fine-tune from the integration's **Configure** dialog – no restart, no
   `template.reload`.

Language follows the Home Assistant UI language (English / German).

### Migration from the template blueprint

1. Install and configure the integration with the same weather entity + rooms.
2. Remove the `template:` `use_blueprint:` block (and the blueprint file) from
   your YAML so the entity ids don't clash.
3. Repoint the dashboard card / notification automation if the entity id changed.

The blueprint stays available; there is no rush.

---

## Template blueprint (legacy, v0.2.1)

Kept for users who cannot run the integration. It is **not** developed further –
new work goes into the integration.

Install: copy
[`blueprints/template/laundry_advisor.yaml`](blueprints/template/laundry_advisor.yaml)
to `config/blueprints/template/chilcott/`, then in `configuration.yaml`:

```yaml
template:
  - use_blueprint:
      path: chilcott/laundry_advisor.yaml
      input:
        weather_entity: weather.home
        precip_prob_entity: weather.metno       # optional
        language: en                            # en | de
        dryer_entity: switch.tumble_dryer_plug  # optional
        room_1_name: Basement
        room_1_temp: sensor.basement_temperature
        room_1_humidity: sensor.basement_humidity
```

> ⚠️ Template blueprints have no UI. After changing the file *or* the
> `use_blueprint` inputs: restart HA, wait for the boot, then `template.reload`
> (occasionally twice).

Up to five room slots. See the file's inputs for the rest.

---

## How it scores

| Factor | Weight |
|---|---:|
| Wind | 35 |
| Humidity / vapour-pressure deficit | 30 |
| Sun | 20 |
| Temperature | 15 |

Rain > 0.1 mm/h → outdoor score 0. Bands: ≥ `score_hang` (70) hang outside,
≥ `score_marginal` (55) marginal, below that indoors. A room is "usable" below
`room_rh_max` (65 %) and at/above `room_temp_min` (15 °C); airing is recommended
when the outdoor dew point is ≥ `vent_dewpoint_margin` (5 K) below the room's.

Derivation & sources: [`docs/logic.md`](docs/logic.md).
Integration design: [`docs/design-v0.3-integration.md`](docs/design-v0.3-integration.md).

---

## Development

```bash
pip install ruff pytest homeassistant
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/
pytest tests/          # pure logic, no HA needed
```

## Credits / prior art

- [GSW Smart Ventilation Suite](https://community.home-assistant.io/t/gsw-smart-ventilation-suite-absolute-humidity-dew-point-logic/995338), [Thermal Comfort](https://github.com/dolezsa/thermal_comfort)
- Forum: *[To line dry or not to line dry?](https://community.home-assistant.io/t/to-line-dry-or-not-to-line-dry/235079)*
- [hackitu.de/drynow](https://www.hackitu.de/drynow/) – Penman over DWD MOSMIX

## Licence

MIT – see [LICENSE](LICENSE).
