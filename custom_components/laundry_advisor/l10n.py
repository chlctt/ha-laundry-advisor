"""Localised headline + reason text for the advisor sensor.

The entity *state* is translated by Home Assistant via translations/*.json. The
free-text `headline` and `reasons` attributes are built here so notifications are
localised too. English is the fallback.
"""

from __future__ import annotations

_HEADLINES: dict[str, dict[str, str]] = {
    "en": {
        "hang_outside_now": "Hang it outside – good drying weather today.",
        "hang_outside_later": "Still possible today, but the window is tight.",
        "outside_marginal": "Outside works, but keep an eye on the sky.",
        "wait_for_tomorrow": "Put it on a rack today – tomorrow is clearly better outside.",
        "defer_wash": "Worth waiting until tomorrow to wash.",
        "room_ok": "Best spot: {room} – warm and dry enough; a fan speeds it up.",
        "room_ventilate": "Best spot: {room} – air it out and run a fan.",
        "room_dehumidify": "Best spot: {room} – use a dehumidifier (airing does nothing now).",
        "dryer_recommended": "No good drying spot – use the tumble dryer.",
        "best_effort": "No really good spot. Best bet: {room} – ventilate well there.",
        "mold_risk": "Warning: every room is too humid – do not hang anything wet.",
        "unknown": "No assessment possible yet.",
    },
    "de": {
        "hang_outside_now": "Raus damit – heute trocknet die Wäsche draußen gut.",
        "hang_outside_later": "Heute noch möglich, aber das Fenster ist knapp.",
        "outside_marginal": "Draußen geht, aber behalte den Himmel im Auge.",
        "wait_for_tomorrow": "Heute auf den Ständer – morgen wird es draußen deutlich besser.",
        "defer_wash": "Mit dem Waschen bis morgen warten lohnt sich.",
        "room_ok": "Bester Ort: {room} – warm und trocken genug, ein Ventilator beschleunigt.",
        "room_ventilate": "Bester Ort: {room} – Fenster stoßlüften und Ventilator an.",
        "room_dehumidify": "Bester Ort: {room} – mit Entfeuchter (Lüften bringt gerade nichts).",
        "dryer_recommended": "Kein guter Trockenort – ab in den Wäschetrockner.",
        "best_effort": "Kein wirklich guter Ort. Am ehesten: {room} – dort gut lüften.",
        "mold_risk": "Achtung: alle Räume zu feucht – nichts Nasses reinhängen.",
        "unknown": "Noch keine Bewertung möglich.",
    },
}

_REASONS: dict[str, dict[str, str]] = {
    "en": {
        "outdoor_rain": "Rain expected – outside is out.",
        "outdoor_good": "Outdoor score today {s}.",
        "outdoor_weak": "Outdoor score today only {s}.",
        "tomorrow_better": "Tomorrow clearly better ({t} vs {d}).",
        "room_best": "{n}: best indoor room (score {s}).",
        "room_too_humid": "{n} at {rh}% RH – above the limit.",
        "room_dry_enough": "{n} at {rh}% RH is dry enough.",
        "vent_useful": "Outdoor air is drier – airing helps.",
        "vent_useless": "Outdoor air not drier – airing does nothing.",
        "no_room": "No indoor room below the humidity limit.",
        "no_dryer": "No tumble dryer configured.",
        "no_forecast": "No weather forecast available.",
        "mold": "{n}: mould risk (RH above 80%).",
    },
    "de": {
        "outdoor_rain": "Regen erwartet – draußen fällt aus.",
        "outdoor_good": "Outdoor-Score heute {s}.",
        "outdoor_weak": "Outdoor-Score heute nur {s}.",
        "tomorrow_better": "Morgen deutlich besser ({t} statt {d}).",
        "room_best": "{n}: bester Innenraum (Score {s}).",
        "room_too_humid": "{n} bei {rh}% rF – über der Grenze.",
        "room_dry_enough": "{n} bei {rh}% rF ist trocken genug.",
        "vent_useful": "Außenluft ist trockener – Lüften hilft.",
        "vent_useless": "Außenluft nicht trockener – Lüften bringt nichts.",
        "no_room": "Kein Innenraum unter der Feuchtegrenze.",
        "no_dryer": "Kein Wäschetrockner konfiguriert.",
        "no_forecast": "Keine Wettervorhersage verfügbar.",
        "mold": "{n}: Schimmelgefahr (rF über 80%).",
    },
}


def _lang(language: str | None) -> str:
    code = (language or "en").lower().split("-")[0]
    return code if code in _HEADLINES else "en"


def headline(language: str | None, state: str, room: str | None) -> str:
    tbl = _HEADLINES[_lang(language)]
    text = tbl.get(state) or _HEADLINES["en"].get(state, "")
    if "{room}" in text:
        return text.format(room=room or "").replace("  ", " ").strip()
    return text


def reasons(language: str | None, codes: list[dict]) -> list[str]:
    tbl = _REASONS[_lang(language)]
    out: list[str] = []
    for c in codes:
        code = c.get("code", "")
        tmpl = tbl.get(code) or _REASONS["en"].get(code, code)
        out.append(
            tmpl.format(
                s=c.get("s", ""),
                t=c.get("t", ""),
                d=c.get("d", ""),
                n=c.get("n", ""),
                rh=c.get("rh", ""),
            )
        )
    return out
