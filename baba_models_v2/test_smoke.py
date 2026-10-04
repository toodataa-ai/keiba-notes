from predict import supported_tracks, condition_probs, update_to_race_time

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
