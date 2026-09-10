# Laundry Advisor

Recommends the **best place to dry laundry** – outside on the line, in one of your
indoor rooms, in the tumble dryer – or tells you to wait until tomorrow to wash.

Ships as a Home Assistant **custom integration**, installable through HACS.

Matching Lovelace card: **[laundry-advisor-card](https://github.com/chlctt/laundry-advisor-card)**.

---

## What it produces

One sensor (`sensor.laundry_advisor`): **state** = the recommendation, everything
else as **attributes**.

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

## Setup

Requires Home Assistant **≥ 2026.9**.

1. **HACS** → ⋮ → *Custom repositories* → `https://github.com/chlctt/ha-laundry-advisor`,
   category **Integration** → download → restart HA.
2. *Settings → Devices & Services → Add Integration → Laundry Advisor.*
   Pick the weather entity (and optionally a second one for precipitation
   probability, outdoor sensors, a dryer entity, an "already washed" boolean).
3. On the integration's page: **Add drying room** for each candidate room –
   name + temperature + humidity sensor; optionally a wall-temperature sensor, a
   window/door contact sensor (see below), a fan and a dehumidifier. Any number
   of rooms.
4. Fine-tune from the integration's **Configure** dialog – no restart.

Language follows the Home Assistant UI language (English / German).

### The window/door contact per room

Set it for a room that **can be aired**. The contact state then only picks the
wording ("open the window there" vs. "the window is already open"). Leave it
empty for a room with no window or outside door – `room_ventilate` and the airing
score bonus are then never applied to that room.

> Coming from an older version without this field: your existing rooms have no
> contact set, so they are treated as not ventilatable until you add one. A
> `binary_sensor` group of the room's window sensors works too.

### Upgrading from the template blueprint (v0.3 and earlier)

The template blueprint was removed in v0.4. If you still run it: install and
configure the integration with the same weather entity + rooms, remove the
`template:` `use_blueprint:` block from your YAML so the entity ids don't clash,
and repoint the dashboard card / notification automation if the id changed. The
last blueprint version stays in the git history (tag `v0.3.1`).

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
when the outdoor dew point is ≥ `vent_dewpoint_margin` (5 K) below the room's
*and* the room has a window/door contact configured.

Derivation & sources: [`docs/logic.md`](docs/logic.md).
Integration design: [`docs/design.md`](docs/design.md).

---

## Development

```bash
pip install ruff pytest
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/
pytest tests/test_drying.py                       # pure logic, no HA needed

pip install pytest-homeassistant-custom-component
pytest tests/integration/                         # HA-dependent (Linux/WSL)
```

## Credits / prior art

- [GSW Smart Ventilation Suite](https://community.home-assistant.io/t/gsw-smart-ventilation-suite-absolute-humidity-dew-point-logic/995338), [Thermal Comfort](https://github.com/dolezsa/thermal_comfort)
- Forum: *[To line dry or not to line dry?](https://community.home-assistant.io/t/to-line-dry-or-not-to-line-dry/235079)*
- [hackitu.de/drynow](https://www.hackitu.de/drynow/) – Penman over DWD MOSMIX

## Licence

MIT – see [LICENSE](LICENSE).
