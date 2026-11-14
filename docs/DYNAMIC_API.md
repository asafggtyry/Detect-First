# Dynamic scanning API

This contract describes the integrated randomized incoming-message demo. The
frontend uses the same-origin session cookie and makes all API requests through
`frontend/api.js`.

## Receive a simulated message

`POST /api/demo/receive` accepts an optional scenario selector and seed:

```json
{"scenario_label": "potential_fraudulent_recruiter"}
```

`scenario_label` is optional and may be `random`, `family_friend`,
`normal_stranger`, or `potential_fraudulent_recruiter`. Omit it (or use
`random`) for equal-probability random selection across the three scenario
types. Equal selection is for demonstration only, not a claim about real-world
scam frequency. Within a type, fixtures are not repeated until its fixtures
have been used.

The optional `seed` may be an integer or a non-empty string (up to 128
characters). It initializes a session's random sequence on the first receive.
Subsequent receives should omit the seed. A different seed after the first
generated message returns `409`; reset the demo with a seed to start a new
reproducible scenario/message sequence. Scenario and fixture order reproduce,
but UUIDs for new unsaved senders are intentionally unique across sessions.

Example response:

```json
{
  "conversation": {
    "id": "8bdcd01f-4bb5-5a76-b70d-79b482fb2f35",
    "sender_name": "Unknown - (213) 555-0181",
    "sender": "+12135550181",
    "saved_contact": false,
    "scenario_label": "potential_fraudulent_recruiter",
    "synthetic": true,
    "messages": [
      {
        "direction": "incoming",
        "text": "🙂 We are hiring for a flexible assistant role. Pay a $35 onboarding fee today to reserve your interview.",
        "time": "10:14 AM",
        "synthetic": true
      }
    ],
    "analysis": {
      "is_scam": true,
      "reasons": [
        {
          "category": "unsolicited_job_offer",
          "evidence": "This is a work offer in the first message from an unsaved sender.",
          "snippet": "hiring",
          "source": "evidence_rule"
        },
        {
          "category": "upfront_payment_request",
          "evidence": "The message asks for a payment to obtain or begin the job.",
          "snippet": "Pay a $35 onboarding fee",
          "source": "evidence_rule"
        },
        {
          "category": "urgency_pressure",
          "evidence": "The message asks for a quick response or sets a short deadline.",
          "snippet": "today",
          "source": "evidence_rule"
        },
        {
          "category": "unverified_employer",
          "evidence": "No employer name appears in the message or sender metadata; this demo cannot independently verify the sender.",
          "snippet": null,
          "source": "evidence_rule"
        }
      ],
      "evidence_spans": [
        {
          "category": "unsolicited_job_offer",
          "excerpt": "hiring",
          "start": 9,
          "end": 15,
          "explanation": "This is a work offer in the first message from an unsaved sender.",
          "source": "evidence_rule"
        },
        {
          "category": "upfront_payment_request",
          "excerpt": "Pay a $35 onboarding fee",
          "start": 47,
          "end": 71,
          "explanation": "The message asks for a payment to obtain or begin the job.",
          "source": "evidence_rule"
        },
        {
          "category": "urgency_pressure",
          "excerpt": "today",
          "start": 72,
          "end": 77,
          "explanation": "The message asks for a quick response or sets a short deadline.",
          "source": "evidence_rule"
        }
      ],
      "model_flagged": true,
      "evidence_flagged": true,
      "warning_source": "both",
      "scanned": true,
      "skipped_reason": null,
      "cached": false
    },
    "decision": null
  },
  "simulation_fixture_check": {
    "fraudulent_fixtures_generated": 1,
    "fraudulent_fixtures_flagged": 1,
    "fraudulent_fixtures_missed": 0,
    "fraudulent_fixtures_model_flagged": 1,
    "normal_stranger_fixtures_generated": 0,
    "normal_stranger_fixtures_flagged": 0,
    "normal_stranger_fixtures_model_flagged": 0,
    "scope": "Synthetic demo fixtures only; not real-world accuracy."
  }
}
```

The values above illustrate one selected fixture with the saved model. The
result fields below are model-version dependent. Scenario labels are
ground-truth metadata for demo reporting only. The prediction path receives
only the message, sender ID, saved-contact status, and first-message flag; it
never receives the scenario label. A missed fraudulent fixture remains
unflagged if neither the classifier nor evidence rules trigger a warning.

