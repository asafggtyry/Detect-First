"""Run the held-out blind evaluation without fitting or changing the model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from detect_first.blind_evaluation import BlindEvaluationService
from detect_first.model import MODEL_PATH, load_pipeline, predict_scam
from detect_first.server import ScanService

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports" / "blind_ai_evaluation.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    model_path = ROOT / MODEL_PATH
    pipeline = load_pipeline(model_path)
    scan_service = ScanService(lambda text: predict_scam(text, pipeline))
    runner = BlindEvaluationService(scan_service.analyze)
    runner.start("report", seed=2026)

    samples = []
    while True:
        result = runner.next("report")
        if result["complete"]:
            metrics = result["metrics"]
            break
        samples.append({
            key: result[key]
            for key in (
                "sample_id", "difficulty", "text", "reference_label",
                "model_prediction", "evidence_prediction", "combined_prediction",
            )
        })

    systems = {
        "model": "model_prediction",
        "evidence_rules": "evidence_prediction",
        "combined_warning": "combined_prediction",
    }
    errors = {
        name: {
            "false_alarms": [item["sample_id"] for item in samples
                             if item[prediction] == 1 and item["reference_label"] == 0],
            "missed_scams": [item["sample_id"] for item in samples
                             if item[prediction] == 0 and item["reference_label"] == 1],
        }
        for name, prediction in systems.items()
    }
    report = {
        "model": {
            "path": str(model_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "training_or_threshold_changes": False,
        },
        "provenance": runner.provenance(),
        "metrics": metrics,
        "errors": errors,
        "samples": samples,
        "limitations": [
            "These 32 messages are repository-authored synthetic examples, not authentic public messages.",
            "They were excluded from fitting and threshold selection but have already been evaluated historically.",
            "No authentic, independently labelled first-contact recruitment benchmark is available here.",
            "Results demonstrate this frozen model and rules on this held-out demonstration set only.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
