#!/usr/bin/env python3
"""Improvement pipeline status (research -> registration -> comparison -> decision).

Read-only over sealed/derived inputs. Writes docs/data/jra_improvement_pipeline_v1.json and,
with --issues, prints JSON lines for units that newly met their registration criteria.
Nothing here registers, approves or promotes anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "e2e_validation/improvement_pipeline_policy_v1.json"
REGISTRY = ROOT / "e2e_validation/improvement_experiments_v1.json"
EXP_STATUS = ROOT / "docs/data/jra_experiment_status_v1.json"
CYCLE = ROOT / "docs/data/jra_improvement_cycle_v1.json"
BABA = ROOT / "docs/data/baba_model_registry.json"
EXPERIENCE_EVIDENCE = ROOT / "docs/data/experience_regime_factor_evidence_status.json"
OUT = ROOT / "docs/data/jra_improvement_pipeline_v1.json"
LABEL = "registration-ready"
STAGES = ["研究", "登録", "比較", "判定"]


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def matching_experiments(unit_id: str, hypothesis_id: str | None, registry: dict, status: dict):
    """Experiments that belong to this unit.

    A registry entry may list `unit_ids`; otherwise it belongs to the hypothesis-wide unit only
    (the unit whose `hypothesis_id` it lists), never to a finer-grained unit.
    """
    by_id = {e["id"]: e for e in status.get("experiments", [])}
    out = []
    for r in registry.get("experiments", []):
        units = r.get("unit_ids")
        if units is not None:
            hit = unit_id in units
        else:
            hit = bool(hypothesis_id) and hypothesis_id in (r.get("hypothesis_ids") or [])
        if hit:
            out.append({**r, **by_id.get(r["id"], {})})
    return out


def comparison_state(exps: list[dict]):
    """(stage, frac, text, experiment_id) for registered experiments."""
    e = exps[0]
    pairs = (e.get("prospective") or {}).get("pairs", 0)
    need = e.get("minimum_prospective_pairs") or 20
    if e.get("status") in ("approved", "rejected"):
        return 3, 1.0, "判定ずみ：" + ("採用" if e["status"] == "approved" else "見送り"), e["id"]
    if e.get("status") == "reviewing" or e.get("ready_for_manual_review"):
        return 3, 0.0, f"判定待ち（{e['id']}）", e["id"]
    return 2, min(1.0, pairs / need), f"比較 {pairs}/{need}レース（{e['id']}）", e["id"]


def unit_record(theme, u, label, stage, frac, state, text, criteria_text, met, exp_id=None, detail=None):
    return {"id": u, "theme": theme, "label": label, "stage": stage, "stage_name": STAGES[stage] if stage is not None else None,
            "frac": round(frac, 4), "state": state, "text": text, "criteria_text": criteria_text,
            "criteria_met": met, "experiment_id": exp_id, "detail": detail or {}}


def build(policy, registry, status, cycle, baba, evidence, today=None):
    today = today or dt.date.today()
    hyp = {h["id"]: h for h in ((cycle or {}).get("formal") or {}).get("hypotheses", [])}
    regimes = {r["id"]: r for r in ((cycle or {}).get("research") or {}).get("regimes", [])}
    crit = policy["criteria"]
    units: list[dict] = []
    done: dict[str, bool] = {}

    def finish(rec):
        units.append(rec)
        done[rec["id"]] = bool(rec["criteria_met"])

    for theme in policy["themes"]:
        tid = theme["id"]
        for u in theme["units"]:
            kind = u["kind"]
            if kind == "screening":
                h = hyp.get(u["hypothesis_id"], {})
                scr = (h.get("next_decision") or {}).get("screening") or {}
                met = bool(scr.get("ready_to_design_experiment"))
                exps = matching_experiments(u["id"], u["hypothesis_id"], registry, status)
                if exps:
                    s, f, t, eid = comparison_state(exps)
                    finish(unit_record(tid, u["id"], u["label"], s, f, "comparing" if s == 2 else "decided", t, crit["screening"]["text"], True, eid))
                elif met:
                    finish(unit_record(tid, u["id"], u["label"], 1, 0.0, "ready_to_register", "条件に届いた（登録待ち）", crit["screening"]["text"], True))
                else:
                    q = scr.get("qualifying_race_reviews", 0)
                    n = scr.get("minimum_qualifying_race_reviews", 3)
                    finish(unit_record(tid, u["id"], u["label"], 0, min(1.0, q / n) if n else 0, "research", f"回顧で課題が出たレース {q}/{n}", crit["screening"]["text"], False))
            elif kind == "baba_tracks":
                models = (baba or {}).get("models", [])
                by: dict[str, dict] = {}
                for m in models:
                    by.setdefault(m["track"], {})[m["surface"]] = m
                score = {"validated": 1.0, "candidate": 0.75, "backtesting": 0.5, "pilot": 0.0}
                label_ja = {k: v for k, v in policy["tracks"]}
                for key, ja in policy["tracks"]:
                    v = by.get(key, {})
                    uid = f"track_condition:track:{key}"
                    st = {s: (v.get(s) or {}).get("status", "—") for s in ("turf", "dirt")}
                    sa = {s: ((v.get(s) or {}).get("stage_a") or {}).get("status", "—") for s in ("turf", "dirt")}
                    sb = {s: ((v.get(s) or {}).get("stage_b") or {}).get("status", "—") for s in ("turf", "dirt")}
                    ja_st = {"validated": "検証済み", "candidate": "候補", "backtesting": "検証中", "pilot": "試作", "—": "—"}
                    in_prod = any((v.get(s) or {}).get("routing", {}).get("production") for s in ("turf", "dirt"))
                    met = all(st[s] in crit["baba_track"]["ok_statuses"] for s in st)
                    detail = {"turf": st["turf"], "dirt": st["dirt"], "stage_a": sa, "stage_b": sb, "in_production": in_prod}
                    text_st = (f"Stage A（翌朝の含水率）：芝{ja_st.get(sa['turf'], sa['turf'])}・ダ{ja_st.get(sa['dirt'], sa['dirt'])} ／ "
                               f"Stage B（発走時の馬場）：芝{ja_st.get(sb['turf'], sb['turf'])}・ダ{ja_st.get(sb['dirt'], sb['dirt'])}")
                    exps = matching_experiments(uid, None, registry, status)
                    if exps:
                        s, f, t, eid = comparison_state(exps)
                        finish(unit_record(tid, uid, ja, s, f, "comparing" if s == 2 else "decided", t, crit["baba_track"]["text"], True, eid, detail))
                    elif in_prod:
                        finish(unit_record(tid, uid, ja, 3, 1.0, "in_production", "本番の予想で使用中（改善案としての比較は不要）", crit["baba_track"]["text"], False, None, detail))
                    elif met:
                        finish(unit_record(tid, uid, ja, 1, 0.0, "ready_to_register", f"条件に届いた（登録待ち）　{text_st}", crit["baba_track"]["text"], True, None, detail))
                    else:
                        # half of the progress is Stage A, half Stage B (the stage that matters at race time)
                        sc = sum(0.5 * score.get(sa[s], 0.0) + 0.5 * score.get(sb[s], 0.0) for s in st) / 2
                        finish(unit_record(tid, uid, ja, 0, sc, "research", text_st, crit["baba_track"]["text"], False, None, detail))
            elif kind == "experience_regime":
                r = regimes.get(u["regime"], {})
                need = crit["experience_regime"]["need_strict_records"]
                rem = (r.get("next_decision") or {}).get("win_probability_horse_records_remaining")
                met = rem == 0
                exps = matching_experiments(u["id"], None, registry, status)
                if exps:
                    s, f, t, eid = comparison_state(exps)
                    finish(unit_record(tid, u["id"], u["label"], s, f, "comparing" if s == 2 else "decided", t, crit["experience_regime"]["text"], True, eid))
                elif met:
                    finish(unit_record(tid, u["id"], u["label"], 1, 0.0, "ready_to_register", "条件に届いた（登録待ち）", crit["experience_regime"]["text"], True))
                else:
                    est = (r.get("next_decision") or {}).get("additional_races_estimate")
                    frac = 0.0 if rem is None else max(0.0, (need - rem) / need)
                    txt = "データを確認中" if rem is None else f"あと{rem}頭分" + (f"（約{est}レース）" if est else "")
                    finish(unit_record(tid, u["id"], u["label"], 0, frac, "research", txt, crit["experience_regime"]["text"], False, None, {"collected_prerace_horses": r.get("collected_prerace_horse_observations")}))
            elif kind == "pedigree":
                pc = crit["pedigree"]
                horses = (evidence or {}).get("horses") or 0
                have = ((evidence or {}).get("factor_support_counts") or {}).get("6", 0)
                cov = (have / horses) if horses else 0.0
                reqs_met = all(done.get(x, False) or any(r["id"] == x and r["stage"] >= 1 for r in units) for x in pc["requires"])
                met = reqs_met and cov >= pc["min_coverage"]
                exps = matching_experiments(u["id"], None, registry, status)
                detail = {"pedigree_coverage": round(cov, 4), "requires_met": reqs_met}
                if exps:
                    s, f, t, eid = comparison_state(exps)
                    finish(unit_record(tid, u["id"], u["label"], s, f, "comparing" if s == 2 else "decided", t, pc["text"], True, eid, detail))
                elif met:
                    finish(unit_record(tid, u["id"], u["label"], 1, 0.0, "ready_to_register", "条件に届いた（登録待ち）", pc["text"], True, None, detail))
                else:
                    parts = [f"血統の情報 {int(cov*100)}%（目標{int(pc['min_coverage']*100)}%）"]
                    if not reqs_met:
                        parts.append("0戦・1〜3戦の条件はこれから")
                    finish(unit_record(tid, u["id"], u["label"], 0, cov * 0.5 if not reqs_met else cov, "research", "／".join(parts), pc["text"], False, None, detail))
    updated = (baba or {}).get("updated_at")
    stale = None
    if updated:
        try:
            age = (today - dt.date.fromisoformat(updated)).days
            stale = {"updated_at": updated, "age_days": age, "is_stale": age > policy["stale_days"], "owner": policy["owners"]["baba"]}
        except ValueError:
            stale = None
    return {
        "schema_version": 1,
        "generated_by": "e2e_validation/improvement_pipeline_v1.py",
        "automatic_promotion": False,
        "stages": STAGES,
        "owners": policy["owners"],
        "themes": [{"id": t["id"], "title": t["title"]} for t in policy["themes"]],
        "baba_registry_freshness": stale,
        "experience_evidence_week": (evidence or {}).get("week_id"),
        "units": units,
    }


SITE = "https://toodataa-ai.github.io/keiba-notes/"


def material_lines(unit: dict, cycle: dict) -> list[str]:
    """判断の材料。Issue だけ読めば A/B/C を決められるようにする。"""
    lines = ["## 判断の材料"]
    theme = unit["theme"]
    h = next((x for x in ((cycle or {}).get("formal") or {}).get("hypotheses", []) if x["id"] == theme), None)
    if h:
        plan = h.get("public_plan") or {}
        scr = (h.get("next_decision") or {}).get("screening") or {}
        rows = [("何を確かめたいか", plan.get("question")), ("比べる案", plan.get("considering")),
                ("必要なデータ", plan.get("data_needed")), ("良し悪しの見方", plan.get("success_metric")),
                ("調べ方", h.get("investigation"))]
        lines += [f"- **{k}**：{v}" for k, v in rows if v]
        lines.append(f"- **回顧で同じ課題が出た回数**：{h.get('race_observation_count')}レース／{h.get('meeting_observation_count')}開催"
                     f"（基準は{scr.get('minimum_qualifying_race_reviews', 3)}レース・{scr.get('minimum_completed_meetings', 2)}開催）")
        races = h.get("observation_races") or []
        if races:
            lines.append("- **課題が出たレース**：" + "、".join(f"{r['date']} {r['race_id'].split('-', 3)[-1]}" for r in races))
    d = unit.get("detail") or {}
    if d:
        lines.append(f"- **単位の詳細**：{json.dumps(d, ensure_ascii=False)}")
    lines += ["", "## 見る場所",
              f"- 予想の改善状況（段階と条件）：{SITE}improvement-cycle.html",
              f"- 過去の結果・回顧（課題の出たレースの振り返り）：{SITE}results.html",
              f"- 判定データ（機械用）：docs/data/jra_improvement_pipeline_v1.json、docs/data/jra_improvement_cycle_v1.json"]
    return lines


def issue_drafts(result: dict, cycle: dict | None = None):
    for u in result["units"]:
        if u["state"] != "ready_to_register":
            continue
        body = "\n".join([
            f"## {u['label']}（{u['id']}）が、改善案として登録できる条件に届きました",
            "",
            f"- 条件：{u['criteria_text']}",
            f"- いまの状況：{u['text']}",
            "",
            *material_lines(u, cycle or {}),
            "",
            "## どう答えるか（コメントで A / B / C）",
            "- **A（登録する）**：Claude が、この単位用の比較プログラム（正式 v3.13 STEP1 だけから決定的に計算する関数）を書き、"
            "別の実験IDとして登録します。登録後に発走するレースから、今の予想と20レースで比べます（約4週間）。",
            "- **B（もう少し待つ）**：条件は満たしているが、いま走っている比較（EXP-001・EXP-002）の結果を見てからにしたい場合など。",
            "- **C（登録しない）**：この単位は改善の対象にしない場合。",
            "",
            "※ このIssueは通知だけです。何も自動では登録・採用されません。",
        ])
        yield {"unit_id": u["id"], "title": f"[登録できます] {u['label']}（{u['id']}）", "body": body}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", action="store_true", help="print JSON lines of Issue drafts instead of writing the status file")
    args = ap.parse_args(argv)
    cycle = load(CYCLE, {})
    result = build(load(POLICY), load(REGISTRY, {}), load(EXP_STATUS, {}), cycle, load(BABA, {}), load(EXPERIENCE_EVIDENCE, {}))
    if args.issues:
        for d in issue_drafts(result, cycle):
            print(json.dumps(d, ensure_ascii=False))
        return 0
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for u in result["units"]:
        print(f"{u['id']:38} {u['state']:18} stage={u['stage']} frac={u['frac']:.2f} {u['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
