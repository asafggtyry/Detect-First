# Prototype privacy and dependency notes

## Data flow

The integrated frontend uses bundled HTML/CSS/JavaScript and inline icons, with no analytics, third-party fonts, remote images or CDN scripts. It submits only the two fictional unknown senders' first messages to the same-origin loopback API. Mom and typed outgoing replies are not submitted for classification. No real messaging account, contacts list, camera or microphone is accessed.

The Flask API processes incoming text locally. It retains a SHA-256 message hash, sender identifier and scan result in memory to enforce first-message behavior and retry caching. Hashes of predictable messages are not anonymization. Raw request text is not intentionally persisted or logged; an inference exception logs a generic error. The default HTTP access log records request paths/status and loopback addresses. The session cookie is HttpOnly and SameSite=Strict. The HTTP development demo has no TLS.

This browser's localStorage holds simulated outgoing replies, read state and Block/Accept choices. They persist across reloads and are not encrypted. Use only fictional text. Successful Reset removes that browser's stored demo state and clears its server scan state; a failed reset deliberately preserves choices and shows an error. Restarting the server clears all in-memory sessions, but does not clear localStorage. Clearing this site's browser data clears localStorage/cookies.

The service binds to `127.0.0.1`, rejects cross-origin API requests, and serves only `frontend/` files. It is a single-process local prototype, not a hardened public service. Session capacity is bounded; after enough abandoned sessions, restart the server. Client-supplied saved-contact/first-message metadata is trusted. No independent employer verification is performed. The separate legacy Streamlit entry point is outside the final demo's data flow.

## Dependencies and reproducibility

The runtime model is a checked-in joblib artifact, pinned to scikit-learn 1.9.1. Joblib/pickle files can execute code when loaded: use the project's reviewed artifact, never a stranger's replacement. The original artifact's SHA-256 is `6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42`.

`requirements.txt` declares runtime dependencies (including the legacy Streamlit app); `requirements-dev.txt` adds pytest and Playwright. `requirements-lock.txt` records the exact resolved Windows/Python 3.12 release-test environment, including transitive dependencies. It is not a cross-platform lock or a hash-locked supply-chain guarantee. Installing dependencies, Chromium and public evaluation datasets needs internet access; running the installed integrated demo does not. No Node build or API key is required.

Dependency consistency is checked with `python -m pip check`. See the release report for any vulnerability-audit result and its scope; compatibility checks alone do not establish freedom from vulnerabilities. Do not expose Flask's development server publicly.

## Repository review

Raw downloaded datasets, virtual environments, Python caches and intermediate research model files are ignored. The two deliverable models and frozen reports are tracked. Reports include public dataset error excerpts and aggregate metrics, not private user chats. Research scripts and historical reports remain for transparency. The four unselected intermediate experimental artifacts are intentionally not shipped; running the app and reproducing release metrics does not depend on them.
