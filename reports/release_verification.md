# Final release verification — 2026-11-14

## Release scope and preservation

Release branch: `release/veritas-2026`, created in a separate `Detect-First-release` worktree from `ai-model-integration` at `3b0cc14`. Remote refs were fetched before release. No newer integration commits were present.

Git ancestry verifies the release includes the original backend (`132235d`, including training commit `99ee49e`), Fable frontend (`1a019a4`), merge (`d9d1200`), live integration (`53abb8c`) and model audit (`3b0cc14`). No merge was needed. The default remote branch was `frontend-fable`; it was not changed.

The `Project` / `ai-improvements` worktree has 11 uncommitted entries (two modified files and nine untracked research files). It was not edited, staged, stashed, reset or cleaned. The clean `Detect-First-integration` worktree and all pre-existing branches were retained. The separate `Detect-First` folder contains another Git metadata directory; it was inspected without modification. The release commit is the commit containing this report; use `git rev-parse HEAD` in the release checkout to obtain its exact ID.

## Fresh installation

Two empty virtual environments were installed during release. The final environment used `requirements-dev.txt` constrained by `requirements-lock.txt`, with Python 3.12.14 on Windows. All 49 locked packages installed, and `pip check` reported no broken requirements. Wheels may come from pip's download cache, but no existing site-packages were inherited.

The bundled agent Python omits `ensurepip`, so standard `python -m venv` could not bootstrap pip here. Verification used `python -m venv --without-pip`, then an existing pip's `--python <new-environment>` option to install pip into that empty environment. The README explains this limitation and recommends full Python 3.12 with pip. This is not a claim that the literal venv bootstrap command passed in the stripped runtime.

The public OpenML dataset was downloaded afresh using `scripts/download_test_data.py`, verified against MD5 `80f28af7c3569233f4b8b9012c2c245b`, and loaded as 12,525 deduplicated postings. Chromium 159.0.8154.6 / Playwright 1.65.2 was downloaded into an ignored environment-local browser directory. Running the app itself needs neither raw data nor Chromium/pytest.

## Final complete automated run

