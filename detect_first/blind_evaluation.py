from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from detect_first.data import load_dataset, normalize_text
from detect_first.metrics import binary_metrics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALUATION_PATH = ROOT / "data" / "synthetic" / "evaluation.jsonl"
DEFAULT_TRAINING_DATA_PATH = ROOT / "data" / "raw" / "fake_job_postings2.arff"


class BenchmarkUnavailable(RuntimeError):
    """Optional benchmark inputs could not be loaded or safely validated."""


@dataclass(frozen=True)
class BlindSample:
    sample_id: str
    label: int
    difficulty: str
    text: str


@dataclass
class EvaluationSession:
    seed: int | str | None
    order: list[int]
    position: int = 0
    actual: list[int] = field(default_factory=list)
    model_predictions: list[int] = field(default_factory=list)
    evidence_predictions: list[int] = field(default_factory=list)
    combined_predictions: list[int] = field(default_factory=list)


class BlindEvaluationService:
    """Score held-out labels only after analysis has produced predictions."""

    def __init__(
        self,
        analyzer: Callable[[str], dict[str, Any]],
        evaluation_path: Path = DEFAULT_EVALUATION_PATH,
        training_data_path: Path = DEFAULT_TRAINING_DATA_PATH,
    ) -> None:
        self.analyzer = analyzer
        self.evaluation_path = evaluation_path
        self.training_data_path = training_data_path
        self._samples: list[BlindSample] | None = None
        self._load_lock = Lock()
        self.sessions: dict[str, EvaluationSession] = {}
        self.lock = Lock()

    @property
    def samples(self) -> list[BlindSample]:
        # No evaluation files are read during app creation or ordinary inference.
        # Cache only successful validation; adding the optional data permits retry
        # without restarting the server. Concurrent first requests load once.
        with self._load_lock:
            if self._samples is None:
                try:
                    self._samples = self._load_samples(self.evaluation_path, self.training_data_path)
                except FileNotFoundError as error:
                    raise BenchmarkUnavailable(
                        "Blind evaluation needs optional benchmark data. From the repository root, "
                        "run python scripts/download_test_data.py, then retry Start Blind Test. "
                        "If data/synthetic/evaluation.jsonl is missing, restore it from the release checkout. "
                        "Chats and Test a Message work without benchmark data."
                    ) from error
                except (OSError, ValueError) as error:
                    raise BenchmarkUnavailable(
                        "Blind evaluation data could not be validated. Restore data/synthetic/evaluation.jsonl "
                        "from the release checkout and re-download data/raw/fake_job_postings2.arff "
                        "with python scripts/download_test_data.py after removing the invalid dataset. "
                        "No evaluation was scored."
                    ) from error
            return self._samples

    @staticmethod
    def _load_samples(
        evaluation_path: Path, training_data_path: Path
    ) -> list[BlindSample]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        with evaluation_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                required = {"id", "label", "difficulty", "text"}
                if (not isinstance(row, dict) or not required <= row.keys()
                        or not isinstance(row["id"], str) or not row["id"].strip()
                        or row["id"] in seen):
                    raise ValueError(f"Invalid or duplicate evaluation row {line_number}.")
                if (type(row["label"]) is not int or row["label"] not in (0, 1)
                        or row["difficulty"] not in ("clear", "subtle")):
                    raise ValueError(f"Invalid evaluation label or difficulty on row {line_number}.")
                if not isinstance(row["text"], str) or not row["text"].strip():
                    raise ValueError(f"Empty evaluation text on row {line_number}.")
                seen.add(row["id"])
                rows.append(row)

        if not rows:
            raise ValueError("No blind evaluation examples found.")

        training_examples, _ = load_dataset(training_data_path)
        training_texts = {normalize_text(example.text) for example in training_examples}
        overlap = training_texts.intersection(normalize_text(str(row["text"])) for row in rows)
        if overlap:
            raise ValueError("Blind evaluation contains normalized text from training data.")

        return [BlindSample(str(row["id"]), int(row["label"]), str(row["difficulty"]), str(row["text"]))
                for row in rows]

    def provenance(self) -> dict[str, Any]:
        return {
            "kind": "synthetic",
            "source": self.evaluation_path.name,
            "samples": len(self.samples),
            "label_meaning": "Repository-authored fictional first-contact recruitment examples.",
            "authentic_public_messages": False,
            "licensing": "Repository-authored synthetic text; no external public-data license applies.",
            "exact_normalized_overlap_with_training": 0,
            "near_duplicate_audit": "See reports/data_split_audit.json and docs/EVALUATION.md; this is not authentic-world validation.",
            "warning": "Synthetic demonstration only; it does not establish real-world recruitment-scam accuracy.",
        }

    @staticmethod
    def _metrics(state: EvaluationSession) -> dict[str, Any]:
        if not state.actual:
            return {}
        return {
            "model": binary_metrics(state.actual, state.model_predictions),
            "evidence_rules": binary_metrics(state.actual, state.evidence_predictions),
            "combined_warning": binary_metrics(state.actual, state.combined_predictions),
        }

    def start(self, session_id: str, seed: int | str | None = None) -> dict[str, Any]:
        with self.lock:
            order = list(range(len(self.samples)))
            random.Random(seed).shuffle(order)
            self.sessions[session_id] = EvaluationSession(seed=seed, order=order)
            return self._status(self.sessions[session_id])

    def next(self, session_id: str) -> dict[str, Any]:
        with self.lock:
            state = self.sessions.setdefault(
                session_id,
                EvaluationSession(None, list(range(len(self.samples)))),
            )
            if state.position >= len(state.order):
                return {"complete": True, **self._status(state)}

            sample = self.samples[state.order[state.position]]
            # The analyzer sees only sample.text. The reference label is appended
            # after this call returns, so it cannot affect prediction.
            analysis = self.analyzer(sample.text)
            model_prediction = int(bool(analysis["model_flagged"]))
            evidence_prediction = int(bool(analysis["evidence_flagged"]))
            combined_prediction = int(bool(analysis["is_scam"]))
            # Commit progress only after all predictions succeeded. A failed
            # request must retry this sample and leave the stored metrics intact.
            state.position += 1
            state.actual.append(sample.label)
            state.model_predictions.append(model_prediction)
            state.evidence_predictions.append(evidence_prediction)
            state.combined_predictions.append(combined_prediction)
            return {
                "complete": False,
                "sample_index": state.position,
                "total_samples": len(state.order),
                "sample_id": sample.sample_id,
                "difficulty": sample.difficulty,
                "text": sample.text,
                "model_prediction": model_prediction,
                "evidence_prediction": evidence_prediction,
                "combined_prediction": combined_prediction,
                "reference_label": sample.label,
                "metrics": self._metrics(state),
                "provenance": self.provenance(),
            }

    def arbitrary(self, message: str, session_id: str) -> dict[str, Any]:
        analysis = self.analyzer(message)
        return {
            "scored": False,
            "text": message,
            "reference_label": None,
            "model_prediction": int(bool(analysis["model_flagged"])),
            "evidence_prediction": int(bool(analysis["evidence_flagged"])),
            "combined_prediction": int(bool(analysis["is_scam"])),
            "analysis": analysis,
            "provenance": {
                "kind": "arbitrary",
                "warning": "No reference label was supplied; this message is not scored.",
            },
        }

    def _status(self, state: EvaluationSession) -> dict[str, Any]:
        return {
            "complete": state.position >= len(state.order),
            "sample_index": state.position,
            "total_samples": len(state.order),
            "metrics": copy.deepcopy(self._metrics(state)),
            "provenance": self.provenance(),
        }
