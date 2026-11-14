# Actual evaluation tables

All precision/recall/F1 values use the positive (fraudulent/spam) class. Matrices are rows actual, columns predicted, in [legitimate, fraudulent] order; for SMS use [ham, spam]. Zero predicted positives is reported as precision 0 by convention. These are raw model/baseline predictions, never evidence-rule UI warnings.

## Historical job-posting holdout — contaminated by near templates

2,505 postings: 2,398 legitimate and 107 fraudulent. A stronger prior audit found 548 near-template matches to original training at cosine >=0.90, including 3 exact matches after contact/number normalization. These are reproducible historical comparisons, not clean generalization estimates. The high always-legitimate accuracy illustrates class imbalance.

| Method/subset | N | Accuracy | Precision | Recall | F1 | FP | FN | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Original classifier | 2505 | 0.9681 | 0.6116 | 0.6916 | 0.6491 | 47 | 33 | `[[2351, 47], [33, 74]]` |
| always_legitimate | 2505 | 0.9573 | 0.0000 | 0.0000 | 0.0000 | 0 | 107 | `[[2398, 0], [107, 0]]` |
| fixed_keyword_rules | 2505 | 0.9529 | 0.1333 | 0.0187 | 0.0328 | 13 | 105 | `[[2385, 13], [105, 2]]` |

## Synthetic messages — not real-world validation

32 hand-authored examples (16 legitimate, 16 scams); 16 subtle examples (8 of each class). These were excluded from fitting and threshold selection but have already been evaluated and inspected. They are not a fresh blind test. Zero false positives among 16 synthetic negatives is not evidence of a negligible real-world rate.

| Method/subset | N | Accuracy | Precision | Recall | F1 | FP | FN | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Original, all | 32 | 0.6562 | 1.0000 | 0.3125 | 0.4762 | 0 | 11 | `[[16, 0], [11, 5]]` |
| Original, clear | 16 | 0.6875 | 1.0000 | 0.3750 | 0.5455 | 0 | 5 | `[[8, 0], [5, 3]]` |
| Original, subtle | 16 | 0.6250 | 1.0000 | 0.2500 | 0.4000 | 0 | 6 | `[[8, 0], [6, 2]]` |
| always_legitimate | 32 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 16 | `[[16, 0], [16, 0]]` |
| fixed_keyword_rules | 32 | 0.6875 | 1.0000 | 0.3750 | 0.5455 | 0 | 10 | `[[16, 0], [10, 6]]` |

## Frozen selected candidate versus original

The candidate is retained for research only. Synthetic regression was the reason to keep the original; no retraining or final-example threshold adjustment was made. Generic SMS labels do not establish recruitment fraud or first-contact status. The candidate posting holdout also has near-template matches (4); SMS and synthetic inputs passed the recorded additional overlap check, which cannot exclude all semantic leakage.

| Method/subset | N | Accuracy | Precision | Recall | F1 | FP | FN | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Synthetic all / Original | 32 | 0.6562 | 1.0000 | 0.3125 | 0.4762 | 0 | 11 | `[[16, 0], [11, 5]]` |
| Synthetic all / Candidate | 32 | 0.6250 | 1.0000 | 0.2500 | 0.4000 | 0 | 12 | `[[16, 0], [12, 4]]` |
| Synthetic subtle / Original | 16 | 0.6250 | 1.0000 | 0.2500 | 0.4000 | 0 | 6 | `[[8, 0], [6, 2]]` |
| Synthetic subtle / Candidate | 16 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 8 | `[[8, 0], [8, 0]]` |
| Reserved UCI SMS / Original | 1027 | 0.8783 | 0.1667 | 0.0265 | 0.0458 | 15 | 110 | `[[899, 15], [110, 3]]` |
| Reserved UCI SMS / Candidate | 1027 | 0.9825 | 0.9060 | 0.9381 | 0.9217 | 11 | 7 | `[[903, 11], [7, 106]]` |
| Historical postings / Original | 2505 | 0.9681 | 0.6116 | 0.6916 | 0.6491 | 47 | 33 | `[[2351, 47], [33, 74]]` |
| Historical postings / Candidate | 2505 | 0.9637 | 0.5851 | 0.5140 | 0.5473 | 39 | 52 | `[[2359, 39], [52, 55]]` |

**Authentic first-contact recruitment test results: unavailable.** No real-world recruitment accuracy claim is supported. The integrated warning policy has not been validated on an authentic recruitment dataset either. A working demonstration is not an accuracy study.

## Sources and reproduction

- [Original posting report](../reports/job_posting_metrics.json) and [synthetic report](../reports/synthetic_evaluation.json): frozen measured results.
- [Release reproduction](../reports/release_metrics.json): original artifact plus both baselines re-evaluated during release; no fitting.
- [Integration audit](../reports/ai_model_integration.md) and [machine-readable audit](../reports/model_integration_verification.json): historical candidate comparisons and contamination findings. Candidate/SMS values in this table are the earlier reproduced audit, not a new release training run.
- [All candidate results](../reports/improvement_evaluation.json): frozen historical research. Four unselected intermediate artifacts are not included in the release.

Run `python scripts/download_test_data.py` then `python scripts/verify_release_metrics.py` inside the installed virtual environment. It checks original and baseline metrics against the frozen reports and verifies the model hash. It does not change those reports or the model.
