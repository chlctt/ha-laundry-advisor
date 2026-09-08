# Changelog

Alle nennenswerten Änderungen an diesem Projekt.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/).

## [Unreleased]

### Added
- Template-Blueprint `blueprints/template/laundry_advisor.yaml` (MVP):
  Outdoor-Score heute/morgen, 9 Empfehlungs-Zustände, Keller-Bewertung
  (Taupunkt/Lüften/Schimmel-Guard), Tagesvorschau, bestes Zeitfenster –
  alles als ein Sensor mit Attributen.
- Kern-Makros `custom_templates/laundry_advisor.jinja` (für die Package-Variante
  und zum Wiederverwenden).
- `docs/logic.md` – Herleitung & Quellen.
- Beispiel-Automation für Benachrichtigung + optionale Keller-Ventilatoren.
