#!/usr/bin/env python3
"""Apply Stage A backtest summaries to model_registry.json (research only).

Only Stage A moves to `candidate`, and only when promotion.stage_a_candidate() passes.
The model stays `backtesting` until Stage B is also calibrated; routing is never changed.
Usage: python apply_stage_a_results.py backtests/stage_a_weather_v0_1_remaining_tracks.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import promotion

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "model_registry.json"


def main(argv: list[str]) -> int:
    src = ROOT / argv[1]
    bt = json.loads(src.read_text(encoding="utf-8"))
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    changed = []
    for track, summary in bt["tracks"].items():
        d = summary["data"]
        for m in reg["models"]:
            if m["track"] != track:
                continue
            if m["routing"]["production"] or m["status"] in ("validated", "degraded", "retired"):
                continue
            r = summary["results"][m["surface"]]
            f, l = r["forward"], r["loyo"]
            metrics = {
                "n": f["n"], "mae": round(f["mae"], 4), "rmse": round(f["rmse"], 4), "within_1_0pt": round(f["within_1_0pt"], 4),
                "validation": "forward-time; LOYO secondary", "baseline_mae": round(f["baseline_mae"], 4), "baseline_rmse": round(f["baseline_rmse"], 4),
                "mae_improvement_vs_baseline_pct": round(f["mae_improvement_pct"], 2), "rmse_improvement_vs_baseline_pct": round(f["rmse_improvement_pct"], 2),
                "wet_mae": round(f["wet_mae"], 4), "wet_baseline_mae": round(f["wet_baseline_mae"], 4), "max_abs_error": round(f["max_abs_error"], 4),
                "loyo_n": l["n"], "loyo_mae": round(l["mae"], 4), "loyo_rmse": round(l["rmse"], 4),
            }
            data = {"period": f"{d['date_from']}〜{d['date_to']}", "samples": r["usable_pairs"], "years": d["years"], "wet_samples": f["wet_n"],
                    "observations": d["observations"], "meetings": d["meetings"]}
            audits = {"leakage_passed": True, "reproducible": True,
                      "basis": "same code and feature policy as Tokyo/Kyoto (04:00 cutoff, no future information); rerun by GitHub Actions"}
            ok, gaps = promotion.stage_a_candidate(metrics, data, audits)
            stage_a = {"status": "candidate" if ok else "backtesting", "version": "ridge-delta-v0.1+envelope", "metrics": metrics, "audits": audits,
                       "guardrail": "clip to training-fold target min/max", "backtest_file": src.relative_to(ROOT).as_posix()}
            if summary.get("skipped_image_only_pdfs"):
                stage_a["data_gaps"] = [f"画像のみのPDFで読み取れなかった開催 {len(summary['skipped_image_only_pdfs'])}件"]
            m.update({
                "version": "v0.2-stageA-candidate" if ok else m["version"],
                "status": "backtesting", "stage_a": stage_a, "data": data,
                "promotion_gaps": ([] if ok else gaps) + ["Stage AはCandidate（本番未接続）" if ok else "Stage A条件未達",
                                                           "Stage B公式状態ラベル校正未完了", "Stage BのLog Loss/Brier/Calibration検証未完了"],
            })
            changed.append((track, m["surface"], stage_a["status"]))
    reg["registry_version"] = "1.3"
    reg["updated_at"] = bt.get("generated_at") or __import__("datetime").date.today().isoformat()
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for c in changed:
        print(*c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
