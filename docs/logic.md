# Logic & derivation

## Outdoor score (0–100)

Computed per forecast hour, then the mean of the **best contiguous window**
(default 5 h) within daylight (local hour `day_start_hour`…`day_end_hour`). If
there are fewer daylight hours than the window, a factor of 0.6 applies.

### Hard gates (hour → 0)
- Precipitation > 0.1 mm/h

### Soft multipliers
- Precipitation probability > 60 % → × 0.4; > 40 % → × 0.7
- Wind gusts > 45 km/h → score capped at 40

### Sub-scores (0–1, weighted)

| Factor | Weight | Curve |
|---|---:|---|
| Wind | 35 | 0 at ≤ 3 km/h, 1 in the 12–25 km/h band, falls to 0 at 40 km/h |
| Humidity / VPD | 30 | the worse of the RH ramp (1 at ≤ 55 %, 0 at 90 %) and the dew-point spread (1 at ≥ 6 K, 0 at ≤ 2 K) |
| Sun | 20 | irradiance `sun_irradiance` (0 at 20 W/m², 1 at 450) – otherwise `1 − cloud/100` |
| Temperature | 15 | 0 at ≤ 5 °C, 1 at ≥ 20 °C |

**Rationale** (from research + verification): drying wet fabric is a
boundary-layer mass-transfer process; air movement and the vapour-pressure
deficit (temperature *and* humidity together) drive it. Wind dominates especially
in shade / under overcast skies – in full sun, radiation can matter as much for
thin/dark fabric, so the sun term is not negligible. A Penman approach
approximates the initial (constant-rate) drying phase; near the end it no longer
holds. Rain makes drying impossible → hard gate.

## Bands

- ≥ 70: hang outside
- 45–69: works, keep an eye on it
- < 45: indoors

## Room assessment

From live sensors (not the forecast), per room:

- Dew point & absolute humidity via Magnus (Alduchov–Eskridge, `b = 17.625`,
  `c = 243.04`; dew-point error ~0.1 °C).
- **Airing worthwhile** when `outdoor dew point ≤ room dew point − vent_margin`
  (default 5 K; commercial dew-point controllers use 5 K on / 1 K off).
- **Room usable**: RH < `room_rh_max` (65 %) and T ≥ `room_temp_min` (15 °C) and
  no mould guard.
- **Mould guard**: `room RH > 80 %`.
- **Room score** (0–100): `ramp(vpd, 2, 12) × 100` + 10 if a dehumidifier is
  configured + 8 if airing helps + 5 if a fan is configured − 25 if RH ≥
  `room_rh_max`; ~2 at mould risk; clamped.

Background values: the German Environment Agency recommends indoor RH < 60 % (for
cellars); mould on a surface needs sustained > ~80 % RH / aw ≈ 0.8
(Sedlbauer / Fraunhofer IBP isopleth model). One wash load releases ~2 L of water
into the room air.

## Ranking

Options: `outside` (score = `today_outdoor_score`) + one per active room
(`room_score`). Indoor rooms get `− indoor_score_bias` for the ranking (not for
the displayed score) so "outside" wins on a tie. Sorted descending.

## Recommendation ("wait" logic)

Laundry must not stay in the machine (musty smell from *Moraxella osloensis*; the
often-quoted "4–5 h" is a rule of thumb without peer review). "Wait" therefore
always means: onto a drying rack.

```
mould across ALL active rooms                   → mold_risk (warning, overrides)
outside >= score_hang, daylight >= 4 h           → hang_outside_now
outside >= score_hang, daylight < 4 h            → hang_outside_later
outside >= 55, daylight >= 3 h                   → outside_marginal
tomorrow >= score_hang and (tomorrow − today) >= wait_delta and no room usable:
    already washed                              → wait_for_tomorrow
    not washed                                  → defer_wash
best room is usable:
    airing helps or no dehumidifier             → room_ventilate  (recommended_room)
    else                                        → room_dehumidify
no room usable:
    dryer_entity set                            → dryer_recommended
    else                                        → best_effort      (least-bad room + warning)
```

## Sources

Full list in the concept document (German). Core:

- German Environment Agency (Umweltbundesamt) – ventilation / mould
- taupunkt-lueftung.de, keller-doktor.de – 5-Kelvin rule
- Fraunhofer IBP / Sedlbauer – isopleths, water activity
- Alduchov & Eskridge 1996 – improved Magnus approximation
- DWD / wetterdienst.de – drying laundry from a scientific perspective
- hackitu.de/drynow – Penman over DWD MOSMIX
- Kubota et al. 2012 (AEM) – *Moraxella osloensis* / 4-methyl-3-hexenoic acid
- HA docs – template blueprints (2024.11), `weather.get_forecasts`
