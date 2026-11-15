"""Real browser + HTTP + saved classifier; failures are simulated only in error tests."""
from pathlib import Path
from threading import Thread

import pytest
from werkzeug.serving import make_server

from detect_first.server import create_app

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def live_url():
    server = make_server("127.0.0.1", 0, create_app(), threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


@pytest.fixture
def page(request):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        dimensions = getattr(getattr(request.node, "callspec", None), "params", {})
        width, height = dimensions.get("width", 390), dimensions.get("height", 844)
        context = browser.new_context(viewport={"width": width, "height": height},
                                      is_mobile=width < 1000, has_touch=width < 1000)
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def home(page):
    page.get_by_role("button", name="Back to chats").click()
    page.wait_for_function("!document.querySelector('#phone').classList.contains('chat-open')")


def test_hash_routes_open_home_and_back_from_deep_link(page, live_url):
    from playwright.sync_api import expect

    page.goto(live_url + "/?debug=2026#/chat/u2")
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect(page.locator("#chat-name")).to_have_text("732-882-1944")
    page.get_by_role("button", name="Back to chats").click()
    expect(page.get_by_role("button", name="Receive random message")).to_be_visible()
    expect(page.locator("#chat-list .row")).to_have_count(3)

    page.goto(live_url + "/#/")
    expect(page.get_by_role("button", name="Receive random message")).to_be_visible()
    expect(page.locator("#chat-list .row")).to_have_count(3)

    page.locator('[data-chat="u2"]').click()
    expect(page.locator("#chat-name")).to_have_text("732-882-1944")
    page.get_by_role("button", name="Back to chats").click()
    expect(page.get_by_role("button", name="Receive random message")).to_be_visible()
    assert page.evaluate("location.hash") == "#/"


def test_blind_ai_screen_reveals_labels_and_keeps_arbitrary_input_unscored(page, live_url):
    from playwright.sync_api import expect

    page.goto(live_url)
    page.get_by_role("link", name="AI Evaluation").click()
    expect(page.locator("#screen-blind")).to_be_visible()
    # The redesign starts the blind test from an explicit button instead of on arrival.
    expect(page.locator("#blind-sample")).to_be_hidden()
    page.get_by_role("button", name="Start Blind Test").click()
    expect(page.locator("#blind-sample")).to_be_visible()
    expect(page.locator("#blind-sample-text")).not_to_be_empty()
    expect(page.locator("#blind-predictions")).to_contain_text("Reference label")
    expect(page.locator("#blind-metrics tr")).to_have_count(3)
    expect(page.locator("#blind-provenance")).to_contain_text("Synthetic demonstration only")

    # Arbitrary input moved to Test a Message: still analyzed by the real backend, never scored.
    totals = page.locator("#blind-metrics").inner_text()
    expect(page.locator(".blind-own")).to_contain_text("cannot be scored")
    page.locator(".blind-own").get_by_role("link", name="Test a Message").click()
    expect(page.locator("#screen-test")).to_be_visible()
    expect(page.locator("#test-unscored")).to_contain_text("Not scored")
    expect(page.locator("#test-unscored")).to_contain_text("no reference label")
    page.get_by_role("textbox", name="Message to analyze").fill("An arbitrary message with no label.")
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#test-status")).to_have_text("Analysis complete.")
    expect(page.locator("[data-model-result]")).to_be_visible()
    assert "Correct" not in page.locator("#test-result").inner_text()
    assert "Reference label" not in page.locator("#test-result").inner_text()
    page.get_by_role("link", name="AI Evaluation").click()
    expect(page.locator("#screen-blind")).to_be_visible()
    assert page.locator("#blind-metrics").inner_text() == totals


@pytest.mark.parametrize("width,height", [(1280, 900), (390, 844), (320, 568)])
def test_mobile_scenarios_actions_and_reset(page, live_url, width, height):
    from playwright.sync_api import expect
    page.set_viewport_size({"width": width, "height": height})
    requests = []
    errors = []
    page.on("request", lambda request: requests.append(request.post_data_json) if request.url.endswith("/api/scan") else None)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    assert len(requests) == 2 and all(not request["is_saved_contact"] for request in requests)
    page.locator('[data-chat="mom"]').click()
    expect(page.get_by_text("Saved contact · not scanned", exact=True)).to_be_visible()
    expect(page.locator(".warning")).to_have_count(0)
    home(page)
    page.locator('[data-chat="u1"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    expect(page.locator(".warning")).to_have_count(0)
    page.get_by_role("textbox", name="Type a message").fill("A simulated reply")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.locator("#thread .bubble-text").filter(has_text="A simulated reply")).to_be_visible()
    assert len(requests) == 2  # Replies never reach the classifier.
    home(page)
    page.locator('[data-chat="u2"]').click()
    expect(page.locator(".warning")).to_be_visible()
    # Minimal panel: title, one line of guidance and the two actions. The model/evidence
    # distinction stays in the data, not in visible technical boxes.
    warning = page.locator(".warning")
    expect(warning.locator("h2")).to_have_text("Potential job scam detected")
    expect(warning.locator(".warning-sub")).to_have_text("Tap highlighted text in the message to learn why.")
    expect(warning).to_have_attribute("data-warning-source", "evidence")
    expect(warning).to_have_attribute("data-model", "not-flagged")
    expect(warning.locator("button")).to_have_count(2)
    expect(page.locator(".warning-split, .warning-reasons, .warning-source, .warning [data-reason]")).to_have_count(0)
    assert warning.evaluate("node => node.scrollHeight <= node.clientHeight")
    assert warning.bounding_box()["height"] <= 150
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # The whole long message stays readable above the compact panel, even on short screens.
    expect(page.locator("#thread .bubble-text")).to_be_in_viewport(ratio=1)
    # The detail lives behind the highlighted phrase, and comes from the evidence rules.
    payment = page.locator('#thread .hl[data-category="upfront_payment_request"]')
    expect(payment).to_have_count(1)
    payment.click()
    popup = page.locator("#evidence-pop")
    expect(popup).to_be_visible()
    expect(page.locator("#evidence-pop-category")).to_have_text("Upfront payment request")
    expect(page.locator("#evidence-pop-phrase")).to_have_text(f"\u201c{payment.inner_text()}\u201d")
    assert page.locator("#evidence-pop-text").inner_text().strip()
    expect(page.locator("#evidence-pop-note")).to_contain_text("Rule-based observation")
    expect(page.locator("#evidence-pop-note")).to_contain_text("not an explanation of the ML model")
    expect(popup).to_be_in_viewport(ratio=1)
    page.wait_for_timeout(250)
    (ROOT / "reports/browser").mkdir(parents=True, exist_ok=True)
    page.screenshot(animations="disabled", path=str(ROOT / f"reports/browser/highlight-explanation-{width}.png"))
    page.get_by_role("button", name="Close explanation").click()
    expect(popup).to_be_hidden()
    for name in ["Block", "Accept Anyway"]:
        button = page.get_by_role("button", name=name, exact=True)
        expect(button).to_be_in_viewport(ratio=1)
        box = button.bounding_box()
        assert box and box["y"] >= 0 and box["y"] + box["height"] <= height
    output = ROOT / "reports/browser"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(animations="disabled", path=str(output / f"warning-{width}.png"))
    page.get_by_role("button", name="Accept Anyway", exact=True).click()
    expect(page.locator('[data-state="accepted"]')).to_be_visible()
    expect(page.get_by_role("textbox", name="Type a message")).to_be_visible()
    page.get_by_role("button", name="Flagged as a possible job scam").click()
    expect(page.get_by_role("button", name="Keep chatting")).to_be_visible()
    page.get_by_role("button", name="Block", exact=True).click()
    expect(page.locator('[data-state="blocked"]')).to_be_visible()
    expect(page.get_by_role("textbox", name="Type a message")).to_have_count(0)
    home(page)
    page.get_by_role("button", name="More options").click()
    page.get_by_role("menuitem", name="Reset demo").click()
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    page.locator('[data-chat="u2"]').click()
    expect(page.get_by_role("button", name="Accept Anyway", exact=True)).to_be_visible()
    assert len(requests) == 4
    assert not errors


@pytest.mark.parametrize("failure", ["offline", "malformed", "http_error", "timeout"])
def test_failed_api_never_uses_sample_results(page, live_url, failure):
    from playwright.sync_api import expect
    def fail(route):
        if failure == "offline":
            route.abort()
        elif failure == "timeout":
            pass  # Leave the request pending; the app's real AbortController must fire.
        elif failure == "malformed":
            route.fulfill(status=200, content_type="application/json", body='{"is_scam":"false"}')
        else:
            route.fulfill(status=503, content_type="application/json", body='{"error":"Unavailable"}')
    page.route("**/api/scan", fail)
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "error")
    page.locator('[data-chat="u2"]').click()
    expect(page.locator('[data-scan="error"]')).to_be_visible()
    expect(page.locator(".warning")).to_have_count(0)
    expect(page.locator('[data-scan="clean"]')).to_have_count(0)
    assert "Sample result" not in page.locator("body").inner_text()
    page.unroute("**/api/scan", fail)
    page.get_by_role("button", name="Try again").click()
    expect(page.locator(".warning")).to_be_visible()


