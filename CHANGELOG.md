# Changelog

Alle nennenswerten Änderungen an diesem Projekt.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/).

## [0.2.0] – unreleased (Branch `v0.2`)

### Added
- **Mehrere Trockenräume** (bis zu 5 Slots, je Name + Temp + Feuchte +
  optional Ventilator + Entfeuchter).
- **Ranking**: „draußen" + jeder Raum werden bewertet; der beste Ort wird
  namentlich empfohlen (`recommended_room`). Attribut `rooms` = sortierte Liste.
- **Zweisprachig**: `language`-Input (de/en) für `headline`/`reasons`;
  `reason_codes` sprachneutral für die Card.
- `dryer_entity`-Input: ohne wird statt „Trockner" der am wenigsten schlechte
  Raum empfohlen (`best_effort`).
- Neue States: `room_ventilate`, `room_dehumidify`, `best_effort`.
- `indoor_score_bias`, `room_rh_max`, `room_temp_min` (ersetzt `cellar_*`).
- `docs/design-v0.2.md`.

### Changed / Breaking
- Inputs `cellar_temp` / `cellar_humidity` / `cellar_wall_temp` **entfallen**.
- Attribut `cellar` **entfällt** → `rooms` (Liste).
- `configuration.yaml`-`use_blueprint` muss angepasst werden (Migration im README).

## [0.1.x]

### Added
- Template-Blueprint (MVP): Outdoor-Score heute/morgen/übermorgen,
  9 Empfehlungs-Zustände, Keller-Bewertung (Taupunkt/Lüften/Schimmel-Guard),
  Tagesvorschau, bestes Zeitfenster – ein Sensor mit Attributen.
- Attribut `outdoor_score_day_after`.
- Kern-Makros `custom_templates/laundry_advisor.jinja`.
- `docs/logic.md`, Beispiel-Notify-Automation.