`simulation_fixture_check` reports generated fraudulent fixtures,
combined-warning flags/misses, and raw model flags. Warnings on normal-stranger
fixtures are exposed as synthetic negative examples (possible demo false
positives). Saved family/friend contacts are deliberately not scanned and are
not prediction negatives. These are scenario checks, not accuracy estimates.
The current model has not been changed or retrained for this feature.

## History, decisions, and reset

- `GET /api/demo/history` returns
  `{"conversations":[...],"decisions":{},"simulation_fixture_check":{...}}`
  for the browser's current session. Each conversation includes the server
  analysis and decision; `decisions` also includes decisions for the three
  starter chats (`mom`, `u1`, and `u2`). It reads state only: opening/reopening
  a chat does not generate a message or invoke classification.
- `GET /api/demo/check` runs all synthetic fixtures through the live analyzer
  without storing messages or changing scan history. It reports, per scenario,
  fixture count, scanned count, model flags, and combined UI warning flags; it
  also reports missed recruiter fixtures and normal-stranger warning counts.
  At implementation time, the saved model flagged 3/10 recruiter fixtures,
  the combined warning flagged 6/10 (4 missed), and neither the model nor the
  combined warning flagged any of the 10 normal-stranger fixtures. The response
  also reports model misses and synthetic model false positives. These are
  synthetic scenario results only, not real-world accuracy.
- `POST /api/demo/conversations/{id}/decision` accepts
  `{"decision":"block"}` or `{"decision":"accept"}` and returns the updated
  conversation. The response decision is `blocked` or `accepted`. Decisions
  for the starter chat IDs are also server-side and included in history.
  Unknown IDs return 404; invalid actions return 400.
- `POST /api/demo/reset` accepts the same optional seed shape as receive,
  removes generated history and scan decisions, and returns
  `{"reset":true,"seed":123}`. The existing `POST /api/reset` remains
  backward-compatible, clears simulation state too, and still returns
  `{"reset":true}`.

Simulation history is in memory and scoped to the browser's HttpOnly session
cookie. Reset or restarting the local process clears it. The integrated
frontend hydrates generated conversations, scan results, and decisions from
the server; it does not use localStorage as authority for those values.
localStorage retains only presentation state and simulated outgoing replies.
Generated scenarios and message text are synthetic, fictional fixtures stored
only for this demo session. They are separate from training, validation, and
the frozen final evaluation set; no fixtures are used to fit or tune a model.

## Evidence spans

`/api/scan`, `/api/analyze`, and each conversation's `analysis` retain the
existing `reasons` array and add `evidence_spans`. Each span is a rule-derived
match in the exact submitted text:

```json
{
  "message": "Deposit $60 within 24 hours",
  "category": "urgency_pressure",
  "excerpt": "within 24 hours",
  "start": 12,
  "end": 27,
  "explanation": "The message asks for a quick response or sets a short deadline.",
  "source": "evidence_rule"
}
```

Offsets are zero-based Python Unicode code-point offsets into the original
message, with an exclusive `end`; the server guarantees
`message[start:end] == excerpt`. JavaScript clients should convert code-point
offsets to UTF-16 indices before using string slicing. Backend spans are
ordered deterministically by `(start, end, category)`. Since message marks
cannot nest, the frontend presents non-overlapping spans deterministically
(leftmost first, longest first at the same start); it never moves a span to a
different phrase.

`reasons` remains backward-compatible, including context-only observations
such as vague job details. Context based on an absence (for example, no
recognized role terms) has no exact phrase to highlight and therefore does not
create a span. The `snippet` field remains as a legacy alias when the rule has
a matched excerpt, otherwise it is `null`. Neither `reasons` nor
`evidence_spans` explains the learned model. The Boolean `model_flagged` and
the evidence-rule results remain separate.

## Errors and existing test lab

`/api/demo/receive` returns 400 for invalid JSON or seed values, 403 for
cross-origin requests, 409 for changing a seed mid-sequence, 429 when the
existing demo scan capacity is reached, and 503 for inference failure. Errors
are JSON objects; failed scans do not create a conversation or return a
success-shaped prediction. The existing `/api/analyze` remains stateless and
continues to serve Test Message, independent of simulation history.

## Fixture provenance

All 30 randomized messages are neutral, fictional, hand-authored synthetic
examples in [`detect_first/simulation_fixtures.py`](../detect_first/simulation_fixtures.py).
There are at least ten each for family/friend, normal stranger, and potential
fraudulent recruiter scenarios. No authentic message dataset is used by this
simulation. The separately maintained training and evaluation datasets and
their provenance are documented in [`data/source.md`](../data/source.md) and
[`docs/EVALUATION.md`](./EVALUATION.md).
