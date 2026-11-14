"""Diagnostics must neither peek at future labels nor promote any model."""
from __future__ import annotations

import pytest

from stage_b_challenger_v1 import adjusted, evaluate, fit_temperature


def one(track, surface, day, index, truth="良"):
    return {
        "race_id": f"{track}-{surface}-{day}-{index}",
        "track": track, "surface": surface, "date": day,
        "official_condition": truth,
        "existing_pilot": {"良": .78, "稍重": .16, "重": .04, "不良": .02},
    }


def payload(rows):
    return {"status": "retrospective_research_only",
            "production_router_changed": False, "race_audit": rows}


def test_no_data_is_explicitly_unvalidated():
    res = evaluate(payload([]))
    assert all(x["paired_test_races"] == 0 and not x["ready_for_candidate"]
               for x in res["models"].values())
    assert res["promotion_allowed"] is False


def test_temperature_preserves_four_labels():
    p = adjusted({"良": .8, "稍重": .1, "重": .06, "不良": .04}, 1.8)
    assert len(p) == 4
    assert abs(sum(p.values()) - 1.0) < 1e-10
    assert p["良"] < .8


def test_forward_time_folds_are_separated_by_year():
    train = [one("tokyo", "turf", f"2024-04-{d:02d}", d, "稍重" if d%2 else "良")
             for d in range(1, 31)]
    future = [one("tokyo", "turf", f"2025-04-{d:02d}", d, "良")
              for d in range(1, 11)]
    res = evaluate(payload(train + future))["models"]["tokyo_turf"]
    assert res["paired_test_races"] == 10
    assert len(res["forward_folds"]) == 1
    fold = res["forward_folds"][0]
    assert fold["max_train_date"] < fold["min_test_date"]
    assert fold["held_out_year"] == "2025"
    assert res["ready_for_production"] is False


def test_challenger_only_learns_training_labels():
    train = [one("kyoto", "dirt", f"2024-05-{d:02d}", d, "稍重") for d in range(1, 25)]
    a = fit_temperature(train)
    test_a = [one("kyoto", "dirt", f"2025-05-{d:02d}", d, "良") for d in range(1, 11)]
    test_b = [one("kyoto", "dirt", f"2025-05-{d:02d}", d, "不良") for d in range(1, 11)]
    x, y = evaluate(payload(train+test_a)), evaluate(payload(train+test_b))
    assert x["models"]["kyoto_dirt"]["forward_folds"][0]["temperature"] == a
    assert y["models"]["kyoto_dirt"]["forward_folds"][0]["temperature"] == a


def test_reject_duplicate_race_ids():
    row = one("tokyo", "turf", "2024-04-01", 1)
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(payload([row, row]))


def test_fail_closed_on_nonresearch_input():
    with pytest.raises(ValueError, match="non-production"):
        evaluate({"status": "validated", "production_router_changed": False, "race_audit": []})
