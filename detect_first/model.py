from __future__ import annotations

from pathlib import Path
from typing import Iterable

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from detect_first.data import Example, load_dataset, split_dataset
from detect_first.metrics import binary_metrics
from detect_first.baselines import always_legitimate, keyword_scam_baseline


MODEL_PATH = Path("models") / "job_posting_classifier.joblib"
METRICS_PATH = Path("reports") / "job_posting_metrics.json"
DATA_PATH = Path("data") / "raw" / "fake_job_postings2.arff"
MODEL_SCHEMA_VERSION = 1


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=80_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1_000,
                    random_state=2026,
                ),
            ),
        ]
    )


def _predictions(
    predictor: Pipeline, texts: Iterable[str]
) -> list[int]:
    return [int(value) for value in predictor.predict(list(texts))]


def train_and_save(
    data_path: Path = DATA_PATH,
    model_path: Path = MODEL_PATH,
    metrics_path: Path = METRICS_PATH,
) -> dict[str, object]:
    examples, dataset_stats = load_dataset(data_path)
    train, test = split_dataset(examples)
    pipeline = build_pipeline()
    pipeline.fit(
        [example.text for example in train],
        [example.label for example in train],
    )

    test_texts = [example.text for example in test]
    actual = [example.label for example in test]
    model_predictions = _predictions(pipeline, test_texts)
    always_predictions = [always_legitimate(text) for text in test_texts]
    keyword_predictions = [keyword_scam_baseline(text) for text in test_texts]

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "schema_version": MODEL_SCHEMA_VERSION,
            "pipeline": pipeline,
            "training_domain": "English job postings",
            "decision_threshold": 0.5,
            "scikit_learn_version": sklearn.__version__,
        },
        model_path,
    )

    results: dict[str, object] = {
        "dataset": dataset_stats,
        "split": {
            "method": "stratified 80/20 holdout",
            "random_state": 2026,
            "train_examples": len(train),
            "test_examples": len(test),
            "train_class_distribution": {
                "legitimate": sum(example.label == 0 for example in train),
                "fraudulent": sum(example.label == 1 for example in train),
            },
            "test_class_distribution": {
                "legitimate": sum(example.label == 0 for example in test),
                "fraudulent": sum(example.label == 1 for example in test),
            },
            "exact_normalized_text_overlap": 0,
            "near_duplicate_check": "not performed",
        },
        "model": {
            "name": "TF-IDF + balanced logistic regression",
            "metrics": binary_metrics(actual, model_predictions),
        },
        "baselines": {
            "always_legitimate": binary_metrics(actual, always_predictions),
            "fixed_keyword_rules": binary_metrics(actual, keyword_predictions),
        },
        "false_positive_examples": [
            example.text[:280]
            for example, actual_label, prediction in zip(
                test, actual, model_predictions
            )
            if actual_label == 0 and prediction == 1
        ][:5],
        "false_negative_examples": [
            example.text[:280]
            for example, actual_label, prediction in zip(
                test, actual, model_predictions
            )
            if actual_label == 1 and prediction == 0
        ][:5],
        "limitations": [
            "The training and held-out examples are job postings, not first-contact messages.",
            "The dataset is imbalanced and may not represent current scams or teenagers' messages.",
            "Exact duplicate text is checked; near-duplicate templates are not.",
            "Logistic-regression scores are not displayed as calibrated message-risk probabilities.",
        ],
    }

    import json

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return results


def load_pipeline(model_path: Path = MODEL_PATH) -> Pipeline:
    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model not found at {model_path}. Run "
            "`python scripts/train_model.py` first."
        )
    artifact = joblib.load(model_path)
    if (
        not isinstance(artifact, dict)
        or artifact.get("schema_version") != MODEL_SCHEMA_VERSION
        or not isinstance(artifact.get("pipeline"), Pipeline)
    ):
        raise ValueError(f"Unsupported or invalid model artifact: {model_path}.")
    if artifact.get("scikit_learn_version") != sklearn.__version__:
        raise RuntimeError(
            "The saved model was trained with scikit-learn "
            f"{artifact.get('scikit_learn_version')}, but {sklearn.__version__} "
            "is installed. Retrain it with `python scripts/train_model.py`."
        )
    return artifact["pipeline"]


def predict_scam(text: str, pipeline: Pipeline | None = None) -> bool:
    if not text.strip():
        raise ValueError("Cannot classify an empty message.")
    active_pipeline = pipeline if pipeline is not None else load_pipeline()
    return bool(active_pipeline.predict([text])[0] == 1)
