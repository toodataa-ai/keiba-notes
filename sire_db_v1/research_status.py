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
            "verified_at": "2026-11-06", "test_races": 507, "logloss_gain": 0.0043, "interval95": [-0.003, 0.012],
            "text": "父の傾向は新馬戦で統計的には効いているが、外れ具合の改善はまだ偶然と区別できない（改善 +0.004、95%の幅 −0.003〜+0.012）。取得がそろったら同じ検証をやり直す。",
        },
        "findings": [
            "父の得意な距離・芝かダートは「どこを走るか」には強く出ますが、オッズ以上に勝つかどうかは、ほとんどオッズに織り込み済みでした。",
            "経験のない新馬戦だけは、オッズに足りない情報を父の傾向が持っている可能性があります。ただし、まだ偶然と区別できる差ではありません。",
            "初勝利の月齢は、別の世代の産駒でも再現しました（成長の速さには遺伝性がありそうです）。予想への使い道は、これから確かめます。",
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
