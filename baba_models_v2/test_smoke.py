from predict import supported_tracks, condition_probs, update_to_race_time
from promotion import stage_a_candidate, stage_b_candidate

EXPECTED = {"sapporo","hakodate","fukushima","niigata","tokyo","nakayama","chukyo","kyoto","hanshin","kokura"}


def test_all_tracks_present():
    assert set(supported_tracks()) == EXPECTED


def test_probabilities_sum_to_one():
    for track in EXPECTED:
        for surface, moisture in (("turf", 13.0), ("dirt", 9.0)):
            p = condition_probs(track, surface, moisture)
            assert set(p) == {"良","稍重","重","不良"}
            assert abs(sum(p.values()) - 1.0) <= 0.001


def test_stage_b_is_explicitly_pilot_and_non_replacing():
    out = update_to_race_time("tokyo", "turf", 15.0)
    assert "pilot" in out["validation_status"]
    assert out["legacy_model_replaced"] is False


def test_unknown_track_fails_closed():
    try:
        update_to_race_time("unknown", "turf", 10.0)
    except ValueError:
        return
    raise AssertionError("unknown track must not silently fall back to another venue")


def test_stage_a_candidate_requires_data_baseline_and_audits():
    ok, gaps = stage_a_candidate(
        {"mae": 0.8, "rmse": 1.0, "within_1_0pt": 0.8},
        {"samples": 27, "years": 8, "wet_samples": 0},
        {"leakage_passed": True, "reproducible": True},
    )
    assert ok is False
    assert gaps


def test_stage_a_candidate_can_pass_when_all_guardrails_pass():
    ok, gaps = stage_a_candidate(
        {
            "mae": 0.80,
            "rmse": 1.00,
            "within_1_0pt": 0.80,
            "baseline_mae": 0.90,
            "baseline_rmse": 1.08,
            "wet_mae": 1.20,
            "wet_baseline_mae": 1.25,
        },
        {"samples": 30, "years": 5, "wet_samples": 8},
        {"leakage_passed": True, "reproducible": True},
    )
    assert ok is True
    assert gaps == []


def test_stage_b_candidate_never_passes_without_official_label_metrics():
    ok, gaps = stage_b_candidate(
        None,
        {"labelled_races": 120, "independent_meeting_days": 20, "years": 4, "rain_transition_days": 8},
        {"leakage_passed": True, "reproducible": True},
    )
    assert ok is False
    assert gaps
