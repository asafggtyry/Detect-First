# Detect First

**A local messaging prototype that helps students pause before replying to unfamiliar job offers.** Built for the Veritas AI 2026 hackathon; intended track: AI + Finance. Official requirements still need confirmation.

The WhatsApp-inspired demo includes three fictional conversations, a real trained classifier, evidence warnings, **Block**, **Accept Anyway**, and **Reset demo**. It is not connected to WhatsApp or a phone, does not independently verify employers, and is not financial advice.

## Windows setup: start here

You need **64-bit Python 3.12**, Git (if cloning), and a current browser. Tested on Windows with Python 3.12.14 and Chromium. Other platforms/versions are not certified by this release. Install once while online; the installed demo needs no API key, raw dataset, training or frontend build.

Open PowerShell where you want the project. Clone the **release branch**, because the default GitHub branch is the earlier frontend:

```powershell
git clone --branch release/veritas-2026 https://github.com/asafggtyry/Detect-First.git
cd Detect-First
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c requirements-lock.txt
.\.venv\Scripts\python.exe -m detect_first.server
```

Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**. Keep PowerShell open. Stop with **Ctrl+C**. No virtual-environment activation or PowerShell policy change is needed. For a branch ZIP, extract it and open PowerShell in the directory containing this README before the `python --version` step.

The server serves both `frontend/` and `/api/scan` from the same origin. Wait for **Live classifier connected**. Do not open `index.html` directly or use a separate static server. The app never falls back to sample responses.

For later runs, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m detect_first.server
```

If port 8000 is occupied, run `.\.venv\Scripts\python.exe -m detect_first.server --port 8001` and open `http://127.0.0.1:8001/`. Use the same origin consistently.

