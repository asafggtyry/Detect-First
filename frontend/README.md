# Detect First frontend

Fable's WhatsApp-inspired interface is plain HTML, CSS, and JavaScript with no
build step. Run it from the repository root with the Python server:

```powershell
.\.venv\Scripts\python.exe -m detect_first.server
```

Open http://127.0.0.1:8000/. The frontend and API share an origin and session
cookie. Do not open `index.html` directly or use a separate static server.

## Dynamic conversations

**Receive random message** calls `POST /api/demo/receive`; the adjacent menu
selects `random`, `family_friend`, `normal_stranger`, or
`potential_fraudulent_recruiter`. Non-random choices are sent as
`{"scenario_label":"<backend-id>"}`. Random selection omits the label. The
backend chooses synthetic fixture text and supplies the actual classifier and
evidence-rule result in the response. The scenario label never determines the
verdict. Saved contacts are skipped; an unsaved sender's first message is
analyzed once. Reopening a chat only reads its current state.

`GET /api/demo/history` hydrates generated chats, server scan results, and
decisions, including after reload. The frontend does not use `localStorage` as
authority for conversations, scans, or Block/Accept decisions. It stores only
local presentation state and simulated outgoing replies. Block, Accept Anyway,
and Reset use the corresponding `/api/demo/conversations/{id}/decision` and
`/api/demo/reset` endpoints. The Test Message lab remains a separate,
stateless `POST /api/analyze` request.

All API requests and response normalization live in `api.js`. It reads only
the backend's structured `evidence_spans`; it does not guess keywords or turn
model predictions into highlights. Each span must have a valid exact `excerpt`,
Python code-point `start`/exclusive `end`, explanation, and
`source: "evidence_rule"`. The adapter converts offsets to JavaScript UTF-16
indices and rejects mismatched ranges. When real spans overlap, the UI keeps
leftmost spans and chooses the longest at a shared start; it never relocates a
match. Model output and rule-derived findings remain distinct.

The warning panel is deliberately minimal: "Potential job scam detected", the
line "Tap highlighted text in the message to learn why.", and the Block and
Accept Anyway buttons. Tapping a highlight (or pressing Enter/Space on it) opens
a popup with the exact phrase, the evidence category and the backend's
explanation, labelled as a rule-based observation rather than an ML
explanation; Escape, the close button or a tap elsewhere dismisses it. When a
message is flagged but has no valid spans, the guidance line becomes a
"Review why this was flagged" button that lists only what the backend returned
(rule findings, and whether the model flagged it). The panel keeps
`data-model`, `data-warning-source` and `data-evidence-count` attributes; the
Test Message screen still shows the model result and rule findings side by side.

All 30 messages are fictional synthetic fixtures, not training or evaluation
data. The backend fixture check is limited to these examples, not real-world
accuracy. At integration time the saved model flagged 3/10 recruiter fixtures;
the combined warning flagged 6/10 and missed 4/10. The normal-stranger
fixtures had zero warnings. Misses remain unflagged in the UI.

## Tests

Install the project's test dependencies if needed, then from the repository
root run the full backend and Chromium suite:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.venv\pw-browsers"
.\.venv\Scripts\python.exe -m pytest -q --browser-tests
```

The browser integration tests start the real Python API and do not intercept
`/api/demo/receive` or `/api/scan`. See [the dynamic API contract](../docs/DYNAMIC_API.md)
and [root README](../README.md) for all endpoints, setup, data provenance, and
model limitations.

## Navigation

A bottom tab bar gives three destinations, each a hash route so the browser's
back and forward buttons work: **Chats** (`#/`, the default and the fallback for
any unknown route), **Test a Message** (`#/test`) and **AI Evaluation**
(`#/evaluation`). Exactly one screen is active (`#phone[data-screen]`); the
others are hidden and `inert`. A conversation (`#/chat/{id}`) slides over the
tab bar and has its own back arrow.

The receive bar is docked at the bottom of Chats only: **Receive Random
Message** plus a category picker (Random by default). A successful response
opens the returned conversation; a failure shows a banner on Chats and adds
nothing. AI Evaluation starts from **Start Blind Test**, advances with **Next
Message**, and validates every evaluation response before showing it.
