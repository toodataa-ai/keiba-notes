"""ChatGPT と Claude の「同じレースだけ」の成績比較（2026-11-06 決定のルール）。
ルール：
  1. 比べるのは、両方が予想して、結果と採点がそろった同じレースだけ（日付＋競馬場で突き合わせ、レース名も合うこと）。
  2. 見送り（購入0円）のレースも、1レースとして数える（購入0円・払戻0円）。
  3. 回収率の優劣は100レースたまるまで結論を出さない（表示だけ）。
読むのは、結果が出たあとの採点済みの数字だけ（ChatGPT の予想そのものは読まない）。出力：docs/data/predictors/head_to_head_v1.json"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_RACES_FOR_VERDICT = 100


def norm(name: str) -> str:
    x = re.sub(r"[\s　（）()]", "", name or "")
    x = x.replace("ステークス", "")
    return re.sub(r"S$", "", x)


def same_race_name(a: str, b: str) -> bool:
    x, y = norm(a), norm(b)
    return bool(x and y and (x in y or y in x))


def build(claude_status: dict, chatgpt_races: dict) -> dict:
    gpt = {}
    for r in chatgpt_races.get("races", []):
        perf = r.get("performance") or {}
        if r.get("scope") == "jra-main" and "stake_yen" in perf and "payout_yen" in perf:
            gpt[(r["date"], r["venue"])] = r
    rows, claude_only, name_mismatch = [], [], []
    seen = set()
    for c in claude_status.get("races", []):
        res = c.get("result")
        if not res or not res.get("prospective"):
            continue
        key = (c["date"], c["venue"])
        g = gpt.get(key)
        if not g:
            claude_only.append({"date": c["date"], "venue": c["venue"], "race_name": c.get("race_name")})
            continue
        if not same_race_name(c.get("race_name", ""), g.get("race", "")):
            name_mismatch.append({"date": c["date"], "venue": c["venue"], "claude": c.get("race_name"), "chatgpt": g.get("race")})
            continue
        seen.add(key)
        gp = g["performance"]
        rows.append({"date": c["date"], "venue": c["venue"], "race_name": c.get("race_name"),
                     "claude": {"stake_yen": res["stake_yen"], "payout_yen": res["payout_yen"], "skipped": res["stake_yen"] == 0},
                     "chatgpt": {"stake_yen": gp["stake_yen"], "payout_yen": gp["payout_yen"], "skipped": gp["stake_yen"] == 0}})
    chatgpt_only = [{"date": k[0], "venue": k[1], "race_name": v.get("race")} for k, v in sorted(gpt.items()) if k not in seen
                    and not any(m["date"] == k[0] and m["venue"] == k[1] for m in name_mismatch)]
    rows.sort(key=lambda r: (r["date"], r["venue"]))

    def side(k):
        s = sum(r[k]["stake_yen"] for r in rows)
        p = sum(r[k]["payout_yen"] for r in rows)
        return {"stake_yen": s, "payout_yen": p, "profit_yen": p - s, "roi": (p / s) if s else None,
                "skipped_races": sum(1 for r in rows if r[k]["skipped"])}
    n = len(rows)
    return {"schema_version": 1, "races": n, "claude": side("claude"), "chatgpt": side("chatgpt"),
            "verdict": "参考表示（回収率の優劣は%dレースたまるまで結論を出さない）" % MIN_RACES_FOR_VERDICT if n < MIN_RACES_FOR_VERDICT else "判定可能（区間を見て判断）",
            "rules": ["両方が予想して結果がそろった同じレースだけで比べる（日付＋競馬場＋レース名）",
                      "見送り（購入0円）も1レースとして数える", "回収率の優劣は100レースまで結論を出さない"],
            "excluded": {"claude_only": claude_only, "chatgpt_only": chatgpt_only, "name_mismatch": name_mismatch},
            "rows": rows}


def main():
    cs = json.loads((ROOT / "docs/data/predictors/claude_status_v1.json").read_text(encoding="utf-8"))
    gr = json.loads((ROOT / "docs/data/races.json").read_text(encoding="utf-8"))
    out = ROOT / "docs/data/predictors/head_to_head_v1.json"
    d = build(cs, gr)
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: common={d['races']}")


if __name__ == "__main__":
    main()
