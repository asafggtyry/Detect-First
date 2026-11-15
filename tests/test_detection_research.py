import json
from pathlib import Path

import pytest

from detect_first.blind_evaluation import BlindEvaluationService
from detect_first.data import load_dataset

ROOT = Path(__file__).resolve().parents[1]


def analyzer(_message):
    return {"is_scam": False, "model_flagged": False, "evidence_flagged": False}


def test_blind_loader_rejects_exact_normalized_training_overlap(tmp_path):
    training, _ = load_dataset(ROOT / "data/raw/fake_job_postings2.arff")
    evaluation = tmp_path / "evaluation.jsonl"
    evaluation.write_text(json.dumps({
        "id": "leak",
        "label": 1,
        "difficulty": "clear",
        "text": training[0].text,
    }) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="normalized text"):
        BlindEvaluationService(
            analyzer,
            evaluation_path=evaluation,
            training_data_path=ROOT / "data/raw/fake_job_postings2.arff",
        )


def test_blind_loader_rejects_invalid_reference_labels(tmp_path):
    evaluation = tmp_path / "evaluation.jsonl"
    evaluation.write_text(json.dumps({
        "id": "invalid",
        "label": 2,
        "difficulty": "clear",
        "text": "A message not present in training.",
    }) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="label"):
        BlindEvaluationService(
            analyzer,
            evaluation_path=evaluation,
            training_data_path=ROOT / "data/raw/fake_job_postings2.arff",
        )
