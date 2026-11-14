from pathlib import Path

from streamlit.testing.v1 import AppTest

from detect_first.data import load_dataset, normalize_text, split_dataset
from detect_first.evaluation import evaluate_synthetic
from detect_first.model import load_pipeline, predict_scam
from detect_first.state import create_demo_store


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "fake_job_postings2.arff"
MODEL_PATH = ROOT / "models" / "job_posting_classifier.joblib"


def test_classifier_returns_a_valid_boolean_response() -> None:
    pipeline = load_pipeline(MODEL_PATH)
    prediction = predict_scam(
        "We are hiring for a remote assistant position. Pay an onboarding fee.",
        pipeline,
    )
    assert isinstance(prediction, bool)


def test_real_model_and_evidence_layer_drive_demo_warning() -> None:
    pipeline = load_pipeline(MODEL_PATH)
    store = create_demo_store(lambda text: predict_scam(text, pipeline))
    assert store.get("mom").scan_count == 0
    assert not store.get("124-5135-2355").should_warn
    suspicious = store.get("732-882-1944")
    assert suspicious.scanned
    assert suspicious.scan_count == 1
    assert suspicious.should_warn
    assert "Upfront payment request" in {
        item.category for item in suspicious.evidence
    }


def test_holdout_has_no_exact_normalized_text_leakage() -> None:
    examples, _stats = load_dataset(DATA_PATH)
    train, test = split_dataset(examples)
    train_texts = {normalize_text(example.text) for example in train}
    test_texts = {normalize_text(example.text) for example in test}
    assert train_texts.isdisjoint(test_texts)
    assert len(test) > 0


def test_synthetic_evaluation_is_unseen_and_reports_required_metrics() -> None:
    report = evaluate_synthetic(
        load_pipeline(MODEL_PATH),
        ROOT / "data" / "synthetic" / "evaluation.jsonl",
        DATA_PATH,
    )
    assert report["exact_text_overlap_with_training"] == 0
    assert report["examples"] == 32
    model_metrics = report["model"]["all_synthetic_examples"]
    assert model_metrics["examples"] == 32
    assert len(model_metrics["confusion_matrix"]["rows_actual_columns_predicted"]) == 2
    assert report["model"]["subtle_examples"]["examples"] == 16
    assert report["model"]["subtle_fraudulent_recall"] is not None


def test_streamlit_app_starts_without_exceptions() -> None:
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
    assert not app.exception
