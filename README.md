# Detect First

Detect First is a local, simulated messaging app that helps high school students pause and review unfamiliar job offers before replying. It was built for the AI + Finance track of the Veritas AI International High School Hackathon 2026.

> **This project is a prototype and is not financial advice.**

## What it does

- Shows a mobile-friendly, WhatsApp-inspired chat list and simulated conversations.
- Skips saved contacts.
- Runs a locally trained scikit-learn text classifier once on the first incoming message from each unsaved sender. Later messages from that sender are not scanned again.
- Keeps ordinary first-contact messages visible without an intrusive warning.
- Explains concrete message evidence using a separate, deterministic evidence layer.
- Lets a student mark a simulated sender blocked or accept the chat anyway.
- Resets the demo so the scenarios can be replayed.
- Serves Fable's frontend and the real Python scan API together. Sample-result fallback is disabled.

There is no sign-in, external messaging connection, real SMS or WhatsApp access, media upload, camera, microphone, or call feature. Typed chat replies stay in the local simulation and are not sent to the classifier.

## How the AI works

The project trains a real text classifier using scikit-learn's `TfidfVectorizer` and balanced `LogisticRegression`. It combines job-posting titles and descriptions, uses a fixed stratified 80/20 holdout split, and does not tune on the final holdout or synthetic evaluation examples. Training and evaluation commands are deterministic.

The model's domain is **job postings**, not first-contact recruitment messages. It is included to demonstrate a genuine trained model and a careful evaluation workflow, not to claim that it can reliably detect chat scams. No risk probability is displayed. The app shows the model's binary result separately from message-pattern evidence.

The warning is shown when the model flags the message **or** the separate evidence layer finds at least two concrete categories. This policy catches explicit red flags even when the out-of-domain classifier misses them; it does not change or overwrite the model prediction. Evidence categories are based on words in the message and available sender metadata:

- **Unsolicited job offer:** work is offered in a first message from an unsaved sender.
- **Upfront payment request:** the message asks for a fee or deposit to get or begin the job.
- **Unrealistic earnings:** a daily amount of at least $200 is advertised. This threshold is a prototype heuristic, not a financial standard.
- **Vague job details:** the message names no recognizable role or work duties.
- **Urgency / pressure:** the message includes a quick-reply request or short deadline.
- **Unverified employer identity:** the sender or employer has not been independently verified by the prototype. The UI states this limitation and never calls the sender a proven scammer.

These are review signals, not proof. In particular, this prototype does not independently look up or verify employers.

## Dataset, source and limitations

Training uses OpenML dataset **46655, `fake_job_postings2`**, a public EMSCAD-derived dataset. The measured file contains **12,725** job postings: **12,174 legitimate** and **551 fraudulent** (about 4.3% fraudulent). See [data/source.md](data/source.md) for provenance, licence notes, class distribution, relevance, and the download checksum.

The Kaggle page for the original “Real / Fake Job Posting Prediction” dataset credits the University of the Aegean Laboratory of Information & Communication Systems Security and displays a CC0 licence. Its download requires a Kaggle subscription/login, so this project instead downloads the public OpenML copy without signing in. OpenML's licence field says only `Kaggle`; the original Kaggle page's CC0 metadata and OpenML provenance are documented rather than treating that OpenML field as a precise licence.

The separate [synthetic evaluation set](data/synthetic/evaluation.jsonl) is balanced and hand-authored from public FTC job-scam patterns. It includes clear and subtle cases, is not EMSCAD data, and is never used for training or threshold tuning. The synthetic set is small and cannot validate real-world behavior. Since training texts are long job postings while application inputs are short messages, performance on the synthetic messages is an out-of-domain stress test only.

Preprocessing removes exact duplicate normalized title/description text and rejects conflicting labels. The training script checks that no exact normalized text overlaps the train and test splits. Near-duplicate descriptions and repeated employer templates are not automatically detected. Current scams, teen-specific contexts, class-prior shifts, and non-English content are additional limitations.

## Baselines and actual results

Two fixed baselines are evaluated: predicting every posting as legitimate and a small keyword detector. The keyword rules are comparison baselines, not the app's classifier. Reports contain precision, recall, F1, accuracy, confusion matrices, false-positive and false-negative counts, and example errors.

The actual saved reports are generated by the commands below:

- [`reports/job_posting_metrics.json`](reports/job_posting_metrics.json): actual held-out EMSCAD-derived metrics and baselines.
- [`reports/synthetic_evaluation.json`](reports/synthetic_evaluation.json): actual evaluation-only synthetic results, including the subtle subset.

