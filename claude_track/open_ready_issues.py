"""Open ONE GitHub Issue per Claude-track experiment that reached its decision threshold (idempotent by title).
The user answers A/B/C in the chat; the Issue is only the notification. Research only; nothing is bought or changed."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "claude-experiment-ready"


def needed(exp: dict) -> list[dict]:
    out = []
    p = exp.get("pace", {})
    if p.get("state") == "ready_for_decision":
        out.append({"title": "[Claude単独] 位置取りの補正：判定できます",
                    "body": (f"Claudeの予想 {p['pairs']} レースで、位置取りの補正あり・なしを比べました。\n\n"
                             f"- 勝ち馬に付けた確率の平均的な外れ具合（小さいほど良い）：補正なし {p['mean_log_loss_base']:.3f} → 補正あり {p['mean_log_loss_pace']:.3f}\n"
                             f"- 良くなったレース {p['races_improved']}／悪くなったレース {p['races_worse']}\n\n"
                             "チャットで A（採用してClaudeの予想に反映）／B（もう少し続ける）／C（採用しない）のどれかを伝えてください。\n"
                             "※ ChatGPT側の結果とは別枠です。研究用で、購入はしません。")})
    g = exp.get("going", {})
    if g.get("state") == "ready_for_decision":
        out.append({"title": "[Claude単独] 馬場の補正：判定できます",
                    "body": (f"Claudeの予想 {g['pairs']} レースで、馬場の補正あり・なしを比べました。\n\n"
                             f"- 勝ち馬に付けた確率の平均的な外れ具合（小さいほど良い）：補正なし {g['mean_log_loss_base']:.3f} → 補正あり {g['mean_log_loss_going']:.3f}\n"
                             f"- 良くなったレース {g['races_improved']}／悪くなったレース {g['races_worse']}\n\n"
                             "チャットで A（採用してClaudeの予想に反映）／B（もう少し続ける）／C（採用しない）のどれかを伝えてください。\n"
                             "※ ChatGPT側の結果とは別枠です。研究用で、購入はしません。")})
    pf = exp.get("portfolio", {})
    if pf.get("state") == "ready_for_decision" and pf.get("summary"):
        c, m = pf["summary"]["claude_own"], pf["summary"]["mechanical_rule"]
        out.append({"title": "[Claude単独] 購入セット：判定できます",
                    "body": (f"Claudeの予想 {pf['pairs']} レースで、Claude自身が作った買い目と、同じ予想・同じオッズから機械ルールで作った買い目を比べました（仮想・購入なし）。\n\n"
                             f"- 回収率：Claude自身 {c['roi']} ／ 機械ルール {m['roi']}\n- 的中レース：Claude自身 {c['hit_races']} ／ 機械ルール {m['hit_races']}\n\n"
                             "チャットで A（機械ルールを採用）／B（もう少し続ける）／C（採用しない）のどれかを伝えてください。")})
    for k, r in (exp.get("experience", {}).get("regimes") or {}).items():
        if r.get("state") == "ready_for_review":
            name = {"E0": "0戦", "E1": "1〜3戦", "E2": "4戦以上"}[k]
            out.append({"title": f"[Claude単独] 若駒（{name}）：確認できます",
                        "body": (f"Claudeの予想で、{name}の馬が {r['horses']} 頭分（{r['races']} レース）たまりました。\n\n"
                                 f"- 予想した勝ちの数（確率の合計）：{r['predicted_wins']}\n- 実際の勝ち：{r['actual_wins']}\n\n"
                                 "予想と実際のずれを確認して、補正を作るか決めます。チャットで A（補正案を作る）／B（もう少し集める）／C（見送り）を伝えてください。")})
    return out


def existing_titles() -> set[str]:
    r = subprocess.run(["gh", "api", f"repos/{subprocess.check_output(['gh','repo','view','--json','nameWithOwner','-q','.nameWithOwner'], text=True).strip()}/issues?state=all&labels={LABEL}&per_page=100", "--jq", ".[].title"],
                       capture_output=True, text=True, check=True)
    return {x for x in r.stdout.splitlines() if x}


def main():
    exp = json.loads((ROOT / "docs/data/predictors/claude_experiments_v1.json").read_text(encoding="utf-8"))
    todo = needed(exp)
    if not todo:
        print("no Claude-track experiment is ready"); return
    have = existing_titles()
    for it in todo:
        if it["title"] in have:
            print("already opened:", it["title"]); continue
        subprocess.run(["gh", "issue", "create", "--title", it["title"], "--body", it["body"], "--label", LABEL], check=True)
        print("opened:", it["title"])


if __name__ == "__main__":
    main()
