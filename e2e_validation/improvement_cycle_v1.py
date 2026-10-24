#!/usr/bin/env python3
"""Non-promoting, audit-friendly weekly JRA and E0/E1/E2 improvement backlog.

Read-only against prestart forecasts and immutable proof. Never uses race results
to generate a new prestart forecast; evidence observations are hypotheses only.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    with (ROOT / path).open(encoding="utf-8") as f:
        return json.load(f)

def build(registry, review_status, e2e, shadow_status, regime_review, topics, experiments):
    verified = {
        x.get("race_id") for x in e2e.get("entries", [])
        if x.get("grade") == "prospective_strict"
        and (x.get("proof") or {}).get("read_from_proof_commit") is True
    }
    valid_reviewed = {
        r["id"]: r for r in registry.get("races", [])
        if r.get("scope") == "jra-main"
        and r.get("status") == "reviewed"
        and r.get("id") in verified
        and all(r.get(k) for k in ("result", "performance", "review", "settlements", "e2e_case"))
    }
    meetings = []
    race_to_meeting = {}
    complete_meetings = set()
    for m in review_status.get("meetings", []):
        complete = m.get("formal_grade_a_review_state") == "complete"
        if complete:
            complete_meetings.add(m["meeting_id"])
        race_ids = [r.get("race_id") for r in m.get("races", [])]
        meetings.append({
            "meeting_id": m["meeting_id"], "dates": m.get("dates", []),
            "reviewed": sum(rid in valid_reviewed for rid in race_ids),
            "expected": m.get("expected_races", len(race_ids)),
            "all_formal_reviews_complete": complete,
            "formal_improvement_decision": m.get("weekly_improvement_decision", "not_evaluated"),
        })
        for rid in race_ids:
            race_to_meeting[rid] = m["meeting_id"]

    # Every observation is tied to a sealed Grade A case and its original review.
    # String matching identifies INVESTIGATION TOPICS, not proven causal errors.
    hypotheses = []
    for topic in topics["topics"]:
        rx = re.compile(topic["pattern"])
        linked = []
        for rid, r in sorted(valid_reviewed.items()):
            review = r.get("review", "")
            review = review if isinstance(review, str) else str(review.get("summary", ""))
            if rx.search(review):
                linked.append({"race_id": rid, "meeting_id": race_to_meeting.get(rid),
                               "date": r.get("date")})
        weeks = sorted({r["meeting_id"] for r in linked if r["meeting_id"]})
        complete_weeks = sorted({r["meeting_id"] for r in linked
                                 if r["meeting_id"] in complete_meetings})
        hypotheses.append({
            "id": topic["id"], "source": "formal_jra_review",
            "title": topic["title"], "investigation": topic["investigation"],
            "race_observation_count": len(linked),
            "meeting_observation_count": len(weeks),
            "completed_meetings_with_observation": len(complete_weeks),
            "observation_races": linked,
            "status": ("repeated_in_completed_meetings"
                       if len(complete_weeks) >= 2 and len(linked) >= 3
                       else "collecting_observations" if linked else "not_observed"),
            "evidence_qualification": "topic_only_not_causal_proof",
            "ready_for_formal_promotion": False,
        })

    # The regime study has its own proof and review gate. Aggregates are NOT
    # interchangeable with paired predictions, so no statistical claims of
    # better accuracy can be made from finish rates alone.
    overall = regime_review.get("overall") or {}
    gaps = shadow_status.get("prerace_evidence_gap_count", 0)
    source_errors = shadow_status.get("evidence_gaps") or []
    regime_topics = []
    for regime, label in [("E0", "0戦"), ("E1", "1〜3戦"), ("E2", "4戦以上")]:
        v = overall.get(regime) or {}
        n = int(v.get("horse_observations") or 0)
        p = int(v.get("win_prediction_observations") or 0)
        q = int(v.get("top3_prediction_observations") or 0)
        regime_topics.append({
            "id": "experience_" + regime.lower(),
            "source": "experience_regime_research",
            "title": regime + "（" + label + "）の能力評価・不確実性",
            "investigation": "戦歴区分ごとの予測誤差・信頼度を発走前固定データで比較する",
            "race_observation_count": int(v.get("races") or 0),
            "horse_observation_count": n,
            "strict_win_probability_observations": p,
            "strict_top3_probability_observations": q,
            "status": ("no_observations" if not n else
                       "prediction_evidence_incomplete" if not p or not q else
                       "research_comparison_needed"),
            "evidence_qualification": "research_only_no_promotion",
            "ready_for_formal_promotion": False,
        })

    c = e2e.get("comparison") or {}
    shared = max(0, int(c.get("strict_shared_cases") or 0))
    minimum = max(1, int(c.get("minimum_strict_shared_cases") or 20))
    # No pairing is reconstructed from distinct races or historic replays.
    comparator_ready = (shared >= minimum and c.get("state") == "ready_for_review"
                        and not e2e.get("errors"))
    proposals = experiments.get("experiments") or []
    # Experiment registry entries are plans; status is never inferred as
    # approved from a self-entered label. Separate human review is required.
    tracked_experiments = [{
        "id": exp["id"], "title": exp["title"],
        "hypothesis_ids": exp.get("hypothesis_ids", []),
        "baseline": exp.get("baseline"), "challenger": exp.get("challenger"),
        "status": exp.get("status", "design"),
        "prestart_pairing_required": True,
        "auto_approved": False,
    } for exp in proposals]
    return {
        "schema_version": 1,
        "source_policy": "prospective_strict_review_only_for_formal_topics;regime_aggregates_research_only",
        "latest_formal_prompt_version": review_status.get("latest_formal_prompt_version"),
        "formal": {
            "strict_verified_reviews": len(valid_reviewed),
            "grade_a_passed": review_status.get("formal_grade_a", {}).get("passed") is True,
            "meetings": meetings,
            "hypotheses": hypotheses,
            "comparison": {
                "baseline": c.get("baseline"), "candidate": c.get("candidate"),
                "paired_strict_cases": shared, "minimum_paired_cases": minimum,
                "state": c.get("state", "unknown"),
                "sufficient_for_review": comparator_ready,
                "data_quality_note": "異なるレースや過去再現の比較を同一レース実戦比較として数えない",
            },
        },
        "research": {
            "source": "E0/E1/E2 research independent of formal Grade A",
            "evidence_gap_count": gaps,
            "evidence_gap_race_ids": sorted({str(x.get("race_id")) for x in source_errors if x.get("race_id")}),
            "regimes": regime_topics,
            "automatic_promotion": False,
            "quality_warning": "研究の結果集計だけでは予測精度・因果効果を証明できない。発走前の固定予測が必要",
        },
        "experiments": tracked_experiments,
        "gates": {
            "formal_candidate_e2e_ready": comparator_ready,
            "a_b_c_manual_approval_required": True,
            "automated_prompt_change": False,
            "past_prediction_immutability": True,
            "pending_experiments": sum(x["status"] != "approved" for x in tracked_experiments),
            "required_next_steps": [
                "週次の全正式メイン回顧を完了して調査テーマを蓄積",
                "E0/E1/E2は発走前研究証拠とカテゴリ別予測確率の欠損を解消",
                "仮説ごとに変更対象を限定したchallengerを発走前に固定",
                "同一レース・同一情報締切の旧版とchallengerを厳格比較",
                "過剰適合チェックとA/B/C承認を通過して初めて正式版変更",
            ],
        },
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="docs/data/jra_improvement_cycle_v1.json")
    args = p.parse_args()
    report = build(
        read("docs/data/races.json"),
        read("docs/data/jra_review_completion.json"),
        read("docs/data/e2e_status.json"),
        read("docs/data/jra_review_completion.json")["shadow_research"],
        read("docs/data/experience_regime_review_status.json"),
        read("e2e_validation/improvement_topics_v1.json"),
        read("e2e_validation/improvement_experiments_v1.json"),
    )
    dest = ROOT / args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("IMPROVEMENT_CYCLE", json.dumps({
        "strict": report["formal"]["strict_verified_reviews"],
        "hypotheses": len(report["formal"]["hypotheses"]),
        "e0e1e2": len(report["research"]["regimes"]),
        "paired": report["formal"]["comparison"]["paired_strict_cases"],
        "automatic_promotion": report["gates"]["automated_prompt_change"],
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
