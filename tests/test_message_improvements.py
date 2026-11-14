"""Backend regressions and safeguards; no demo-label assertions for training."""
import importlib.util
import json
from pathlib import Path

import joblib
import pytest

from detect_first.message_data import (assert_disjoint_groups, clean_text,
                                       group_partition, template_groups,
                                       training_overlap_audit, require_no_training_overlap)
from detect_first.message_model import build_message_pipeline
from detect_first.model import predict_scam
from detect_first.state import Conversation, ConversationStore

ROOT = Path(__file__).resolve().parents[1]


def test_contact_normalization_is_shared_and_removes_identifiers():
    result = clean_text("<p>Mail person@example.org or https://example.org/id/13, call +1 (212) 555-0199 for $60.</p>")
    assert "person" not in result and "example.org" not in result and "555" not in result
    assert {"emailtoken", "urltoken", "phonetoken", "numbertoken"} <= set(result.replace("$", "").replace(".", "").split())


def test_template_families_cannot_cross_partitions():
    texts = ["Claim your new prize at https://one.example/12 now",
             "Claim your new prize at https://two.example/45 now",
             "Library assistant interviews next Monday",
             "School chemistry class starts tomorrow",
             "Please collect your homework from reception"]
    groups = template_groups(texts)
    assert groups[0] == groups[1]
    left, right = group_partition(list(range(len(texts))), groups, .4)
    assert_disjoint_groups({"train": left, "test": right}, groups)
    with pytest.raises(ValueError, match="leakage"):
        assert_disjoint_groups({"train": [0], "test": [1]}, groups)


def test_near_duplicates_group_even_when_not_exact():
    repeated = "The library seeks an assistant to catalog books organize shelves and help patrons " * 8
    groups = template_groups([repeated + "Monday", repeated + "Tuesday", "Unrelated museum ticket"])
    assert groups[0] == groups[1] != groups[2]


@pytest.mark.parametrize("features", ["word", "char", "hybrid"])
def test_learned_pipeline_serialization_and_unseen_vocabulary(tmp_path, features):
    pipeline = build_message_pipeline(features)
    pipeline.fit(["library assistant shelving books", "library assistant catalog books",
                  "prize winner call now", "prize winner claim now"], [0, 0, 1, 1])
    heldout = "quasaruniquetoken"
    before = pipeline.predict([heldout, "library books"])
    transformer = pipeline.named_steps["features"]
    vectorizers = [v for _, v in transformer.transformer_list] if features == "hybrid" else [transformer]
    assert all(heldout not in vectorizer.vocabulary_ for vectorizer in vectorizers)
    path = tmp_path / "model.joblib"
    joblib.dump(pipeline, path)
    loaded = joblib.load(path)
    assert list(loaded.predict([heldout, "library books"])) == list(before)
    assert isinstance(predict_scam("library books", loaded), bool)
    loaded.named_steps["classifier"].threshold = 1.0
    assert not predict_scam("prize winner now", loaded)
    loaded.named_steps["classifier"].threshold = 0.0
    assert predict_scam("library books", loaded)


def test_empty_new_conversation_does_not_mutate_or_classify():
    calls = []
    store = ConversationStore(lambda text: calls.append(text) or False, [])
    with pytest.raises(ValueError, match="empty"):
        store.add_test_conversation("sender", "  ")
    assert not store.conversations and not calls


def test_failed_first_scan_does_not_insert_sender_or_message():
    def failing_classifier(text):
        raise RuntimeError("Model unavailable")
    store = ConversationStore(failing_classifier, [])
    with pytest.raises(RuntimeError):
        store.add_test_conversation("new", "Hello there")
    assert "new" not in store.conversations
    conversation = Conversation("existing", "Existing", False, [])
    store = ConversationStore(failing_classifier, [conversation])
    with pytest.raises(RuntimeError):
        store.add_incoming("existing", "Hello there")
    assert not conversation.messages and not conversation.scanned


def test_evidence_does_not_overwrite_negative_model_output():
    store = ConversationStore(lambda _: False, [])
    conversation = store.add_test_conversation("sender", "We are hiring. Pay a registration fee today.")
    assert conversation.should_warn
    assert conversation.model_flagged is False


def test_threshold_selection_respects_false_positive_guardrail():
    spec = importlib.util.spec_from_file_location("improve_model", ROOT / "scripts/improve_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    options = [
        {"threshold": .35, "domains": {"job": {"f1": .9, "false_positives": 10, "true_negatives": 90}}},
        {"threshold": .5, "domains": {"job": {"f1": .8, "false_positives": 2, "true_negatives": 98}}},
    ]
    assert module.select_threshold(options)["threshold"] == .5


