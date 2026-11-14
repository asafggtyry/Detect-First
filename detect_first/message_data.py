"""Public SMS ingestion and label-independent template leakage checks."""
from __future__ import annotations

import hashlib
import re
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GroupShuffleSplit

from detect_first.data import Example, normalize_text

SMS_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
SMS_SHA256 = "1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3"
SMS_PATH = Path("data/raw/sms_spam_collection.zip")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_sms(path: Path = SMS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    try:
        with urllib.request.urlopen(SMS_URL, timeout=60) as response:
            temporary.write_bytes(response.read())
        if sha256(temporary) != SMS_SHA256:
            raise ValueError("UCI SMS archive checksum mismatch")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def clean_text(text: str) -> str:
    """Shared train/inference normalization; no keyword decisions or labels."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", " emailtoken ", text)
    text = re.sub(r"(?i)\b(?:https?://|www\.)\S+", " urltoken ", text)
    text = re.sub(r"\+?\d[\d ().-]{6,}\d", " phonetoken ", text)
    text = re.sub(r"\d+(?:[.,]\d+)*", " numbertoken ", text)
    return normalize_text(text)


def load_sms(path: Path = SMS_PATH) -> tuple[list[Example], dict]:
    if sha256(path) != SMS_SHA256:
        raise ValueError("UCI SMS archive checksum mismatch")
    by_text: dict[str, list[Example]] = {}
    with zipfile.ZipFile(path) as archive:
        lines = archive.read("SMSSpamCollection").decode("utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        label, separator, text = line.partition("\t")
        if not separator or label not in {"ham", "spam"} or not text.strip():
            raise ValueError(f"Invalid UCI SMS row {number}")
        key = clean_text(text)
        by_text.setdefault(key, []).append(Example(text, int(label == "spam")))
    conflicts = [key for key, rows in by_text.items() if len({r.label for r in rows}) > 1]
    examples = [rows[0] for key, rows in by_text.items() if key not in conflicts]
    return examples, {
        "source": SMS_URL, "sha256": SMS_SHA256, "raw_rows": len(lines),
        "retained_rows": len(examples), "conflicting_templates_removed": len(conflicts),
        "duplicate_or_conflicting_rows_removed": len(lines) - len(examples),
        "class_counts": dict(Counter(str(e.label) for e in examples)),
        "label_meaning": {"0": "ham", "1": "spam (not necessarily fraud)"},
    }


def template_groups(texts: list[str], similarity: float = 0.90) -> list[int]:
    """Connected components, including normalized exact and cosine near copies.

    The audit vocabulary sees all text ONLY to define split groups. Classifiers
    fit independent vocabularies on training data. No labels enter this function.
    """
    normalized = [clean_text(text) for text in texts]
    parents = list(range(len(texts)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(a: int, b: int) -> None:
        a, b = root(a), root(b)
        parents[max(a, b)] = min(a, b)

    seen: dict[str, int] = {}
    for index, text in enumerate(normalized):
        if text in seen:
            union(index, seen[text])
        else:
            seen[text] = index
    if len(texts) < 2:
        return parents
    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=80_000,
                             sublinear_tf=True, dtype=np.float32).fit_transform(normalized)
    for start in range(0, len(texts), 128):
        similarities = (matrix[start:start + 128] @ matrix.T).tocoo()
        for row, col in zip(similarities.row[similarities.data >= similarity],
                            similarities.col[similarities.data >= similarity]):
            if start + row < col:
                union(int(start + row), int(col))
    return [root(index) for index in range(len(texts))]


def group_partition(indices: list[int], groups: list[int], fraction: float,
                    seed: int = 2026) -> tuple[list[int], list[int]]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=fraction, random_state=seed)
    left, right = next(splitter.split(indices, groups=[groups[i] for i in indices]))
    return [indices[i] for i in left], [indices[i] for i in right]


def assert_disjoint_groups(partitions: dict[str, list[int]], groups: list[int]) -> None:
    names = list(partitions)
    for i, name in enumerate(names):
        left = {groups[j] for j in partitions[name]}
        for other in names[i + 1:]:
            if left.intersection(groups[j] for j in partitions[other]):
                raise ValueError(f"Template leakage between {name} and {other}")


def training_overlap_audit(training: list[str], partitions: dict[str, list[Example]]) -> dict:
    """Check actual fitted inputs, including augmentations, against reserved rows.

    This is a label-independent audit, never a classifier vocabulary. Do not
    remove final examples in response to failures: stop the experiment instead.
    """
    normalized = {clean_text(text) for text in training}
    vectorizer = TfidfVectorizer(preprocessor=clean_text, ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform(training)
    result = {}
    for name, rows in partitions.items():
        exact = sum(clean_text(e.text) in normalized for e in rows)
        maxima = []
        for start in range(0, len(rows), 128):
            similarities = vectorizer.transform([e.text for e in rows[start:start + 128]]) @ matrix.T
            maxima.extend(similarities.max(axis=1).toarray().ravel().tolist())
        result[name] = dict(exact_overlaps=exact, near_overlaps_at_090=sum(v >= .90 for v in maxima),
                            maximum_cosine_similarity=max(maxima, default=0))
    return result


def require_no_training_overlap(audit: dict) -> None:
    contaminated = [name for name, row in audit.items()
                    if row["exact_overlaps"] or row["near_overlaps_at_090"]]
    if contaminated:
        raise ValueError("Effective-training template leakage in " + ", ".join(contaminated)
                         + ". Stop; do not filter or tune on the final evaluation rows.")
