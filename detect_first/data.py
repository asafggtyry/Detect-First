from __future__ import annotations

import csv
import hashlib
import os
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sklearn.model_selection import train_test_split


DATASET_URL = (
    "https://www.openml.org/data/v1/download/22121348/"
    "fake_job_postings2.arff"
)
DATASET_MD5 = "80f28af7c3569233f4b8b9012c2c245b"
EXPECTED_COLUMNS = 6


@dataclass(frozen=True)
class Example:
    text: str
    label: int


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(destination.name + ".download")
    request = urllib.request.Request(
        DATASET_URL,
        headers={"User-Agent": "DetectFirstPrototype/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with temporary_path.open("wb") as file:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    file.write(chunk)
        actual_md5 = file_md5(temporary_path)
        if actual_md5 != DATASET_MD5:
            raise ValueError(
                f"Dataset checksum mismatch: expected {DATASET_MD5}, "
                f"received {actual_md5}."
            )
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def load_dataset(path: Path) -> tuple[list[Example], dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Training data not found at {path}. Run scripts/download_test_data.py "
            "to download the public dataset."
        )

    actual_md5 = file_md5(path)
    if actual_md5 != DATASET_MD5:
        raise ValueError(
            f"Unexpected dataset checksum for {path}: {actual_md5}. "
            "Download the documented OpenML dataset again."
        )

    examples_by_text: dict[str, Example] = {}
    duplicate_count = 0
    raw_counts: Counter[int] = Counter()
    active = False

    with path.open(encoding="utf-8", errors="replace", newline="") as file:
        for line in file:
            if line.strip().casefold() == "@data":
                active = True
                break
        if not active:
            raise ValueError(f"No @DATA section found in {path}.")

        reader = csv.reader(
            file,
            delimiter=",",
            quotechar="'",
            escapechar="\\",
            strict=True,
        )
        for row_number, row in enumerate(reader, start=1):
            if not row:
                continue
            if len(row) != EXPECTED_COLUMNS:
                raise ValueError(
                    f"Expected {EXPECTED_COLUMNS} fields in ARFF row "
                    f"{row_number}; found {len(row)}."
                )
            try:
                label = int(row[-1].strip())
            except ValueError as exc:
                raise ValueError(
                    f"Invalid class label in ARFF row {row_number}: {row[-1]!r}."
                ) from exc
            if label not in (0, 1):
                raise ValueError(
                    f"Expected a binary class label in row {row_number}; "
                    f"found {label}."
                )

            title = "" if row[0].strip() == "?" else row[0].strip()
            description = "" if row[2].strip() == "?" else row[2].strip()
            text = "\n".join(part for part in (title, description) if part).strip()
            normalized = normalize_text(text)
            if not normalized:
                continue
            raw_counts[label] += 1

            existing = examples_by_text.get(normalized)
            if existing is not None:
                if existing.label != label:
                    raise ValueError(
                        "Conflicting labels were found for duplicate normalized "
                        f"text in ARFF row {row_number}."
                    )
                duplicate_count += 1
                continue
            examples_by_text[normalized] = Example(text=text, label=label)

    examples = list(examples_by_text.values())
    counts = Counter(example.label for example in examples)
    if not examples or set(counts) != {0, 1}:
        raise ValueError("Dataset must contain both classes after preprocessing.")

    stats: dict[str, object] = {
        "source_rows_with_text": sum(raw_counts.values()),
        "class_distribution_before_deduplication": {
            str(label): count for label, count in sorted(raw_counts.items())
        },
        "rows_after_exact_deduplication": len(examples),
        "duplicate_rows_removed": duplicate_count,
        "class_distribution_after_deduplication": {
            str(label): count for label, count in sorted(counts.items())
        },
        "md5": actual_md5,
    }
    return examples, stats


def split_dataset(
    examples: list[Example],
) -> tuple[list[Example], list[Example]]:
    texts = [example.text for example in examples]
    labels = [example.label for example in examples]
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=2026,
        stratify=labels,
    )
    train = [
        Example(text=text, label=label)
        for text, label in zip(train_texts, train_labels)
    ]
    test = [
        Example(text=text, label=label)
        for text, label in zip(test_texts, test_labels)
    ]

    train_text_set = {normalize_text(example.text) for example in train}
    test_text_set = {normalize_text(example.text) for example in test}
    overlap = train_text_set.intersection(test_text_set)
    if overlap:
        raise ValueError(
            f"Exact-text leakage check failed: {len(overlap)} overlaps found."
        )
    return train, test
