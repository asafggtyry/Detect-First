"""Live browser integration for the server-backed incoming-message simulator."""
from collections import Counter
from pathlib import Path
from threading import Thread

import pytest
from werkzeug.serving import make_server

from detect_first.server import create_app
from test_browser import home, live_url, page  # noqa: F401

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports" / "browser"


def load(page, url, expected_kind="live"):
    from playwright.sync_api import expect

    page.goto(url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", expected_kind)
    expect(page.locator("#receive-btn")).to_be_enabled()


def receive(page, scenario="random"):
    if scenario != "random":
        page.get_by_role("button", name="Choose demo scenario").click()
        page.locator(f'[data-scenario="{scenario}"]').click()
    with page.expect_response(lambda response: response.url.endswith("/api/demo/receive")) as response:
        page.locator("#receive-btn").click()
    result = response.value
    assert result.status == 200
    return result.json()


def analyze_in_browser(page, message):
    return page.evaluate(
        """async message => {
          const result = await window.DetectFirstApi.analyze(message);
          return {
            flagged: result.flagged,
            spans: result.spans.map(span => ({
              phrase: span.phrase,
              start: span.start,
              end: span.end,
              exact: message.slice(span.start, span.end) === span.phrase
            }))
          };
        }""",
        message,
    )


@pytest.mark.parametrize("width,height", [(390, 844), (320, 568)])
def test_real_scenario_selectors_classifier_spans_decisions_and_reset(
    page, live_url, width, height
):
    from playwright.sync_api import expect

    page.set_viewport_size({"width": width, "height": height})
    errors, scan_requests, receive_requests = [], [], []
    receive_responses = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: scan_requests.append(request.post_data_json)
            if request.url.endswith("/api/scan") else None)
    page.on("request", lambda request: receive_requests.append(request.post_data_json)
            if request.url.endswith("/api/demo/receive") else None)
    page.on("response", lambda response: receive_responses.append(response.json())
            if response.url.endswith("/api/demo/receive") and response.status == 200 else None)
    load(page, live_url)
    rows = page.locator("#chat-list .row")
    expect(rows).to_have_count(3)
    initial_scan_count = len(scan_requests)
    assert initial_scan_count == 2
    assert all(not request["is_saved_contact"] for request in scan_requests)

    receive_button = page.get_by_role("button", name="Receive random message")
    expect(receive_button).to_be_in_viewport(ratio=1)
    expect(page.get_by_role("button", name="Choose demo scenario")).to_be_in_viewport(ratio=1)
    expect(page.locator("#scenario-menu")).to_contain_text("The classifier decides every verdict")

    family = receive(page, "family_friend")["conversation"]
    assert family["scenario_label"] == "family_friend"
    assert family["saved_contact"] is True
    assert family["analysis"]["scanned"] is False
    expect(page.locator(f'[data-chat="{family["id"]}"]')).to_have_count(1)
    page.locator(f'[data-chat="{family["id"]}"]').click()
    expect(page.get_by_text("Saved contact · not scanned", exact=True)).to_be_visible()
    expect(page.locator(".warning, .hl, [data-scan]")).to_have_count(0)
    home(page)

    stranger = receive(page, "normal_stranger")["conversation"]
    assert stranger["scenario_label"] == "normal_stranger"
    assert stranger["saved_contact"] is False
    assert stranger["analysis"]["scanned"] is True
    assert stranger["analysis"]["model_flagged"] is False
    assert stranger["analysis"]["is_scam"] is False
    page.locator(f'[data-chat="{stranger["id"]}"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    expect(page.locator(".warning, .hl")).to_have_count(0)
    home(page)

    recruiter_records = [
        receive(page, "potential_fraudulent_recruiter")["conversation"]
        for _ in range(10)
    ]
    assert all(item["scenario_label"] == "potential_fraudulent_recruiter" for item in recruiter_records)
    assert len({item["sender"] for item in recruiter_records}) == 10
    assert sum(item["analysis"]["model_flagged"] is True for item in recruiter_records) == 3
    assert sum(item["analysis"]["is_scam"] is True for item in recruiter_records) == 6
    assert sum(item["analysis"]["is_scam"] is False for item in recruiter_records) == 4
    assert len(scan_requests) == initial_scan_count  # receive includes its own first-message scan

    unicode_record = next(item for item in recruiter_records if item["messages"][0]["text"].startswith("🙂 "))
    assert unicode_record["analysis"]["is_scam"] is True
    assert all(
        unicode_record["messages"][0]["text"][span["start"]:span["end"]] == span["excerpt"]
        for span in unicode_record["analysis"]["evidence_spans"]
    )
    unicode_id = unicode_record["id"]
    page.locator(f'[data-chat="{unicode_id}"]').click()
    expect(page.locator(".warning")).to_be_visible()
    expect(page.locator('.warning[data-model="flagged"]')).to_be_visible()
    expect(page.locator(".warning-sub")).to_have_text("Tap highlighted text in the message to learn why.")
    spans = unicode_record["analysis"]["evidence_spans"]
    marks = page.locator("#thread .hl")
    assert marks.all_inner_texts() == [span["excerpt"] for span in spans]
    assert page.locator("#thread .bubble-text").inner_text() == unicode_record["messages"][0]["text"]
    first_span = spans[0]
    mark = page.locator(f'#thread .hl[data-category="{first_span["category"]}"]')
    mark.click()
    expect(page.locator("#evidence-pop-phrase")).to_have_text(f'“{first_span["excerpt"]}”')
    expect(page.locator("#evidence-pop-text")).to_have_text(first_span["explanation"])
    expect(page.locator("#evidence-pop-category")).to_have_text(
        next(item["label"] for item in window_scenarios() if item["key"] == first_span["category"])
    )

    page.get_by_role("button", name="Accept Anyway", exact=True).click()
    expect(page.locator('[data-state="accepted"]')).to_be_visible()
    home(page)
    page.reload()
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect(page.locator(f'[data-chat="{unicode_id}"]')).to_have_count(1)
    expect(page.locator(f'[data-chat="{unicode_id}"]')).not_to_contain_text("You blocked this contact")
    page.locator(f'[data-chat="{unicode_id}"]').click()
    expect(page.locator('[data-state="accepted"]')).to_be_visible()
    page.get_by_role("button", name="Flagged as a possible job scam").click()
    page.get_by_role("button", name="Block", exact=True).click()
    expect(page.locator('[data-state="blocked"]')).to_be_visible()
    home(page)
    page.reload()
    expect(page.locator(f'[data-chat="{unicode_id}"]')).to_contain_text("You blocked this contact")

    # A missed recruiter remains clean; the scenario label never supplies its verdict.
    missed = next(item for item in recruiter_records if item["analysis"]["is_scam"] is False)
    page.locator(f'[data-chat="{missed["id"]}"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    expect(page.locator(".warning, .hl")).to_have_count(0)
    home(page)

    # Random selection is omitted from the request; the server chooses its scenario.
    random_result = receive(page)["conversation"]
    assert random_result["scenario_label"] in {
        "family_friend", "normal_stranger", "potential_fraudulent_recruiter"
    }
    assert receive_requests[-1] == {}
    assert len(receive_responses) == len(receive_requests)
    assert all(request["is_saved_contact"] is False for request in scan_requests)
    dynamic_senders = {
        item["sender"] for item in recruiter_records + [stranger]
    }
    assert all(request["sender"] not in dynamic_senders for request in scan_requests)

    # Reopening an existing chat is read-only and cannot create or rescan a message.
    receive_count, scan_count = len(receive_requests), len(scan_requests)
    page.locator(f'[data-chat="{unicode_id}"]').click()
    home(page)
    page.locator(f'[data-chat="{unicode_id}"]').click()
    assert len(receive_requests) == receive_count
    assert len(scan_requests) == scan_count
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"dynamic-live-{width}.png"))

    page.get_by_role("button", name="Back to chats").click()
    page.get_by_role("button", name="More options").click()
    page.get_by_role("menuitem", name="Reset demo").click()
    expect(rows).to_have_count(3)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    assert [row.get_attribute("data-chat") for row in rows.all()] == ["mom", "u1", "u2"]
    history = page.evaluate(
        """async () => (await fetch("/api/demo/history", {credentials: "same-origin"})).json()"""
    )
    assert history["conversations"] == []
    assert history["decisions"] == {}
    assert not errors


