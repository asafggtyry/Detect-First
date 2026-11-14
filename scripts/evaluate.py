from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detect_first.evaluation import evaluate_synthetic
from detect_first.model import DATA_PATH, MODEL_PATH, load_pipeline


def main() -> None:
    result = evaluate_synthetic(
        load_pipeline(MODEL_PATH),
        ROOT / "data" / "synthetic" / "evaluation.jsonl",
        DATA_PATH,
    )
    report_path = ROOT / "reports" / "synthetic_evaluation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Synthetic evaluation report saved to {report_path}")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
