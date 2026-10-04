from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "baba_models_v2" / "model_registry.json"
TARGET = ROOT / "docs" / "data" / "baba_model_registry.json"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} from {SOURCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
