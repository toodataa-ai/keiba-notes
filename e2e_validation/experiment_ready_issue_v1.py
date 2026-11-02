#!/usr/bin/env python3
"""Print GitHub Issue drafts for experiments that reached the paired-race minimum.

Read-only. Output is JSON lines {"experiment_id", "title", "body"} consumed by
.github/workflows/jra-improvement-experiments-v1.yml, which opens one Issue per
experiment (never twice) to start the manual A/B/C approval review.
Nothing here approves or promotes anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "experiment-ready"
NAMES = {"honmei_win": "◎勝率", "honmei_top3": "◎3着内率", "win_brier": "勝率Brier（低いほど良い）",
         "win_log_loss": "勝率log loss（低いほど良い）", "top3_brier": "3着内Brier（低いほど良い）"}


def title(exp_id: str) -> str:
    return f"[判定準備完了] {exp_id}：新旧比較が規定件数に到達"


def body(exp: dict, registry_exp: dict) -> str:
    p = exp["prospective"]
    lines = [
        f"## {exp['id']} {exp['title']}",
        "",
        f"- 正式版：{exp['baseline']} ／ 改善案：{exp['challenger']}",
        f"- 事前登録後の同一レース比較：**{p['pairs']}件**（規定 {exp['minimum_prospective_pairs']}件）",
        f"- 事前に決めた採用条件：{registry_exp.get('decision_rule', '（未記載）')}",
        "",
        "| 指標 | 正式版 | 改善案 | 差 |",
        "|---|---|---|---|",
    ]
    for key, label in NAMES.items():
        m = p.get(key) or {}
        lines.append(f"| {label} | {m.get('formal')} | {m.get('challenger')} | {m.get('delta')} |")
    lines += [
        "",
        f"log lossで改善案が上回ったレース：{p.get('challenger_better_log_loss_races')} / {p['pairs']}",
        "",
        "## 次の手順（手動）",
        "1. Claudeのチャットで「このIssueの判定材料をまとめて」と依頼する（副作用の内訳と推奨を作成）",
        "2. A（採用）／B（条件付き・追加検証）／C（見送り）を決めてこのIssueにコメントする",
        "3. Aの場合のみ、Claudeが正式プロンプトの新しい版を作成する",
        "",
        "この Issue は自動作成です。自動で採用・正式版変更は行いません。",
        "詳細：`docs/data/jra_experiment_status_v1.json`",
    ]
    return "\n".join(lines)


def main():
    status = json.loads((ROOT / "docs/data/jra_experiment_status_v1.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "e2e_validation/improvement_experiments_v1.json").read_text(encoding="utf-8"))
    reg = {e["id"]: e for e in registry.get("experiments", [])}
    for exp in status.get("experiments", []):
        if exp.get("ready_for_manual_review") and exp["prospective"].get("pairs", 0) >= exp["minimum_prospective_pairs"]:
            sys.stdout.write(json.dumps({"experiment_id": exp["id"], "title": title(exp["id"]),
                                         "body": body(exp, reg.get(exp["id"], {}))}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
