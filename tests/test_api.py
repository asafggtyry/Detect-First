from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from detect_first.model import load_pipeline, predict_scam
from detect_first.server import ScanService, create_app
from detect_first.state import create_demo_store

ROOT = Path(__file__).resolve().parents[1]


def payload(**overrides):
    return dict(message="Hello from the school library.", sender="new-sender",
                is_saved_contact=False, is_first_message=True) | overrides


@pytest.fixture
def spy_app():
    calls = []
    app = create_app(classifier=lambda text: calls.append(text) or False)
    app.config["TESTING"] = True
    return app, calls


def test_real_model_demo_contract_and_evidence_provenance():
    pipeline = load_pipeline(ROOT / "models/job_posting_classifier.joblib")
    client = create_app().test_client()
    for conversation in create_demo_store(lambda text: predict_scam(text, pipeline)).conversations.values():
        response = client.post("/api/scan", json=payload(
            sender=conversation.sender_id, message=conversation.messages[0].text,
            is_saved_contact=conversation.saved_contact))
        assert response.status_code == 200
        result = response.json
        assert result["is_scam"] == conversation.should_warn
        assert result["model_flagged"] == conversation.model_flagged
        assert result["scanned"] is (not conversation.saved_contact)
        assert len(result["reasons"]) == len(conversation.evidence)
        assert all(reason["source"] == "evidence_rule" for reason in result["reasons"])
        if conversation.evidence and not conversation.model_flagged:
            assert result["warning_source"] == "evidence"


def test_saved_contacts_and_later_messages_never_call_classifier(spy_app):
    app, calls = spy_app
    client = app.test_client()
    assert client.post("/api/scan", json=payload(is_saved_contact=True)).json["skipped_reason"] == "saved_contact"
    assert client.post("/api/scan", json=payload()).json["skipped_reason"] == "saved_contact"
    assert client.post("/api/scan", json=payload(sender="later", is_first_message=False)).json["skipped_reason"] == "not_first_message"
    assert client.post("/api/scan", json=payload(sender="later")).json["scanned"] is False
    assert calls == []


def test_duplicate_retries_changed_messages_and_reset(spy_app):
    app, calls = spy_app
    client = app.test_client()
    first = client.post("/api/scan", json=payload()).json
    duplicate = client.post("/api/scan", json=payload()).json
    assert first["scanned"] and not first["cached"]
    assert duplicate == dict(first, cached=True)
    assert client.post("/api/scan", json=payload(message="Different later message")).json["skipped_reason"] == "already_scanned"
    assert len(calls) == 1
    assert client.post("/api/reset").json == {"reset": True}
    assert client.post("/api/scan", json=payload()).json["cached"] is False
    assert len(calls) == 2


def test_browser_sessions_are_isolated(spy_app):
    app, calls = spy_app
    first, second = app.test_client(), app.test_client()
    first.post("/api/scan", json=payload())
    second.post("/api/scan", json=payload())
    first.post("/api/reset")
    assert second.post("/api/scan", json=payload()).json["cached"] is True
    assert len(calls) == 2


def test_concurrent_duplicate_requests_classify_once():
    calls = []
    service = ScanService(lambda text: calls.append(text) or False)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: service.scan("session", payload()), range(12)))
    assert len(calls) == 1
    assert sum(not result["cached"] for result in results) == 1


@pytest.mark.parametrize("changes", [
    {"message": " "}, {"message": None}, {"message": 42}, {"message": "x" * 5001},
    {"sender": ""}, {"sender": []}, {"sender": "x" * 201},
    {"is_saved_contact": "false"}, {"is_saved_contact": 0}, {"is_first_message": None},
])
def test_invalid_inputs_do_not_consume_first_scan(spy_app, changes):
    app, calls = spy_app
    client = app.test_client()
    response = client.post("/api/scan", json=payload(**changes))
    assert response.status_code == 400 and "error" in response.json
    assert calls == []
    assert client.post("/api/scan", json=payload()).json["scanned"]


def test_missing_flags_bad_json_and_size_limits(spy_app):
    app, calls = spy_app
    client = app.test_client()
    for data in [{}, [], {"message": "hello", "sender": "unknown"}]:
        assert client.post("/api/scan", json=data).status_code == 400
    assert client.post("/api/scan", data="{bad", content_type="application/json").status_code == 400
    assert client.post("/api/scan", data="text").status_code == 415
    assert client.post("/api/scan", data="x" * 33_000, content_type="application/json").status_code == 413
    assert calls == []


def test_inference_failure_is_not_a_clean_result_and_can_retry():
    calls = []
    def classifier(text):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("Test failure")
        return False
    client = create_app(classifier=classifier).test_client()
    failed = client.post("/api/scan", json=payload())
    assert failed.status_code == 503 and "is_scam" not in failed.json
    assert client.post("/api/scan", json=payload()).json["scanned"] is True
    assert len(calls) == 2


@pytest.mark.parametrize("model_flagged,message,source", [
    (True, "Hello there", "model"),
    (False, "We are hiring. Pay an activation fee today.", "evidence"),
    (True, "We are hiring. Pay an activation fee today.", "both"),
    (False, "Hello there", "none"),
])
def test_warning_sources_are_separate(model_flagged, message, source):
    client = create_app(classifier=lambda _: model_flagged).test_client()
    result = client.post("/api/scan", json=payload(message=message)).json
    assert result["model_flagged"] is model_flagged
    assert result["warning_source"] == source
    assert result["is_scam"] is (source != "none")


def test_static_files_same_origin_and_private_files_unavailable(spy_app):
    app, calls = spy_app
    client = app.test_client()
    page = client.get("/")
    assert page.status_code == 200 and "scan_session" not in page.text
    assert "demo-fixtures.js" not in page.text
    assert "HttpOnly" in page.headers["Set-Cookie"]
    for path in ["/app.js", "/styles.css", "/config.js"]:
        assert client.get(path).status_code == 200
    for path in ["/models/job_posting_classifier.joblib", "/.git", "/../requirements.txt"]:
        assert client.get(path).status_code == 404
    assert client.post("/api/scan", json=payload(), headers={"Origin": "https://unrelated.example"}).status_code == 403
    assert calls == []


def test_missing_model_fails_startup_instead_of_using_sample_results(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(model_path=tmp_path / "missing.joblib")
