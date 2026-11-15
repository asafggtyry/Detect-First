"""Clean-install regression: saved-model inference needs no raw/evaluation data."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError

import pytest

from detect_first.blind_evaluation import BlindEvaluationService, BenchmarkUnavailable
from detect_first.server import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_clean_install_starts_real_http_server_without_datasets(tmp_path):
    # Isolated filesystem and interpreter: no inherited module cache or dataset.
    for directory in ("detect_first", "frontend", "models"):
        shutil.copytree(ROOT / directory, tmp_path / directory,
                        ignore=shutil.ignore_patterns("__pycache__"))
    code = r'''
import hashlib, json
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from werkzeug.serving import make_server
from detect_first.server import create_app
from pathlib import Path

model = Path("models/job_posting_classifier.joblib")
before = hashlib.sha256(model.read_bytes()).hexdigest()
with patch("detect_first.data.download_dataset", side_effect=AssertionError("No downloads")), \
     patch("detect_first.model.train_and_save", side_effect=AssertionError("No training")), \
     patch("urllib.request.urlopen", side_effect=AssertionError("No network downloads")):
    app = create_app()
    assert app.extensions["blind_evaluation"]._samples is None
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for asset in ("/", "/app.js", "/api.js", "/styles.css", "/config.js"):
            with urlopen(base + asset, timeout=10) as response:
                assert response.status == 200 and response.read()
        def post(path, payload):
            return urlopen(Request(base + path, json.dumps(payload).encode(),
                                  {"Content-Type": "application/json"}), timeout=10)
        for endpoint in ("/api/analyze", "/api/evaluation/arbitrary"):
            with post(endpoint, {"message": "Please pay an activation fee for this job."}) as response:
                result = json.load(response)
                if endpoint.endswith("arbitrary"):
                    assert result["reference_label"] is None and result["scored"] is False
                else:
                    assert type(result["model_flagged"]) is bool
        with post("/api/demo/receive", {}) as response:
            assert "conversation" in json.load(response)
        for endpoint in ("/api/evaluation/start", "/api/evaluation/next"):
            try:
                post(endpoint, {})
                raise AssertionError("Missing benchmark must not be scored")
            except HTTPError as error:
                result = json.load(error)
                assert error.code == 503 and result["code"] == "benchmark_unavailable"
                assert "python scripts/download_test_data.py" in result["error"]
        assert not Path("data").exists()
        assert hashlib.sha256(model.read_bytes()).hexdigest() == before
        print("Clean install: HTTP/assets/inference passed; optional evaluation returns actionable 503.")
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()
'''
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_training_data_is_lazy_and_can_be_added_without_restart(tmp_path):
    missing = tmp_path / "fake_job_postings2.arff"
    app = create_app()
    runner = app.extensions["blind_evaluation"]
    runner.training_data_path = missing
    client = app.test_client()
    assert client.post("/api/analyze", json={"message": "See you tomorrow"}).status_code == 200
    assert runner._samples is None
    response = client.post("/api/evaluation/start", json={"seed": 7})
    assert response.status_code == 503
    assert "download_test_data.py" in response.json["error"]
    assert runner.sessions == {} and runner._samples is None
    shutil.copyfile(ROOT / "data/raw/fake_job_postings2.arff", missing)
    assert client.post("/api/evaluation/start", json={"seed": 7}).status_code == 200
    assert client.post("/api/evaluation/next").json["sample_index"] == 1


def test_failed_prediction_does_not_consume_sample_or_change_metrics():
    calls = []
    fail = False
    runner = None

    def analyze(text):
        calls.append(text)
        # The label for this sample is not yet present in stored scoring state.
        assert len(runner.sessions["retry"].actual) == runner.sessions["retry"].position
        if fail:
            raise RuntimeError("temporary classifier failure")
        return {"model_flagged": False, "evidence_flagged": False, "is_scam": False}

    runner = BlindEvaluationService(analyze)
    runner.start("retry", seed=17)
    first = runner.next("retry")
    fail = True
    with pytest.raises(RuntimeError, match="temporary"):
        runner.next("retry")
    assert runner.sessions["retry"].position == 1
    assert runner._metrics(runner.sessions["retry"]) == first["metrics"]
    fail = False
    second = runner.next("retry")
    assert calls[1] == calls[2] == second["text"]
    assert second["sample_index"] == 2
    assert all(metrics["examples"] == 2 for metrics in second["metrics"].values())


@pytest.mark.parametrize("row", [None, [], {}, {"id": [], "label": 0},
    {"id": "x", "label": True, "difficulty": "clear", "text": "Hello"},
    {"id": "x", "label": 0, "difficulty": [], "text": "Hello"}])
def test_invalid_benchmark_rows_fail_closed(tmp_path, row):
    path = tmp_path / "evaluation.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    runner = BlindEvaluationService(lambda _: pytest.fail("Must not predict"), evaluation_path=path)
    with pytest.raises(BenchmarkUnavailable, match="could not be validated"):
        runner.start("invalid")
    assert runner.sessions == {} and runner._samples is None


def test_empty_benchmark_fails_closed(tmp_path):
    path = tmp_path / "evaluation.jsonl"
    path.write_text("\n", encoding="utf-8")
    runner = BlindEvaluationService(lambda _: pytest.fail("Must not predict"), evaluation_path=path)
    with pytest.raises(BenchmarkUnavailable, match="could not be validated"):
        runner.start("empty")


def test_cli_reports_occupied_port_and_launches_after_it_is_freed(tmp_path):
    with socket.socket() as occupied:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        command = [sys.executable, "-m", "detect_first.server", "--port", str(port)]
        failed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert failed.returncode != 0
        message = (failed.stdout + failed.stderr).lower()
        assert any(fragment in message for fragment in ("in use", "forbidden", "10013", "10048"))
    # The documented CLI can use that port when the conflicting listener stops.
    with (tmp_path / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                assert process.poll() is None, "Server exited before accepting requests"
                try:
                    with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                        assert response.status == 200 and b"Detect First" in response.read()
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                pytest.fail("CLI server did not start within 25 seconds")
        finally:
            process.terminate()
            process.wait(timeout=10)
