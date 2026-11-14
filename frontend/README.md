# Detect First frontend

Fable's WhatsApp-inspired UI uses plain HTML, CSS and JavaScript, with no build
step. Run it through the Python server from the **repository root**:

```powershell
.\.venv\Scripts\python.exe -m detect_first.server
```

Open http://127.0.0.1:8000/. See the [root README](../README.md) for setup,
the complete API contract, model limitations, and tests. A standalone static
server cannot provide `/api/scan` or `/api/reset`.

The frontend calls `POST /api/scan` with `message`, `sender`,
`is_saved_contact`, and `is_first_message`. Responses include the legacy
`is_scam` warning decision and `reasons`, plus `model_flagged`,
`evidence_flagged`, `warning_source`, `scanned`, `skipped_reason`, and `cached`.
The ML prediction stays separate from evidence rules. Each reason has a
`category`, an `evidence` explanation, and `source: "evidence_rule"`.

- Saved contacts are not sent to the API. The server enforces the exclusion too.
- Only the first incoming message is scanned. Replies stay in the simulation.
- The warning states whether it came from the model, evidence rules, or both.
- `config.js` uses the same-origin live API. All sample fallback code is removed
  from `app.js`; the retained `demo-fixtures.js` file is not loaded.
- Missing server, non-2xx responses, invalid JSON/schema and timeouts show a
  connection error with a retry button, never a substitute prediction.
- Block, Accept Anyway, reopening the warning, chat navigation and local reply
  persistence keep their original behavior.
- Reset first calls `/api/reset`, then clears this browser's simulated decisions
  and replies and requests fresh scans. A failed reset leaves saved decisions
  intact and shows an error.

Files: `index.html` (page shell), `styles.css` (original design with release scrolling/accessibility fixes), `app.js`
(UI/state and live requests), `config.js` (same-origin connection settings),
and unused historical `demo-fixtures.js`. Automated browser tests live in
`tests/test_browser.py` and exercise the full app at mobile sizes.

Release polish adds an explicit fictional-prototype label, cautious rule labels,
keyboard scrolling for the evidence list, corrupt-localStorage recovery, and a
non-scrollable outer phone frame so navigation cannot shift the app sideways.
The message thread and evidence list each scroll inside that frame. See the
[release report](../reports/release_verification.md) for final test counts.