The recorded 80/20 posting holdout contains 2,505 examples (2,398 legitimate and 107 fraudulent). The model reached **96.81% accuracy, 61.16% precision, 69.16% recall, and 64.91% F1**. Its confusion matrix, with rows actual and columns predicted in `[legitimate, fraudulent]` order, is `[[2351, 47], [33, 74]]`: **47 false positives and 33 false negatives**.

| Job-posting holdout method | Accuracy | Precision | Recall | F1 | False positives | False negatives |
|---|---:|---:|---:|---:|---:|---:|
| TF-IDF + logistic regression | 0.9681 | 0.6116 | 0.6916 | 0.6491 | 47 | 33 |
| Always predict legitimate | 0.9573 | 0.0000 | 0.0000 | 0.0000 | 0 | 107 |
| Fixed keyword rules | 0.9529 | 0.1333 | 0.0187 | 0.0328 | 13 | 105 |

The high holdout accuracy partly reflects the class imbalance. The always-legitimate baseline gets 95.73% accuracy while catching no fraudulent postings, so accuracy alone is not meaningful.

On the **32 synthetic messages**, the trained model reached 65.63% accuracy, 100% precision, 31.25% recall, and 47.62% F1, with 0 false positives and **11 false negatives out of 16 synthetic scams**. On the 16 subtle examples it reached 62.50% accuracy and 25.00% recall, missing **6 of 8 subtle synthetic scams**. The fixed keyword baseline reached 37.50% recall on all synthetic messages; always-legitimate reached 0%. These small, hand-authored results are not a fair estimate of real-world message performance, but they make the domain mismatch visible: the classifier misses many short scam messages. The demonstration warning for the provided recruitment text is therefore produced by multiple independent evidence signals, not by overriding or falsifying the model's negative prediction.

## Candidate model review (2026-11-14)

**The API keeps the original model.** The development-selected `joint_hybrid_prefix` candidate regressed on the unchanged synthetic first-contact benchmark: **4/16 scams caught versus 5/16**, and **0/8 subtle scams versus 2/8**. Both had zero false positives among 16 synthetic legitimate messages. Better SMS-spam scores did not transfer to recruitment scams; no threshold was retuned on final examples.

All frozen candidate results were independently reproduced. An additional audit found near-template matches in the candidate posting holdout and development inputs, despite the historical parent-group audit. Future experiments now stop on effective-training overlaps, including posting-prefix augmentation. The reserved SMS holdout and synthetic benchmark passed this additional check, but neither provides authentic first-contact recruitment validation.

See [the integration decision and full measured comparison](reports/ai_model_integration.md), [machine-readable reproduction](reports/model_integration_verification.json), and [all candidate results](reports/improvement_evaluation.json). The report includes precision, recall, F1, FP/FN, subtle results, hashes, leakage findings, 60-test verification, and reproducible commands. `models/first_contact_candidate.joblib` is retained for research only; it is not the default for `/api/scan`.

## Run locally (Windows)

Use Python 3.11 or newer (tested with 3.12). One-time setup from the repository folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Start the full application with one command:**

```powershell
.\.venv\Scripts\python.exe -m detect_first.server
```

Open **http://127.0.0.1:8000/**. The server serves `frontend/` and the API from the same origin; no frontend build or separate static server is needed. Use `--port 8001` if port 8000 is occupied. Stop with Ctrl+C. The checked-in model is loaded once on startup; no retraining, data download or external API is needed to run the demo. scikit-learn is pinned to the artifact's training version (1.9.1). A missing/incompatible model fails startup rather than returning fabricated predictions.

`app.py` remains the original, separate Streamlit prototype, including its synthetic input panel. It is not the entry point for the integrated Fable app.

## Live API contract

`POST /api/scan`, `Content-Type: application/json`:

```json
{"message":"Hi, we met yesterday.","sender":"124-5135-2355","is_saved_contact":false,"is_first_message":true}
```

Successful response for that message with the saved model:

```json
{
  "is_scam": false,
  "reasons": [],
  "model_flagged": false,
  "evidence_flagged": false,
  "warning_source": "none",
  "scanned": true,
  "skipped_reason": null,
  "cached": false
}
```

