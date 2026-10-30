"""Offline safety tests for the Tokyo/Kyoto Stage B replay."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from stage_b_tokyo_kyoto_v1 import replay, norm_probs, score


def label(track="tokyo", surface="turf", day="2026-10-24"):
    return {
        "race_id": f"{track}-{surface}-{day}", "track": track,
        "surface": surface, "race_date": day, "post_time_jst": "15:00",
        "official_condition": "稍重",
        "official_result_url": "https://www.jra.go.jp/JRADB/accessS.html?test=1",
        "verified_at_jst": f"{day}T18:00",
    }


def observation(track="tokyo", day="2026-10-24"):
    return {
        "track": track, "observed_date": day, "race_day": "true",
        "moisture_time": "07:00", "turf_goal": "18", "turf_corner": "16",
        "dirt_goal": "8", "dirt_corner": "10",
        "source_url": "https://www.jra.go.jp/keiba/baba/archive/2026.html",
    }


def hourly(track="tokyo", day="2026-10-24", future_rain=0):
    names = ["fuchu"] if track == "tokyo" else ["nagaokakyo", "kyotanabe"]
    result = []
    for station in names:
        for hour in range(8, 16):
            result.append({
                "station": station, "end_at": f"{day}T{hour:02d}:00",
                "precipitation_mm": str(future_rain if hour == 15 else (1 if hour == 12 else 0)),
                "temperature_c": "20", "wind_mps": "2",
                "sunshine_hours": "0",
            })
    return result


@pytest.mark.parametrize("track", ["tokyo", "kyoto"])
@pytest.mark.parametrize("surface", ["turf", "dirt"])
def test_four_model_replay_with_official_label_and_timed_anchor(track, surface):
    r = replay([label(track, surface)], [observation(track)], hourly(track))
    assert r["audit"]["accepted_races"] == 1
    assert r["audit"]["formal_promotion_eligible"] is False
    key = f"{track}_{surface}"
    assert r["models"][key]["existing_operational_pilot"]["n"] == 1
    assert r["models"][key]["stage_b_candidate"] is False
    assert all(not v["stage_b_candidate"] for v in r["models"].values())
    assert r["race_audit"][0]["weather_latest_used_jst"].endswith("14:00")


def test_weather_after_safe_cutoff_does_not_leak_into_prediction():
    a = replay([label()], [observation()], hourly(future_rain=0))
    b = replay([label()], [observation()], hourly(future_rain=100))
    assert a["race_audit"][0]["existing_pilot"] == b["race_audit"][0]["existing_pilot"]
    assert a["race_audit"][0]["rain_after_anchor_mm"] == b["race_audit"][0]["rain_after_anchor_mm"]


def test_do_not_silently_backfill_unknown_post_time():
    x = label()
    x["post_time_jst"] = ""
    result = replay([x], [observation()], hourly())
    assert result["audit"]["accepted_races"] == 0
    assert result["audit"]["rejected_races"] == 1


def test_unverified_official_label_is_not_accepted():
    x = label()
    x["official_result_url"] = "https://example.com/fake"
    result = replay([x], [observation()], hourly())
    assert result["audit"]["accepted_races"] == 0


def test_missing_morning_anchor_and_weather_are_excluded():
    assert replay([label()], [], hourly())["audit"]["accepted_races"] == 0
    assert replay([label()], [observation()], [])["audit"]["accepted_races"] == 0


def test_kyoto_old_regime_is_excluded():
    x = label("kyoto", day="2022-10-24")
    result = replay([x], [observation("kyoto", "2022-10-24")], hourly("kyoto", "2022-10-24"))
    assert result["audit"]["rejection_reasons"]["pre_rebuild_kyoto_regime"] == 1


def test_duplicate_races_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        replay([label(), label()], [observation()], hourly())


def test_normalizer_rejects_invalid_probabilities():
    with pytest.raises(ValueError):
        norm_probs({"良": 1.0, "稍重": -1.0, "重": 1.0, "不良": 0.0})


def test_scoring_four_classes_and_ece():
    row = {"official_condition": "良", "baseline": {"良": 0.7, "稍重": 0.2, "重": 0.05, "不良": 0.05}}
    s = score([row], "baseline")
    assert s["top1_accuracy"] == 1.0
    assert s["adjacent_class_accuracy"] == 1.0
    assert s["multiclass_log_loss"] > 0
    assert score([], "baseline") is None
