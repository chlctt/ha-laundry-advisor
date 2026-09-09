# Laundry Advisor / Wäschewetter

Ein Home-Assistant-**Template-Blueprint**, der den **besten Ort** empfiehlt, um
Wäsche zu trocknen – draußen an der Leine, in einem von bis zu fünf Innenräumen,
im Wäschetrockner – oder rät, mit dem Waschen auf morgen zu warten.

Passende Lovelace-Card: **[laundry-advisor-card](https://github.com/chlctt/laundry-advisor-card)**.

> **v0.2** (Branch `v0.2`): mehrere Trockenräume, Ranking, zweisprachig (de/en).
> Details: [`docs/design-v0.2.md`](docs/design-v0.2.md).

---

## Sensor-Ausgabe

Ein Sensor (`sensor.laundry_advisor`): **State** = Empfehlung, alles Weitere als
**Attribute**.

| Wert | Ort |
|---|---|
| Empfehlungs-Zustand | `state` |
| Klartext (lokalisiert) | `attributes.headline` |
| Begründungen (lokalisiert) | `attributes.reasons` |
| Begründungs-Codes (sprachneutral, für die Card) | `attributes.reason_codes` |
| Empfohlener Raum (Name) / Ventilator / Entfeuchter | `attributes.recommended_room` / `_fan` / `_dehumidifier` |
| Outdoor-Score heute / morgen / übermorgen (0–100) | `attributes.outdoor_score` / `_tomorrow` / `_day_after` |
| Bestes Aufhäng-Fenster heute | `attributes.best_window_start_hour` / `_end_hour` |
| Tagesvorschau (bis 6 Tage) | `attributes.forecast_days` |
| Räume, nach Trockeneignung sortiert | `attributes.rooms` |
| Verbleibendes Tageslicht | `attributes.daylight_left_h` |

### Empfehlungs-Zustände

| State | Bedeutung |
|---|---|
| `hang_outside_now` | Jetzt raushängen |
| `hang_outside_later` | Heute noch, aber Fenster knapp |
| `outside_marginal` | Geht raus, aber beobachten |
| `wait_for_tomorrow` | Heute auf den **Ständer**, morgen raus (Wäsche ist schon gewaschen) |
| `defer_wash` | Mit dem **Waschen** auf morgen warten |
| `room_ventilate` | Bester Raum (`recommended_room`) – stoßlüften + Ventilator |
| `room_dehumidify` | Bester Raum – nur mit Entfeuchter (Lüften bringt nichts) |
| `dryer_recommended` | Wäschetrockner (nur wenn `dryer_entity` gesetzt) |
| `best_effort` | Kein Raum unter der Feuchtegrenze, kein Trockner – am wenigsten schlechter Raum + Warnung |
| `mold_risk` | Alle Räume zu feucht – nichts Nasses reinhängen |

### `rooms`-Objekt (je Raum)

```yaml
- name: "Waschkeller"
  score: 29                    # 0–100 Trockeneignung
  status: too_humid            # ok | too_humid | too_cold | mold_risk
  temperature: 20.9
  humidity: 72.0
  dewpoint: 15.6
  vpd: 6.9                     # Sättigungsdefizit hPa
  ventilation_useful: false    # Außenluft absolut trockener (5-K-Regel)?
  has_fan: true
  has_dehumidifier: false
  suitable: false
  mold_risk: false
  recommended: false
```

---

## Installation

1. **Import** (Home Assistant ≥ 2024.11):

   [![Blueprint importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fchlctt%2Fha-laundry-advisor%2Fblob%2Fv0.2%2Fblueprints%2Ftemplate%2Flaundry_advisor.yaml)

2. **Helfer anlegen** (optional): ein `input_boolean` (z. B.
   `input_boolean.waesche_gewaschen`) für `wait_for_tomorrow` vs. `defer_wash`.

3. **Template-Entität per YAML** (Template-Blueprints haben keinen UI-Dialog).
   In `configuration.yaml`:

   ```yaml
   template:
     - use_blueprint:
         path: chilcott/laundry_advisor.yaml
         input:
           weather_entity: weather.itzehoe
           precip_prob_entity: weather.forecast_home
           language: de
           dryer_entity: switch.waschetrockner        # optional
           room_1_name: Waschkeller
           room_1_temp: sensor.waschkeller_temperatur
           room_1_humidity: sensor.waschkeller_luftfeuchte
           room_1_fan: fan.waschkeller_ventilator      # optional
           room_2_name: Dachboden
           room_2_temp: sensor.dachboden_temperatur
           room_2_humidity: sensor.dachboden_luftfeuchte
           already_washed_boolean: input_boolean.waesche_gewaschen
   ```

   Dann *Entwicklerwerkzeuge → YAML → Template-Entitäten neu laden*.

> ⚠️ **Nach einer Blueprint-Änderung: HA neu starten _und danach_
> `template.reload`.** „Template-Entitäten neu laden" allein liest die
> Blueprint-Datei nicht neu ein; ein Neustart tut es, aber die
> trigger-basierte Entity stellt danach oft ihren alten State wieder her und
> rechnet erst beim nächsten Trigger neu – ein `template.reload` unmittelbar
> nach dem Neustart erzwingt die Neuberechnung.

### Migration v0.1 → v0.2

Die Inputs `cellar_temp` / `cellar_humidity` / `cellar_wall_temp` entfallen.
Stattdessen `room_1_name` + `room_1_temp` + `room_1_humidity` setzen (der alte
Keller wird zu „Raum 1"). Das Attribut `cellar` heißt jetzt `rooms` (Liste).

### Datenquellen-Hinweise

- **Primär-Wetter:** jede `weather`-Entität mit stündlicher **und** täglicher
  Vorhersage. Der DWD (`dwd_weather`) liefert zusätzlich `dew_point`,
  `humidity_absolute`, `sun_irradiance`, `fog_probability`.
- **Regenwahrscheinlichkeit:** DWD hat im Stundenmodus keine – dann Met.no
  (`weather.forecast_home`) als `precip_prob_entity`.
- **Jeder aktive Raum braucht Temp + rF.** Ein Raum ohne Namen/Sensoren wird
  ignoriert. Raum 1 ist Pflicht.
- **Außen-Sensoren optional** (Fallback Wetter-Entität).

---

## Feineinstellung

Sektion *Feineinstellung* (eingeklappt). Recherche-Defaults:

| Faktor | Gewicht |
|---|---:|
| Wind | 35 |
| Luftfeuchte / Sättigungsdefizit | 30 |
| Sonne | 20 |
| Temperatur | 15 |

Regen > 0,1 mm/h → Score 0. `indoor_score_bias` (Default 15) zieht Innenräume im
Ranking ab, damit „draußen" bei Gleichstand gewinnt. Raum „nutzbar" ab rF <
`room_rh_max` (65 %) und T ≥ `room_temp_min` (15 °C). Lüften empfohlen, wenn der
Außentaupunkt ≥ `vent_dewpoint_margin` (5 K) unter dem Raumtaupunkt liegt.

Details & Quellen: [`docs/logic.md`](docs/logic.md).

---

## Benachrichtigungen

Beispiel: [`examples/notify_automation.yaml`](examples/notify_automation.yaml) –
Meldung bei Zustandswechsel, schaltet optional Ventilator/Entfeuchter des
empfohlenen Raums (`recommended_fan` / `recommended_dehumidifier`).

---

## Dank / Vorbilder

- [GSW Smart Ventilation Suite](https://community.home-assistant.io/t/gsw-smart-ventilation-suite-absolute-humidity-dew-point-logic/995338)
- [Thermal Comfort](https://github.com/dolezsa/thermal_comfort)
- Forum: *[To line dry or not to line dry?](https://community.home-assistant.io/t/to-line-dry-or-not-to-line-dry/235079)*
- [hackitu.de/drynow](https://www.hackitu.de/drynow/)

## Lizenz

MIT – siehe [LICENSE](LICENSE).