- `is_scam` is the **UI warning decision**, not proof of fraud or the raw ML output. It follows the original policy: `model_flagged` OR at least two evidence categories.
- `model_flagged` is exclusively the trained classifier's Boolean prediction; it is `null` when scanning is skipped.
- `evidence_flagged` means at least two separate rule categories were found. `warning_source` is `none`, `model`, `evidence`, or `both`.
- `reasons` contains objects such as `{"category":"upfront_payment_request","evidence":"The message asks for a payment to obtain or begin the job.","source":"evidence_rule"}`. These are rule observations, not learned model explanations or necessarily verbatim quotes.
- Categories: `unsolicited_job_offer`, `upfront_payment_request`, `unrealistic_earnings`, `vague_job_details`, `urgency_pressure`, `unverified_employer`.
- Saved contacts and later messages return `scanned:false`, `is_scam:false`, `model_flagged:null`, `reasons:[]`, and `skipped_reason` of `saved_contact`, `not_first_message`, or `already_scanned`. A skipped message is **not** a clean prediction.
- First-message tracking is per browser session and sender. Identical first-message retries return the original result with `cached:true`, without rerunning inference. Changed messages for an already-seen sender are skipped, even if flagged as first. Concurrent retries are serialized. API clients must retain the session cookie; browsers establish it when loading `/` or `/index.html`.
- `POST /api/reset` returns `{"reset":true}` and starts a fresh scan session for that browser. The frontend waits for success before clearing decisions/replies and rescanning. Other browser sessions are unaffected.
- All four request fields are required. Boolean fields must be real JSON booleans. Message length is 1–5,000 characters; sender length is 1–200; whitespace-only strings are rejected. Errors return `{"error":"..."}`: 400 invalid fields/JSON, 413 oversized body, 415 wrong content type, 403 cross-origin request, 429 demo capacity reached, or 503 inference failure. No failure produces a fake clean verdict or sample result.

The frontend is live-only: HTTP failures, invalid responses, and timeouts show a connection error and **Try again**. The old `demo-fixtures.js` file is retained but is neither loaded nor used. Warning text explicitly distinguishes model and evidence sources; reasons are labelled as separate evidence-rule observations.

This is a single-process local demo bound to loopback, not a production messaging service. Sender/contact/first-message metadata is supplied by the client and cannot be independently verified. Session state is in memory (at most 256 sessions / 512 senders each); restart, cookie clearing or Reset starts new scan history. Raw incoming messages are not retained by the server; it stores a message hash, sender, and scan results in memory. Simulated outgoing replies and user decisions remain in browser localStorage. The first-message-only policy intentionally does not detect scams introduced in later messages.

## Testing and model tooling

The existing evaluation tests need the public dataset. Download it without retraining or overwriting the saved model:

```powershell
.\.venv\Scripts\python.exe scripts\download_test_data.py
.\.venv\Scripts\python.exe -m pytest -q
```

Run **all tests, including real Chromium mobile integration tests**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q --browser-tests
```

Browser tests start their own local server and use the real saved classifier at 390×844 and 320×568. They cover all three conversations, Block, Accept Anyway, reopening warnings, Reset, outgoing replies not being scanned, unavailable API, malformed responses, and recovery. Without `--browser-tests`, browser cases are explicitly skipped. Screenshots are saved under `reports/browser/`. The original Streamlit startup test requires local sockets; restrictive sandboxes can block it.

The original training and evaluation commands remain `python scripts/train_model.py` and `python scripts/evaluate.py`. Training overwrites the original model/report, so it is not part of startup or integration testing. Raw downloaded data remains Git-ignored. Integration does not change the classifier, evidence patterns, or recorded model metrics above.

## Two-minute presentation walkthrough

1. Open Detect First and point out that this is a simulation, not connected to a phone or WhatsApp.
2. Select **Mom**: the saved-contact note explains why scanning was skipped.
3. Select **124-5135-2355**: the first message was scanned once and remains visible without a warning.
4. Select **732-882-1944**: show the “Potential job scam detected” card, the separate model result, and the concrete message evidence. Emphasize that the warning is not a verdict.
5. Demonstrate **Block sender**, then use **Reset demo** to replay; on the reset screen, use **Accept anyway** to show the alternate response.
6. Briefly mention the holdout and synthetic reports, the dataset's job-posting/SMS mismatch, and how the evaluation-only examples remain separate from training.

## Credits

- **Dataset:** EMSCAD-derived `fake_job_postings2`, OpenML data ID 46655; original Kaggle dataset credits the University of the Aegean Laboratory of Information & Communication Systems Security. See [source notes](data/source.md).
- **Synthetic evaluation patterns:** U.S. Federal Trade Commission consumer guidance about job scams; synthetic examples were written for this project and are not copied as real messages.
- **Libraries:** scikit-learn (TF-IDF and logistic regression), Flask (local API/static server), Streamlit (original prototype), joblib (model persistence), pytest and Playwright (tests).
- **Model:** trained by this project; no pretrained model or paid API is used.
- **AI coding assistance:** GitHub Copilot SDK in VS Code.
- **Tutorials:** no tutorial code was copied.

## Original contribution

The project combines a first-contact-only scan state machine, a real but carefully caveated text classifier, independent evidence explanations, and two user actions that change the simulated conversation state. The aim is to teach students to pause and inspect a job offer rather than to label people or employers as proven scammers.
