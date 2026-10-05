import pandas as pd

from closing_index_v1_1 import (
    add_prior_features,
    add_race_relative_features,
    apply_aci,
    apply_demand_profile,
    fit_demand_profile,
    fit_position_adjustment,
)


def sample_rows():
    rows = []
    for race in range(1, 401):
        for pos, last3f in [(1, 35.0), (2, 34.8), (3, 34.5), (4, 34.2), (5, 34.0), (6, 33.8), (7, 33.6), (8, 33.4)]:
            rows.append({"レースID": race, "上り": last3f, "4コーナー": pos, "距離(m)": 1800, "芝・ダート区分": "芝"})
    return pd.DataFrame(rows)


def test_aci_penalizes_expected_rear_speed_and_rewards_front_speed():
    base = add_race_relative_features(sample_rows())
    model = fit_position_adjustment(base, min_exact_count=100, min_fallback_count=100)
    race = pd.DataFrame([
        {"レースID": 999, "上り": 33.8, "4コーナー": 1, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 33.8, "4コーナー": 8, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 34.5, "4コーナー": 4, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 34.7, "4コーナー": 5, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 35.0, "4コーナー": 6, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 35.2, "4コーナー": 7, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 35.4, "4コーナー": 2, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 999, "上り": 35.5, "4コーナー": 3, "距離(m)": 1800, "芝・ダート区分": "芝"},
    ])
    scored = apply_aci(add_race_relative_features(race), model)
    assert float(scored.iloc[0]["aci"]) > float(scored.iloc[1]["aci"])


def test_race_relative_score_is_not_absolute_time_only():
    df = pd.DataFrame([
        {"レースID": 1, "上り": 34.0, "4コーナー": 2, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 1, "上り": 35.0, "4コーナー": 3, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 1, "上り": 36.0, "4コーナー": 4, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 2, "上り": 33.0, "4コーナー": 2, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 2, "上り": 32.9, "4コーナー": 3, "距離(m)": 1800, "芝・ダート区分": "芝"},
        {"レースID": 2, "上り": 32.8, "4コーナー": 4, "距離(m)": 1800, "芝・ダート区分": "芝"},
    ])
    out = add_race_relative_features(df)
    assert float(out.iloc[0]["raw_close_z"]) > 0
    assert float(out.iloc[3]["raw_close_z"]) < 0


def test_demand_profile_distinguishes_closing_reliance_without_rewarding_slow_time():
    rows = []
    for venue_idx, venue in enumerate(["A", "B"]):
        for r in range(1, 31):
            race_id = venue_idx * 1000 + r
            for finish in range(1, 9):
                adjusted = (2.0 if finish <= 3 else -0.5) if venue == "A" else (0.1 if finish <= 3 else 0.0)
                rows.append({
                    "レースID": race_id, "競馬場名": venue, "surface_norm": "turf",
                    "distance_band": "mile_1800", "going_norm": "firm",
                    "着順": finish, "adjusted_close_z": adjusted,
                })
    df = pd.DataFrame(rows)
    demand = fit_demand_profile(df, min_exact_rows=20, min_exact_races=2)
    out = apply_demand_profile(df, demand)
    a = out[out["競馬場名"] == "A"]["closing_reliance_edge"].iloc[0]
    b = out[out["競馬場名"] == "B"]["closing_reliance_edge"].iloc[0]
    assert a > b


def test_reproducibility_is_separate_from_peak_ability():
    rows = []
    acis = [115, 86, 114, 88, 116, 90, 112]
    for i, aci in enumerate(acis, start=1):
        rows.append({
            "馬名": "mood-horse", "レース日付": pd.Timestamp(2020, 1, i), "レースID": i,
            "上り": 34.0, "raw_close_z": 0.0, "aci": aci, "demand_type": "balanced",
        })
    out = add_prior_features(pd.DataFrame(rows))
    last = out.iloc[-1]
    assert float(last["prev6_aci_peak"]) >= 115
    assert float(last["reproducibility_mad"]) > 5
    assert float(last["reproducibility_score"]) < 70