def window_scenarios():
    return [
        {"key": "unsolicited_job_offer", "label": "First-contact job offer"},
        {"key": "upfront_payment_request", "label": "Upfront payment request"},
        {"key": "unrealistic_earnings", "label": "High daily earnings claim"},
        {"key": "vague_job_details", "label": "Limited role details"},
        {"key": "urgency_pressure", "label": "Urgency / pressure"},
        {"key": "unverified_employer", "label": "Employer not verified by demo"},
    ]


def test_fixed_demo_chat_highlights_only_live_backend_evidence(page, live_url):
    from playwright.sync_api import expect

    scan_responses = []
    page.on("response", lambda response: scan_responses.append(response.json())
            if response.url.endswith("/api/scan") and response.status == 200 else None)
    load(page, live_url)
    page.locator('[data-chat="u2"]').click()
    expect(page.locator(".warning")).to_be_visible()
    result = next(item for item in scan_responses if item["is_scam"])
    spans = result["evidence_spans"]
    assert spans
    assert page.locator("#thread .hl").all_inner_texts() == [item["excerpt"] for item in spans]
    message = page.locator("#thread .bubble-text").inner_text()
    assert all(message[item["start"]:item["end"]] == item["excerpt"] for item in spans)
    expect(page.locator('.warning[data-model="not-flagged"]')).to_be_visible()
    home(page)
    page.locator('[data-chat="u1"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    expect(page.locator(".hl")).to_have_count(0)


def test_repeated_unknown_sender_reuses_conversation_and_first_analysis(page, live_url):
    from playwright.sync_api import expect

    scan_requests = []
    receive_requests = []
    page.on("request", lambda request: scan_requests.append(request.post_data_json)
            if request.url.endswith("/api/scan") else None)
    page.on("request", lambda request: receive_requests.append(request.post_data_json)
            if request.url.endswith("/api/demo/receive") else None)
    load(page, live_url)
    conversations = [
        receive(page, "normal_stranger")["conversation"]
        for _ in range(11)
    ]
    by_id = Counter(item["id"] for item in conversations)
    assert len(by_id) == 10
    repeated_id = next(identifier for identifier, count in by_id.items() if count == 2)
    repeated = next(item for item in conversations if item["id"] == repeated_id and len(item["messages"]) == 2)
    assert repeated["analysis"]["scanned"] is True
    assert len(repeated["messages"]) == 2
    assert len(scan_requests) == 2
    assert len(receive_requests) == 11

    page.locator(f'[data-chat="{repeated_id}"]').click()
    expect(page.locator("#thread .bubble-in")).to_have_count(2)
    assert len(scan_requests) == 2
    home(page)
    page.locator(f'[data-chat="{repeated_id}"]').click()
    expect(page.locator("#thread .bubble-in")).to_have_count(2)
    assert len(receive_requests) == 11
    assert len(scan_requests) == 2


def test_frontend_converts_unicode_codepoint_spans_against_exact_analyzer_text(page, live_url):
    load(page, live_url)
    message = "🙂 Café! We are hiring. Deposit $60, then within 24 hours; deposit $60."
    raw = page.request.post(
        live_url + "/api/analyze",
        data={"message": message},
    ).json()
    normalized = analyze_in_browser(page, message)
    assert raw["evidence_spans"]
    assert [item["phrase"] for item in normalized["spans"]] == [
        item["excerpt"] for item in raw["evidence_spans"]
    ]
    assert all(item["exact"] for item in normalized["spans"])
    assert normalized["flagged"] == raw["is_scam"]
    assert message.casefold().count("deposit $60") == 2


@pytest.fixture
def classifier_error_url():
    def unavailable(_text):
        raise RuntimeError("test classifier failure")

    server = make_server("127.0.0.1", 0, create_app(classifier=unavailable), threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def test_real_server_inference_errors_never_create_sample_results(page, classifier_error_url):
    from playwright.sync_api import expect

    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    load(page, classifier_error_url, expected_kind="error")
    initial_rows = page.locator("#chat-list .row")
    expect(initial_rows).to_have_count(3)
    with page.expect_response(lambda response: response.url.endswith("/api/demo/receive")) as response:
        page.get_by_role("button", name="Choose demo scenario").click()
        page.locator('[data-scenario="potential_fraudulent_recruiter"]').click()
        page.locator("#receive-btn").click()
    assert response.value.status == 503
    banner = page.locator("#receive-error")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("Classifier unavailable")
    expect(initial_rows).to_have_count(3)
    expect(page.locator(".warning, .hl")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


def test_highlight_explanations_open_and_dismiss_from_the_keyboard(page, live_url):
    from playwright.sync_api import expect

    scan_responses = []
    page.on("response", lambda response: scan_responses.append(response.json())
            if response.url.endswith("/api/scan") and response.status == 200 else None)
    load(page, live_url)
    page.locator('[data-chat="u2"]').click()
    expect(page.locator(".warning")).to_be_visible()
    spans = next(item for item in scan_responses if item["is_scam"])["evidence_spans"]
    popup = page.locator("#evidence-pop")
    marks = page.locator("#thread .hl")
    labels = {item["key"]: item["label"] for item in window_scenarios()}

    # Every highlight is a focusable button; Enter and Space open it, Escape returns focus.
    for index, key in enumerate(["Enter", " "]):
        mark = marks.nth(index)
        expect(mark).to_have_attribute("role", "button")
        expect(mark).to_have_attribute("tabindex", "0")
        mark.focus()
        page.keyboard.press(key)
        expect(popup).to_be_visible()
        expect(page.locator("#evidence-pop-phrase")).to_have_text(f'\u201c{spans[index]["excerpt"]}\u201d')
        expect(page.locator("#evidence-pop-category")).to_have_text(labels[spans[index]["category"]])
        expect(page.locator("#evidence-pop-text")).to_have_text(spans[index]["explanation"])
        expect(page.get_by_role("button", name="Close explanation")).to_be_focused()
        page.keyboard.press("Escape")
        expect(popup).to_be_hidden()
        expect(mark).to_be_focused()

    # Tapping elsewhere also dismisses it, and the actions stay usable underneath.
    marks.first.click()
    expect(popup).to_be_visible()
    page.locator("#chat-name").click()
    expect(popup).to_be_hidden()
    expect(page.get_by_role("button", name="Block", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Accept Anyway", exact=True)).to_be_visible()


@pytest.mark.parametrize("width,height", [(390, 844), (320, 568)])
@pytest.mark.parametrize("spans", ["missing", "invalid"])
def test_flagged_message_without_valid_spans_offers_review_of_real_evidence_only(
    page, live_url, width, height, spans
):
    """Only the span list is altered; verdict, reasons and model flag are the real analyzer's."""
    import json
    from playwright.sync_api import expect

    page.set_viewport_size({"width": width, "height": height})
    real = []

    def strip_spans(route):
        response = route.fetch()
        body = response.json()
        if body.get("is_scam"):
            real.append(json.loads(json.dumps(body)))
            if spans == "missing":
                body.pop("evidence_spans", None)
            else:
                body["evidence_spans"] = [
                    {"start": 9000, "end": 9010, "excerpt": "not in message", "category": "urgency_pressure",
                     "explanation": "Out of range."},
                    {"start": 0, "end": 5, "excerpt": "wrong", "category": "urgency_pressure",
                     "explanation": "Excerpt does not match the message."},
                    "nonsense",
                ]
        route.fulfill(response=response, body=json.dumps(body), content_type="application/json")

    page.route("**/api/scan", strip_spans)
    load(page, live_url)
    page.locator('[data-chat="u2"]').click()
    warning = page.locator(".warning")
    expect(warning).to_be_visible()
    expect(page.locator("#thread .hl")).to_have_count(0)
    expect(warning.locator("h2")).to_have_text("Potential job scam detected")
    assert "Tap highlighted text" not in warning.inner_text()
    review = page.get_by_role("button", name="Review why this was flagged")
    expect(review).to_be_in_viewport(ratio=1)
    for name in ["Block", "Accept Anyway"]:
        expect(page.get_by_role("button", name=name, exact=True)).to_be_in_viewport(ratio=1)

    review.focus()
    page.keyboard.press("Enter")
    popup = page.locator("#evidence-pop")
    expect(popup).to_be_visible()
    expect(popup).to_be_in_viewport(ratio=1)
    expect(page.locator("#evidence-pop-phrase")).to_be_hidden()
    reasons = real[0]["reasons"]
    assert reasons and real[0]["model_flagged"] is False
    items = page.locator("#evidence-pop-list li")
    expect(items).to_have_count(len(reasons))
    for index, reason in enumerate(reasons):
        expect(items.nth(index)).to_have_attribute("data-reason", reason["category"])
        expect(items.nth(index)).to_contain_text(reason["evidence"])
    expect(page.locator("#evidence-pop-text")).to_contain_text("evidence rules")
    expect(page.locator("#evidence-pop-text")).not_to_contain_text("ML classifier flagged")
    expect(page.locator("#evidence-pop-note")).to_contain_text("not an explanation of the ML model")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.wait_for_timeout(250)
    if spans == "missing":
        page.screenshot(path=str(SHOTS / f"warning-review-{width}.png"))
    page.keyboard.press("Escape")
    expect(popup).to_be_hidden()
    expect(review).to_be_focused()
    page.get_by_role("button", name="Accept Anyway", exact=True).click()
    expect(page.locator('[data-state="accepted"]')).to_be_visible()