| Problem | Fix |
|---|---|
| `python` opens the Store or is missing | Install full Python 3.12 with pip from [python.org](https://www.python.org/downloads/), enable PATH, and reopen PowerShell. |
| `venv` reports missing `ensurepip` | Use a full Python distribution. The bundled agent runtime lacked it during verification; pip was bootstrapped separately into the fresh environment. |
| Missing/incompatible model | Restore `models/job_posting_classifier.joblib` from the release checkout and reinstall requirements. Do not retrain to fix the demo. |
| Connection error | Start/restart the server, open its loopback URL and use **Try again**. No substitute verdict is shown. |
| Old choices/replies remain | **More options → Reset demo** with the API running. Clearing this site's browser data also removes local choices. |
| Session capacity reached | Reset this browser or restart the local server. |

`app.py` is the earlier standalone Streamlit prototype, retained for history/testing. **It is not the final demo entry point.**

## Demo walkthrough

1. Open **Mom**: saved contact, not scanned. This is a scope rule, not proof of safety.
2. Open **124-5135-2355**: a harmless unknown sender's first message is scanned once and triggers no warning. No warning is not a safety guarantee.
3. Open **732-882-1944**: inspect the $60 deposit, up to $300/day claim and quick-reply pressure. Scroll the evidence list.
4. Point out **the ML classifier did not flag this message**. Separate rules trigger this warning. No employer was independently verified.
5. **Block** removes the reply box. **Accept Anyway** allows simulated replies and reopening the warning. **Reset demo** clears choices/replies and requests fresh scans.

The home screen starts the two unknown-sender scans. Saved contacts and outgoing replies are not sent for classification. Later messages are outside this first-message-only policy.

Submission assets: [two-minute demo script](docs/DEMO.md), [short write-up](docs/SUBMISSION.md), [remaining checklist](docs/SUBMISSION_CHECKLIST.md), [complete test report](reports/release_verification.md).

## Model versus evidence rules

The original model is **TF-IDF word unigrams/bigrams + balanced logistic regression**, trained with scikit-learn 1.9.1 on job-posting titles/descriptions. It uses a stratified 80/20 split, seed 2026. No release training or threshold tuning was performed.

- `model_flagged` is exclusively the learned Boolean prediction; it is `null` when skipped.
- `reasons` and `evidence_flagged` are deterministic rule/context observations, not model explanations.
- `is_scam` is the legacy field name for the **UI warning decision**: model flags OR at least two rule categories. It is not proof of fraud.
- `warning_source` separates `none`, `model`, `evidence` and `both`.

Rules inspect work-offer wording, payment wording, daily earnings of at least $200, a limited role/duty word list, urgency, and sender context. The earnings threshold is only a prototype heuristic. Unknown contact does not prove unsolicited contact, and unverified employer does not mean fake employer; the UI labels make these limits clearer.

**An unknown first-contact job message can trigger a warning from two context categories alone.** Categories can be correlated. Rules can misread negation/context and cause false warnings. No employer lookup or calibrated risk probability is provided. See the [API contract](docs/API.md).

## Dataset, baselines and actual metrics

Training uses **OpenML 46655, `fake_job_postings2`**, an English EMSCAD-derived posting dataset: 12,725 records, including 551 fraudulent labels. Case/whitespace deduplication removes 200 records, leaving 12,525. The 2,505-record test split contains 107 fraudulent postings. [Provenance, checksum and licence caveats](data/source.md) identify the public source; raw downloads are Git-ignored.

**Historical posting scores have known near-template contamination.** A stronger prior audit found 548 holdout rows at cosine ≥0.90 against training, including three exact matches after contact/number normalization. The original exact-text test missed those templates. These scores reproduce, but are historical comparisons, not clean generalization estimates or recruitment-chat accuracy.

| Historical posting method | Accuracy | Precision | Recall | F1 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| Original classifier | 96.81% | 61.16% | 69.16% | 64.91% | 47 | 33 |
| Always legitimate | 95.73% | 0.00% | 0.00% | 0.00% | 0 | 107 |
| Fixed keyword baseline | 95.29% | 13.33% | 1.87% | 3.28% | 13 | 105 |

The separate 32-message evaluation is **hand-authored synthetic data**, inspired by FTC patterns. It is balanced and excluded from fitting/threshold selection, but already inspected repeatedly: neither a fresh blind test nor real-world validation.

| Synthetic method (16 scams + 16 legitimate) | Accuracy | Precision | Recall | F1 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| Original classifier | 65.63% | 100.00% | 31.25% | 47.62% | 0 | 11 |
| Always legitimate | 50.00% | 0.00% | 0.00% | 0.00% | 0 | 16 |
| Fixed keyword baseline | 68.75% | 100.00% | 37.50% | 54.55% | 0 | 10 |

The classifier catches **5/16 synthetic scams**, including **2/8 subtle scams**. Zero FP on 16 synthetic negatives does not establish a low real-world false-positive rate. The keyword baseline is separate from the app's multi-category warning policy. All table metrics count classifier/baseline predictions, never combined warnings.

The rejected research candidate catches **4/16 overall and 0/8 subtle synthetic scams**, so the original remains in use. Better generic SMS-spam scores do not establish recruitment performance. **Authentic first-contact recruitment validation is unavailable.** Neither model is demonstrated reliable for that task.

See [all evaluation tables and matrices](docs/EVALUATION.md), [release metric reproduction](reports/release_metrics.json), and [frozen integration audit](reports/ai_model_integration.md).

## Run all tests and reproduce metrics

From the repository root after setup:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c requirements-lock.txt
.\.venv\Scripts\python.exe scripts\download_test_data.py
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q --browser-tests --junitxml=reports/release_tests.xml
.\.venv\Scripts\python.exe scripts\verify_release_metrics.py
```

Tests start their own local server. They exercise the saved model, HTTP contract, sessions/caching, first-message exclusions, all conversations/actions, Reset and failure recovery in Chromium at **390×844 and 320×568**. Browser tests require local process/socket permission. Omitting `--browser-tests` explicitly skips browser cases; that is not a complete run. Mobile emulation does not certify physical devices or Safari.

See [complete release verification](reports/release_verification.md) and [JUnit results](reports/release_tests.xml). The metric verifier compares original model/baseline results to the committed reports and checks the artifact hash without fitting anything.

To capture actual browser/API responses from a separately running demo server, run `.\.venv\Scripts\python.exe scripts\verify_live_demo.py` in a second PowerShell window with the same `PLAYWRIGHT_BROWSERS_PATH` setting. Add `--url http://127.0.0.1:8001` if you used that port. This writes `reports/release_demo_responses.json` and home screenshots; it checks that fixture scripts and external requests are absent.

`requirements-lock.txt` records the exact tested Windows/Python 3.12 versions. Using it as constraints pins runtime setup; `pip install -r requirements-lock.txt` installs the full tested environment. Node is unnecessary for the app; it was used only to syntax-check JavaScript.

## Reproduction files and research history

| Path | Purpose |
|---|---|
| `frontend/` | Complete no-build UI. Historical `demo-fixtures.js` is never loaded. |
| `detect_first/` | API, model loader, evidence, state and research utilities. |
| `models/job_posting_classifier.joblib` | Original release model; SHA-256 `6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42`. |
| `models/first_contact_candidate.joblib` | Rejected research artifact; not the API default. |
| `data/synthetic/`, `reports/`, `tests/`, `scripts/` | Evaluation examples, measured results, tests and source/download tools. |
| `docs/` | Submission text, demo, API, privacy, evaluation and checklist. |

All code/artifacts needed to **run the demo and reproduce release metrics** are tracked. Public datasets download with checksum verification. Four unselected intermediate experimental artifacts are not shipped; their historical metrics remain documented. The two shipped artifacts can be verified with `scripts/verify_model_integration.py --rebuild-groups` after downloading posting and SMS data as described in the [audit](reports/ai_model_integration.md).

Training scripts remain for transparency, not demo setup. `scripts/train_model.py` overwrites the original model/report. The candidate experiment is frozen and prevents rerunning into existing reports. Do not train or tune on exposed final examples for this submission.

## Privacy, limits and credits

This is a local single-process educational prototype, with no real messaging, employer verification, calibrated probability, authentic recruitment validation or later-message detection. Block affects only the simulation. Text is processed locally; the server retains hashes/senders/results in memory and localStorage retains choices/replies until successful Reset or browser-data clearing. Use fictional text. [Privacy and dependency notes](docs/PRIVACY.md) describe retention and scope.

Credits: OpenML/EMSCAD and the University of the Aegean Laboratory of Information & Communication Systems Security; FTC guidance for synthetic patterns; the repository's Fable frontend inspired by WhatsApp (no affiliation); scikit-learn, Flask, Streamlit, joblib, pytest and Playwright. The prior README credits GitHub Copilot SDK in VS Code; **OpenAI Codex assisted release engineering, testing and documentation**. The model was trained within this project, not obtained from a pretrained-model API. Team names/roles and complete AI disclosures need team confirmation.

Official rules, deadline, portal, judge access, allowed AI assistance, asset requirements and licensing obligations remain unconfirmed. Follow the [submission checklist](docs/SUBMISSION_CHECKLIST.md). No default branch or repository visibility was changed.
