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
        "## 副作用の確認（条件別の勝率log loss。差がマイナスなら改善案が良い）",
        "",
        "| 区分 | 条件 | 件数 | 正式版 | 改善案 | 差 | ◎3着内率の差 |",
        "|---|---|---|---|---|---|---|",
    ]
    dims = {"surface": "芝ダート", "going": "馬場", "venue": "競馬場"}
    worse = []
    for dim, label in dims.items():
        for key, m in (exp.get("prospective_breakdown") or {}).get(dim, {}).items():
            ll, t3 = m.get("win_log_loss") or {}, m.get("honmei_top3") or {}
            lines.append(f"| {label} | {key} | {m.get('pairs')} | {ll.get('formal')} | "
                         f"{ll.get('challenger')} | {ll.get('delta')} | {t3.get('delta')} |")
            if (ll.get("delta") or 0) > 0 and m.get("pairs", 0) >= 3:
                worse.append(f"{label}：{key}")
    lines += [
        "",
        "## 自動チェック（事前に決めた採用条件との照合）",
    ]
    ll, br, t3 = (p.get(k) or {} for k in ("win_log_loss", "win_brier", "honmei_top3"))
    checks = [
        ("勝率log lossが改善", (ll.get("delta") or 0) < 0),
        ("勝率Brierが改善", (br.get("delta") or 0) < 0),
        ("◎3着内率が悪化していない", (t3.get("delta") or 0) >= 0),
    ]
    lines += [f"- {'✅' if ok else '❌'} {name}" for name, ok in checks]
    verdict = ("採用条件をすべて満たしています（A候補）" if all(ok for _, ok in checks)
               else "採用条件を満たしていません（C候補）")
    lines.append(f"- **機械判定：{verdict}**")
    if worse:
        lines.append(f"- ⚠️ 3件以上ある条件で悪化：{'、'.join(worse)}（Bで追加検証も検討）")
    lines += [
        "",
        "これは機械的な照合です。最終判断はあなたが行います。",
        "",
        "## 次の手順（手動）",
        "1. 上の成績・副作用・自動チェックを見て、A（採用）／B（追加検証）／C（見送り）を決める",
        "2. このIssueに A / B / C とコメントする",
        "3. Aの場合のみ、Claudeのチャットで「EXP-xxxをAで反映して」と依頼する（正式プロンプトの新しい版を作成）",
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
