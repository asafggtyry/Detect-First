# Final Detect First release verification

Verified on 2026-11-14 (America/New_York), Windows x64, Python 3.12.14.
Release branch: `release/final-detect-first`. Use `git rev-parse HEAD` for the
checkout's exact commit. This report supersedes earlier release verification
reports for the final navigation integration.

## Integration and preservation

- Started an isolated worktree from the latest remote Fable navigation branch,
  `91199a164a4c176302a2ef066d7b9e9907a62955`, which already contains the blind
  evaluation base `d4b1ad2` and minimal-warning integration `214237e`.
- Cherry-picked only `9d44f3969cc24aebbe6ce8722ae6007701e96da1`: the detection
  research document and two backend leakage tests. The tests still assert exact
  overlap and invalid labels are rejected; they now trigger validation at Start,
  matching lazy initialization, and assert the original validation cause.
- Kept Fable's frontend implementation, model artifacts, evidence rules and warning
  policy unchanged. No production fitting, replacement or threshold adjustment.
- Preserved other worktrees and the existing dirty `Project` worktree. Both local
  and remote `release/veritas-2026` remain at
  `f4657abd3d99f67104c229c0b0e93aabe5f55a9a`.
- The remote default was observed as `experiment/live-detection-lab`; this work
  does not alter it. Only the new release branch is a delivery target.

## Defects corrected

1. **Fresh-clone startup failed:** `create_app()` constructed
   `BlindEvaluationService`, whose constructor read the Git-ignored original
   training dataset for a benchmark overlap audit. The model loader itself did
   not need that dataset. Evaluation now loads and validates its data on the
   first Start/Next request, with a lock and successful-load cache.
2. **Missing benchmark recovery was not actionable:** Start/Next now return
   HTTP 503 with `code: benchmark_unavailable` and setup/restore instructions.
   Adding valid data permits retry without restarting. No data is downloaded by
   app startup or inference. Raw-data checksum and leakage validation remain.
3. **Failed predictions skipped evaluation samples:** cursor advancement now
   happens only after predictions succeed. Retries use the same text and leave
   existing scoring arrays/totals intact on failure.
4. **Malformed benchmark rows could crash validation or be scored incorrectly:**
   non-object rows, invalid identifiers, Boolean labels, invalid difficulty and
   empty datasets fail validation before any predictions or scores are stored.
5. **Setup and demo documentation described older branches/navigation:** README,
   API/evaluation docs, submission write-up/checklist and demo script now describe
   the final branch, three tabs, automatic opening and optional benchmark setup.
   Runtime requirements explicitly declare imported numerical, joblib, Werkzeug
   and threadpoolctl dependencies instead of relying solely on transitives.

## Final full-suite result

**158 passed, 0 failed, 0 errors, 0 skipped in 287.82 seconds.**
This includes **94 backend/regression tests and 64 real Chromium tests**.
No existing test was deleted or weakened to obtain this result.

| Module | Passed |
|---|---:|
| API | 33 |
| Blind evaluation | 7 |
| Browser | 16 |
| Research leakage | 2 |
| Dynamic UI | 15 |
| Evidence | 5 |
| Model improvements/frozen artifacts | 17 |
| Model and legacy Streamlit | 5 |
| Navigation | 27 |
| Release UI: missing data/loading/retry | 6 |
| Simulation | 9 |
| Startup/data validation/CLI | 11 |
| State | 5 |

Machine-readable results: [JUnit](final_release_tests.xml).
Console summary: [test log](final_release_tests.log).
The initial full run also passed all 157 cases; the final run adds the CLI
port-conflict test, native desktop context and complete 32-step browser evaluation.

Final execution used a newly installed `.venv`, the locked runtime/development
requirements, and the existing Playwright Chromium installation from the adjacent
release worktree. The bundled Python lacks `ensurepip`; pip was bootstrapped into
the isolated environment using the existing environment's `pip --python` option.
The README recommends a full Python distribution for ordinary fresh setup.
`python -m pip check` reports no broken requirements. Tested versions include
scikit-learn 1.9.1, Flask 3.1.3, joblib 1.6.0, pytest 9.2.0 and Playwright 1.65.2.
`node --check` passes for app.js, api.js and config.js.

