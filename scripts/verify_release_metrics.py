"""Reproduce release model/baseline metrics without fitting or overwriting artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detect_first.baselines import always_legitimate, keyword_scam_baseline
from detect_first.data import load_dataset, split_dataset
from detect_first.evaluation import evaluate_synthetic
from detect_first.metrics import binary_metrics
from detect_first.model import load_pipeline


def main():
    model_path = ROOT / "models/job_posting_classifier.joblib"
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    pipeline = load_pipeline(model_path)
    rows, stats = load_dataset(ROOT / "data/raw/fake_job_postings2.arff")
    _, test = split_dataset(rows)
    actual = [row.label for row in test]
    texts = [row.text for row in test]
    posting = {
        "model": binary_metrics(actual, [int(p) for p in pipeline.predict(texts)]),
        "always_legitimate": binary_metrics(actual, [always_legitimate(t) for t in texts]),
        "fixed_keyword_rules": binary_metrics(actual, [keyword_scam_baseline(t) for t in texts]),
    }
    recorded = json.loads((ROOT / "reports/job_posting_metrics.json").read_text())
    assert stats == recorded["dataset"], "Dataset metadata changed"
    assert posting["model"] == recorded["model"]["metrics"], "Posting model metrics changed"
    for name in ("always_legitimate", "fixed_keyword_rules"):
        assert posting[name] == recorded["baselines"][name], f"Baseline changed: {name}"
    synthetic = evaluate_synthetic(pipeline, ROOT / "data/synthetic/evaluation.jsonl",
                                   ROOT / "data/raw/fake_job_postings2.arff")
    assert synthetic == json.loads((ROOT / "reports/synthetic_evaluation.json").read_text()), "Synthetic results changed"
    audit = json.loads((ROOT / "reports/model_integration_verification.json").read_text())
    assert model_hash == audit["artifact_sha256"]["original_saved_model"], "Model artifact changed"
    report = {
        "status": "all_original_metrics_and_baselines_reproduced",
        "model_sha256": model_hash,
        "training_performed": False,
        "job_posting_holdout": posting,
        "synthetic": synthetic,
        "historical_original_training_overlap": audit["original_training_overlap"]["job_holdout"],
        "limits": [
            "Posting holdout has known near-template contamination; historical comparison only.",
            "Synthetic messages are not real-world validation.",
            "Authentic first-contact recruitment validation is unavailable.",
            "Metrics measure classifier predictions, not combined evidence-rule warnings.",
        ],
    }
    output = ROOT / "reports/release_metrics.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Reproduced model and both baselines: 2,505 postings; 32 synthetic messages (16 subtle).")
    print(f"Model unchanged: {model_hash}")


if __name__ == "__main__":
    main()
