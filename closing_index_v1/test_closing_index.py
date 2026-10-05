import pandas as pd

from closing_index import (
    add_race_relative_features,
    apply_aci,
    fit_position_adjustment,
)


def sample_rows():
    rows = []
    # 複数レースを作り、後方ほど上がりが速くなる典型傾向を学習させる。
    for race in range(1, 401):
        for pos, last3f in [(1, 35.0), (2, 34.8), (3, 34.5), (4, 34.2), (5, 34.0), (6, 33.8), (7, 33.6), (8, 33.4)]:
            rows.append(
                {
                    "レースID": race,
                    "上り": last3f,
                    "4コーナー": pos,
                    "距離(m)": 1800,
                    "芝・ダート区分": "芝",
                }
            )
    return pd.DataFrame(rows)


def test_aci_penalizes_expected_rear_speed_and_rewards_front_speed():
    base = add_race_relative_features(sample_rows())
    model = fit_position_adjustment(base, min_exact_count=100, min_fallback_count=100)

    # 同じレース内で、先行馬33.8は非常に強く、後方馬33.8は位置取り期待値込みでは普通に近い。
    race = pd.DataFrame(
        [
            {"レースID": 999, "上り": 33.8, "4コーナー": 1, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 33.8, "4コーナー": 8, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 34.5, "4コーナー": 4, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 34.7, "4コーナー": 5, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 35.0, "4コーナー": 6, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 35.2, "4コーナー": 7, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 35.4, "4コーナー": 2, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 999, "上り": 35.5, "4コーナー": 3, "距離(m)": 1800, "芝・ダート区分": "芝"},
        ]
    )
    scored = apply_aci(add_race_relative_features(race), model)
    front_aci = float(scored.iloc[0]["aci"])
    rear_aci = float(scored.iloc[1]["aci"])
    assert front_aci > rear_aci


def test_race_relative_score_is_not_absolute_time_only():
    df = pd.DataFrame(
        [
            {"レースID": 1, "上り": 34.0, "4コーナー": 2, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 1, "上り": 35.0, "4コーナー": 3, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 1, "上り": 36.0, "4コーナー": 4, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 2, "上り": 33.0, "4コーナー": 2, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 2, "上り": 32.9, "4コーナー": 3, "距離(m)": 1800, "芝・ダート区分": "芝"},
            {"レースID": 2, "上り": 32.8, "4コーナー": 4, "距離(m)": 1800, "芝・ダート区分": "芝"},
        ]
    )
    out = add_race_relative_features(df)
    # 34.0でもレース内では最速なら正、33.0でもレース内最遅なら負になり得る。
    assert float(out.iloc[0]["raw_close_z"]) > 0
    assert float(out.iloc[3]["raw_close_z"]) < 0
