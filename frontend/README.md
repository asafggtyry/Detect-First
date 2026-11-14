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

## Incoming messages and evidence highlights

**Receive random message** (the green button on the chat list) asks the backend
simulation for one incoming message and shows it as a new chat, or as a further
message in the chat of a sender who already exists. The arrow beside it opens an
optional presenter menu: Random, family or friend, everyday unknown sender, or
recruiter-style offer. The menu only chooses the kind of sample text requested.
Every verdict still comes from `/api/scan` (or from an analysis the simulation
returns with the message), and nothing is generated when a chat is opened.

Inside a flagged first message, the phrases the analyzer reported are
highlighted. Tapping one opens a small explanation with the matched phrase, the
evidence category and the analyzer's explanation. The frontend holds no keyword
lists: it marks only text the backend points to, and silently skips any span
that does not fit the message. Messages with no warning get no highlights.

All requests and all response parsing are in `api.js`; `app.js` never reads raw
JSON. Received chats, decisions and replies are kept in `localStorage` until
**Reset demo**.

### Backend integration (provisional)

`docs/DYNAMIC_API.md` did not exist when this was built, so the simulation call
is a best guess isolated in `api.js` (`receiveMessage`, `normalizeIncoming`,
`collectSpans`) and `config.js` (`simulateEndpoint`, `scenarios`). On a server
without the endpoint the button shows a clear error and adds nothing.

Request currently sent: `POST /api/simulate` with `{"scenario": "random"}`.
Scenario values are `random`, `saved_contact`, `unknown_harmless`, `recruiter`
and can be remapped in `config.js`.

Response currently understood (other field names need a small change in
`normalizeIncoming`):

```json
{"sender": "555-0142", "is_saved_contact": false, "message": "Hi! We are hiring..."}
```

- `sender` (1-200 characters), `message` (1-5,000) and a real boolean
  `is_saved_contact` are required. Nested `sender: {"name", "is_saved_contact"}`
  and `message: {"text"}` are also read.
- Optional `analysis`: a result in the `/api/scan` shape. If present for an
  unsaved sender the frontend uses it and does not call `/api/scan` for that
  message until the page reloads.
- For unsaved senders without `analysis`, the frontend calls `/api/scan` with
  `is_first_message: true`, so the sender name must be 200 characters or fewer.

Evidence spans are read from a scan/analyze result in any of these forms:

- today's `reasons[].snippet`, located by exact match in the message;
- `reasons[].spans` (or `span`) as `{"start", "end"}`;
- a top-level `spans` list of `{"start", "end", "category", "explanation"}`.

`start`/`end` are treated as Python string indices (code points, end exclusive).
An optional `text` on a span is checked against the message. Spans that are out
of range, empty, non-integer, mismatched or overlapping an earlier span are not
rendered; the warning panel still lists the reason.

Browser checks for all of this are in `tests/test_dynamic_ui.py`. They answer
`/api/simulate` inside the browser with the provisional shape above and use the
real server and saved model for scanning.

Files: `index.html` (page shell), `styles.css` (original design with release scrolling/accessibility fixes), `app.js`
(UI and state), `api.js` (all backend requests and response parsing), `config.js` (same-origin connection settings),
and unused historical `demo-fixtures.js`. Automated browser tests live in
`tests/test_browser.py` and exercise the full app at mobile sizes.

Release polish adds an explicit fictional-prototype label, cautious rule labels,
keyboard scrolling for the evidence list, corrupt-localStorage recovery, and a
non-scrollable outer phone frame so navigation cannot shift the app sideways.
The message thread and evidence list each scroll inside that frame. See the
[release report](../reports/release_verification.md) for final test counts.
