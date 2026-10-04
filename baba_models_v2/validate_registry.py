from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "model_registry.json"
POLICY = ROOT / "promotion_policy.json"
EXPECTED_TRACKS = {"sapporo","hakodate","fukushima","niigata","tokyo","nakayama","chukyo","kyoto","hanshin","kokura"}
EXPECTED_SURFACES = {"turf", "dirt"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(msg: str):
    raise AssertionError(msg)


def validate() -> None:
    registry = load(REGISTRY)
    policy = load(POLICY)
    allowed = set(policy["allowed_statuses"])
    models = registry.get("models", [])
    if len(models) != 20:
        fail(f"expected 20 track/surface models, got {len(models)}")

    keys = set()
    for model in models:
        key = (model["track"], model["surface"])
        if key in keys:
            fail(f"duplicate model: {key}")
        keys.add(key)
        if model["track"] not in EXPECTED_TRACKS:
            fail(f"unknown track: {model['track']}")
        if model["surface"] not in EXPECTED_SURFACES:
            fail(f"unknown surface: {model['surface']}")
        if model["status"] not in allowed:
            fail(f"invalid overall status for {key}: {model['status']}")
        for stage in ("stage_a", "stage_b"):
            status = model[stage]["status"]
            if status not in allowed:
                fail(f"invalid {stage} status for {key}: {status}")

        routing = model.get("routing", {})
        if routing.get("production") and model["status"] not in {"validated", "degraded"}:
            fail(f"non-validated model cannot be routed to production: {key}")
        if model["status"] == "candidate" and routing.get("production"):
            fail(f"candidate cannot auto-activate production routing: {key}")

        if model["stage_a"]["status"] in {"candidate", "validated"}:
            metrics = model["stage_a"].get("metrics") or {}
            for metric in policy["stage_a"]["required_metrics"]:
                if metric not in metrics:
                    fail(f"{key} missing Stage A metric {metric}")

        if model["stage_b"]["status"] in {"candidate", "validated"}:
            metrics = model["stage_b"].get("metrics") or {}
            for metric in policy["stage_b"]["required_metrics"]:
                if metric not in metrics:
                    fail(f"{key} missing Stage B metric {metric}")

    expected = {(t, s) for t in EXPECTED_TRACKS for s in EXPECTED_SURFACES}
    if keys != expected:
        fail(f"registry coverage mismatch: missing={sorted(expected-keys)}, extra={sorted(keys-expected)}")

    if registry.get("production_router_changed") is not False:
        fail("B-scope registry change must not claim a production router change")


def main() -> int:
    try:
        validate()
    except Exception as exc:
        print(f"BABA REGISTRY INVALID: {exc}", file=sys.stderr)
        return 1
    print("BABA REGISTRY OK: 20 track/surface models; no unauthorized production activation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
