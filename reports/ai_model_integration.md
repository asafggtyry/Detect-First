# AI model integration verification (2026-11-14)

## Decision

**Retain the existing API classifier.** The frozen `joint_hybrid_prefix` candidate is worse on the task-specific synthetic first-contact benchmark: 4/16 scams caught versus 5/16, and 0/8 subtle scams versus 2/8. Its strong SMS-spam performance does not justify replacing the recruitment classifier. No candidate was reselected, retrained, or threshold-tuned after final evaluation. All five frozen candidates were independently re-evaluated; none improved overall synthetic recall over the original.

## Measured paired results

Positive-class metrics below use the same examples and labels for each model. They count raw ML predictions only, never evidence-based UI warnings. The candidate threshold remains the development-selected 0.50.

| Evaluation subset | Model | N | Precision | Recall | F1 | FP | FN | TP |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Synthetic first contact | Original | 32 | 1.0000 | 0.3125 | 0.4762 | 0 | 11 | 5 |
| Synthetic first contact | Candidate | 32 | 1.0000 | 0.2500 | 0.4000 | 0 | 12 | 4 |
| Synthetic clear | Original | 16 | 1.0000 | 0.3750 | 0.5455 | 0 | 5 | 3 |
| Synthetic clear | Candidate | 16 | 1.0000 | 0.5000 | 0.6667 | 0 | 4 | 4 |
| Synthetic subtle | Original | 16 | 1.0000 | 0.2500 | 0.4000 | 0 | 6 | 2 |
| Synthetic subtle | Candidate | 16 | 0.0000 | 0.0000 | 0.0000 | 0 | 8 | 0 |
| Historical posting holdout | Original | 2505 | 0.6116 | 0.6916 | 0.6491 | 47 | 33 | 74 |
| Historical posting holdout | Candidate | 2505 | 0.5851 | 0.5140 | 0.5473 | 39 | 52 | 55 |
| Reserved UCI SMS | Original | 1027 | 0.1667 | 0.0265 | 0.0458 | 15 | 110 | 3 |
| Reserved UCI SMS | Candidate | 1027 | 0.9060 | 0.9381 | 0.9217 | 11 | 7 | 106 |

Zero predicted positives gives precision 0 by the reporting convention (candidate subtle subset); it does not mean measured precision among alerts. Synthetic all/clear/subtle contain 16/8/8 positive and 16/8/8 negative examples respectively. Zero FP on just 16 synthetic negatives is not evidence of a negligible real-world false-positive rate.

## What is genuinely held out

- The 1,027 SMS examples (113 spam, 914 ham) are group-reserved from candidate training and development. Their membership was independently reconstructed from the checksum-verified public archives. The additional effective-input audit found no exact or >=0.90 cosine match to candidate training. They are real SMS data, but spam labels are not confirmed recruitment fraud and first-contact/saved-contact status is unknown.
- The 32 first-contact examples are **synthetic**, held out from fitting and development selection but historically evaluated. Their unchanged hash and absence of exact/near training matches were verified. They are not a fresh blind test or authentic messages.
- **Authentic first-contact recruitment test results: unavailable.** No appropriately labelled real first-contact recruitment corpus is present. This work does not manufacture a new synthetic set and call it real-world validation.
- The historical 2,505 posting examples are identical for both classifiers, but do not constitute a clean near-template holdout. The original training split lacked near-duplicate protection; the new audit also found remaining candidate near matches. Keep these scores as historical comparisons, not leakage-free validation.

## Leakage and provenance audit

The imported protocol, selection, split audit, final report, and selected candidate are preserved byte-for-byte from Project. Their linked SHA-256 hashes were verified. The public sources were reloaded and all six split memberships were independently reconstructed, including transitive near-template groups; every reported metric and error ID for the original and all five candidates reproduced exactly.

The historical parent-text split audit reported zero group overlap after purging 1,234 job rows against the original holdout. That check was insufficient. A second audit fits its own vocabulary to the effective candidate training inputs, including the 60-word posting prefixes, and compares every reserved row:

| Reserved subset | Exact matches | Near matches >=0.90 | Maximum cosine |
|---|---:|---:|---:|
| job_holdout | 0 | 4 | 0.982764 |
| sms_holdout | 0 | 0 | 0.865499 |
| synthetic_all | 0 | 0 | 0.244380 |
| job_dev | 0 | 12 | 0.944535 |
| sms_dev | 0 | 1 | 0.908081 |

The same audit against the original model's reconstructed training split found **548 posting holdout rows at cosine >=0.90**, including **3 exact matches after contact/number normalization**. The original exact-deduplication check used only case/whitespace normalization, so it did not catch those normalized templates. Original-to-SMS and original-to-synthetic comparisons both had zero exact/near matches (maximum cosine 0.320569 and 0.187478 respectively). Thus the synthetic and SMS comparisons pass this check for both models, while posting metrics for both remain compromised.

