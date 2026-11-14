# Backend QA verification

Date: 2026-11-14
Branch: `integration/minimal-warning-ui`
Base commit: `91f76c1`
Fable commit: `70032e3`

## Automated results

- Focused backend/API/evidence/simulation tests: **47 passed**.
- Complete suite with browser tests: **100 passed, 0 failed**.
- Browser coverage ran against the real saved model and Chromium, including mobile viewports, dynamic receive/history, evidence highlights, Accept, Block, Reset, Test Message, API failures, and retry behavior.
- The compact warning regression passed at both 390x844 and 320x568.

## Verified behavior

- Port 8000 served the integrated frontend from this checkout; the root response contained the dynamic receive control.
- `POST /api/demo/receive` returned a conversation and analysis.
- `GET /api/demo/history` returned the generated conversation and session state.
- Conversation decisions returned `blocked` and `accepted` for Block and Accept.
- `POST /api/demo/reset` cleared generated demo state.
- `POST /api/analyze` returned separate model and evidence results.
- Evidence spans used zero-based Python offsets, exclusive ends, and exact excerpts from the submitted text, including punctuation and Unicode coverage.
- Frontend explanations distinguish trained-model output from evidence-rule observations and do not present rule text as model attribution.
- `See all findings` opens a compact backend-driven popup for findings without valid matching spans; those findings are not displayed permanently in the warning card.
- Tests retain coverage for no valid highlighted evidence, evidence-only warnings, model-only warnings, missed synthetic recruiter fixtures, and combined warnings.

## Live-server screenshots

Chromium verified the actual Python server started from this branch on port 8000:

- [Compact warning](browser/integration-warning-390.png)
- [Highlighted phrase explanation](browser/integration-highlight-390.png)
- [See all findings](browser/integration-all-findings-390.png)

## Defects and handoff

No backend or integration defects were found. The trained model was not modified or retrained, and demo fixtures were not used for training.

Fable's redesigned warning card must preserve the existing response fields and provenance distinction: `model_flagged`, `evidence_flagged`, `warning_source`, and exact `evidence_spans`. Context-only reasons may have no span and must remain unhighlighted.

The worktree already contained an uncommitted change in `tests/test_browser.py`; it was preserved. The QA report was carried onto this integration branch. No default-branch or release-branch change was performed.
