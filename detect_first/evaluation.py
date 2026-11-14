from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sklearn.pipeline import Pipeline

from detect_first.baselines import always_legitimate, keyword_scam_baseline
from detect_first.data import DATASET_MD5, DATASET_URL, load_dataset, normalize_text
from detect_first.metrics import binary_metrics


def load_synthetic_evaluation(path: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not {"id", "label", "difficulty", "text"} <= row.keys():
                raise ValueError(
                    f"Synthetic evaluation row {line_number} is missing fields."
                )
            if row["label"] not in (0, 1):
                raise ValueError(
                    f"Synthetic evaluation row {line_number} has an invalid label."
                )
            if row["difficulty"] not in {"clear", "subtle"}:
                raise ValueError(
                    f"Synthetic evaluation row {line_number} has an invalid "
                    "difficulty."
                )
            if not row["text"].strip() or row["id"] in seen_ids:
                raise ValueError(
                    f"Synthetic evaluation row {line_number} is empty or duplicated."
                )
            seen_ids.add(row["id"])
            examples.append(row)
    if not examples:
        raise ValueError(f"No synthetic evaluation examples found in {path}.")
    return examples


def evaluate_synthetic(
    pipeline: Pipeline,
    evaluation_path: Path,
    training_data_path: Path,
) -> dict[str, object]:
    examples = load_synthetic_evaluation(evaluation_path)
    training_examples, dataset_stats = load_dataset(training_data_path)
    training_texts = {normalize_text(example.text) for example in training_examples}
    evaluation_texts = {
        normalize_text(str(example["text"])) for example in examples
    }
    overlap = training_texts.intersection(evaluation_texts)
    if overlap:
        raise ValueError(
            "Synthetic evaluation contains exact normalized text from training data."
        )

    texts = [str(example["text"]) for example in examples]
    actual = [int(example["label"]) for example in examples]
    predicted = [int(label) for label in pipeline.predict(texts)]
    clear_indices = [
        index for index, example in enumerate(examples)
        if example["difficulty"] == "clear"
    ]
    subtle_indices = [
        index for index, example in enumerate(examples)
        if example["difficulty"] == "subtle"
    ]
    subtle_scam_indices = [
        index for index, example in enumerate(examples)
        if example["difficulty"] == "subtle" and int(example["label"]) == 1
    ]

    def selected_metrics(indices: list[int]) -> dict[str, object]:
        return binary_metrics(
            [actual[index] for index in indices],
            [predicted[index] for index in indices],
        )

    return {
        "source": evaluation_path.name,
        "examples": len(examples),
        "class_distribution": {
            "legitimate": sum(label == 0 for label in actual),
            "fraudulent": sum(label == 1 for label in actual),
        },
        "training_dataset_md5": DATASET_MD5,
        "training_dataset_url": DATASET_URL,
        "exact_text_overlap_with_training": 0,
        "difficulty_counts": {
            "clear": len(clear_indices),
            "subtle": len(subtle_indices),
            "subtle_fraudulent": len(subtle_scam_indices),
        },
        "model": {
            "all_synthetic_examples": binary_metrics(actual, predicted),
            "clear_examples": selected_metrics(clear_indices),
            "subtle_examples": selected_metrics(subtle_indices),
            "subtle_fraudulent_recall": (
                sum(predicted[index] == 1 for index in subtle_scam_indices)
                / len(subtle_scam_indices)
                if subtle_scam_indices
                else None
            ),
        },
        "baselines": {
            "always_legitimate": binary_metrics(
                actual, [always_legitimate(text) for text in texts]
            ),
            "fixed_keyword_rules": binary_metrics(
                actual, [keyword_scam_baseline(text) for text in texts]
            ),
        },
        "limitations": [
            "All examples are hand-authored synthetic messages, not observed messages.",
            "The set is small and must not be used to claim real-world performance.",
            "The job-posting classifier is evaluated here out of domain.",
            f"Training data rows after exact deduplication: "
            f"{dataset_stats['rows_after_exact_deduplication']}.",
        ],
    }
