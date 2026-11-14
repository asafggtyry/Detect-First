# Live integration verification — 2026-11-14

Implemented on `integration/backend-frontend`, based on merge `d9d1200`.
All development and testing used the integration worktree; the original
`Project` working files and unfinished AI improvements were not changed.

## Result

The Flask server serves the existing Fable frontend and `POST /api/scan` at
http://127.0.0.1:8000/. It loads the original saved classifier once and uses the
original evidence rules and warning policy. No model retraining, demo label
lookup, or sample-response fallback is involved.

Start from the repository root:

```powershell
.\.venv\Scripts\python.exe -m detect_first.server
```

## Actual HTTP demo responses

See [integration_demo_responses.json](integration_demo_responses.json) for the
complete requests, HTTP status codes and responses captured from the running
server. These are fictional demo messages already present in the project.

| Sender | Scanned | Model flagged | Evidence warning | UI warning | Source |
|---|---|---|---|---|---|
| Mom | No | null | false | false | Saved contact; skipped |
| 124-5135-2355 | Yes | false | false | false | none |
| 732-882-1944 | Yes | false | true | true | evidence |

Mom's response was checked directly against the API to verify server-side
exclusion. The frontend itself does not send Mom to the API.

The recruitment warning has six evidence-rule categories: unsolicited job
offer, unrealistic earnings, upfront payment request, vague job details,
urgency/pressure, and unverified employer identity. The UI explicitly says the
ML classifier did not flag it. These rules are observations, not proof of fraud
or explanations of the model's internals.

## Tests and visual checks

Final command (after installing requirements-dev.txt and Chromium):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\Scripts\python.exe -m pytest -q --browser-tests --junitxml=reports/integration_tests.xml
```

**43 passed, 0 failed, 0 errors, 0 skipped**, in 22.79 seconds in the recorded
run. [JUnit report](integration_tests.xml): 13 original backend tests, 23 API
cases, and 7 real Chromium browser cases. Hostname metadata was removed from
the saved report; test outcomes were not changed.

- Real model/evidence response parity, saved-contact and later-message exclusion.
- Per-session isolation, identical retry caching, changed-message skipping,
  concurrent duplicate requests, and reset behavior.
- Invalid/missing fields, malformed JSON, wrong content type, request limits,
  cross-origin rejection, unavailable model and inference failure/retry.
- Same-origin static serving without exposing the model or repository files.
- Mobile sizes 390×844 and 320×568: all three chats, navigation, local replies,
  Block, Accept Anyway, reopening warnings, and Reset.
- No horizontal overflow and both warning action buttons within the viewport.
- Unavailable API, malformed responses, HTTP errors, and real client timeouts
  produce connection errors, never sample or clean results; recovery works.
- Reload uses cached scans. A failed reset preserves user decisions.

The first browser runs exposed ambiguous test selectors and measurements taken
during the existing slide animation. Tests were corrected to target the message
bubble and wait for the buttons to enter the viewport. No UI style changes
were needed. Final tests include all previously failing cases.

The live app was also opened in the in-app browser at 390×844 and visually
inspected. Mobile screenshots: [390px](browser/warning-390.png),
[320px](browser/warning-320.png). The compact view keeps the action buttons
visible while the reasons and message thread scroll.

JavaScript syntax checks and `git diff --check` passed. The original `app.py`,
classifier code/artifact, evidence code, state machine, CSS, and historical
demo fixtures are unchanged from `d9d1200`. The fixture file is no longer loaded.

## Remaining limitations

The classifier still learns from job postings and catches only 5/16 scams in
the existing synthetic first-contact benchmark. Integration does not improve
that model. Evidence rules can also produce false alarms. No-warning and
skipped responses do not establish safety.

The local single-process demo trusts client-supplied contact/first-message
metadata, retains scan state only in memory, and has bounded session capacity.
Reset, clearing cookies, or restarting the server starts fresh scan history.
There is no real messaging connection, employer verification, or production
deployment. Later scam messages are deliberately outside the first-message
scan policy.
