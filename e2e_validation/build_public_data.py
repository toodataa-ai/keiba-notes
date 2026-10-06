from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Derived public data only. Source-of-truth prediction/result/case files stay under e2e_validation/.
ROOT = Path(__file__).resolve().parents[1]
E2E = ROOT / "e2e_validation"
DOCS_DATA = ROOT / "docs" / "data"
PUBLIC_ROOT = DOCS_DATA / "e2e-shadow"
PUBLIC_MANIFEST = DOCS_DATA / "e2e_public.json"
STATUS_PATH = DOCS_DATA / "e2e_status.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def copy_json(src: Path, relative_public: Path) -> str | None:
    if not src.exists():
        return None
    dest = ROOT / "docs" / relative_public
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return relative_public.as_posix()


def resolve_repo_path(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def preview_prediction(pred: dict) -> dict:
    ctx = pred.get("race_context") or {}
    return {
        "version": pred.get("prompt_version"),
        "generated_at": pred.get("generated_at"),
        "information_cutoff_at": pred.get("information_cutoff_at"),
        "sample_origin": ctx.get("sample_origin"),
        "race_no": ctx.get("race_no"),
        "race_name": ctx.get("race_name"),
        "marks": pred.get("marks") or {},
        "pace": (pred.get("pace") or {}).get("label"),
        "going_probabilities": (pred.get("track") or {}).get("going_probabilities") or {},
        "step1_ranking": pred.get("step1_ranking") or [],
        "bets": pred.get("bets") or [],
    }


def build_case_entry(case_path: Path, grade: str) -> dict:
    case = load_json(case_path)
    race_id = case.get("race_id") or case_path.parent.name
    public_case_rel = Path("data/e2e-shadow/cases") / race_id / case_path.name
    copied_case = copy_json(case_path, public_case_rel)

    predictions = []
    for p in case.get("predictions") or []:
        src = resolve_repo_path(p.get("path"))
        pred = load_json(src) if src and src.exists() else {}
        filename = src.name if src else f"{p.get('version','unknown')}.json"
        public_rel = Path("data/e2e-shadow/predictions") / race_id / filename
        copied = copy_json(src, public_rel) if src else None
        item = preview_prediction(pred)
        item.update(
            {
                "version": p.get("version") or item.get("version"),
                "proof_commit": p.get("proof_commit"),
                "prompt_manifest": pred.get("prompt_manifest"),
                "prediction_path": copied,
                "source_prediction_path": p.get("path"),
            }
        )
        predictions.append(item)

    result_src = resolve_repo_path(case.get("result_path"))
    result = load_json(result_src) if result_src and result_src.exists() else None
    result_rel = Path("data/e2e-shadow/results") / (result_src.name if result_src else f"{race_id}.json")
    copied_result = copy_json(result_src, result_rel) if result_src else None

    first_pred = predictions[0] if predictions else {}
    return {
        "race_id": race_id,
        "date": case.get("date"),
        "venue": case.get("venue"),
        "surface": case.get("surface"),
        "race_name": case.get("race") or first_pred.get("race_name"),
        "race_no": first_pred.get("race_no"),
        "grade": grade,
        "status": "reviewed" if result else "predicted",
        "cutoff_at": case.get("cutoff_at"),
        "case_path": copied_case,
        "result_path": copied_result,
        "official_result_at": (result or {}).get("official_result_at"),
        "official_going": (result or {}).get("official_going"),
        "finish_order": (result or {}).get("finish_order") or [],
        "predictions": predictions,
    }


def main() -> None:
    if PUBLIC_ROOT.exists():
        shutil.rmtree(PUBLIC_ROOT)
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)

    strict = []
    historical = []
    cases_root = E2E / "cases"
    if cases_root.exists():
        for race_dir in sorted([p for p in cases_root.iterdir() if p.is_dir()]):
            strict_case = race_dir / "case.json"
            replay_case = race_dir / "historical-replay.json"
            if strict_case.exists():
                strict.append(build_case_entry(strict_case, "prospective_strict"))
            if replay_case.exists():
                historical.append(build_case_entry(replay_case, "historical_replay"))

    strict.sort(key=lambda x: ((x.get("date") or ""), x.get("race_id") or ""), reverse=True)
    historical.sort(key=lambda x: ((x.get("date") or ""), x.get("race_id") or ""), reverse=True)

    status = load_json(STATUS_PATH) if STATUS_PATH.exists() else {}
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "jra_e2e_shadow_public",
        "production_effect": False,
        "policy": {
            "formal_comparison_grade": "prospective_strict",
            "historical_replay_supporting_only": True,
            "prediction_immutable_after_cutoff": True,
            "result_joined_separately": True,
        },
        "comparison": status.get("comparison") or {},
        "totals": {
            "prospective_strict_races": len(strict),
            "historical_replay_races": len(historical),
            "prospective_prediction_entries": sum(len(x.get("predictions") or []) for x in strict),
            "prospective_results_joined": sum(1 for x in strict if x.get("status") == "reviewed"),
        },
        "races": strict,
        "historical_replays": historical,
    }
    write_json(PUBLIC_MANIFEST, manifest)


if __name__ == "__main__":
    main()
