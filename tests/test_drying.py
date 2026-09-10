"""Unit tests for the pure drying logic (no Home Assistant needed)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "laundry_advisor")
)

import drying as d

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 9, 9, 10, 0, tzinfo=TZ)


# --------------------------------------------------------------- psychrometrics
def test_dew_point_matches_reference():
    # DWD reported dew_point 15.9 for 19.3 °C / 81 % RH
    assert d.dew_point(19.3, 81) == pytest.approx(15.96, abs=0.1)
    assert d.dew_point(16, 70) == pytest.approx(10.53, abs=0.1)


def test_dew_point_le_temperature():
    for t in range(-10, 40, 5):
        for rh in range(10, 101, 10):
            assert d.dew_point(t, rh) <= t + 1e-6


def test_abs_humidity_reasonable():
    # ~9.4 g/m³ at 20 °C / 55 %
    assert d.abs_humidity(20, 55) == pytest.approx(9.5, abs=0.5)


def test_vpd_zero_at_saturation():
    assert d.vpd(20, 100) == pytest.approx(0.0, abs=1e-9)


def test_ramp_clamps():
    assert d.ramp(0, 5, 10) == 0.0
    assert d.ramp(15, 5, 10) == 1.0
    assert d.ramp(7.5, 5, 10) == pytest.approx(0.5)
    assert d.ramp(20, 40, 25) == 1.0  # falling ramp, past the 1-end
    assert d.ramp(45, 40, 25) == 0.0
    assert d.ramp(30, 40, 25) == pytest.approx(2 / 3)  # 1 at 25, 0 at 40


# ------------------------------------------------------------------- hour_score
def _h(**kw):
    return d.HourFc(dt=NOW, **kw)


def test_hour_score_rain_gate():
    assert d.hour_score(_h(temperature=18, humidity=50, precipitation=0.5), d.Weights()) == 0.0


def test_hour_score_rain_gate_scaled_by_interval():
    # 0.2 mm over a 3-hour interval = 0.067 mm/h -> not a gate
    assert (
        d.hour_score(
            _h(temperature=18, humidity=50, wind_speed=15, precipitation=0.2),
            d.Weights(),
            interval_h=3,
        )
        > 0
    )


def test_hour_score_good_day_high():
    s = d.hour_score(
        _h(
            temperature=18,
            humidity=55,
            wind_speed=16,
            wind_gust_speed=28,
            cloud_coverage=10,
            precipitation=0,
            sun_irradiance=500,
        ),
        d.Weights(),
    )
    assert s >= 90


def test_hour_score_cold_windy_beats_warm_humid_still():
    cold = d.hour_score(
        _h(temperature=8, humidity=50, wind_speed=22, cloud_coverage=20, precipitation=0),
        d.Weights(),
    )
    warm = d.hour_score(
        _h(temperature=26, humidity=78, wind_speed=4, cloud_coverage=40, precipitation=0),
        d.Weights(),
    )
    assert cold > warm


def test_hour_score_gust_cap():
    s = d.hour_score(
        _h(
            temperature=18,
            humidity=45,
            wind_speed=18,
            wind_gust_speed=50,
            cloud_coverage=0,
            precipitation=0,
        ),
        d.Weights(),
    )
    assert s <= 40


def test_hour_score_precip_probability_discount():
    base = dict(temperature=18, humidity=55, wind_speed=15, cloud_coverage=20, precipitation=0)
    dry = d.hour_score(_h(**base, precipitation_probability=10), d.Weights())
    likely = d.hour_score(_h(**base, precipitation_probability=70), d.Weights())
    assert likely == pytest.approx(dry * 0.4, rel=0.01)


# ------------------------------------------------------------------ best_block
def _day(scores: list[float], start_hour: int = 9) -> list[d.HourFc]:
    out = []
    for i, sc in enumerate(scores):
        h = d.HourFc(dt=NOW.replace(hour=start_hour) + timedelta(hours=i))
        h.score = sc
        h.is_day = True
        out.append(h)
    return out


def test_best_block_picks_best_window():
    # start_hour 9 -> indices 2..6 are hours 11..15
    score, win = d.best_block(_day([10, 10, 80, 80, 80, 80, 80, 20]), 5)
    assert score == pytest.approx(80.0)
    assert win == (11, 16)


def test_best_block_short_day_penalty():
    score, _ = d.best_block(_day([80, 80, 80]), 5)  # only 3 daylight hours
    assert score == pytest.approx(48.0)  # 80 * 0.6


def test_best_block_empty():
    assert d.best_block([], 5) == (0.0, None)


def test_best_block_all_zero_no_window():
    score, win = d.best_block(_day([0, 0, 0, 0, 0]), 5)
    assert score == 0.0
    assert win is None


# ------------------------------------------------------------------ room_score
def test_room_score_none_without_sensors():
    assert d.room_score(d.RoomState("X", None, None), None, d.Config()) is None


def test_room_score_dry_warm_room_suitable_high():
    rs = d.room_score(d.RoomState("Attic", 24, 52), 10.0, d.Config())
    assert rs.suitable
    assert rs.status == "ok"
    assert rs.score >= 70


def test_room_score_humid_room_penalised():
    rs = d.room_score(d.RoomState("Cellar", 20, 72), 18.0, d.Config())
    assert not rs.suitable
    assert rs.status == "too_humid"
    assert rs.score < 40


def test_room_score_mould_guard():
    rs = d.room_score(d.RoomState("Wet", 20, 85), None, d.Config())
    assert rs.mold_risk
    assert rs.status == "mold_risk"
    assert rs.score <= 5


def test_room_score_too_cold():
    rs = d.room_score(d.RoomState("Garage", 10, 55), None, d.Config())
    assert not rs.suitable
    assert rs.status == "too_cold"


def test_room_score_ventilation_useful_bonus():
    # room 20/70 -> dew ~14.4; outdoor dew 8 is > 5 K below -> airing helps
    win = "binary_sensor.r_window"
    dry_out = d.room_score(d.RoomState("R", 20, 70, window_entity=win), 8.0, d.Config())
    no_out = d.room_score(d.RoomState("R", 20, 70, window_entity=win), None, d.Config())
    assert dry_out.ventilation_useful and not no_out.ventilation_useful
    assert dry_out.score > no_out.score


def test_room_score_no_window_is_not_ventilatable():
    # outdoor air much drier, but the room has no window -> cannot air it
    with_win = d.room_score(
        d.RoomState("R", 20, 70, window_entity="binary_sensor.w"), 8.0, d.Config()
    )
    without = d.room_score(d.RoomState("R", 20, 70), 8.0, d.Config())
    assert with_win.ventilation_useful and not without.ventilation_useful
    assert without.has_window is False
    assert with_win.score > without.score  # airing bonus only with a window


def test_room_score_window_open_passthrough():
    rs = d.room_score(
        d.RoomState("R", 22, 55, window_entity="binary_sensor.w", window_open=True),
        None,
        d.Config(),
    )
    assert rs.has_window is True
    assert rs.window_open is True
    assert rs.as_dict()["window_open"] is True


def test_room_score_wall_temp_raises_surface_rh():
    warm_wall = d.room_score(d.RoomState("R", 20, 60, wall_temp=19), None, d.Config())
    cold_wall = d.room_score(d.RoomState("R", 20, 60, wall_temp=13), None, d.Config())
    assert cold_wall.surface_rh_estimate > warm_wall.surface_rh_estimate


# -------------------------------------------------------------------- evaluate
def _forecast(hourly_score_profile, hours=60, **hour_kw):
    """Build a forecast where each hour gets attributes producing a target score
    is hard, so instead we craft weather that yields known scores by band."""
    out = []
    for i in range(hours):
        out.append(d.HourFc(dt=NOW.replace(minute=0) + timedelta(hours=i), **hour_kw))
    return out


def _good_hours(n=60):
    return _forecast(
        None,
        n,
        temperature=18,
        humidity=52,
        wind_speed=16,
        wind_gust_speed=26,
        cloud_coverage=10,
        precipitation=0,
        sun_irradiance=500,
    )


def _rainy_hours(n=60):
    return _forecast(
        None,
        n,
        temperature=15,
        humidity=95,
        wind_speed=8,
        cloud_coverage=100,
        precipitation=1.0,
        precipitation_probability=90,
    )


def test_evaluate_no_forecast_is_unknown():
    r = d.evaluate(
        hourly=[],
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "unknown"
    assert r.reason_codes == [{"code": "no_forecast"}]


def test_evaluate_hang_outside_now():
    r = d.evaluate(
        hourly=_good_hours(),
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "hang_outside_now"


def test_evaluate_hang_outside_later_when_little_daylight():
    late = NOW.replace(hour=18)
    r = d.evaluate(
        hourly=_good_hours(),
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=late,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "hang_outside_later"


def test_evaluate_no_hang_later_with_zero_daylight():
    night = NOW.replace(hour=21)
    r = d.evaluate(
        hourly=_good_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 24, 52)],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=night,
        washed=False,
        has_dryer=True,
    )
    assert r.state != "hang_outside_later"


def test_evaluate_rainy_today_dry_room_is_room_ok():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 24, 52)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_ok"
    assert r.recommended_room == "Attic"


def test_evaluate_rainy_today_no_room_uses_dryer():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Cellar", 20, 75)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "dryer_recommended"


def test_evaluate_rainy_today_no_room_no_dryer_is_best_effort():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Cellar", 20, 75)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=False,
    )
    assert r.state == "best_effort"
    assert r.recommended_room == "Cellar"


def test_evaluate_all_rooms_mould_is_mold_risk():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("A", 20, 88), d.RoomState("B", 21, 90)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "mold_risk"


def test_evaluate_room_dehumidify_when_humid_and_dehumidifier():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 22, 60, dehumidifier_entity="switch.d")],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_dehumidify"


def test_evaluate_recommended_room_flag_set():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 24, 52), d.RoomState("Cellar", 20, 72)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    recs = [x for x in r.rooms if x["recommended"]]
    assert len(recs) == 1 and recs[0]["name"] == "Attic"


def test_evaluate_attributes_present():
    r = d.evaluate(
        hourly=_good_hours(),
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert 0 <= r.outdoor_score <= 100
    assert isinstance(r.forecast_days, list)
    assert r.best_window_start_hour is not None
    assert r.daylight_left_h == pytest.approx(9.0)  # 10:00 -> 19:00, hourly
    assert [f["date"] for f in r.forecast_days][:2] == ["2026-09-09", "2026-09-10"]


def _mixed_hours(today_score_hours, tomorrow_score_hours):
    """Today's daylight hours get `today_...` weather, tomorrow's get `tomorrow_...`."""
    out = []
    for i in range(60):
        dt = NOW.replace(minute=0) + timedelta(hours=i)
        kw = today_score_hours if dt.date() == NOW.date() else tomorrow_score_hours
        out.append(d.HourFc(dt=dt, **kw))
    return out


_GOOD = dict(
    temperature=18,
    humidity=52,
    wind_speed=16,
    wind_gust_speed=26,
    cloud_coverage=10,
    precipitation=0,
    sun_irradiance=500,
)
_MEH = dict(
    temperature=16,
    humidity=68,
    wind_speed=9,
    cloud_coverage=60,
    precipitation=0,
    sun_irradiance=180,
)  # tuned to the 55-69 band
_RAIN = dict(
    temperature=15,
    humidity=95,
    wind_speed=8,
    cloud_coverage=100,
    precipitation=1.0,
    precipitation_probability=90,
)


def test_evaluate_defer_wash_when_tomorrow_much_better_not_washed():
    r = d.evaluate(
        hourly=_mixed_hours(_RAIN, _GOOD),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Cellar", 20, 75)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=False,
    )
    assert r.state == "defer_wash"


def test_evaluate_wait_for_tomorrow_when_washed():
    r = d.evaluate(
        hourly=_mixed_hours(_RAIN, _GOOD),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Cellar", 20, 75)],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=True,
        has_dryer=False,
    )
    assert r.state == "wait_for_tomorrow"


def test_evaluate_outside_marginal_band():
    r = d.evaluate(
        hourly=_mixed_hours(_MEH, _MEH),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Cellar", 20, 75)],
        outdoor=d.Outdoor(15, 72),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "outside_marginal"
    assert d.Config().score_marginal <= r.outdoor_score < d.Config().score_hang


def test_evaluate_room_ventilate_end_to_end():
    # rainy outside, dry-ish room, outdoor air much drier -> airing helps
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[
            d.RoomState("Attic", 20, 62, window_entity="binary_sensor.attic", window_open=False)
        ],
        outdoor=d.Outdoor(2, 70),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_ventilate"
    assert {"code": "vent_useful"} in r.reason_codes
    assert {"code": "window_closed", "n": "Attic"} in r.reason_codes


def test_evaluate_room_without_window_is_room_ok_not_ventilate():
    # identical to the case above but no window -> falls through to room_ok
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 20, 62)],
        outdoor=d.Outdoor(2, 70),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_ok"


def test_evaluate_room_ventilate_window_open_reason():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 20, 62, window_entity="binary_sensor.attic", window_open=True)],
        outdoor=d.Outdoor(2, 70),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_ventilate"
    assert {"code": "window_open", "n": "Attic"} in r.reason_codes


def test_evaluate_room_ventilate_unknown_contact_no_window_reason():
    # window_open None (contact unknown/unavailable) -> still ventilate, no window_* code
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 20, 62, window_entity="binary_sensor.attic", window_open=None)],
        outdoor=d.Outdoor(2, 70),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_ventilate"
    assert not any(c["code"] in ("window_open", "window_closed") for c in r.reason_codes)


def test_evaluate_windowless_room_still_reaches_dehumidify():
    # humid, dehumidifier present, no window -> dehumidify (not blocked by the window gate)
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[d.RoomState("Attic", 22, 60, dehumidifier_entity="switch.d")],
        outdoor=d.Outdoor(2, 70),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.state == "room_dehumidify"


def test_evaluate_final_unknown_no_rooms_no_dryer():
    r = d.evaluate(
        hourly=_rainy_hours(),
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(15, 95),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=False,
    )
    assert r.state == "unknown"


def test_evaluate_hang_boundary_dl_left_4_vs_3():
    cfg = d.Config()
    at16 = NOW.replace(hour=16)  # 16:00 -> 19:00 end -> 3 h left -> not "now"
    r = d.evaluate(
        hourly=_good_hours(),
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=cfg,
        now=at16,
        washed=False,
        has_dryer=True,
    )
    assert r.daylight_left_h == pytest.approx(3.0)
    assert r.state == "hang_outside_later"
    at15 = NOW.replace(hour=15)  # 4 h left
    r2 = d.evaluate(
        hourly=_good_hours(),
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=cfg,
        now=at15,
        washed=False,
        has_dryer=True,
    )
    assert r2.daylight_left_h == pytest.approx(4.0)
    assert r2.state == "hang_outside_now"


def test_evaluate_precip_probability_merged_from_second_source():
    base = dict(
        temperature=18,
        humidity=52,
        wind_speed=16,
        wind_gust_speed=26,
        cloud_coverage=10,
        precipitation=0,
        sun_irradiance=500,
    )
    hourly = [d.HourFc(dt=NOW.replace(minute=0) + timedelta(hours=i), **base) for i in range(30)]
    prob = [
        d.HourFc(dt=NOW.replace(minute=0) + timedelta(hours=i), precipitation_probability=95)
        for i in range(30)
    ]
    with_prob = d.evaluate(
        hourly=hourly,
        daily=[],
        prob=prob,
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    without = d.evaluate(
        hourly=hourly,
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert with_prob.outdoor_score < without.outdoor_score  # 0.4x discount applied


def test_evaluate_does_not_mutate_input():
    hourly = _good_hours()
    snapshot = [(h.score, h.is_day, h.precipitation_probability) for h in hourly]
    d.evaluate(
        hourly=hourly,
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert [(h.score, h.is_day, h.precipitation_probability) for h in hourly] == snapshot


def test_evaluate_subhourly_interval_daylight_hours():
    # 30-minute forecast: 18 daylight entries between 10:00 and 19:00 -> 9 h
    hourly = []
    for i in range(80):
        hourly.append(
            d.HourFc(
                dt=NOW.replace(minute=0) + timedelta(minutes=30 * i),
                temperature=18,
                humidity=52,
                wind_speed=16,
                cloud_coverage=10,
                precipitation=0,
                sun_irradiance=500,
            )
        )
    r = d.evaluate(
        hourly=hourly,
        daily=[],
        prob=[],
        rooms=[],
        outdoor=d.Outdoor(18, 52),
        cfg=d.Config(),
        now=NOW,
        washed=False,
        has_dryer=True,
    )
    assert r.daylight_left_h == pytest.approx(9.0, abs=0.6)


def test_hour_score_missing_gust_no_cap():
    s = d.hour_score(
        _h(
            temperature=18,
            humidity=45,
            wind_speed=18,
            cloud_coverage=0,
            precipitation=0,
            sun_irradiance=400,
        ),
        d.Weights(),
    )
    assert s > 40  # gust None must not cap


def test_hour_score_pp_medium_band():
    base = dict(temperature=18, humidity=55, wind_speed=15, cloud_coverage=20, precipitation=0)
    dry = d.hour_score(_h(**base, precipitation_probability=10), d.Weights())
    medium = d.hour_score(_h(**base, precipitation_probability=50), d.Weights())
    assert medium == pytest.approx(dry * 0.7, rel=0.01)


def test_room_score_cold_wall_flips_to_mould():
    warm = d.room_score(d.RoomState("R", 20, 60, wall_temp=19), None, d.Config())
    cold = d.room_score(d.RoomState("R", 20, 60, wall_temp=12), None, d.Config())
    assert warm.status == "ok" and not warm.mold_risk
    assert cold.mold_risk and cold.status == "mold_risk" and cold.score <= 5
