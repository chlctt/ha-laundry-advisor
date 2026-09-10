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

## Bands (outdoor)

- `today_score ≥ score_hang` (70): hang outside
- `score_hang > today_score ≥ score_marginal` (55): `outside_marginal` – still
  recommend outside, keep an eye on it
- `< score_marginal`: indoors

`score_hang` needs ≥ 4 daylight hours left for `hang_outside_now`, ≥ 1 for
`hang_outside_later`; `outside_marginal` needs ≥ 3.

`daylight_left_h` is real hours: the count of remaining daylight forecast
entries is multiplied by the forecast interval derived from two consecutive
`datetime` values, so it is correct for sub-hourly and multi-hourly providers.
For an hourly forecast the two are identical. Note that with a coarse (e.g.
3-hourly) forecast `daylight_left_h` is quantised to multiples of the interval,
so the `≥ 4` / `≥ 3` / `≥ 1` gates effectively round up to the next multiple.

**No unified ranking.** "Outside" enters via these absolute thresholds; the rooms
are only ranked among each other. Whether to fold everything into one ranking is
[#8](https://github.com/chlctt/ha-laundry-advisor/issues/8).

The forecast is assumed **hourly** and precipitation in **mm/h**
([#9](https://github.com/chlctt/ha-laundry-advisor/issues/9)).

## Room assessment

From live sensors (not the forecast), per room:

- Dew point & absolute humidity via Magnus (Alduchov–Eskridge, `b = 17.625`,
  `c = 243.04`; dew-point error ~0.1 °C).
- **Airing worthwhile** when the room has a window/door contact configured *and*
  `outdoor dew point ≤ room dew point − vent_margin` (default 5 K; commercial
  dew-point controllers use 5 K on / 1 K off). A room with no contact configured
  is treated as not ventilatable.
- **Room usable**: RH < `room_rh_max` (65 %) and T ≥ `room_temp_min` (15 °C) and
  no mould guard.
- **Mould guard**: surface RH > 80 %, or the wall is at/below the room dew point.
  Without a wall-temperature sensor the surface RH equals the room RH, so the
  guard is simply `room RH > 80 %`. With a wall sensor the surface RH is
  `RH · E_s(T_room) / E_s(T_wall)` – a cold wall trips the guard at a much lower
  room humidity.
- **Room score** (0–100): `ramp(vpd, 2, 12) × 100` + 10 if a dehumidifier is
  configured + 8 if airing helps + 5 if a fan is configured − 25 if RH ≥
  `room_rh_max`; ~2 at mould risk; clamped.

Background values: the German Environment Agency recommends indoor RH < 60 % (for
cellars); mould on a surface needs sustained > ~80 % RH / aw ≈ 0.8
(Sedlbauer / Fraunhofer IBP isopleth model). One wash load releases ~2 L of water
into the room air.

## Recommendation ("wait" logic)

Laundry must not stay in the machine (musty smell from *Moraxella osloensis*; the
often-quoted "4–5 h" is a rule of thumb without peer review). "Wait" therefore
always means: onto a drying rack.

```
no forecast available                           → unknown (no_forecast)
mould across ALL active rooms                    → mold_risk (warning, overrides)
outside >= score_hang, daylight >= 4 h           → hang_outside_now
outside >= score_hang, daylight >= 1 h           → hang_outside_later
outside >= score_marginal, daylight >= 3 h       → outside_marginal
tomorrow >= score_hang and (tomorrow − today) >= wait_delta and no room usable:
    already washed                              → wait_for_tomorrow
    not washed                                  → defer_wash
best room is usable:
    airing helps                                → room_ventilate  (recommended_room)
    dehumidifier present and room RH >= room_dehumidify_rh (55 %) → room_dehumidify
    else                                        → room_ok         (warm & dry enough)
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
- HA developer docs – config entries / subentries, `weather.get_forecasts`