@pytest.mark.parametrize("width,height", [(320, 568), (1280, 900)])
def test_test_message_lab_uses_live_api_without_changing_demo_state(page, live_url, width, height):
    from playwright.sync_api import expect
    page.set_viewport_size({"width": width, "height": height})
    scan_requests = []
    analysis_requests = []
    request_urls = []
    page.on("request", lambda request: request_urls.append(request.url))
    page.on("request", lambda request: scan_requests.append(request.post_data_json)
            if request.url.endswith("/api/scan") else None)
    page.on("request", lambda request: analysis_requests.append(request.post_data_json)
            if request.url.endswith("/api/analyze") else None)
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    assert len(scan_requests) == 2

    page.get_by_role("link", name="Test a Message").click()
    expect(page.locator("#screen-test")).to_be_visible()
    message = "Hi, we're hiring for a remote assistant. Deposit $25 today to get started. Reply now for details."
    page.get_by_role("textbox", name="Message to analyze").fill(message)
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#test-status")).to_have_text("Analysis complete.")
    expect(page.locator("[data-model-result]")).to_be_visible()
    expect(page.locator('[data-evidence="upfront_payment_request"]')).to_contain_text("Deposit $25")
    assert analysis_requests == [{"message": message}]
    assert len(scan_requests) == 2
    assert all(url.startswith(live_url) for url in request_urls)
    assert message not in (page.evaluate("localStorage.getItem('detect-first-demo-v1')") or "")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    page.get_by_role("button", name="Reset test").click()
    expect(page.get_by_role("textbox", name="Message to analyze")).to_have_value("")
    expect(page.locator("#test-result")).to_be_empty()
    second_message = "Thanks for sharing the recipe. I'll try it this weekend."
    page.get_by_role("textbox", name="Message to analyze").fill(second_message)
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#test-status")).to_have_text("Analysis complete.")
    expect(page.locator("#test-verdict")).to_have_text("No major warning signals detected")
    expect(page.locator(".test-caution")).to_contain_text("does not prove the message is safe")
    assert analysis_requests == [{"message": message}, {"message": second_message}]
    page.get_by_role("link", name="Chats").click()
    page.locator('[data-chat="u2"]').click()
    expect(page.locator(".warning")).to_be_visible()
    assert len(scan_requests) == 2