Reproduction (after README setup and optional benchmark download):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q --browser-tests --basetemp=.venv\pytest-run --junitxml=reports/final_release_tests.xml
.\.venv\Scripts\python.exe scripts\verify_release_metrics.py
.\.venv\Scripts\python.exe -m scripts.run_blind_evaluation --output reports/final_blind_evaluation.json
```

## Fresh-install and server checks

The clean-install regression copies only application code, frontend and saved
models into an isolated directory and launches a separate Python interpreter and
real HTTP listener. There is no `data/` directory. Home, JavaScript, CSS, ordinary
analysis, arbitrary unscored analysis and random incoming messages work. Start
and Next return the documented benchmark error. Download/training functions are
guarded against execution, no dataset directory is created, and the model hash
is unchanged. Another regression adds the raw dataset after the initial failure
and successfully retries evaluation in the same service.

The actual `python -m detect_first.server --port ...` command exits on an occupied
port without killing the other listener and starts successfully after that port
is freed. Tests use dynamic ports to avoid unrelated services. The README gives
`--port 8001` as an alternative to the default 8000. Frontend assets resolve from
the same Python server; no separate build or static server is required.

## Browser coverage and visual review

The real saved-model Python HTTP server was exercised at **1280×900** (desktop,
no mobile/touch emulation), **390×844**, and **320×568** (mobile/touch emulation).
Checks cover default Chats, tab isolation, random receive/automatic open/newest
first, legitimate and suspicious unknown senders, saved-contact skipping, exact
backend evidence highlights, clickable explanations, See all findings, Block,
Accept Anyway, replies, Reset demo, Test a Message, browser back/forward, loading,
API errors and retry recovery. Each viewport completes all 32 AI Evaluation
messages, verifies Correct/Incorrect against actual returned labels, checks
running totals, completion and restart.

Visually reviewed desktop Chats and Test a Message, mobile warning and findings,
the missing-benchmark error, and the completed 32-message evaluation/table.
No horizontal overflow or inactive-screen controls covering the active screen
was observed. Screenshots capture settled animation states; they are real browser
captures, not mockups. Only error-state tests intercept requests, as documented
in the test sources and [screenshot index](browser/README.md).

Representative captures:

- [Desktop Chats](browser/nav-chats-1280.png)
- [390px Chats](browser/nav-chats-390.png)
- [320px compact warning](browser/warning-320.png)
- [320px all findings](browser/all-findings-320.png)
- [390px completed evaluation](browser/nav-evaluation-390.png)
- [320px final totals](browser/nav-evaluation-totals-320.png)
- [320px missing benchmark](browser/benchmark-unavailable-320.png)

## Honest evaluation

The classifier receives only text; sender/scenario IDs and ground-truth labels
are not prediction features. Rule observations remain separate. Labels are added
after prediction, arbitrary input is unscored, and API metrics are recomputed
from the actual stored prediction arrays in regression tests.

The metric verifier reproduced 2,505 historical posting results and the 32
synthetic results. The new [blind report](final_blind_evaluation.json) preserves:

| System | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| ML | 5 | 16 | 0 | 11 |
| Evidence rules | 9 | 8 | 8 | 7 |
| Combined | 11 | 8 | 8 | 5 |

These are repeatedly inspected, repository-authored synthetic examples. They
do not establish real-world scam-detection accuracy. The historical posting
holdout also has known near-template contamination. No model/policy change was
made to improve exposed test scores.

Production model SHA-256:
`6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42`.

## Release boundaries and remaining submission work

Reviewed tracked paths and common credential patterns: no local environment,
raw training dataset, private key or apparent access token is included in the
release changes. Model binaries and intentional browser evidence are retained.

No software defect from the requested QA remains open. Submission still needs
team confirmation of official rules/deadline, names/roles and disclosures,
judge access, licensing choices, and any required video/hosting. Physical mobile
devices and Safari were not certified. The local educational prototype and its
unchanged detection limitations are documented. Repository visibility, default
branch and hackathon submission are separate user decisions.
