"""Pure drying-advice logic. No Home Assistant imports – fully unit-testable.

See docs/logic.md for the derivation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

_UTC = UTC

# --- Magnus / Alduchov–Eskridge (dew-point error ~0.1 K over -40..+50 C) -------
_A = 6.1094
_B = 17.625
_C = 243.04

STATES = (
    "hang_outside_now",
    "hang_outside_later",
    "outside_marginal",
    "wait_for_tomorrow",
    "defer_wash",
    "room_ok",
    "room_ventilate",
    "room_dehumidify",
    "dryer_recommended",
    "best_effort",
    "mold_risk",
    "unknown",
)

ROOM_STATUSES = ("ok", "too_humid", "too_cold", "mold_risk", "no_data")


def sat_vp(t: float) -> float:
    """Saturation vapour pressure over water, hPa."""
    return _A * math.exp(_B * t / (_C + t))


def _clamp_rh(rh: float) -> float:
    """Keep a relative humidity in a physical 0.5..100 % range."""
    return min(max(rh, 0.5), 100.0)


def dew_point(t: float, rh: float) -> float:
    """Dew point in °C from temperature (°C) and relative humidity (%)."""
    rh = _clamp_rh(rh)
    gamma = math.log(rh / 100.0) + _B * t / (_C + t)
    return _C * gamma / (_B - gamma)


def abs_humidity(t: float, rh: float) -> float:
    """Absolute humidity in g/m³."""
    return 216.7 * (rh / 100.0 * sat_vp(t)) / (t + 273.15)


def vpd(t: float, rh: float) -> float:
    """Vapour-pressure deficit in hPa – the drying driver."""
    return sat_vp(t) * (1.0 - rh / 100.0)


def ramp(x: float, x0: float, x1: float) -> float:
    """0 at x0, 1 at x1 (x1 may be < x0 for a falling ramp), clamped to [0, 1]."""
    return max(0.0, min(1.0, (x - x0) / (x1 - x0)))


# --- data --------------------------------------------------------------------
@dataclass(slots=True)
class Weights:
    wind: float = 35.0
    humidity: float = 30.0
    sun: float = 20.0
    temperature: float = 15.0


@dataclass(slots=True)
class Config:
    weights: Weights = field(default_factory=Weights)
    block_hours: int = 5
    day_start: int = 8
    day_end: int = 20
    score_hang: float = 70.0
    score_marginal: float = 55.0
    wait_delta: float = 20.0
    room_rh_max: float = 65.0
    room_temp_min: float = 15.0
    room_dehumidify_rh: float = 55.0
    vent_margin: float = 5.0


@dataclass(slots=True)
class HourFc:
    dt: datetime  # timezone-aware, local
    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    wind_gust_speed: float | None = None
    cloud_coverage: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    sun_irradiance: float | None = None
    # filled in by evaluate()
    score: float = 0.0
    is_day: bool = False


@dataclass(slots=True)
class RoomState:
    name: str
    temp: float | None
    humidity: float | None
    wall_temp: float | None = None
    fan_entity: str | None = None
    dehumidifier_entity: str | None = None
    # A window/door contact means the room can be aired. Without one the room is
    # treated as not ventilatable (no room_ventilate, no airing bonus).
    window_entity: str | None = None
    window_open: bool | None = None  # resolved contact state; None = unknown


@dataclass(slots=True)
class Outdoor:
    temp: float | None = None
    humidity: float | None = None


@dataclass(slots=True)
class RoomScore:
    name: str
    score: float
    status: str
    temperature: float | None
    humidity: float | None
    dewpoint: float | None
    abs_humidity: float | None
    vpd: float | None
    ventilation_useful: bool
    has_window: bool
    window_open: bool | None
    has_fan: bool
    has_dehumidifier: bool
    fan: str | None
    dehumidifier: str | None
    surface_rh_estimate: float | None
    suitable: bool
    mold_risk: bool
    recommended: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "score": self.score,
            "status": self.status,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "dewpoint": self.dewpoint,
            "abs_humidity": self.abs_humidity,
            "vpd": self.vpd,
            "ventilation_useful": self.ventilation_useful,
            "has_window": self.has_window,
            "window_open": self.window_open,
            "has_fan": self.has_fan,
            "has_dehumidifier": self.has_dehumidifier,
            "fan": self.fan,
            "dehumidifier": self.dehumidifier,
            "surface_rh_estimate": self.surface_rh_estimate,
            "suitable": self.suitable,
            "mold_risk": self.mold_risk,
            "recommended": self.recommended,
        }


@dataclass(slots=True)
class Result:
    state: str
    reason_codes: list[dict]
    recommended_room: str | None
    recommended_fan: str | None
    recommended_dehumidifier: str | None
    outdoor_score: float
    outdoor_score_tomorrow: float
    outdoor_score_day_after: float
    daylight_left_h: float
    best_window_start_hour: int | None
    best_window_end_hour: int | None
    forecast_days: list[dict]
    rooms: list[dict]


# --- scoring ---------------------------------------------------------------
def hour_score(h: HourFc, w: Weights, interval_h: float = 1.0) -> float:
    """Outdoor drying score for one forecast hour, 0..100 (0 = rain gate)."""
    precip = (h.precipitation or 0.0) / max(interval_h, 0.01)
    if precip > 0.1:
        return 0.0
    temp = h.temperature if h.temperature is not None else 10.0
    rh = h.humidity if h.humidity is not None else 80.0
    wind = h.wind_speed or 0.0
    # a missing gust must not trigger the blow-off cap
    gust = h.wind_gust_speed if h.wind_gust_speed is not None else 0.0
    cloud = h.cloud_coverage if h.cloud_coverage is not None else 50.0
    pp = h.precipitation_probability
    irr = h.sun_irradiance

    s_wind = min(ramp(wind, 3, 12), ramp(wind, 40, 25))
    spread = temp - dew_point(temp, rh)
    s_hum = min(ramp(rh, 90, 55), ramp(spread, 2, 6))
    s_sun = ramp(irr, 20, 450) if (irr is not None and irr >= 0) else (1.0 - cloud / 100.0)
    s_temp = ramp(temp, 5, 20)

    wsum = max(w.wind + w.humidity + w.sun + w.temperature, 1.0)
    base = (
        (w.wind * s_wind + w.humidity * s_hum + w.sun * s_sun + w.temperature * s_temp)
        / wsum
        * 100.0
    )

    if pp is not None and pp > 60:
        base *= 0.4
    elif pp is not None and pp > 40:
        base *= 0.7

    if gust > 45:
        base = min(base, 40.0)
    return round(max(base, 0.0), 1)


def _forecast_interval_h(hours: list[HourFc]) -> float:
    """Median spacing of the forecast in hours (default 1.0)."""
    if len(hours) < 2:
        return 1.0
    deltas = sorted(
        (hours[i + 1].dt - hours[i].dt).total_seconds() / 3600.0
        for i in range(len(hours) - 1)
        if (hours[i + 1].dt - hours[i].dt).total_seconds() > 0
    )
    return deltas[len(deltas) // 2] if deltas else 1.0


def _is_day(h: HourFc, cfg: Config) -> bool:
    return cfg.day_start <= h.dt.hour < cfg.day_end


def best_block(hours: list[HourFc], block_hours: int) -> tuple[float, tuple[int, int] | None]:
    """Mean score of the best contiguous daylight window, and its (start, end) hour.

    ``block_hours`` is wall-clock hours. The spacing is taken from *this day's*
    own daylight entries, so a regularly 3-hourly day is fine – only a genuinely
    missing entry (a gap larger than 1.5x the day's own step) breaks a window.
    Only daylight hours (``is_day``) are considered. The end hour is exclusive
    and may be 24 (= end of day).
    """
    day = sorted((h for h in hours if h.is_day), key=lambda h: h.dt)
    if not day:
        return 0.0, None
    steps = sorted(
        (day[k + 1].dt - day[k].dt).total_seconds() / 3600.0
        for k in range(len(day) - 1)
        if (day[k + 1].dt - day[k].dt).total_seconds() > 0
    )
    step_h = steps[len(steps) // 2] if steps else 1.0
    win = max(1, min(int(block_hours / max(step_h, 0.01) + 0.5), len(day)))
    label_h = max(1, round(step_h))
    best_v = 0.0
    best_win: tuple[int, int] | None = None
    for i in range(len(day) - win + 1):
        seg = day[i : i + win]
        gaps = [(seg[k + 1].dt - seg[k].dt).total_seconds() / 3600.0 for k in range(len(seg) - 1)]
        if gaps and max(gaps) > step_h * 1.5:
            continue  # a missing forecast entry – the window label would lie
        mean = sum(h.score for h in seg) / win
        if mean > best_v:
            best_v = mean
            best_win = (seg[0].dt.hour, min(seg[-1].dt.hour + label_h, 24))
    daylight_h = len(day) * step_h
    pen = 0.6 if daylight_h < min(block_hours, 4) else 1.0
    return round(best_v * pen, 1), best_win


def room_score(r: RoomState, outdoor_dew: float | None, cfg: Config) -> RoomScore:
    has_fan = r.fan_entity is not None
    has_deh = r.dehumidifier_entity is not None
    has_window = r.window_entity is not None
    if r.temp is None or r.humidity is None:
        # keep the configured room visible (as "no data") instead of dropping it
        return RoomScore(
            name=r.name,
            score=0.0,
            status="no_data",
            temperature=None if r.temp is None else round(r.temp, 1),
            humidity=None if r.humidity is None else round(_clamp_rh(r.humidity), 1),
            dewpoint=None,
            abs_humidity=None,
            vpd=None,
            ventilation_useful=False,
            has_window=has_window,
            window_open=r.window_open,
            has_fan=has_fan,
            has_dehumidifier=has_deh,
            fan=r.fan_entity if has_fan else None,
            dehumidifier=r.dehumidifier_entity if has_deh else None,
            surface_rh_estimate=None,
            suitable=False,
            mold_risk=False,
        )
    rh = _clamp_rh(r.humidity)  # a sensor reporting > 100 % must not break the maths
    td = dew_point(r.temp, rh)
    ah = abs_humidity(r.temp, rh)
    v = vpd(r.temp, rh)
    # airing only helps if the room can be aired AND the outdoor air is drier
    vent = has_window and outdoor_dew is not None and outdoor_dew <= td - cfg.vent_margin

    if r.wall_temp is not None:
        surf_rh = min(rh * sat_vp(r.temp) / sat_vp(r.wall_temp), 100.0)
    else:
        surf_rh = rh
    mold = surf_rh > 80.0 or (r.wall_temp is not None and r.wall_temp <= td)
    suitable = rh < cfg.room_rh_max and r.temp >= cfg.room_temp_min and not mold

    sc = ramp(v, 2, 12) * 100.0
    sc += (10 if has_deh else 0) + (8 if vent else 0) + (5 if has_fan else 0)
    sc -= 25 if rh >= cfg.room_rh_max else 0
    if mold:
        sc = 2.0
    sc = round(max(0.0, min(100.0, sc)), 1)

    status = (
        "mold_risk"
        if mold
        else "too_humid"
        if rh >= cfg.room_rh_max
        else "too_cold"
        if r.temp < cfg.room_temp_min
        else "ok"
    )
    return RoomScore(
        name=r.name,
        score=sc,
        status=status,
        temperature=round(r.temp, 1),
        humidity=round(rh, 1),
        dewpoint=round(td, 2),
        abs_humidity=round(ah, 2),
        vpd=round(v, 1),
        ventilation_useful=vent,
        has_window=has_window,
        window_open=r.window_open,
        has_fan=has_fan,
        has_dehumidifier=has_deh,
        fan=r.fan_entity if has_fan else None,
        dehumidifier=r.dehumidifier_entity if has_deh else None,
        surface_rh_estimate=round(surf_rh, 1),
        suitable=suitable,
        mold_risk=mold,
    )


def evaluate(
    *,
    hourly: list[HourFc],
    daily: list[HourFc],
    prob: list[HourFc],
    rooms: list[RoomState],
    outdoor: Outdoor,
    cfg: Config,
    now: datetime,
    washed: bool,
    has_dryer: bool,
) -> Result:
    """Run the full advice. ``daily`` is reserved – not used yet.

    Does not mutate the input lists – it works on copies.
    """
    interval_h = _forecast_interval_h(hourly)

    def _hour_key(dt: datetime) -> datetime:
        return dt.astimezone(_UTC).replace(minute=0, second=0, microsecond=0)

    prob_by_hour = {_hour_key(p.dt): p for p in prob}

    # score every hour on a private copy, group by local date
    by_date: dict[str, list[HourFc]] = {}
    for src in hourly:
        h = replace(src)
        if h.precipitation_probability is None and (p := prob_by_hour.get(_hour_key(h.dt))):
            h.precipitation_probability = p.precipitation_probability
        h.score = hour_score(h, cfg.weights, interval_h)
        h.is_day = _is_day(h, cfg)
        by_date.setdefault(h.dt.strftime("%Y-%m-%d"), []).append(h)

    def day_hours(date_str: str) -> list[HourFc]:
        return [h for h in by_date.get(date_str, []) if h.is_day]

    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (now + timedelta(days=2)).strftime("%Y-%m-%d")

    # one best_block per date, reused everywhere
    blocks: dict[str, tuple[float, tuple[int, int] | None]] = {
        d: best_block(day_hours(d), cfg.block_hours) for d in sorted(by_date)
    }

    def score_of(date_str: str) -> float:
        return blocks.get(date_str, (0.0, None))[0]

    today_score = score_of(today)
    today_win = blocks.get(today, (0.0, None))[1]
    tomorrow_score = score_of(tomorrow)
    day_after_score = score_of(day_after)

    dl_left = interval_h * sum(1 for h in day_hours(today) if h.dt > now)

    forecast_days = [{"date": d, "score": score_of(d)} for d in sorted(by_date)[:6]]

    forecast_ok = bool(hourly)

    # outdoor dew point (live) for the room comparison
    outdoor_dew = (
        dew_point(outdoor.temp, outdoor.humidity)
        if outdoor.temp is not None and outdoor.humidity is not None
        else None
    )

    scored = [room_score(r, outdoor_dew, cfg) for r in rooms]
    scored.sort(key=lambda rs: rs.score, reverse=True)
    # rooms whose sensors are actually reporting – the only ones we reason about
    live = [rs for rs in scored if rs.status != "no_data"]
    best_room = live[0] if live else None
    suitable = [rs for rs in live if rs.suitable]
    all_mold = bool(live) and all(rs.mold_risk for rs in live)

    st = "unknown"
    chosen: RoomScore | None = None  # the specific room object we recommend
    codes: list[dict] = []

    if not forecast_ok:
        st, codes = "unknown", [{"code": "no_forecast"}]
    elif all_mold:
        st, codes = "mold_risk", [{"code": "mold", "n": best_room.name}]
    elif today_score >= cfg.score_hang and dl_left >= 4:
        st, codes = "hang_outside_now", [{"code": "outdoor_good", "s": round(today_score)}]
    elif today_score >= cfg.score_hang and dl_left >= 1:
        st, codes = "hang_outside_later", [{"code": "outdoor_good", "s": round(today_score)}]
    elif today_score >= cfg.score_marginal and dl_left >= 3:
        st, codes = "outside_marginal", [{"code": "outdoor_good", "s": round(today_score)}]
    elif (
        tomorrow_score >= cfg.score_hang
        and (tomorrow_score - today_score) >= cfg.wait_delta
        and not suitable
    ):
        st = "wait_for_tomorrow" if washed else "defer_wash"
        codes = [
            {"code": "tomorrow_better", "t": round(tomorrow_score), "d": round(today_score)},
            {"code": "no_room"},
        ]
    elif suitable:
        cand = suitable[0]
        chosen = cand
        if cand.ventilation_useful:
            st = "room_ventilate"
            codes = [
                {"code": "room_best", "n": cand.name, "s": round(cand.score)},
                {"code": "vent_useful"},
            ]
            if cand.window_open is True:
                codes.append({"code": "window_open", "n": cand.name})
            elif cand.window_open is False:
                codes.append({"code": "window_closed", "n": cand.name})
        elif cand.has_dehumidifier and (cand.humidity or 0) >= cfg.room_dehumidify_rh:
            st = "room_dehumidify"
            codes = [
                {"code": "room_best", "n": cand.name, "s": round(cand.score)},
                {"code": "vent_useless"},
            ]
        else:
            st = "room_ok"
            codes = [
                {"code": "room_best", "n": cand.name, "s": round(cand.score)},
                {"code": "room_dry_enough", "n": cand.name, "rh": round(cand.humidity or 0)},
            ]
    elif has_dryer:
        st = "dryer_recommended"
        codes = [{"code": "no_room"}, {"code": "outdoor_weak", "s": round(today_score)}]
    elif best_room is not None:
        st = "best_effort"
        chosen = best_room
        codes = [
            {"code": "no_room"},
            {"code": "no_dryer"},
            {"code": "room_best", "n": best_room.name, "s": round(best_room.score)},
        ]
    else:
        st, codes = "unknown", [{"code": "no_room"}]

    for rs in scored:
        rs.recommended = rs is chosen

    return Result(
        state=st,
        reason_codes=codes,
        recommended_room=chosen.name if chosen else None,
        recommended_fan=chosen.fan if chosen else None,
        recommended_dehumidifier=chosen.dehumidifier if chosen else None,
        outdoor_score=today_score,
        outdoor_score_tomorrow=tomorrow_score,
        outdoor_score_day_after=day_after_score,
        daylight_left_h=round(dl_left, 1),
        best_window_start_hour=today_win[0] if today_win else None,
        best_window_end_hour=today_win[1] if today_win else None,
        forecast_days=forecast_days,
        rooms=[rs.as_dict() for rs in scored],
    )
