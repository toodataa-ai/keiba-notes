from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "baba_models_v2" / "model_registry.json"
TARGET = ROOT / "docs" / "data" / "baba_model_registry.json"


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    public = {
        "schema_version": data["schema_version"],
        "registry_version": data["registry_version"],
        "updated_at": data["updated_at"],
        "production_router_changed": data["production_router_changed"],
        "models": data["models"],
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
