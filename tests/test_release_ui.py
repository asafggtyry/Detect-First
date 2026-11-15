"""Release checks using Chromium and the Python HTTP server, at all target sizes."""
from pathlib import Path
from threading import Thread

import pytest
from werkzeug.serving import make_server

from detect_first.server import create_app
from test_browser import live_url, page  # noqa: F401
from test_navigation import load, tab, expect_screen, SHOTS, SIZES

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def missing_benchmark_url(tmp_path):
    app = create_app()
    runner = app.extensions["blind_evaluation"]
    runner.training_data_path = tmp_path / "absent.arff"
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", runner
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


@pytest.mark.parametrize("width,height", SIZES)
def test_missing_benchmark_has_actionable_error_and_retry(page, missing_benchmark_url, width, height):
    from playwright.sync_api import expect
    url, runner = missing_benchmark_url
    load(page, url, width, height)
    expect_screen(page, "chats")
    tab(page, "AI Evaluation").click()
    page.get_by_role("button", name="Start Blind Test", exact=True).click()
    expect(page.locator("#blind-status")).to_contain_text("python scripts/download_test_data.py")
    expect(page.locator("#blind-status")).to_contain_text("No result was made up")
    expect(page.locator("#blind-sample")).to_be_hidden()
    expect(page.locator("#blind-results")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(animations="disabled", path=str(SHOTS / f"benchmark-unavailable-{width}.png"))
    # The same running service can retry after optional data becomes available.
    runner.training_data_path = ROOT / "data/raw/fake_job_postings2.arff"
    page.get_by_role("button", name="Start Blind Test", exact=True).click()
    expect(page.locator("#blind-sample")).to_be_visible()
    expect(page.locator("#blind-tested")).to_have_text("Messages Tested: 1 of 32")


@pytest.mark.parametrize("width,height", SIZES)
def test_loading_states_disable_duplicate_requests_and_recover(page, live_url, width, height):
    from playwright.sync_api import expect
    load(page, live_url, width, height)
    held = []
    page.route("**/api/demo/receive", lambda route: held.append(route))
    page.locator("#receive-btn").click()
    expect(page.locator("#receive-btn")).to_be_disabled()
    expect(page.locator("#receive-label")).to_have_text("Receiving…")
    expect(page.locator("#scenario-btn")).to_be_disabled()
    assert len(held) == 1
    held.pop().continue_()
    expect_screen(page, "chat")
    page.get_by_role("button", name="Back to chats").click()
    page.unroute("**/api/demo/receive")

    tab(page, "Test a Message").click()
    page.route("**/api/analyze", lambda route: held.append(route))
    page.get_by_role("textbox", name="Message to analyze").fill("Pay an activation fee for the job today.")
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#analyze-btn")).to_be_disabled()
    assert len(held) == 1
    held.pop().continue_()
    expect(page.locator("#test-status")).to_have_text("Analysis complete.")
    page.unroute("**/api/analyze")

    tab(page, "AI Evaluation").click()
    page.route("**/api/evaluation/start", lambda route: held.append(route))
    page.get_by_role("button", name="Start Blind Test", exact=True).click()
    expect(page.locator("#blind-start-btn")).to_be_disabled()
    expect(page.locator("#blind-status")).to_contain_text("Starting")
    assert len(held) == 1
    held.pop().continue_()
    expect(page.locator("#blind-tested")).to_have_text("Messages Tested: 1 of 32")
    page.unroute("**/api/evaluation/start")

    page.route("**/api/evaluation/next", lambda route: held.append(route))
    page.get_by_role("button", name="Next Message", exact=True).click()
    expect(page.locator("#blind-start-btn")).to_be_disabled()
    expect(page.locator("#blind-next-btn")).to_be_disabled()
    expect(page.locator("#blind-status")).to_contain_text("Getting predictions")
    assert len(held) == 1
    held.pop().abort()
    expect(page.locator("#blind-status")).to_contain_text("No result was made up")
    expect(page.locator("#blind-tested")).to_have_text("Messages Tested: 1 of 32")
    expect(page.locator("#blind-next-btn")).to_be_enabled()
    page.unroute("**/api/evaluation/next")
    page.get_by_role("button", name="Next Message", exact=True).click()
    expect(page.locator("#blind-tested")).to_have_text("Messages Tested: 2 of 32")
