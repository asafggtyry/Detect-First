"""Same-origin local app. Start with python -m detect_first.server."""
from __future__ import annotations

import argparse
import hashlib
import secrets
from pathlib import Path
from threading import Lock
from typing import Callable

from flask import Flask, jsonify, request, session
from werkzeug.exceptions import HTTPException, TooManyRequests

from detect_first.evidence import explain_message
from detect_first.model import MODEL_PATH, load_pipeline, predict_scam
from detect_first.state import Conversation

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {
    "Unsolicited job offer": "unsolicited_job_offer",
    "Upfront payment request": "upfront_payment_request",
    "Unrealistic earnings": "unrealistic_earnings",
    "Vague job details": "vague_job_details",
    "Urgency / pressure": "urgency_pressure",
    "Unverified employer identity": "unverified_employer",
}


def skipped(reason: str) -> dict:
    return dict(is_scam=False, reasons=[], model_flagged=None, evidence_flagged=False,
                warning_source="none", scanned=False, skipped_reason=reason, cached=False)


class ScanService:
    """First-contact decisions per browser session; raw messages are never retained."""

    def __init__(self, classifier: Callable[[str], bool]):
        self.classifier = classifier
        self.sessions: dict[str, dict] = {}
        self.lock = Lock()

    def reset(self, session_id: str) -> None:
        with self.lock:
            self.sessions.pop(session_id, None)

    def scan(self, session_id: str, data: dict) -> dict:
        sender = data["sender"].strip()
        fingerprint = hashlib.sha256(data["message"].strip().encode()).hexdigest()
        # Lookup, inference and save are atomic, including concurrent retries.
        with self.lock:
            if session_id not in self.sessions and len(self.sessions) >= 256:
                raise TooManyRequests("Demo session limit reached. Restart the local server.")
            senders = self.sessions.setdefault(session_id, {})
            previous = senders.get(sender)
            if sender not in senders and len(senders) >= 512:
                raise TooManyRequests("Sender limit reached. Reset this demo session.")
            if data["is_saved_contact"]:
                senders[sender] = {"saved": True}
                return skipped("saved_contact")
            if previous and previous.get("saved"):
                return skipped("saved_contact")
            if not data["is_first_message"]:
                senders.setdefault(sender, {"saved": False})
                return skipped("not_first_message")
            if previous is not None:
                if previous.get("fingerprint") == fingerprint:
                    return dict(previous["result"], cached=True)
                return skipped("already_scanned")

            model_flagged = bool(self.classifier(data["message"]))
            evidence = explain_message(data["message"], first_contact=True, saved_contact=False)
            # Reuse the original application's policy without relabeling rules as ML.
            conversation = Conversation(sender, sender, False, [], scanned=True,
                                        model_flagged=model_flagged, evidence=evidence)
            evidence_flagged = len(evidence) >= 2
            source = ("both" if model_flagged and evidence_flagged else "model" if model_flagged
                      else "evidence" if evidence_flagged else "none")
            result = dict(
                is_scam=conversation.should_warn,
                reasons=[dict(category=CATEGORIES[e.category], evidence=e.explanation,
                              source="evidence_rule") for e in evidence],
                model_flagged=model_flagged, evidence_flagged=evidence_flagged,
                warning_source=source, scanned=True, skipped_reason=None, cached=False,
            )
            # Inference failures never consume the sender's first scan.
            senders[sender] = dict(fingerprint=fingerprint, result=result, saved=False)
            return result


def validate_scan(data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")
    for name, limit in [("message", 5000), ("sender", 200)]:
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError(f"{name} must be a non-empty string.")
        if len(data[name]) > limit:
            raise ValueError(f"{name} must be at most {limit} characters.")
    for name in ["is_saved_contact", "is_first_message"]:
        if type(data.get(name)) is not bool:
            raise ValueError(f"{name} must be a JSON boolean.")
    return data


def create_app(*, model_path: Path = ROOT / MODEL_PATH,
               classifier: Callable[[str], bool] | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(ROOT / "frontend"), static_url_path="")
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=32_768,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"])
    if classifier is None:
        pipeline = load_pipeline(model_path)
        classifier = lambda text: predict_scam(text, pipeline)
    service = ScanService(classifier)
    app.extensions["scan_service"] = service

    def session_id() -> str:
        if "scan_session" not in session:
            session["scan_session"] = secrets.token_hex(24)
        return session["scan_session"]

    @app.before_request
    def same_origin():
        if request.method == "GET" and request.path in {"/", "/index.html"}:
            session_id()
        if request.path.startswith("/api/") and request.method == "POST":
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                return jsonify(error="Cross-origin requests are not supported."), 403

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get("/")
    def index():
        # Establish the cookie before JavaScript starts concurrent requests.
        session_id()
        return app.send_static_file("index.html")

    @app.post("/api/scan")
    def scan():
        try:
            data = validate_scan(request.get_json())
        except ValueError as error:
            return jsonify(error=str(error)), 400
        try:
            return jsonify(service.scan(session_id(), data))
        except HTTPException:
            raise
        except Exception:
            app.logger.error("Classifier scan failed; request may be retried.")
            return jsonify(error="Classifier unavailable. Please retry or restart the local server."), 503

    @app.post("/api/reset")
    def reset():
        service.reset(session_id())
        session["scan_session"] = secrets.token_hex(24)
        return jsonify(reset=True)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    create_app().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
