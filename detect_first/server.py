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
from detect_first.simulation import SeedConflict, SimulationService
from detect_first.simulation_fixtures import SCENARIO_LABELS, SIMULATION_FIXTURES
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
                evidence_spans=[], warning_source="none", scanned=False,
                skipped_reason=reason, cached=False)


class ScanService:
    """First-contact decisions per browser session; raw messages are never retained."""

    def __init__(self, classifier: Callable[[str], bool]):
        self.classifier = classifier
        self.sessions: dict[str, dict] = {}
        self.lock = Lock()

    def reset(self, session_id: str) -> None:
        with self.lock:
            self.sessions.pop(session_id, None)

    def analyze(self, message: str) -> dict:
        """Analyze a one-off message without reading or changing demo session state."""
        with self.lock:
            return self._analyze(message)

    def _analyze(self, message: str) -> dict:
        model_flagged = bool(self.classifier(message))
        evidence = explain_message(message, first_contact=True, saved_contact=False)
        conversation = Conversation("test-message", "Test Message", False, [], scanned=True,
                                    model_flagged=model_flagged, evidence=evidence)
        evidence_spans = sorted(
            (item for item in evidence if item.start is not None and item.end is not None),
            key=lambda item: (item.start, item.end, item.category),
        )
        evidence_flagged = len(evidence) >= 2
        source = ("both" if model_flagged and evidence_flagged else "model" if model_flagged
                  else "evidence" if evidence_flagged else "none")
        return dict(
            is_scam=conversation.should_warn,
            reasons=[dict(category=CATEGORIES[item.category],
                          evidence=item.explanation, snippet=item.snippet,
                          source="evidence_rule") for item in evidence],
            evidence_spans=[
                dict(category=CATEGORIES[item.category], excerpt=item.snippet,
                     start=item.start, end=item.end, explanation=item.explanation,
                     source="evidence_rule")
                for item in evidence_spans
            ],
            model_flagged=model_flagged, evidence_flagged=evidence_flagged,
            warning_source=source, scanned=True, skipped_reason=None, cached=False,
        )

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

            result = self._analyze(data["message"])
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


def validate_analysis(data: object) -> str:
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string.")
    if len(message) > 5000:
        raise ValueError("message must be at most 5000 characters.")
    return message


def validate_optional_seed(data: object) -> int | str | None:
    if data is None:
        return None
    if not isinstance(data, dict) or set(data) - {"seed"}:
        raise ValueError('Expected an optional JSON object containing only "seed".')
    seed = data.get("seed")
    if seed is None:
        return None
    if type(seed) is int and abs(seed) <= 2**53:
        return seed
    if isinstance(seed, str) and seed.strip() and len(seed) <= 128:
        return seed
    raise ValueError("seed must be an integer or a non-empty string of at most 128 characters.")


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
    simulation = SimulationService()
    app.extensions["scan_service"] = service
    app.extensions["demo_simulation"] = simulation

    def session_id() -> str:
        if "scan_session" not in session:
            session["scan_session"] = secrets.token_hex(24)
        return session["scan_session"]

    def optional_json_body() -> object:
        return request.get_json() if request.get_data(cache=True) else None

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

    @app.post("/api/analyze")
    def analyze():
        try:
            message = validate_analysis(request.get_json())
        except ValueError as error:
            return jsonify(error=str(error)), 400
        try:
            return jsonify(service.analyze(message))
        except Exception:
            app.logger.error("One-off classifier analysis failed; request may be retried.")
            return jsonify(error="Classifier unavailable. Please retry or restart the local server."), 503

    @app.post("/api/reset")
    def reset():
        old_session_id = session_id()
        service.reset(old_session_id)
        simulation.reset(old_session_id)
        session["scan_session"] = secrets.token_hex(24)
        return jsonify(reset=True)

    @app.get("/api/demo/history")
    def demo_history():
        return jsonify(simulation.history(session_id()))

    @app.get("/api/demo/check")
    def demo_check():
        counts = {
            label: {
                "fixtures": 0,
                "scanned": 0,
                "model_flagged": 0,
                "warning_flagged": 0,
            }
            for label in SCENARIO_LABELS
        }
        try:
            for fixture in SIMULATION_FIXTURES:
                summary = counts[fixture.scenario_label]
                summary["fixtures"] += 1
                if fixture.saved_contact:
                    continue
                result = service.analyze(fixture.message)
                summary["scanned"] += 1
                summary["model_flagged"] += result["model_flagged"] is True
                summary["warning_flagged"] += result["is_scam"] is True
        except Exception:
            app.logger.error("Synthetic scenario check failed; results are unavailable.")
            return jsonify(error="Classifier unavailable. Please retry or restart the local server."), 503

        recruiter = counts["potential_fraudulent_recruiter"]
        stranger = counts["normal_stranger"]
        return jsonify(
            scenarios=counts,
            fraudulent_fixtures_missed=recruiter["fixtures"] - recruiter["warning_flagged"],
            fraudulent_fixtures_model_missed=recruiter["fixtures"] - recruiter["model_flagged"],
            synthetic_false_positive_warnings=stranger["warning_flagged"],
            synthetic_model_false_positives=stranger["model_flagged"],
            scope="Synthetic demo fixtures only; not real-world accuracy.",
        )

    @app.post("/api/demo/receive")
    def demo_receive():
        try:
            seed = validate_optional_seed(optional_json_body())
        except ValueError as error:
            return jsonify(error=str(error)), 400
        try:
            result = simulation.receive(
                session_id(),
                lambda data: service.scan(session_id(), data),
                seed,
            )
            return jsonify(result)
        except SeedConflict as error:
            return jsonify(error=str(error)), 409
        except HTTPException:
            raise
        except Exception:
            app.logger.error("Simulated message scan failed; request may be retried.")
            return jsonify(error="Classifier unavailable. Please retry or restart the local server."), 503

    @app.post("/api/demo/conversations/<conversation_id>/decision")
    def demo_decision(conversation_id: str):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {"decision"}:
            return jsonify(error='Expected a JSON object with "decision".'), 400
        decision = data["decision"]
        if decision not in {"block", "accept"}:
            return jsonify(error='decision must be "block" or "accept".'), 400
        stored = simulation.decide(
            session_id(), conversation_id,
            "blocked" if decision == "block" else "accepted",
        )
        if stored is None:
            return jsonify(error="Conversation not found."), 404
        return jsonify(conversation=stored)

    @app.post("/api/demo/reset")
    def demo_reset():
        try:
            seed = validate_optional_seed(optional_json_body())
        except ValueError as error:
            return jsonify(error=str(error)), 400
        old_session_id = session_id()
        service.reset(old_session_id)
        simulation.reset(old_session_id)
        new_session_id = secrets.token_hex(24)
        session["scan_session"] = new_session_id
        simulation.reset(new_session_id, seed)
        return jsonify(reset=True, seed=seed)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    create_app().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
