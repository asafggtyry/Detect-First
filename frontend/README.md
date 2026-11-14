# Detect First frontend

A static, mobile-first messaging UI (plain HTML, CSS and JavaScript, no build step and no dependencies). It contains no detection logic: every verdict and every warning reason comes from the Python classifier through one HTTP endpoint.

## Run it

```
cd frontend
python -m http.server 8000
```

Open http://localhost:8000. On a desktop the app is shown in a 390px phone frame; on a phone it fills the screen.

With no backend running, the UI falls back to hand-written sample responses from `demo-fixtures.js` and says so on screen ("Sample result — the classifier is not connected"). These are placeholders for layout work, not model output.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Page shell: chat list screen, conversation screen, desktop caption |
| `styles.css` | All styling and transitions |
| `app.js` | Demo chats, navigation, Block / Accept Anyway / Reset state, the call to the backend |
| `config.js` | Backend URL and mode. The only file to edit when connecting the backend |
| `demo-fixtures.js` | Sample responses used only when the backend is unreachable |

## Connecting the Python classifier

The backend needs one endpoint. The UI calls it once for the first incoming message of each sender who is not a saved contact. Saved contacts are never sent.

**Request** — `POST /api/scan`, JSON body:

```json
{
  "message": "Hello! We are hiring students for remote work. ...",
  "sender": "732-882-1944",
  "is_saved_contact": false,
  "is_first_message": true
}
```

**Response** — JSON:

```json
{
  "is_scam": true,
  "reasons": [
    { "category": "unrealistic_earnings", "evidence": "earning up to $300 per day" },
    { "category": "urgency_pressure" }
  ]
}
```

- `is_scam` (boolean, required): `true` shows the warning panel, `false` leaves the message unflagged.
- `reasons` (array, may be empty): only the categories the model found. The UI shows exactly what is returned, in order. Each item is either an object with `category` and optional `evidence` (a short quote or note shown under the label), or just the category string.
- Category ids: `unsolicited_job_offer`, `unrealistic_earnings`, `vague_job_details`, `urgency_pressure`, `unverified_employer`. The display labels (for example `"Urgency / pressure"`) are accepted too. An unrecognised value is shown as-is.
- Any non-2xx status, a timeout (`timeoutMs`, default 4s) or invalid JSON counts as a failed scan.

If your classifier already returns a different shape, either adapt it in the endpoint or adjust `normalizeResult()` in `app.js`, which is the single place responses are read.

### Example endpoint (Flask)

`classify_message` below stands for whatever function your project already exposes; this frontend was built without access to the backend code, so the name is a placeholder.

```python
from flask import Flask, jsonify, request, send_from_directory
from your_module import classify_message  # existing classifier

app = Flask(__name__, static_folder="frontend", static_url_path="")

@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.post("/api/scan")
def scan():
    data = request.get_json()
    result = classify_message(data["message"])
    return jsonify({"is_scam": result.is_scam, "reasons": result.reasons})
```

Serving the `frontend/` folder from the same app keeps everything on one origin, so `config.js` needs no changes. If the API runs on a different origin, set `apiBase` in `config.js` (for example `"http://localhost:5000"`) and enable CORS for `POST /api/scan` on the backend.

### Modes (`config.js`)

| `mode` | Behaviour |
| --- | --- |
| `"auto"` (default) | Call the backend; if it cannot be reached, show labelled sample results |
| `"live"` | Call the backend only; a failure shows "Couldn't check this message" with a retry |
| `"demo"` | Never call the backend |

Use `"live"` for any real demo of the model so a backend failure can never be mistaken for a prediction.

## Behaviour

- Saved contacts (Mom) are not scanned.
- For unsaved senders, the first incoming message is scanned when the app loads.
- An unflagged message shows a small "nothing suspicious found" note in the chat.
- A flagged message shows a warning icon in the chat list and the warning panel in the conversation, with **Block** and **Accept Anyway**.
- Block marks the chat as blocked and disables replying. Accept Anyway closes the panel and enables replying; the "Flagged" tag on the message reopens the panel, so the sender can still be blocked later.
- Decisions, read state and sent messages are kept in `localStorage`. **Reset demo** (the ⋮ menu, or the button beside the phone on desktop) clears them and rescans.

Demo conversations are defined in the `CHATS` array at the top of `app.js`.
