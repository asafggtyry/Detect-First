"""Auditable offline rule comparison. No production changes or model fitting.

Run audit, then develop, commit selection, then final ONCE. Final creates an
exclusive marker before any inference and refuses overwrites or changed inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detect_first.data import normalize_text
from detect_first.experimental_policy import POLICIES, analyze_rules, combine
from detect_first.metrics import binary_metrics
from detect_first.model import load_pipeline, predict_scam
from detect_first.server import ScanService

OUT = ROOT / "reports/false_positive_reduction"
DEV = ROOT / "data/development/false_positive_reduction.jsonl"
FINAL = ROOT / "data/synthetic/evaluation.jsonl"
MODEL = ROOT / "models/job_posting_classifier.joblib"
BASE = "16c657c853a90b7d63d6ca0272141d7ae9713d3a"
MODEL_SHA = "6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or row["id"] in seen or type(row.get("label")) is not int
                or row["label"] not in (0, 1) or not isinstance(row.get("text"), str)
                or not row["text"].strip()):
            raise ValueError("Invalid or duplicate evaluation row")
        seen.add(row["id"])
    if not rows:
        raise ValueError("Empty evaluation set")
    return rows


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def frozen_inputs():
    files = sorted((ROOT / "detect_first").glob("*.py")) + [
        DEV, ROOT / "data/development/README.md", ROOT / "docs/FALSE_POSITIVE_PROTOCOL.md",
        Path(__file__), MODEL, FINAL,
    ]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in files}


def verify_protected():
    if sha(MODEL) != MODEL_SHA:
        raise ValueError("Production model changed")
    paths = ["frontend", "models", "data/synthetic", "detect_first/evidence.py",
             "detect_first/state.py", "detect_first/server.py", "detect_first/model.py",
             "detect_first/simulation.py", "detect_first/simulation_fixtures.py"]
    if git("diff", BASE, "--", *paths):
        raise ValueError("Protected production code/data differs from release")


def audit():
    """Lexical separation only: never display final/demo rows or labels."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from detect_first.message_data import clean_text
    from detect_first.simulation_fixtures import SIMULATION_FIXTURES
    from detect_first.state import create_demo_store
    verify_protected()
    rows = read_rows(DEV)
    final = read_rows(FINAL)
    static = create_demo_store(lambda _: False)
    demo = [f.message for f in SIMULATION_FIXTURES]
    demo += [m.text for c in static.conversations.values() for m in c.messages]
    texts = [r["text"] for r in rows]
    normalized = [clean_text(t) for t in texts]
    references = [r["text"] for r in final] + demo
    all_text = normalized + [clean_text(t) for t in references]
    matrix = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(all_text)
    similarities = (matrix[:len(rows)] @ matrix[len(rows):].T).toarray()
    internal = (matrix[:len(rows)] @ matrix[:len(rows)].T).toarray()
    import numpy as np
    np.fill_diagonal(internal, 0)
    result = {
        "development_sha256": sha(DEV), "final_sha256": sha(FINAL),
        "development_count": len(rows), "class_counts": dict(Counter(r["label"] for r in rows)),
        "reference_counts": {"final": len(final), "demo": len(demo)},
        "normalized_exact_overlaps": len(set(normalized) & set(all_text[len(rows):])),
        "internal_exact_duplicates": len(normalized) - len(set(normalized)),
        "maximum_cross_cosine": float(similarities.max()),
        "cross_pairs_at_085": int((similarities >= .85).sum()),
        "internal_maximum_cosine": float(internal.max()),
        "internal_pairs_at_085": int((internal >= .85).sum() // 2),
        "scope": "Automated lexical audit, not semantic independence; final/demo text and labels not displayed.",
    }
    if result["normalized_exact_overlaps"] or result["cross_pairs_at_085"] or result["internal_exact_duplicates"]:
        raise ValueError("Development separation failed; stop without scoring")
    write_new(OUT / "separation.json", result)
    print(json.dumps(result, indent=2))


def score_rows(rows, policies, analyzer):
    records = []
    for row in rows:
        # Only text crosses the predictor boundary. Labels/IDs are appended later.
        text = row["text"]
        original = analyzer(text)
        predictions = {"ml": int(original["model_flagged"]),
                       "original_rules": int(original["evidence_flagged"]),
                       "original_combined": int(original["is_scam"])}
        observations = {"original": original["reasons"]}
        for policy in policies:
            result = analyze_rules(text, policy)
            observations[policy] = result["signals"]
            predictions[policy + "_rules"] = int(result["rule_flagged"])
            predictions[policy + "_combined"] = int(combine(original["model_flagged"], result["rule_flagged"]))
        records.append({"id": row["id"], "reference_label": row["label"],
                        "family": row.get("family", row.get("difficulty", "unknown")),
                        "predictions": predictions, "rule_observations": observations})
    metrics, errors = {}, {}
    for name in records[0]["predictions"]:
        actual = [r["reference_label"] for r in records]
        predicted = [r["predictions"][name] for r in records]
        metrics[name] = binary_metrics(actual, predicted)
        m = metrics[name]
        m["false_positive_rate"] = m["false_positives"] / (m["false_positives"] + m["true_negatives"]) if 0 in actual else None
        errors[name] = {
            "false_positive_ids": [r["id"] for r in records if r["reference_label"] == 0 and r["predictions"][name] == 1],
            "false_negative_ids": [r["id"] for r in records if r["reference_label"] == 1 and r["predictions"][name] == 0],
        }
    families = {}
    for family in sorted({r["family"] for r in records}):
        subset = [r for r in records if r["family"] == family]
        families[family] = {name: {
            "examples": len(subset),
            "false_positives": sum(r["reference_label"] == 0 and r["predictions"][name] == 1 for r in subset),
            "false_negatives": sum(r["reference_label"] == 1 and r["predictions"][name] == 0 for r in subset),
        } for name in metrics}
    return {"metrics": metrics, "errors": errors, "families": families, "records": records}


def select_candidate(metrics):
    baseline = metrics["original_combined"]
    eligibility = {}
    for name in POLICIES:
        m = metrics[name + "_combined"]
        eligibility[name] = (
            m["false_positive_rate"] <= .05 and m["false_positives"] < baseline["false_positives"]
            and m["false_negatives"] <= baseline["false_negatives"]
            and m["f1"] >= baseline["f1"] + .05)
    def rank(name):
        m = metrics[name + "_combined"]
        return (not eligibility[name], -m["f1"], m["false_positives"], m["false_negatives"], POLICIES.index(name))
    chosen = min(POLICIES, key=rank)
    return {"selected_policy": chosen, "eligibility": eligibility,
            "passes_development_gate": eligibility[chosen],
            "selection_scope": "development only; ineligible winner is diagnostic, not a deployment recommendation"}


def develop():
    verify_protected()
    if (OUT / "development.json").exists() or (OUT / "selection.json").exists():
        raise FileExistsError("Development results already frozen; do not tune or overwrite")
    if git("status", "--porcelain"):
        raise ValueError("Commit implementation, data, protocol and audit before development scoring")
    separation = json.loads((OUT / "separation.json").read_text())
    if separation["development_sha256"] != sha(DEV) or separation["final_sha256"] != sha(FINAL):
        raise ValueError("Separation audit is stale")
    pipeline = load_pipeline(MODEL)
    service = ScanService(lambda text: predict_scam(text, pipeline))
    report = score_rows(read_rows(DEV), POLICIES, service.analyze)
    report.update(scope="Authored synthetic development only; no independent human labeling.",
                  frozen_commit=git("rev-parse", "HEAD"), inputs=frozen_inputs())
    write_new(OUT / "development.json", report)
    selection = select_candidate(report["metrics"])
    selection.update(inputs=frozen_inputs(), development_report_sha256=sha(OUT / "development.json"),
                     separation_sha256=sha(OUT / "separation.json"),
                     frozen_commit=git("rev-parse", "HEAD"))
    write_new(OUT / "selection.json", selection)
    print(json.dumps({"metrics": report["metrics"], "selection": {k: v for k, v in selection.items() if k != "inputs"}}, indent=2))


def claim_final_run(output: Path, payload: dict):
    if (output / "final.json").exists():
        raise FileExistsError("Final report exists; no repeat evaluation")
    write_new(output / "final_run_started.json", payload)


def final():
    verify_protected()
    selection = json.loads((OUT / "selection.json").read_text())
    if git("status", "--porcelain"):
        raise ValueError("Commit frozen development selection before final evaluation")
    if selection["inputs"] != frozen_inputs():
        raise ValueError("Frozen experiment inputs changed; final evaluation refused")
    if (selection["development_report_sha256"] != sha(OUT / "development.json")
            or selection["separation_sha256"] != sha(OUT / "separation.json")):
        raise ValueError("Development report/audit changed")
    policy = selection["selected_policy"]
    # Lock before any candidate or model prediction, even if later processing fails.
    claim_final_run(OUT, {"started_utc": datetime.now(timezone.utc).isoformat(),
                         "selection_sha256": sha(OUT / "selection.json"),
                         "commit": git("rev-parse", "HEAD"), "policy": policy})
    pipeline = load_pipeline(MODEL)
    service = ScanService(lambda text: predict_scam(text, pipeline))
    report = score_rows(read_rows(FINAL), [policy], service.analyze)
    report.update(selected_policy=policy, passes_development_gate=selection["passes_development_gate"],
                  selection_sha256=sha(OUT / "selection.json"), final_sha256=sha(FINAL),
                  production_model_sha256=sha(MODEL),
                  scope="One candidate pass on 32 historically exposed synthetic examples. Not unseen or real-world validation.")
    write_new(OUT / "final.json", report)
    print(json.dumps({"selected_policy": policy, "metrics": report["metrics"], "errors": report["errors"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["audit", "develop", "final"])
    args = parser.parse_args()
    {"audit": audit, "develop": develop, "final": final}[args.stage]()
