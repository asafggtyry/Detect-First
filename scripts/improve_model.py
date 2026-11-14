"""Run `train`, then `final`: final evaluation cannot influence selection."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from threadpoolctl import threadpool_limits

from detect_first.baselines import always_legitimate, keyword_scam_baseline
from detect_first.data import download_dataset, load_dataset, normalize_text, split_dataset
from detect_first.evaluation import load_synthetic_evaluation
from detect_first.message_data import (SMS_PATH, assert_disjoint_groups, clean_text,
                                       download_sms, group_partition, load_sms,
                                       sha256, template_groups, training_overlap_audit,
                                       require_no_training_overlap)
from detect_first.message_model import build_message_pipeline
from detect_first.metrics import binary_metrics
from detect_first.model import MODEL_SCHEMA_VERSION, load_pipeline

REPORTS = ROOT / "reports"
EXPERIMENTS = ROOT / "models/experiments"
CACHE = ROOT / "data/raw/improvement_split.joblib"
SYNTHETIC = ROOT / "data/synthetic/evaluation.jsonl"
SYNTHETIC_SHA = "e4e81f6b40849761443bcb1634a9b0fc16253061737bcfc49da5cd4383156256"
ORIGINAL = ROOT / "models/job_posting_classifier.joblib"
CANDIDATES = {
    "job_word": ("word", False, False),
    "job_char": ("char", False, False),
    "joint_word": ("word", True, False),
    "joint_hybrid": ("hybrid", True, False),
    "joint_hybrid_prefix": ("hybrid", True, True),
}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def summarize(examples, indices):
    return {"examples": len(indices), "class_counts": dict(Counter(
        str(examples[i].label) for i in indices)), "membership_sha256": hashlib.sha256(
            "\n".join(sorted(hashlib.sha256(normalize_text(examples[i].text).encode()).hexdigest()
                             for i in indices)).encode()).hexdigest()}


def prepare():
    path = ROOT / "data/raw/fake_job_postings2.arff"
    if not path.exists():
        download_dataset(path)
    if not (ROOT / SMS_PATH).exists():
        download_sms(ROOT / SMS_PATH)
    jobs, job_stats = load_dataset(path)
    sms, sms_stats = load_sms(ROOT / SMS_PATH)
    examples = jobs + sms
    print("Grouping normalized exact and near-duplicate templates...", flush=True)
    groups = template_groups([e.text for e in examples])
    _, old_test = split_dataset(jobs)
    test_texts = {normalize_text(e.text) for e in old_test}
    job_test = [i for i, e in enumerate(jobs) if normalize_text(e.text) in test_texts]
    test_groups = {groups[i] for i in job_test}
    pool = [i for i in range(len(jobs)) if groups[i] not in test_groups]
    job_train, job_dev = group_partition(pool, groups, .25)
    job_groups = set(groups[:len(jobs)])
    sms_pool = [i for i in range(len(jobs), len(examples)) if groups[i] not in job_groups]
    sms_pool_train, sms_test = group_partition(sms_pool, groups, .2)
    sms_train, sms_dev = group_partition(sms_pool_train, groups, .25)
    partitions = dict(job_train=job_train, job_dev=job_dev, job_test=job_test,
                      sms_train=sms_train, sms_dev=sms_dev, sms_test=sms_test)
    assert_disjoint_groups(partitions, groups)
    for indices in partitions.values():
        if {examples[i].label for i in indices} != {0, 1}:
            raise ValueError("Every partition must contain both classes")
    cache = dict(examples=examples, groups=groups, partitions=partitions)
    joblib.dump(cache, CACHE)
    audit = {
        "job_source": job_stats, "sms_source": sms_stats,
        "partitions": {name: summarize(examples, indices) for name, indices in partitions.items()},
        "job_training_rows_purged_against_historical_test": len(jobs) - len(job_test) - len(pool),
        "sms_cross_source_rows_excluded": len(sms) - len(sms_pool),
        "group_overlap_between_partitions": 0, "similarity_threshold": .90,
        "components": len(set(groups)), "cache_sha256": sha256(CACHE),
        "original_model_sha256": sha256(ORIGINAL),
        "synthetic_sha256": SYNTHETIC_SHA,
        "length_words": {name: float(np.median([len(e.text.split()) for e in rows]))
                         for name, rows in [("job_postings", jobs), ("sms", sms)]},
    }
    write_json(REPORTS / "data_split_audit.json", audit)
    return cache


def evaluate(pipeline, examples, indices):
    return binary_metrics([examples[i].label for i in indices],
                          [int(x) for x in pipeline.predict([examples[i].text for i in indices])])


def select_threshold(options):
    """Fixed validation objective and guardrails; no final labels accepted."""
    def eligible(row):
        return all(m["false_positives"] / (m["false_positives"] + m["true_negatives"]) <= .05
                   for m in row["domains"].values())
    for row in options:
        row["eligible"] = eligible(row)
        row["mean_domain_f1"] = float(np.mean([m["f1"] for m in row["domains"].values()]))
    feasible = [row for row in options if row["eligible"]]
    return max(feasible or options, key=lambda row: (row["mean_domain_f1"], row["threshold"]))


def train():
    if (REPORTS / "selection.json").exists() or (REPORTS / "improvement_evaluation.json").exists():
        raise FileExistsError("Experiment already frozen. Use a separate experiment directory for new research.")
    if sha256(SYNTHETIC) != SYNTHETIC_SHA:
        raise ValueError("Protected synthetic evaluation changed")
    data = prepare()
    examples, splits = data["examples"], data["partitions"]
    # Audit every planned training input BEFORE fitting or selecting anything.
    # Parent-only groups miss overlaps introduced by truncation or a different
    # audit vocabulary. Never repair this by removing final evaluation rows.
    effective_training = [examples[i].text for name in ["job_train", "sms_train"]
                          for i in splits[name]]
    effective_training += [" ".join(examples[i].text.split()[:60]) for i in splits["job_train"]]
    require_no_training_overlap(training_overlap_audit(effective_training, {
        name: [examples[i] for i in splits[name]]
        for name in ["job_dev", "sms_dev", "job_test", "sms_test"]}))
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, (features, use_sms, augment) in CANDIDATES.items():
        print(f"Training {name}...", flush=True)
        indices = splits["job_train"] + (splits["sms_train"] if use_sms else [])
        texts, labels = [examples[i].text for i in indices], [examples[i].label for i in indices]
        if augment:
            # Keep each posting's total influence at one when adding its prefix.
            weights = [0.5 if i in set(splits["job_train"]) else 1.0 for i in indices]
            for i in splits["job_train"]:
                texts.append(" ".join(examples[i].text.split()[:60]))
                labels.append(examples[i].label)
                weights.append(.5)
        else:
            weights = None
        pipeline = build_message_pipeline(features)
        pipeline.fit(texts, labels, classifier__sample_weight=weights)
        options = []
        for threshold in [.35, .5, .65]:
            pipeline.named_steps["classifier"].threshold = threshold
            options.append({"threshold": threshold, "domains": {
                domain: evaluate(pipeline, examples, splits[f"{domain}_dev"])
                for domain in ["job", "sms"]}})
        chosen = select_threshold(options)
        pipeline.named_steps["classifier"].threshold = chosen["threshold"]
        model_path = EXPERIMENTS / f"{name}.joblib"
        joblib.dump({"schema_version": MODEL_SCHEMA_VERSION, "pipeline": pipeline,
                     "training_domain": "English job postings + UCI ham/spam" if use_sms else "English job postings",
                     "decision_threshold": chosen["threshold"], "candidate": name,
                     "scikit_learn_version": sklearn.__version__}, model_path, compress=3)
        results[name] = {"validation_options": options, "chosen": chosen,
                         "artifact_sha256": sha256(model_path)}
        print(f"{name}: threshold={chosen['threshold']}, mean development F1={chosen['mean_domain_f1']:.4f}", flush=True)
    feasible = [name for name in results if results[name]["chosen"]["eligible"]]
    winner = max(feasible, key=lambda name: results[name]["chosen"]["mean_domain_f1"]) if feasible else None
    write_json(REPORTS / "selection.json", {
        "status": "frozen_before_final_evaluation", "selected_candidate": winner,
        "selection_rule": "mean job/SMS development F1; <=5% FPR each; thresholds 0.35/0.5/0.65",
        "scikit_learn_version": sklearn.__version__, "candidates": results,
        "split_audit_sha256": sha256(REPORTS / "data_split_audit.json"),
    })
    print(f"Frozen candidate: {winner}. Run final evaluation separately.", flush=True)


def report_predictions(examples, predictions, ids=None):
    metrics = binary_metrics([e.label for e in examples], predictions)
    metrics["negative_class"] = {"examples": metrics["true_negatives"] + metrics["false_positives"],
                                 "false_positives": metrics["false_positives"]}
    metrics["positive_class"] = {"examples": metrics["true_positives"] + metrics["false_negatives"],
                                 "false_negatives": metrics["false_negatives"]}
    identifiers = ids if ids is not None else [hashlib.sha256(normalize_text(e.text).encode()).hexdigest() for e in examples]
    for label, key in [(0, "false_positive_ids"), (1, "false_negative_ids")]:
        metrics[key] = [identifier for identifier, e, p in zip(identifiers, examples, predictions)
                        if e.label == label and p != label]
    return metrics


def final():
    output = REPORTS / "improvement_evaluation.json"
    if output.exists():
        raise FileExistsError("Final report exists; do not repeatedly tune against it")
    selection = json.loads((REPORTS / "selection.json").read_text())
    audit = json.loads((REPORTS / "data_split_audit.json").read_text())
    if (sha256(REPORTS / "data_split_audit.json") != selection["split_audit_sha256"]
            or sha256(CACHE) != audit["cache_sha256"] or sha256(SYNTHETIC) != SYNTHETIC_SHA
            or sha256(ORIGINAL) != audit["original_model_sha256"]):
        raise ValueError("Frozen data or original artifact changed")
    data = joblib.load(CACHE)
    examples, splits = data["examples"], data["partitions"]
    synthetic = load_synthetic_evaluation(SYNTHETIC)
    from detect_first.data import Example
    synthetic_examples = [Example(row["text"], row["label"]) for row in synthetic]
    # Final-only leakage audit. Abort rather than remove troublesome test rows.
    training = [examples[i].text for name in ["job_train", "sms_train"] for i in splits[name]]
    training += [" ".join(examples[i].text.split()[:60]) for i in splits["job_train"]]
    require_no_training_overlap(training_overlap_audit(training, {
        name: [examples[i] for i in splits[name]]
        for name in ["job_dev", "sms_dev", "job_test", "sms_test"]}
        | {"synthetic_all": synthetic_examples}))
    if {clean_text(t) for t in training} & {clean_text(e.text) for e in synthetic_examples}:
        raise ValueError("Synthetic/training exact template leakage")
    vectorizer = TfidfVectorizer(preprocessor=clean_text, ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform(training)
    similarity = vectorizer.transform([e.text for e in synthetic_examples]) @ matrix.T
    maximum_similarity = float(similarity.max())
    if maximum_similarity >= .90:
        raise ValueError("Synthetic/training near-template leakage")
    methods = {"original_saved_model": load_pipeline(ORIGINAL)}
    for name, result in selection["candidates"].items():
        path = EXPERIMENTS / f"{name}.joblib"
        if sha256(path) != result["artifact_sha256"]:
            raise ValueError(f"Frozen candidate changed: {name}")
        methods[name] = load_pipeline(path)
    methods.update(fixed_keyword_rules=keyword_scam_baseline, always_legitimate=always_legitimate)
    sets = {"job_holdout": [examples[i] for i in splits["job_test"]],
            "sms_holdout": [examples[i] for i in splits["sms_test"]],
            "synthetic_all": synthetic_examples}
    results = {}
    for name, method in methods.items():
        results[name] = {}
        for domain, rows in sets.items():
            texts = [e.text for e in rows]
            pred = [int(x) for x in (method.predict(texts) if hasattr(method, "predict") else map(method, texts))]
            ids = [row["id"] for row in synthetic] if domain == "synthetic_all" else None
            results[name][domain] = report_predictions(rows, pred, ids)
            if domain == "synthetic_all":
                for difficulty in ["clear", "subtle"]:
                    indices = [i for i, row in enumerate(synthetic) if row["difficulty"] == difficulty]
                    results[name][f"synthetic_{difficulty}"] = report_predictions(
                        [rows[i] for i in indices], [pred[i] for i in indices], [ids[i] for i in indices])
    write_json(output, {
        "selected_candidate": selection["selected_candidate"],
        "selection_sha256": sha256(REPORTS / "selection.json"),
        "synthetic_max_training_cosine_similarity": maximum_similarity,
        "synthetic_median_words": float(np.median([len(e.text.split()) for e in synthetic_examples])),
        "results": results,
        "limitations": ["SMS positive labels are spam, not confirmed fraud.",
                        "Synthetic examples are held out from training/selection, but historically evaluated.",
                        "Original model had no near-duplicate purge; candidates have a smaller training set.",
                        "Near-duplicate checks cannot exclude all semantic template leakage.",
                        "No real first-contact recruitment benchmark was available with verified access and suitable labels."]})
    for name in results:
        row = results[name]["synthetic_all"]
        print(name, {k: row[k] for k in ["precision", "recall", "f1", "false_positives", "false_negatives"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["train", "final"])
    args = parser.parse_args()
    # Avoid machine-dependent BLAS oversubscription; numerical work is small/sparse.
    with threadpool_limits(limits=2):
        {"train": train, "final": final}[args.stage]()
