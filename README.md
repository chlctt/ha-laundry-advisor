# Laundry Advisor / Wäschewetter

Ein Home-Assistant-**Template-Blueprint**, der entscheidet, ob Wäsche **draußen**,
**im Keller** oder **gar nicht heute** getrocknet werden sollte – und ob es sich
lohnt, mit dem Waschen auf morgen zu warten.

Passende Lovelace-Card: **[laundry-advisor-card](https://github.com/chlctt/laundry-advisor-card)**.

> Status: **MVP / in Entwicklung.** Zuerst auf eine konkrete Instanz
> (DWD `weather.itzehoe` + Waschkeller-Sensoren) zugeschnitten, danach
> generalisiert.

---

## Was es macht

Der Blueprint erzeugt **einen** Sensor (`sensor.laundry_advisor`), dessen **State**
die Empfehlung ist und dessen **Attribute** alle Detailwerte liefern:

| Wert | Ort |
|---|---|
| Empfehlungs-Zustand | `state` |
| Klartext-Satz | `attributes.headline` |
| Begründungen | `attributes.reasons` |
| Outdoor-Score heute / morgen / übermorgen (0–100) | `attributes.outdoor_score` / `_tomorrow` / `_day_after` |
| Bestes Aufhäng-Fenster heute | `attributes.best_window_start_hour` / `_end_hour` |
| Tagesvorschau (bis 6 Tage) | `attributes.forecast_days` |
| Keller-Bewertung | `attributes.cellar` (Objekt) |
| Verbleibendes Tageslicht | `attributes.daylight_left_h` |

### Empfehlungs-Zustände

| State | Bedeutung |
|---|---|
| `hang_outside_now` | Jetzt raushängen |
| `hang_outside_later` | Heute noch, aber Fenster knapp (Tau/Nebel abwarten, ggf. morgen früh) |
| `outside_marginal` | Geht raus, aber beobachten |
| `wait_for_tomorrow` | Heute auf den **Wäscheständer**, morgen raus (Wäsche ist schon gewaschen) |
| `defer_wash` | Mit dem **Waschen** auf morgen warten |
| `cellar_ok` | Keller – mit Fensterlüftung + Ventilator |
| `cellar_dehumidifier` | Keller – nur mit Entfeuchter (Lüften bringt nichts) |
| `dryer_recommended` | Wäschetrockner / bestbelüfteter Wohnraum |
| `mold_risk` | Warnung: Keller aktuell zu feucht, nichts Nasses reinhängen |

---

## Installation

1. **Import** (Home Assistant ≥ 2024.11):

   [![Blueprint importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fchlctt%2Fha-laundry-advisor%2Fblob%2Fmain%2Fblueprints%2Ftemplate%2Flaundry_advisor.yaml)

   oder manuell: *Einstellungen → Automatisierungen & Szenen → Blueprints →
   Blueprint importieren* und die Roh-URL von
   [`blueprints/template/laundry_advisor.yaml`](blueprints/template/laundry_advisor.yaml)
   einfügen.

2. **Helfer anlegen** (optional, empfohlen): ein `input_boolean`, z. B.
   `input_boolean.waesche_gewaschen`, das anzeigt, ob gerade Wäsche gewaschen
   wurde. Steuert `wait_for_tomorrow` vs. `defer_wash`.

3. **Template-Entität aus dem Blueprint erstellen** – nur per YAML
   (Template-Blueprints haben keinen UI-Dialog). In `configuration.yaml`:

   ```yaml
   template:
     - use_blueprint:
         path: chilcott/laundry_advisor.yaml
       input:
         weather_entity: weather.itzehoe
         precip_prob_entity: weather.forecast_home
         cellar_temp: sensor.umgebungssensor_waschkeller_temperature
         cellar_humidity: sensor.umgebungssensor_waschkeller_humidity
         already_washed_boolean: input_boolean.waesche_gewaschen
   ```

   Dann *Entwicklerwerkzeuge → YAML → Template-Entitäten neu laden* (oder Neustart).

### Datenquellen-Hinweise

- **Primär-Wetter:** jede `weather`-Entität mit stündlicher **und** täglicher
  Vorhersage. Der DWD (`dwd_weather`, FL550) liefert zusätzlich `dew_point`,
  `humidity_absolute`, `sun_irradiance`, `fog_probability` – die werden genutzt,
  wenn vorhanden.
- **Regenwahrscheinlichkeit:** der DWD liefert im Stundenmodus **keine**
  `precipitation_probability`. Dann eine zweite Entität (z. B. Met.no
  `weather.forecast_home`) als `precip_prob_entity` angeben – sie wird
  stundenweise gematcht.
- **Keller-Sensoren sind Pflicht.** Ohne Temp + rF im Keller keine
  Keller-Empfehlung.
- **Außen-Sensoren optional.** Fallback ist die Wetter-Entität.
- Der DWD-Wind ist relativ grob quantisiert; wer einen echten Windmesser oder
  eine feiner auflösende Quelle hat, sollte diese als Primär-Wetter oder
  (später) als eigenen Wind-Input nutzen.

---

## Feineinstellung

Alle Schwellen und Gewichte sind Blueprint-Inputs (Sektion *Feineinstellung*,
eingeklappt). Defaults aus der Recherche:

| Faktor | Gewicht |
|---|---:|
| Wind | 35 |
| Luftfeuchte / Sättigungsdefizit | 30 |
| Sonne (Einstrahlung / Bewölkung) | 20 |
| Temperatur | 15 |

Regen > 0,1 mm/h ist ein hartes K.-o. (Score 0), Regenwahrscheinlichkeit > 60 %
multipliziert mit 0,4, Böen > 45 km/h deckeln den Score bei 40. Bewertet wird der
Mittelwert des besten zusammenhängenden Fensters (Default 5 h) im Tageslicht.

Keller: Lüften wird empfohlen, wenn der Außentaupunkt ≥ 5 K unter dem
Keller-Taupunkt liegt; „nutzbar" ab < 65 % rF und ≥ 15 °C; Schimmel-Guard bei
geschätzter Oberflächenfeuchte > 80 % oder Wandtemperatur ≤ Raumtaupunkt.

Details & Quellen: [`docs/logic.md`](docs/logic.md).

---

## Benachrichtigungen

Beispiel-Automation: [`examples/notify_automation.yaml`](examples/notify_automation.yaml).
Optional schaltet sie auch Abluft- und Raumventilator im Keller.

---

## Dank / Vorbilder

- [GSW Smart Ventilation Suite](https://community.home-assistant.io/t/gsw-smart-ventilation-suite-absolute-humidity-dew-point-logic/995338) – Taupunkt-Lüftungslogik
- [Thermal Comfort](https://github.com/dolezsa/thermal_comfort) – Taupunkt-/Absolutfeuchte-Sensoren
- Forum: *[To line dry or not to line dry?](https://community.home-assistant.io/t/to-line-dry-or-not-to-line-dry/235079)*, *[Laundry Drying Outside / Drying Index](https://community.home-assistant.io/t/laundry-drying-outside-drying-index-schedule/149311)*
- [hackitu.de/drynow](https://www.hackitu.de/drynow/) – Penman auf DWD-MOSMIX

## Lizenz

MIT – siehe [LICENSE](LICENSE).