Command in the fresh environment (equivalent to the README's `.venv` command):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\fresh\Scripts\python.exe -m pytest -q --browser-tests --junitxml=reports/release_tests.xml
.\.venv\fresh\Scripts\python.exe scripts\verify_release_metrics.py
```

**63 passed, 0 failed, 0 errors, 0 skipped; 41.33 seconds reported by pytest.** Test runner: pytest 9.2.0. Complete per-test outcomes/timings: [JUnit XML](release_tests.xml). Hostname metadata was removed without changing outcomes.

| Module | Passed |
|---|---:|
| `tests.test_api` | 23 |
| `tests.test_browser` | 10 |
| `tests.test_evidence` | 3 |
| `tests.test_message_improvements` | 17 |
| `tests.test_model` | 5 |
| `tests.test_state` | 5 |

Coverage includes real default/candidate model outputs; training/evaluation safeguards; evidence provenance; saved-contact and later-message exclusion; per-browser isolation, retries/caching, concurrency and reset; malformed inputs, size limits, CORS and classifier failures; all three browser conversations; outgoing replies; Accept Anyway, reopening warnings, Block and successful/failed Reset; unavailable/malformed/503/timeout API responses and recovery; reload behavior; corrupted browser storage; mobile thread/evidence scrolling and action visibility.

The first expanded run reported 61 passes and 2 failures in new reset-error viewport assertions. Those failures exposed real sideways scrolling of the outer phone frame. A focused diagnostic run reproduced it. Changing that outer frame from scrollable `overflow:hidden` to `overflow:clip` fixed it; a subsequent full run passed 63 tests. The final run above repeats all tests after the pytest dependency update in the second empty environment. No failing case was removed or skipped.

## CLI startup and live responses

Verified actual startup command: `python -m detect_first.server --port 8765` from the repository root. The default parser port is 8000, used in the README; the alternate port avoids disturbing other local servers. Both static frontend and live API are served by this one command. Debug/reloader are disabled and the listener binds to loopback.

`scripts/verify_live_demo.py --url http://127.0.0.1:8765` launched Chromium against that separately started CLI server. Its [captured HTTP responses](release_demo_responses.json) show:

| Conversation | Scanned | ML flagged | Evidence warning | Combined warning |
|---|---|---|---|---|
| Mom (direct API exclusion check) | No | null | No | No |
| Harmless unknown | Yes | No | No | No |
| Recruitment example | Yes | No | Yes | Yes |

The frontend itself made exactly two scan requests, all page network requests stayed on the local origin, no `demo-fixtures.js` was loaded, and there were no JavaScript errors. Model, raw-data and Git paths returned 404. The recruitment response has six rule categories; its warning is explicitly evidence-based. No employer verification, sample fallback or fabricated model result is involved.

One initial CLI/browser check could not connect because the server ran inside the restricted sandbox and the browser outside it. Repeating with both on the same local network boundary passed; this environment setup failure is not hidden as an application pass.

## Mobile visual review and polish

Both 390×844 and 320×568 Chromium mobile viewports were visually inspected. No horizontal shift/overflow remains; Block and Accept Anyway are fully in view. The compact screen intentionally scrolls its long message and evidence list independently. Keyboard End reaches the final employer-limit explanation; every reason remains accessible. This is browser emulation, not physical-device or Safari certification.

- [390 warning](browser/warning-390.png), [320 warning](browser/warning-320.png)
- [390 home](browser/home-390.png), [320 home](browser/home-320.png)
- [390 reset error](browser/reset-error-390.png), [320 reset error](browser/reset-error-320.png)

Release polish preserves the visual design: a fictional-prototype label, cautious evidence category wording, a more precise limited-word-list explanation, a keyboard-scrollable reason list, input focus styling, non-shrinking message bubbles, contained toast text, and corrupt-localStorage recovery. Model-load/data errors now suggest restoring the release artifacts/dependencies or downloading test data, rather than unnecessary retraining.

## Metrics and model preservation

`verify_release_metrics.py` reproduced every original posting/model/baseline metric and the entire synthetic report exactly. No training, model replacement, threshold change, or dataset relabeling occurred. The original model SHA-256 remains `6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42`. The candidate is retained for research only.

See [release metrics](release_metrics.json) and [evaluation tables](../docs/EVALUATION.md). The 2,505-posting scores remain contaminated historical comparisons (548 near-template matches in the prior audit). The 32-message synthetic benchmark is not real-world validation. Authentic first-contact recruitment validation remains unavailable. The warning policy has not been validated on authentic recruitment messages either.

## Dependencies, privacy and repository checks

The initial dependency audit flagged one unique pytest advisory (the database returned it twice), `PYSEC-2026-1845` / `CVE-2025-71176`, concerning UNIX temporary-directory handling. pytest was moved to development requirements and upgraded from 8.4.2 to 9.2.0. The final lock was audited using pip-audit 2.10.1 in a separate audit environment with `--disable-pip --no-deps -r requirements-lock.txt` (the lock enumerates all 49 installed packages).

**Final audit: zero reported known vulnerabilities, zero skipped packages.** [Machine-readable audit](dependency_audit.json). This is a point-in-time database check, not a guarantee against unknown vulnerabilities. No runtime model dependencies were experimentally upgraded; the saved scikit-learn version remains pinned.

Static review found no embedded API credentials or user-message analytics; the server generates its session secret at startup. The live browser check found no external requests. Only fictional demo text is used. Private repository/model/data files are not exposed by static routes. Retention, localStorage behavior, trusted client metadata and limits are documented in [privacy notes](../docs/PRIVACY.md).

JavaScript syntax (`node --check frontend/app.js` and `frontend/config.js`) and Git whitespace checks passed. Raw data, virtual environments, caches and intermediate experimental models remain ignored. The release includes both deliverable model files, complete frontend/backend, tests, source/download scripts, the synthetic examples, dependency lock, reproducible metrics and submission documents. Four unselected intermediate research artifacts are intentionally absent; they are not needed to run the app or reproduce release metrics.

All local Markdown links resolve. A `git checkout-index` export of only staged files was loaded using the fresh interpreter: the app served its frontend and returned the real recruitment evidence warning with `model_flagged:false`, despite no raw dataset or other-worktree files being present. Both model files and frozen metric/selection reports match `3b0cc14`. A final comparison of all 32 tracked/nonignored Project files and its Git status matched the pre-publication preservation snapshot; the integration worktree remained clean.

## Remaining submission actions

No official organizer rules or submission portal were present in the inspected repository. Confirm deadline/timezone, eligibility, track, allowed prior work/AI tools, judge access, required assets/video length, hosting and licence requirements. Confirm team names/roles and credits, rehearse and record as required, then submit the **explicit release branch/commit**. The default frontend branch is unchanged. Full actions: [submission checklist](../docs/SUBMISSION_CHECKLIST.md).
