#!/usr/bin/env python3
"""若駒・新馬戦（父の血統データ）の研究の進み具合を、公開してよい集計だけで書き出す。

入力：非公開リポジトリの data_v2（--data）。数えるのは「取得したレース数・馬の頭数」だけで、1頭ずつの記録は出さない。
出力：docs/data/sire_research_status_v1.json（改善状況ページと改善パイプラインが読む）。
検証結果（findings・debut_sire）は研究の結論を人が書き写したもの。検証をやり直したら verified_at と数字を更新する。
自動更新はしない（取得が進んだときに手で作り直す）。
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def total_races():
    n = 0
    for f in glob.glob(os.path.join(ROOT, "baba_models_v2", "going_labels", "jra_going_*.csv")):
        with open(f, encoding="utf-8") as fh:
            n += max(0, sum(1 for _ in csv.reader(fh)) - 1)
    return n


def lineage_block(data_dir):
    """系統の割り当ての結果（研究のみ）。系統ごとの割合と新馬戦のA/Eは、データから計算する。検証の数字（gain）は人が書き写す。"""
    import sys
    sys.path.insert(0, ROOT)
    from sire_db_v1.debut_common import load_horses
    from sire_db_v1.lineage import summary
    sm = summary(load_horses(data_dir))
    sm.update({
        "verified_at": "2026-11-12",
        "gain": {"father_only": 0.0049, "father_and_lineage": 0.0056, "lineage_only": 0.0019},
        "ci95": {"father_only": [-0.006, 0.016], "father_and_lineage": [-0.006, 0.017], "lineage_only": [-0.002, 0.006]},
        "text": "父を系統にまとめても、新馬戦の外れ具合の改善は増えず（父だけ +0.005、父＋系統 +0.006、系統だけ +0.002。どれも95%の幅が0をまたぐ）、まだ採用には足りません。ロベルト系・ダンチヒ系・シアトルスルー系は、新馬戦でオッズ以上に勝つ傾向が前後半とも出ていますが、系統が多いため偶然の可能性が残ります。",
    })
    return sm


def build(data_dir, today=None):
    today = today or dt.date.today().isoformat()
    total = total_races()
    done = count_lines(os.path.join(data_dir, "races_done.txt"))
    pages = count_lines(os.path.join(data_dir, "race_pages_done.txt"))
    horses = sum(count_lines(f) for f in glob.glob(os.path.join(data_dir, "horses_*.jsonl")))
    frac = (done / total) if total else 0.0
    return {
        "schema_version": 1,
        "generated_by": "sire_db_v1/research_status.py",
        "updated_at": today,
        "note": "取得の数は updated_at 時点。検証の結果は verified_at 時点。自動更新はしない。",
        "sire_db": {
            "races_done": done, "races_total": total, "horses": horses, "frac": round(frac, 4),
            "text": f"過去レースの取得 {round(frac * 100)}%（{done:,}/{total:,}レース・馬{horses:,}頭）",
        },
        "race_pages": {
            "races_done": pages, "races_total": total,
            "text": f"レースごとのラップ・通過順位・払戻の取得 {round(pages / total * 100) if total else 0}%（{pages:,}/{total:,}レース）",
        },
        "debut_sire": {
            "verified_at": "2026-11-12", "test_races": 507, "logloss_gain": 0.0049, "interval95": [-0.006, 0.016],
            "text": "父の傾向は新馬戦で統計的には効いている（取得がそろい、前回より強まった）が、外れ具合の改善はまだ偶然と区別できない（改善 +0.005、95%の幅 −0.006〜+0.016）。系統を足しても改善は増えなかった。",
        },
        "lineage": lineage_block(data_dir),
        "findings": [
            "父の得意な距離・芝かダートは「どこを走るか」には強く出ますが、オッズ以上に勝つかどうかは、ほとんどオッズに織り込み済みでした。",
            "経験のない新馬戦だけは、オッズに足りない情報を父の傾向が持っている可能性があります。ただし、まだ偶然と区別できる差ではありません。",
            "初勝利の月齢は、別の世代の産駒でも再現しました（成長の速さには遺伝性がありそうです）。予想への使い道は、これから確かめます。",
            "父を「系統」（サンデーサイレンス系など）にまとめても、新馬戦の予想の改善は増えませんでした。母の父の系統は効果なしでした。",
        ],
        "stopped": "経験の区分（0戦・1〜3戦・4戦以上）ごとの研究は、あまり意味がないため止めました（2026-11-07）。",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"), required=not os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "data", "sire_research_status_v1.json"))
    a = ap.parse_args(argv)
    doc = build(a.data)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(doc["sire_db"]["text"]); print(doc["race_pages"]["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
