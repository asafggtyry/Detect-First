"""Re-evaluate frozen artifacts without fitting, selecting, or overwriting them.

Requires the checksum-verified public job and SMS files in data/raw. The optional
original split cache is checked byte-for-byte; otherwise splits are reconstructed.
Use --rebuild-groups to independently reproduce grouping from public source text.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
from threadpoolctl import threadpool_limits

from detect_first.data import Example, load_dataset, normalize_text, split_dataset
from detect_first.evaluation import load_synthetic_evaluation
from detect_first.message_data import (assert_disjoint_groups,
                                       group_partition, load_sms, sha256, template_groups,
                                       training_overlap_audit)
from detect_first.model import load_pipeline
from improve_model import report_predictions, summarize


def require_equal(actual, expected, description):
    if actual != expected:
        raise ValueError(f"Frozen experiment mismatch: {description}")


def reconstruct(jobs, sms):
    examples = jobs + sms
    groups = template_groups([e.text for e in examples])
    _, test = split_dataset(jobs)
    test_texts = {normalize_text(e.text) for e in test}
    job_test = [i for i, e in enumerate(jobs) if normalize_text(e.text) in test_texts]
    test_groups = {groups[i] for i in job_test}
    pool = [i for i in range(len(jobs)) if groups[i] not in test_groups]
    job_train, job_dev = group_partition(pool, groups, .25)
    job_groups = set(groups[:len(jobs)])
    pool = [i for i in range(len(jobs), len(examples)) if groups[i] not in job_groups]
    pool, sms_test = group_partition(pool, groups, .2)
    sms_train, sms_dev = group_partition(pool, groups, .25)
    return dict(examples=examples, groups=groups, partitions=dict(
        job_train=job_train, job_dev=job_dev, job_test=job_test,
        sms_train=sms_train, sms_dev=sms_dev, sms_test=sms_test))


def verify(rebuild_groups=False):
    reports = ROOT / "reports"
    selection = json.loads((reports / "selection.json").read_text())
    audit = json.loads((reports / "data_split_audit.json").read_text())
    recorded = json.loads((reports / "improvement_evaluation.json").read_text())
    require_equal(sha256(reports / "selection.json"), recorded["selection_sha256"], "selection")
    require_equal(sha256(reports / "data_split_audit.json"), selection["split_audit_sha256"], "audit")
    original = ROOT / "models/job_posting_classifier.joblib"
    candidate = ROOT / "models/first_contact_candidate.joblib"
    chosen = selection["selected_candidate"]
    require_equal(sha256(original), audit["original_model_sha256"], "original model")
    require_equal(sha256(candidate), selection["candidates"][chosen]["artifact_sha256"], "candidate")
    synthetic_path = ROOT / "data/synthetic/evaluation.jsonl"
    require_equal(sha256(synthetic_path), audit["synthetic_sha256"], "synthetic benchmark")
    jobs, _ = load_dataset(ROOT / "data/raw/fake_job_postings2.arff")
    sms, _ = load_sms(ROOT / "data/raw/sms_spam_collection.zip")
    cache = ROOT / "data/raw/improvement_split.joblib"
    if cache.exists() and not rebuild_groups:
        require_equal(sha256(cache), audit["cache_sha256"], "split cache")
        data = joblib.load(cache)
    else:
        data = reconstruct(jobs, sms)
    require_equal(data["examples"], jobs + sms, "cache examples and source labels")
    examples, splits = data["examples"], data["partitions"]
    assert_disjoint_groups(splits, data["groups"])
    for name, indices in splits.items():
        require_equal(summarize(examples, indices), audit["partitions"][name], f"{name} membership")
    synthetic = load_synthetic_evaluation(synthetic_path)
    sets = {"job_holdout": [examples[i] for i in splits["job_test"]],
            "sms_holdout": [examples[i] for i in splits["sms_test"]],
            "synthetic_all": [Example(row["text"], row["label"]) for row in synthetic]}
    training = [examples[i].text for name in ["job_train", "sms_train"] for i in splits[name]]
    training += [" ".join(examples[i].text.split()[:60]) for i in splits["job_train"]]
    leakage = training_overlap_audit(training, sets | {
        name: [examples[i] for i in splits[name]] for name in ["job_dev", "sms_dev"]})
    original_training, _ = split_dataset(jobs)
    original_leakage = training_overlap_audit([e.text for e in original_training], sets)
    methods = {"original_saved_model": original, chosen: candidate}
    # All other frozen candidates can be verified when their ignored files exist.
    for name, details in selection["candidates"].items():
        path = ROOT / f"models/experiments/{name}.joblib"
        if path.exists():
            require_equal(sha256(path), details["artifact_sha256"], name)
            methods.setdefault(name, path)
    results = {}
    for name, path in methods.items():
        pipeline = load_pipeline(path)
        results[name] = {}
        for domain, rows in sets.items():
            pred = [int(p) for p in pipeline.predict([e.text for e in rows])]
            ids = [row["id"] for row in synthetic] if domain == "synthetic_all" else None
            results[name][domain] = report_predictions(rows, pred, ids)
            if domain == "synthetic_all":
                for difficulty in ["clear", "subtle"]:
                    indices = [i for i, row in enumerate(synthetic) if row["difficulty"] == difficulty]
                    results[name][f"synthetic_{difficulty}"] = report_predictions(
                        [rows[i] for i in indices], [pred[i] for i in indices], [ids[i] for i in indices])
        require_equal(results[name], recorded["results"][name], f"{name} metrics/error IDs")
        print(name, {k: results[name]["synthetic_all"][k] for k in ["precision", "recall", "f1", "false_positives", "false_negatives"]}, flush=True)
    return dict(status="frozen_results_reproduced", group_membership_rebuilt=rebuild_groups or not cache.exists(),
                selection_sha256=sha256(reports / "selection.json"),
                artifact_sha256={name: sha256(path) for name, path in methods.items()},
                effective_candidate_training_overlap=leakage,
                original_training_overlap=original_leakage, results=results,
                api_model="models/job_posting_classifier.joblib",
                decision="Retain original: selected candidate regresses on synthetic overall and subtle scams.",
                authentic_first_contact_recruitment_test="Unavailable; no real-world recruitment-message performance claim.",
                final_set_policy="No fitting, threshold changes, or candidate reselection in this verification.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-groups", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/model_integration_verification.json")
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        result = verify(args.rebuild_groups)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
