# Live API contract


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