def test_test_message_lab_api_failure_does_not_show_a_verdict(page, live_url):
    from playwright.sync_api import expect
    page.route("**/api/analyze", lambda route: route.fulfill(
        status=503, content_type="application/json", body='{"error":"Unavailable"}'))
    page.goto(live_url)
    page.get_by_role("link", name="Test a Message").click()
    message = "Private one-off message that must not be stored"
    page.get_by_role("textbox", name="Message to analyze").fill(message)
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#test-status")).to_contain_text("Analysis failed")
    expect(page.locator("#test-result")).to_be_empty()
    assert message not in (page.evaluate("localStorage.getItem('detect-first-demo-v1')") or "")


@pytest.mark.parametrize("storage", ['{broken', '{"decisions":null,"read":42,"sent":{"u1":[null,{"dir":"in","text":"bad"}]}}'])
def test_corrupt_local_storage_recovers_with_live_scans(page, live_url, storage):
    import json
    from playwright.sync_api import expect
    page.add_init_script("localStorage.setItem('detect-first-demo-v1', " + json.dumps(storage) + ")")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    page.locator('[data-chat="u1"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    home(page)
    page.locator('[data-chat="u2"]').click()
    expect(page.locator(".warning")).to_be_visible()
    assert not errors


@pytest.mark.parametrize("width,height", [(390, 844), (320, 568)])
def test_failed_reset_preserves_decisions_and_reload_reuses_scans(page, live_url, width, height):
    from playwright.sync_api import expect
    page.set_viewport_size({"width": width, "height": height})
    responses = []
    page.on("response", lambda response: responses.append(response.json())
            if response.url.endswith("/api/scan") and response.status == 200 else None)
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    page.wait_for_load_state("networkidle")
    page.reload()
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    page.wait_for_load_state("networkidle")
    assert len(responses) == 4 and all(result["cached"] for result in responses[2:])
    page.locator('[data-chat="u2"]').click()
    page.get_by_role("button", name="Block", exact=True).click()
    home(page)
    page.route("**/api/demo/reset", lambda route: route.abort())
    page.get_by_role("button", name="More options").click()
    page.get_by_role("menuitem", name="Reset demo").click()
    expect(page.locator("#toast")).to_contain_text("Reset failed")
    expect(page.locator("#toast")).to_be_in_viewport(ratio=1)
    assert page.locator("#phone").evaluate("node => node.scrollLeft") == 0
    page.screenshot(animations="disabled", path=str(ROOT / f"reports/browser/reset-error-{width}.png"))
    page.locator('[data-chat="u2"]').click()
    expect(page.locator('[data-state="blocked"]')).to_be_visible()
    expect(page.locator(".warning")).to_have_count(0)
