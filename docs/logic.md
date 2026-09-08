# Logik & Herleitung

## Outdoor-Score (0–100)

Pro Vorhersagestunde berechnet, dann Mittelwert des **besten zusammenhängenden
Fensters** (Default 5 h) innerhalb des Tageslichts (lokale Stunde
`day_start_hour`…`day_end_hour`). Gibt es weniger Tageslichtstunden als das
Fenster, greift ein Faktor 0,6.

### Harte Gates (Stunde → 0)
- Niederschlag > 0,1 mm/h

### Weiche Multiplikatoren
- Regenwahrscheinlichkeit > 60 % → × 0,4; > 40 % → × 0,7
- Windböen > 45 km/h → Score-Deckel 40

### Teil-Scores (0–1, gewichtet)

| Faktor | Gewicht | Kurve |
|---|---:|---|
| Wind | 35 | 0 bei ≤ 3 km/h, 1 im Band 12–25 km/h, fällt auf 0 bei 40 km/h |
| Luftfeuchte / VPD | 30 | schlechterer Wert aus rF-Rampe (1 bei ≤ 55 %, 0 bei 90 %) und Taupunktspread (1 bei ≥ 6 K, 0 bei ≤ 2 K) |
| Sonne | 20 | Einstrahlung `sun_irradiance` (0 bei 20 W/m², 1 bei 450) – sonst `1 − Bewölkung/100` |
| Temperatur | 15 | 0 bei ≤ 5 °C, 1 bei ≥ 20 °C |

**Begründung** (aus Recherche + Verifikation): Trocknen nasser Textilien ist ein
Grenzschicht-Stoffübergang; Luftbewegung und das Sättigungsdefizit (Temperatur
*und* Feuchte gemeinsam) treiben es. Wind dominiert v. a. im Schatten/bei
bedecktem Himmel – in praller Sonne kann Strahlung bei dünnem/dunklem Stoff
ähnlich stark wirken, deshalb ist der Sonnen-Term nicht vernachlässigbar. Ein
Penman-Ansatz nähert die erste (konstante) Trocknungsphase; gegen Ende gilt er
nicht mehr. Regen macht Trocknen unmöglich → hartes Gate.

## Bänder

- ≥ 70: raushängen
- 45–69: geht, beobachten
- < 45: Keller

## Keller-Bewertung

Aus Live-Sensoren (nicht aus der Vorhersage):

- Taupunkt & absolute Feuchte via Magnus (Alduchov–Eskridge, `b = 17.625`,
  `c = 243.04`; Taupunktfehler ~0,1 °C).
- **Lüften sinnvoll**, wenn `Außentaupunkt ≤ Keller-Taupunkt − vent_margin`
  (Default 5 K; kommerzielle Taupunktsteuerungen nutzen 5 K EIN / 1 K AUS).
- **Keller nutzbar**: rF < `cellar_rh_max` (65 %) und T ≥ `cellar_temp_min`
  (15 °C) und kein Schimmel-Guard.
- **Oberflächenfeuchte** (falls Wandsensor): `rF_wand = rF_raum ·
  E_s(T_raum) / E_s(T_wand)`, gedeckelt 100 %. Ohne Wandsensor = Raumfeuchte.
- **Schimmel-Guard**: `rF_wand > 80 %` oder `T_wand ≤ Raumtaupunkt`.

Zielwerte-Hintergrund: Umweltbundesamt empfiehlt Raum-rF < 60 % (Keller);
Schimmel an einer Oberfläche braucht anhaltend > ~80 % rF / aw ≈ 0,8
(Sedlbauer/Fraunhofer-IBP-Isoplethenmodell). Eine Waschladung gibt ~2 l Wasser
an die Raumluft ab.

## „Warten"-Entscheidung

Wäsche darf nicht in der Maschine bleiben (Muffelgeruch durch *Moraxella
osloensis*; die oft genannten „4–5 h" sind eine Faustregel ohne Peer-Review).
„Warten" heißt daher immer: auf den Wäscheständer.

```
heute >= score_hang und Tageslicht >= 4 h        → hang_outside_now
heute >= score_hang und Tageslicht < 4 h         → hang_outside_later
heute >= 55 und Tageslicht >= 3 h                 → outside_marginal
morgen >= score_hang und (morgen − heute) >= wait_delta:
    schon gewaschen                              → wait_for_tomorrow
    nicht gewaschen und Keller ungünstig         → defer_wash
    sonst                                        → cellar_ok / cellar_dehumidifier
Keller nutzbar und Außenluft trockener           → cellar_ok
Keller nutzbar, Außenluft nicht trockener        → cellar_dehumidifier
sonst                                            → dryer_recommended
Schimmel-Guard aktiv                             → mold_risk  (schlägt alles)
```

## Quellen

Vollständige Quellenliste im [Konzeptdokument](https://github.com/chlctt/ha-laundry-advisor)
bzw. `homelab/docs/projects/waeschewetter-konzept.md`. Kern:

- Umweltbundesamt – Lüften / Schimmel
- taupunkt-lueftung.de, keller-doktor.de – 5-Kelvin-Regel
- Fraunhofer IBP / Sedlbauer – Isoplethen, aw-Wert
- Alduchov & Eskridge 1996 – verbesserte Magnus-Approximation
- DWD / wetterdienst.de – Wäschetrocknen aus wissenschaftlicher Sicht
- hackitu.de/drynow – Penman auf DWD-MOSMIX
- Kubota et al. 2012 (AEM) – *Moraxella osloensis* / 4-Methyl-3-Hexensäure
- HA-Doku – Template-Blueprints (2024.11), `weather.get_forecasts`
