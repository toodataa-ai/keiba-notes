"""馬場傾向（前日の傾向）の研究の進み具合を、改善状況ページ向けにまとめる（数字だけ。使用量0）。
- Claudeの予想（STEP1）に記録した前日の傾向（bias_used）の件数を、週ごとに数える
- 過去データでの検証結果（人が書き写す。VERIFIED）を載せる
出力：docs/data/baba_bias/research_status_v1.json"""
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

TARGET = 300   # 小さな効果（+0.005）でも確かめるのに必要なレース数の下限の目安（Opusの検証 2026-11-08）
JST = timezone(timedelta(hours=9))
# 過去データでの検証（2022〜2024で係数を決め、2025〜2026で評価。＋が改善。95%の幅が0をまたぐ＝偶然と区別できない）
VERIFIED = [
    {"on": "2026-11-08", "what": "全レースで、前日の前残り・速さに合わせて先行馬・差し馬の勝率を補正", "result": "ダート +0.0004（−0.0007〜+0.0016）、芝1500m以上 −0.0017、芝1400m以下 −0.0041。偶然と区別できない"},
    {"on": "2026-11-08", "what": "脚質（どの馬が前に行くか）の予測を強めて再検証（予測位置と実際の位置の相関 0.48→0.56）", "result": "ダート +0.0000（−0.0006〜+0.0007）。最初のコーナーの位置を完全に当てても上積みは +0.0014〜+0.0016"},
    {"on": "2026-11-08", "what": "『続く日』に絞って検証（ダート・朝の馬場状態が前日と同じ・前日の傾向が強い日）", "result": "3つの組み合わせとも ±0.001 未満で、95%の幅は0をまたぐ。当てはまる11Rは1日あたり約0.09レースで、Claude自身の予想では確かめられない"},
]


def week_id(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def count_recorded(root="."):
    """step1 に bias_used（null でない）を記録したレース → {週: 件数}"""
    weekly, total = {}, 0
    for f in glob.glob(os.path.join(root, "claude_track", "predictions", "*", "step1-*.json")):
        rid = os.path.basename(os.path.dirname(f))
        try:
            d = datetime.strptime(rid[:10], "%Y-%m-%d").date()
            if json.load(open(f, encoding="utf-8")).get("bias_used") is None:
                continue
        except (ValueError, OSError):
            continue
        weekly[week_id(d)] = weekly.get(week_id(d), 0) + 1
        total += 1
    return weekly, total


def build(root=".", today=None):
    today = today or datetime.now(JST).date()
    weekly, total = count_recorded(root)
    this_week = weekly.get(week_id(today), 0)
    text = (f"前日の傾向の記録 {total}/{TARGET}レース（今週 +{this_week}）。"
            "過去データでの検証3回（全レース／脚質の予測を強めた／続く日に絞った）は、いずれも予想の当たり具合の改善が偶然と区別できませんでした。"
            "いまは記録のみで、印・勝率は変えません。")
    return {"schema_version": 1, "updated_at": today.isoformat(),
            "prev_day_bias": {"frac": round(min(1.0, total / TARGET), 4), "text": text, "recorded": total, "target": TARGET,
                              "weekly": [{"week": k, "races": weekly[k]} for k in sorted(weekly)], "verified": VERIFIED}}


def main(out="docs/data/baba_bias/research_status_v1.json"):
    doc = build()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    old = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    if old != text:
        open(out, "w", encoding="utf-8").write(text)
        print("updated", out)
    else:
        print("no change")


if __name__ == "__main__":
    main(*sys.argv[1:2])