This is an additional audit with an effective-training vocabulary, not the historical all-parent-text grouping vocabulary. Augmentation and vocabulary choice can expose matches missed by the original check; these counts should not be attributed exclusively to prefix augmentation. Cosine checks still cannot exclude semantic leakage. No final examples were removed and no scores were repaired after seeing them.

Future training/final-evaluation code now checks actual planned training inputs before fitting or reporting and aborts on these overlaps. The frozen experiment is read-only: its existing selection/final files prevent reruns. A future experiment needs a new directory and a new predeclared split that accounts for every augmentation before fitting. The independent verification command intentionally reports historical contamination instead of certifying it as clean or silently changing its data.

## Exact API model and contract

- Default: `models/job_posting_classifier.joblib`, TF-IDF word unigrams/bigrams + balanced logistic regression, decision threshold 0.50, scikit-learn 1.9.1.
- SHA-256: `6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42`.
- Rejected research artifact: `models/first_contact_candidate.joblib`, `joint_hybrid_prefix`, word + character TF-IDF, job postings + UCI SMS + weakly labelled training-only posting prefixes; threshold 0.50.
- Candidate SHA-256: `a8413ef50b155b36714c2cddd49827f3c56a7885340926b3b01144a82f437f21`.
- Frontend files, `detect_first/server.py`, original artifact, evidence rules, and API response fields are unchanged. The candidate can be explicitly injected into `create_app(model_path=...)` for research tests but is never the runtime default.
- `model_flagged` remains raw learned output; `evidence_flagged`, `reasons[*].source`, and `warning_source` retain their separate provenance. `is_scam` remains the combined UI-warning decision.
- Saved contacts and later messages bypass classification; repeated identical first requests reuse cached results. Tests verify the default and candidate against all 32 synthetic examples through the real endpoint, without counting warnings as model hits.

## Verification

- Final full suite: **60 passed, 0 failed, 0 skipped** (43 existing + 17 added). See `reports/ai_integration_tests.xml`.
- Seven real Chromium mobile-emulation tests at 390x844 and 320x568: saved contact, benign/scam chats, replies skipped, Block, Accept Anyway, reopening warnings, Reset, cached reloads, offline/malformed/503/timeout responses and recovery. Screenshots visually inspected in `reports/browser/warning-390.png` and `warning-320.png`. This is mobile browser emulation, not a physical handset or iOS Safari test.
- Initial sandbox attempts had browser-startup/temp-directory setup errors (including three temporary-directory errors in the new unit tests). Browser attempts were stopped and the full suite was rerun successfully with local browser/socket/temp access. These were environment failures, not suppressed test failures.
- Verified Project source preservation by comparing SHA-256 hashes of every tracked/nonignored file and its full Git status before/after. Public raw inputs and intermediate models were copied read-only into Git-ignored integration directories. No edits, staging, commits, or cleanup were performed in Project.
- Ported the conversation-store fix that rejects empty input and completes inference before inserting a sender/message, so failed scans can be retried without partial state.

## Reproduce without fitting

From the integration repository, with its pinned dependencies installed:

```powershell
.\.venv\Scripts\python.exe scripts\download_test_data.py
.\.venv\Scripts\python.exe -c "from detect_first.message_data import download_sms; download_sms()"
.\.venv\Scripts\python.exe scripts\verify_model_integration.py --rebuild-groups
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q --browser-tests
```

`.gitattributes` preserves frozen report bytes and pins the synthetic fixture to CRLF because historical hashes were measured on Windows. An index checkout with `core.autocrlf=false` was verified to preserve every frozen hash input byte-for-byte. The verifier uses the two checked-in artifacts. If the four other experimental files are available in ignored `models/experiments/`, it verifies them as well; their historical results remain in `reports/improvement_evaluation.json`. Raw data and split cache are not pushed. The original Project experiment protocol is an archived record; its historical no-commit/no-push scope does not describe this integration task.

## Remaining limitations

Neither model reliably detects first-contact recruitment scams. The original misses 11/16 synthetic scams and 6/8 subtle scams. Current warnings still rely heavily on evidence heuristics, and a negative result is not a safety guarantee. The candidate learns SMS spam rather than verified recruitment fraud; prefix labels are inherited and may be wrong for a short excerpt. Both domains and the tiny synthetic benchmark differ from real teen messaging. Scores are not calibrated risk probabilities. The prototype trusts client-supplied contact metadata, keeps only per-session in-memory history, and intentionally misses scams introduced in later messages. Do not tune further on these already exposed final examples.

## Files added or modified

- `.gitattributes`
- `.gitignore`
- `README.md`
- `detect_first/message_data.py`
- `detect_first/message_model.py`
- `detect_first/state.py`
- `models/first_contact_candidate.joblib`
- `reports/ai_integration_tests.xml`
- `reports/ai_model_integration.md`
- `reports/browser/warning-390.png`
- `reports/data_split_audit.json`
- `reports/experiment_protocol.md`
- `reports/improvement_evaluation.json`
- `reports/model_integration_verification.json`
- `reports/selection.json`
- `reports/source_preservation.json`
- `scripts/improve_model.py`
- `scripts/verify_model_integration.py`
- `tests/test_message_improvements.py`
