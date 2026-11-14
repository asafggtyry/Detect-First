from __future__ import annotations

from typing import Sequence

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.metrics import precision_score, recall_score


def binary_metrics(
    actual: Sequence[int], predicted: Sequence[int]
) -> dict[str, object]:
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted labels must have equal lengths.")
    if not actual:
        raise ValueError("Cannot evaluate an empty set.")

    matrix = confusion_matrix(actual, predicted, labels=[0, 1])
    true_negative, false_positive, false_negative, true_positive = (
        int(value) for value in matrix.ravel()
    )
    return {
        "examples": len(actual),
        "accuracy": float(accuracy_score(actual, predicted)),
        "precision": float(
            precision_score(actual, predicted, zero_division=0)
        ),
        "recall": float(recall_score(actual, predicted, zero_division=0)),
        "f1": float(f1_score(actual, predicted, zero_division=0)),
        "confusion_matrix": {
            "labels": ["legitimate", "fraudulent"],
            "rows_actual_columns_predicted": matrix.tolist(),
        },
        "true_negatives": true_negative,
        "false_positives": false_positive,
        "false_negatives": false_negative,
        "true_positives": true_positive,
    }
