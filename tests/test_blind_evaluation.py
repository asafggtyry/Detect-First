import hashlib
import json
from pathlib import Path

from detect_first.blind_evaluation import BlindEvaluationService
from detect_first.server import ScanService, create_app
from detect_first.metrics import binary_metrics

ROOT = Path(__file__).resolve().parents[1]


def test_full_blind_run_matches_frozen_report_and_stored_predictions():
    app = create_app()
    client = app.test_client()
    assert client.post("/api/evaluation/start", json={"seed": 2026}).status_code == 200
    results = []
    for _ in range(32):
        response = client.post("/api/evaluation/next")
        assert response.status_code == 200
        results.append(response.json)
    final = client.post("/api/evaluation/next").json
    assert final["complete"] is True and final["sample_index"] == 32
    assert len({row["sample_id"] for row in results}) == 32
    frozen = json.loads((ROOT / "reports/blind_ai_evaluation.json").read_text())
    assert final["metrics"] == frozen["metrics"]
    state = next(iter(app.extensions["blind_evaluation"].sessions.values()))
    assert state.actual == [row["reference_label"] for row in results]
    for system, field, stored in (
        ("model", "model_prediction", state.model_predictions),
        ("evidence_rules", "evidence_prediction", state.evidence_predictions),
        ("combined_warning", "combined_prediction", state.combined_predictions),
    ):
        assert stored == [row[field] for row in results]
        assert final["metrics"][system] == binary_metrics(state.actual, stored)


def test_classifier_receives_only_message_text_and_same_text_is_independent_of_context():
    calls = []

    def classifier(message):
        calls.append(message)
        return "fee" in message.lower()

    service = ScanService(classifier)
    message = "We are hiring. Pay an activation fee today."
    first = service.analyze(message)
    second = service.analyze(message)

    assert first["model_flagged"] is True
    assert second["model_flagged"] is True
    assert calls == [message, message]
    assert first["evidence_flagged"] is True
    assert first["warning_source"] == "both"

    contextual = ScanService(classifier)
    normal_sender = contextual.scan("normal-sender", {
        "message": message,
        "sender": "normal-sender",
        "is_saved_contact": False,
        "is_first_message": True,
    })
    recruiter_sender = contextual.scan("recruiter-sender", {
        "message": message,
        "sender": "recruiter-sender",
        "is_saved_contact": False,
        "is_first_message": True,
    })
    assert normal_sender["model_flagged"] == recruiter_sender["model_flagged"]


def test_blind_runner_predicts_before_revealing_independent_label():
    observed = []

    def analyzer(message):
        observed.append(message)
        return {
            "is_scam": "fee" in message.lower(),
            "model_flagged": "fee" in message.lower(),
            "evidence_flagged": False,
        }

    runner = BlindEvaluationService(analyzer)
    started = runner.start("session", seed=7)
    assert started["provenance"]["kind"] == "synthetic"
    result = runner.next("session")

    assert result["reference_label"] in (0, 1)
    assert result["text"] == observed[0]
    assert result["model_prediction"] == int("fee" in result["text"].lower())
    assert result["evidence_prediction"] == 0
    assert set(result["metrics"]) == {"model", "evidence_rules", "combined_warning"}
    assert result["metrics"]["model"]["examples"] == 1


def test_blind_runner_keeps_arbitrary_messages_unscored():
    runner = BlindEvaluationService(
        lambda message: {
            "is_scam": False,
            "model_flagged": False,
            "evidence_flagged": False,
        }
    )
    result = runner.arbitrary("An arbitrary message with no label.", "session")

    assert result["scored"] is False
    assert result["reference_label"] is None
    assert result["provenance"]["kind"] == "arbitrary"


def test_blind_dataset_is_disjoint_from_training_text_and_has_expected_labels():
    runner = BlindEvaluationService(lambda _: {
        "is_scam": False,
        "model_flagged": False,
        "evidence_flagged": False,
    })
    assert len(runner.samples) == 32
    assert sum(sample.label == 1 for sample in runner.samples) == 16
    assert sum(sample.label == 0 for sample in runner.samples) == 16
    assert runner.provenance()["exact_normalized_overlap_with_training"] == 0


def test_production_model_artifact_is_unchanged():
    model_path = ROOT / "models" / "job_posting_classifier.joblib"
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == (
        "6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42"
    )


def test_blind_evaluation_api_reveals_label_after_text_only_analysis():
    calls = []
    client = create_app(classifier=lambda text: calls.append(text) or False).test_client()

    started = client.post("/api/evaluation/start", json={"seed": 11})
    assert started.status_code == 200
    result = client.post("/api/evaluation/next", json={})
    assert result.status_code == 200
    sample = result.json
    assert sample["reference_label"] in (0, 1)
    assert calls == [sample["text"]]
    assert set(sample["metrics"]) == {"model", "evidence_rules", "combined_warning"}

    arbitrary = client.post(
        "/api/evaluation/arbitrary", json={"message": "An unlabeled message."}
    )
    assert arbitrary.status_code == 200
    assert arbitrary.json["scored"] is False
    assert arbitrary.json["reference_label"] is None
