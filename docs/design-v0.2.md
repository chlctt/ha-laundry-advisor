# v0.2 – Design

Status: Entwurf, in Umsetzung auf Branch `v0.2`. Review vor Merge.

## Ziele

1. **Mehrere Trockenräume** statt einem festen Keller.
2. **Ranking**: Blueprint bewertet „draußen" + jeden Raum, empfiehlt den **einen besten
   Ort namentlich**. Card zeigt die Rangliste.
3. **Zweisprachig** (de/en): `language`-Input im Blueprint (für Benachrichtigungen),
   Card übersetzt zusätzlich über `hass.language`.
4. Neue Optionen: **Wäschetrockner-Entität**, **pro Raum Ventilator + Entfeuchter**.

## Breaking Changes ggü. v0.1

- Inputs `cellar_temp` / `cellar_humidity` / `cellar_wall_temp` **entfallen** →
  ersetzt durch 5 Raum-Slots.
- Attribut `cellar` (Objekt) **entfällt** → ersetzt durch `rooms` (Liste).
- Neue States (s. u.). `outdoor_score*`, `forecast_days`, `best_window_*` bleiben.
- `configuration.yaml`-`use_blueprint` muss mitgezogen werden (Migrationshinweis im
  README).

## Inputs

### Sektion „Datenquellen"
| Input | Pflicht | Default |
|---|---|---|
| `weather_entity` | ✅ | – |
| `precip_prob_entity` | – | – |
| `outdoor_temp` / `outdoor_humidity` | – | aus Wetter-Entität |
| `already_washed_boolean` | – | – |

### Sektion „Sprache & Ausgabe"
| Input | Default |
|---|---|
| `language` (select `de`/`en`) | `de` |
| `dryer_entity` (optional) | – |

`dryer_entity` gesetzt → State `dryer_recommended` möglich. Nicht gesetzt → statt
Trockner wird der **am wenigsten schlechte Raum** empfohlen (`best_effort`).

### Sektionen „Raum 1"…„Raum 5" (Raum 2–5 collapsed)
| Input | Pflicht für aktiven Raum |
|---|---|
| `room_N_name` (text) | ✅ (leer = Slot ungenutzt) |
| `room_N_temp` (sensor/temperature) | ✅ |
| `room_N_humidity` (sensor/humidity) | ✅ |
| `room_N_fan` (entity, optional) | – |
| `room_N_dehumidifier` (entity, optional) | – |

Ein Raum zählt nur, wenn `name` + `temp` + `humidity` gesetzt sind.

### Sektion „Feineinstellung" (collapsed)
`block_hours`, `day_start_hour`, `day_end_hour`, `score_hang`, `score_marginal`,
`wait_delta`, `weight_wind/humidity/sun/temperature`,
`room_rh_max` (65), `room_temp_min` (15), `vent_dewpoint_margin` (5),
`indoor_score_bias` (Abschlag Innenräume ggü. draußen, Default 15 – „draußen ist
präferiert").

## Raum-Bewertung (je Raum, 0–100)

Aus Live-Sensoren:

```
td_room      = Taupunkt(T_room, rh_room)
ah_room      = abs. Feuchte
vent_useful  = td_outdoor <= td_room - vent_dewpoint_margin
vpd_room     = E_s(T_room) * (1 - rh_room/100)          # Trocken-Treiber
mold_risk    = rh_room > 80
suitable     = rh_room < room_rh_max AND T_room >= room_temp_min AND not mold_risk

room_score:
  start = ramp(vpd_room, 2, 12) * 100          # 0 bei 2 hPa, 100 bei 12 hPa
  + 10  wenn Entfeuchter vorhanden
  + 8   wenn vent_useful (Lüften bringt was)
  + 5   wenn Ventilator vorhanden
  − 25  wenn rh_room >= room_rh_max
  − 100 (→ ~0) wenn mold_risk
  geklemmt 0..100
```

## Ranking & Empfehlung

Optionsliste: `outside` (Score = `today_outdoor_score`) + je aktiver Raum
(`room_score`). Innenräume bekommen `− indoor_score_bias` fürs Ranking (nicht für
die Anzeige), damit „draußen" bei Gleichstand gewinnt.

Sortierung absteigend. Dann:

```
mold über ALLE aktiven Räume            → mold_risk (Warnung)
outside_score >= score_hang, Tageslicht >= 4h   → hang_outside_now
outside_score >= score_hang, Tageslicht < 4h    → hang_outside_later
outside_score >= 55, Tageslicht >= 3h           → outside_marginal
tomorrow >= score_hang und (tomorrow − today) >= wait_delta:
    schon gewaschen                     → wait_for_tomorrow
    nicht gewaschen, kein Raum suitable  → defer_wash
bester Raum ist suitable:
    vent_useful                         → room_ventilate   (recommended_room = Name)
    sonst, Entfeuchter vorhanden        → room_dehumidify
    sonst                               → room_ventilate   (mit Hinweis „stoßlüften")
kein Raum suitable:
    dryer_entity gesetzt                → dryer_recommended
    sonst                               → best_effort       (bester Raum + Warnung)
```

## States (Enum)

`hang_outside_now`, `hang_outside_later`, `outside_marginal`,
`wait_for_tomorrow`, `defer_wash`,
`room_ventilate`, `room_dehumidify`,
`dryer_recommended`, `best_effort`, `mold_risk`, `unknown`

## Attribute des Sensors

```yaml
state: <einer der States>
attributes:
  language: de
  headline: "<lokalisiert>"
  reasons: ["<lokalisiert>", ...]
  reason_codes:                       # für die Card-i18n
    - {code: outdoor_rain, ...}
  recommended_room: "Waschkeller"     # oder null (draußen/Trockner)
  recommended_fan: fan.waschkeller    # Entität des empfohlenen Raums, oder null
  recommended_dehumidifier: null
  outdoor_score: 42
  outdoor_score_tomorrow: 68
  outdoor_score_day_after: 55
  forecast_days: [...]
  best_window_start_hour: 11
  best_window_end_hour: 16
  daylight_left_h: 5
  rooms:                              # nach Score sortiert
    - name: "Waschkeller"
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
      recommended: false
```

## i18n

Blueprint: interne Tabelle `T[language]` mit `headlines` + `reason`-Vorlagen.
`language`-Input steuert `headline`/`reasons`. `reason_codes` bleibt sprachneutral.

Card: `src/localize/{de,en}.json`, Auswahl über `hass.locale.language` bzw.
`hass.language`, Fallback `en`. Übersetzt States, Status-Chips, `reason_codes`.

## Card v0.2

- 3 Score-Ringe bleiben (Heute/Morgen/Übermorgen).
- Neue **Raum-Liste**: pro Raum eine Zeile mit Name, Score, Status-Chip,
  Lüften-/Entfeuchter-Hinweis; der empfohlene Raum ist hervorgehoben.
- `cellar`-Zeile entfällt.
- Config: `show_rooms` statt `show_cellar`.