def test_original_artifact_and_final_synthetic_are_preserved():
    from detect_first.message_data import sha256
    assert sha256(ROOT / "models/job_posting_classifier.joblib") == "6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42"
    assert sha256(ROOT / "data/synthetic/evaluation.jsonl") == "e4e81f6b40849761443bcb1634a9b0fc16253061737bcfc49da5cd4383156256"


def test_saved_evaluation_matches_frozen_selection():
    from detect_first.message_data import sha256
    report = ROOT / "reports/improvement_evaluation.json"
    if not report.exists():
        pytest.skip("Run the frozen experiment before checking report provenance")
    data = json.loads(report.read_text())
    assert data["selection_sha256"] == sha256(ROOT / "reports/selection.json")
    assert data["synthetic_max_training_cosine_similarity"] < .90
    for method in data["results"].values():
        for metrics in method.values():
            assert metrics["examples"] == sum(metrics[k] for k in ["true_positives", "true_negatives", "false_positives", "false_negatives"])


def test_effective_training_audit_catches_prefix_leakage():
    from detect_first.data import Example
    prefix = "The library seeks an assistant to catalog books organize shelves and help patrons " * 8
    audit = training_overlap_audit([prefix + "Monday", "School chemistry class starts tomorrow"], {
        "exact_test": [Example(prefix + "Monday", 0)],
        "near_test": [Example(prefix + "Tuesday", 0)],
        "clean_test": [Example("Museum exhibit ticket", 1)],
    })
    assert audit["exact_test"]["exact_overlaps"] == 1
    assert audit["near_test"]["exact_overlaps"] == 0
    assert audit["near_test"]["near_overlaps_at_090"] == 1
    with pytest.raises(ValueError, match="Stop; do not filter or tune"):
        require_no_training_overlap(audit)
    require_no_training_overlap({"clean_test": audit["clean_test"]})


def test_candidate_artifact_matches_frozen_selection_and_threshold():
    from detect_first.message_data import sha256
    selection = json.loads((ROOT / "reports/selection.json").read_text())
    name = selection["selected_candidate"]
    candidate = ROOT / "models/first_contact_candidate.joblib"
    assert sha256(candidate) == selection["candidates"][name]["artifact_sha256"]
    artifact = joblib.load(candidate)
    threshold = selection["candidates"][name]["chosen"]["threshold"]
    assert artifact["candidate"] == name
    assert artifact["decision_threshold"] == threshold
    assert artifact["pipeline"].named_steps["classifier"].threshold == threshold


@pytest.mark.parametrize("model_name,artifact", [
    ("original_saved_model", None),
    ("joint_hybrid_prefix", "first_contact_candidate.joblib"),
])
def test_real_api_ml_predictions_match_frozen_first_contact_results(model_name, artifact):
    """Test the actual API default, plus explicit candidate injection without deployment."""
    from detect_first.evaluation import load_synthetic_evaluation
    from detect_first.metrics import binary_metrics
    from detect_first.server import create_app
    client = (create_app() if artifact is None else create_app(model_path=ROOT / "models" / artifact)).test_client()
    rows = load_synthetic_evaluation(ROOT / "data/synthetic/evaluation.jsonl")
    predictions = []
    for row in rows:
        payload = dict(sender=row["id"], message=row["text"], is_saved_contact=False, is_first_message=True)
        response = client.post("/api/scan", json=payload)
        assert response.status_code == 200
        result = response.json
        assert set(result) == {"is_scam", "reasons", "model_flagged", "evidence_flagged",
                               "warning_source", "scanned", "skipped_reason", "cached"}
        assert result["scanned"] and not result["cached"]
        assert type(result["model_flagged"]) is bool
        predictions.append(int(result["model_flagged"]))
        assert result["is_scam"] == (result["model_flagged"] or result["evidence_flagged"])
        assert all(reason["source"] == "evidence_rule" for reason in result["reasons"])
        retry = client.post("/api/scan", json=payload).json
        assert retry == dict(result, cached=True)
        later = client.post("/api/scan", json=payload | {"message": "Follow-up"}).json
        assert not later["scanned"] and later["model_flagged"] is None
    expected = json.loads((ROOT / "reports/improvement_evaluation.json").read_text())["results"][model_name]
    for name, indices in [("synthetic_all", range(len(rows))),
                          ("synthetic_subtle", [i for i, row in enumerate(rows) if row["difficulty"] == "subtle"])]:
        metrics = binary_metrics([rows[i]["label"] for i in indices], [predictions[i] for i in indices])
        assert metrics == {key: expected[name][key] for key in metrics}


def test_frozen_experiment_cannot_be_retrained_or_final_report_overwritten():
    spec = importlib.util.spec_from_file_location("improve_model", ROOT / "scripts/improve_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(FileExistsError, match="frozen"):
        module.train()
    with pytest.raises(FileExistsError, match="Final report exists"):
        module.final()
