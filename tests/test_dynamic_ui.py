"""Browser checks for incoming-message simulation and evidence highlighting.

The message simulation endpoint is not part of the server on this branch, so
`Simulation` below answers `/api/simulate` in the browser using the provisional
shape read by frontend/api.js. Everything else is real: unknown senders are
scanned by the live server and the saved classifier unless a test says otherwise.
"""
import json
from pathlib import Path

import pytest

from test_browser import home, live_url, page  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports/browser"

RECRUITER_TEXT = ("Hi! We are hiring students for remote work. Earn up to $300 per day. "
                  "Deposit $60 within 24 hours to secure your position.")
HARMLESS_TEXT = "Hey, is this still your number? It's Sam from the chess club."
FAMILY = [("Aunt Priya", "Are you coming to dinner on Sunday?"),
          ("Coach Dan", "Practice moved to 4pm tomorrow."),
          ("Grandpa Joe", "Call me when you get home.")]
SPAN_TEXT = "Earn $300 per day. Deposit $60 within 24 hours."


class Simulation:
    """Stand-in for the backend message simulation (provisional contract)."""

    def __init__(self, page):
        self.requests = []
        self.next_payload = None
        self.family_sent = 0
        page.route("**/api/simulate", self.handle)

    def handle(self, route):
        body = route.request.post_data_json
        self.requests.append(body)
        if self.next_payload is not None:
            payload, self.next_payload = self.next_payload, None
        else:
            count = len(self.requests)
            kind = body["scenario"]
            if kind == "random":
                kind = ["unknown_harmless", "recruiter", "saved_contact"][count % 3]
            if kind == "saved_contact":
                name, text = FAMILY[self.family_sent % len(FAMILY)]
                self.family_sent += 1
                payload = {"sender": name, "is_saved_contact": True, "message": text}
            elif kind == "recruiter":
                payload = {"sender": f"555-01{count:02d}", "is_saved_contact": False, "message": RECRUITER_TEXT}
            else:
                payload = {"sender": f"555-02{count:02d}", "is_saved_contact": False, "message": HARMLESS_TEXT}
            payload["scenario"] = kind
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


def scan_result(**overrides):
    """A response in the documented /api/scan shape (docs/API.md)."""
    result = dict(is_scam=True, reasons=[], model_flagged=False, evidence_flagged=True,
                  warning_source="evidence", scanned=True, skipped_reason=None, cached=False)
    result.update(overrides)
    return result


def reason(category, explanation, snippet=None):
    return dict(category=category, evidence=explanation, snippet=snippet, source="evidence_rule")


def load(page, live_url):
    from playwright.sync_api import expect
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")


def receive(page, scenario=None):
    """Use the Receive button, optionally picking a presenter scenario first."""
    if scenario:
        page.get_by_role("button", name="Choose demo scenario").click()
        page.locator(f'[data-scenario="{scenario}"]').click()
    page.locator("#receive-btn").click()


def newest(page):
    return page.locator("#chat-list .row").first


@pytest.mark.parametrize("width,height", [(390, 844), (320, 568)])
def test_receive_messages_scenarios_highlights_and_reset(page, live_url, width, height):
    from playwright.sync_api import expect
    page.set_viewport_size({"width": width, "height": height})
    errors, scan_requests, scan_responses = [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: scan_requests.append(request.post_data_json)
            if request.url.endswith("/api/scan") else None)
    page.on("response", lambda response: scan_responses.append(response.json())
            if response.url.endswith("/api/scan") and response.status == 200 else None)
    simulation = Simulation(page)
    load(page, live_url)
    rows = page.locator("#chat-list .row")
    expect(rows).to_have_count(3)

    # The action is clearly labelled and fully on screen, even at 320px.
    button = page.get_by_role("button", name="Receive random message")
    expect(button).to_be_in_viewport(ratio=1)
    expect(page.get_by_role("button", name="Choose demo scenario")).to_be_in_viewport(ratio=1)

    # True random: the frontend asks for "random" and shows whatever arrives.
    button.click()
    expect(rows).to_have_count(4)
    assert simulation.requests == [{"scenario": "random"}]
    expect(newest(page).locator(".row-name")).to_have_text("555-0101")  # recruiter per the stub's rotation
    expect(newest(page).locator(".badge")).to_have_text("1")
    expect(newest(page).locator(".row-time")).to_have_text(__import__("re").compile(r"^\d{1,2}:\d{2} [AP]M$"))
    expect(newest(page).locator(".avatar svg")).to_have_count(1)
    expect(newest(page).locator(".ico-warn")).to_have_count(1)  # verdict from the real analyzer
    expect(page.locator('[data-chat="mom"]')).to_have_count(1)  # demo chats are preserved

    # Selectable scenarios only choose the sample category.
    page.get_by_role("button", name="Choose demo scenario").click()
    menu = page.locator("#scenario-menu")
    expect(menu).to_be_in_viewport(ratio=1)
    expect(menu).to_contain_text("The classifier decides every verdict")
    expect(menu.get_by_role("menuitemradio")).to_have_count(4)
    expect(menu.get_by_role("menuitemradio", name="Random")).to_have_attribute("aria-checked", "true")
    page.locator('[data-scenario="saved_contact"]').click()
    expect(page.locator("#receive-label")).to_have_text("Receive: family or friend")
    scans_before = len(scan_requests)
    page.locator("#receive-btn").click()
    expect(rows).to_have_count(5)
    assert simulation.requests[-1] == {"scenario": "saved_contact"}
    saved_name = newest(page).locator(".row-name").inner_text()
    assert saved_name in [name for name, _ in FAMILY]
    expect(newest(page).locator(".avatar")).to_have_text(saved_name[0])
    expect(newest(page).locator(".ico-warn")).to_have_count(0)

    receive(page, "unknown_harmless")
    expect(rows).to_have_count(6)
    harmless_id = newest(page).get_attribute("data-chat")
    receive(page, "recruiter")
    expect(rows).to_have_count(7)
    recruiter_id = newest(page).get_attribute("data-chat")
    expect(newest(page).locator(".ico-warn")).to_have_count(1)
    assert [request["scenario"] for request in simulation.requests] == [
        "random", "saved_contact", "unknown_harmless", "recruiter"]
    # Saved contacts are never sent to the classifier; each unknown sender is scanned once.
    assert all(not request["is_saved_contact"] for request in scan_requests)
    assert len(scan_requests) == scans_before + 2

    # Back to true random.
    receive(page, "random")
    expect(rows).to_have_count(8)
    expect(page.locator("#receive-label")).to_have_text("Receive random message")
    assert simulation.requests[-1] == {"scenario": "random"}

    # Many conversations: the list scrolls and the last chat clears the button.
    body = page.locator(".home-body")
    assert body.evaluate("node => node.scrollHeight > node.clientHeight")
    body.evaluate("node => node.scrollTop = node.scrollHeight")
    last_row = rows.last.bounding_box()
    fab = page.locator(".receive-fab").bounding_box()
    assert last_row["y"] + last_row["height"] <= fab["y"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    body.evaluate("node => node.scrollTop = 0")
    page.screenshot(path=str(SHOTS / f"dynamic-list-{width}.png"))

    # A saved contact opens as a normal, unscanned chat.
    page.locator("#chat-list .row", has_text=saved_name).click()
    expect(page.get_by_text("Saved contact · not scanned", exact=True)).to_be_visible()
    expect(page.locator("#thread .bubble-in")).to_have_count(1)
    expect(page.locator(".warning, .hl, [data-scan]")).to_have_count(0)
    home(page)

    # A harmless unknown sender is checked and gets no warning and no highlights.
    page.locator(f'[data-chat="{harmless_id}"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    expect(page.locator("#thread .bubble-text")).to_have_text(HARMLESS_TEXT)
    expect(page.locator(".warning, .hl")).to_have_count(0)
    home(page)

    # Opening and reopening never generates another message.
    simulated = len(simulation.requests)
    scanned = len(scan_requests)
    page.locator(f'[data-chat="{recruiter_id}"]').click()
    expect(page.locator("#thread .bubble-in")).to_have_count(1)
    expect(page.locator("#thread .bubble-text")).to_have_text(RECRUITER_TEXT)
    home(page)
    expect(page.locator(f'[data-chat="{recruiter_id}"] .badge')).to_have_count(0)
    page.locator(f'[data-chat="{recruiter_id}"]').click()
    expect(page.locator("#thread .bubble-in")).to_have_count(1)
    assert len(simulation.requests) == simulated and len(scan_requests) == scanned

    # Warning panel: model prediction and evidence findings are reported separately.
    warning = page.locator(".warning")
    expect(warning).to_contain_text("Potential job scam detected")
    expect(warning.locator("[data-model]")).to_contain_text("Model prediction")
    expect(warning.locator("[data-evidence-count]")).to_contain_text("findings")
    for name in ["Block", "Accept Anyway"]:
        expect(page.get_by_role("button", name=name, exact=True)).to_be_in_viewport(ratio=1)

    # Highlights are exactly the snippets the real analyzer returned for this message.
    result = next(response for request, response in zip(scan_requests, scan_responses)
                  if request["message"] == RECRUITER_TEXT)
    snippets = [item["snippet"] for item in result["reasons"] if item["snippet"]]
    expected = sorted(snippets, key=RECRUITER_TEXT.index)
    assert len(expected) >= 3
    marks = page.locator("#thread .hl")
    assert marks.all_inner_texts() == expected
    assert page.locator("#thread .bubble-text").inner_text() == RECRUITER_TEXT
    assert marks.first.evaluate("node => getComputedStyle(node).userSelect") != "none"

    # Tapping a phrase opens a compact explanation: phrase, category and explanation.
    payment = next(item for item in result["reasons"] if item["category"] == "upfront_payment_request")
    mark = page.locator('#thread .hl[data-category="upfront_payment_request"]')
    page.locator("#thread").evaluate("node => node.scrollTop = 0")
    mark.scroll_into_view_if_needed()
    mark.click()
    popup = page.locator("#evidence-pop")
    expect(popup).to_be_visible()
    expect(popup).to_be_in_viewport(ratio=1)
    expect(popup.locator("#evidence-pop-phrase")).to_contain_text(payment["snippet"])
    expect(popup.locator("#evidence-pop-category")).to_have_text("Upfront payment request")
    expect(popup.locator("#evidence-pop-text")).to_have_text(payment["evidence"])
    box = popup.bounding_box()
    assert box["height"] < height * 0.45  # compact: the bubble is not covered wholesale
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.wait_for_timeout(250)  # let the popup's fade-in finish before the screenshot
    page.screenshot(path=str(SHOTS / f"dynamic-highlight-{width}.png"))
    page.keyboard.press("Escape")
    expect(popup).to_be_hidden()
    # Keyboard access, and tapping elsewhere dismisses it.
    mark.focus()
    page.keyboard.press("Enter")
    expect(popup).to_be_visible()
    page.locator("#chat-name").click()
    expect(popup).to_be_hidden()

    # Accept Anyway and Block work on generated chats.
    page.get_by_role("button", name="Accept Anyway", exact=True).click()
    expect(page.locator('[data-state="accepted"]')).to_be_visible()
    expect(page.get_by_role("textbox", name="Type a message")).to_be_visible()
    expect(page.locator("#thread .hl")).to_have_count(len(expected))
    page.get_by_role("button", name="Flagged as a possible job scam").click()
    page.get_by_role("button", name="Block", exact=True).click()
    expect(page.locator('[data-state="blocked"]')).to_be_visible()
    home(page)
    expect(page.locator(f'[data-chat="{recruiter_id}"]')).to_contain_text("You blocked this contact")

    # A reload keeps the received chats without asking the simulation again.
    page.reload()
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect(rows).to_have_count(8)
    expect(page.locator(f'[data-chat="{recruiter_id}"]')).to_contain_text("You blocked this contact")
    assert len(simulation.requests) == simulated

    # Reset removes generated chats and restores the three demo chats.
    page.get_by_role("button", name="More options").click()
    page.get_by_role("menuitem", name="Reset demo").click()
    expect(rows).to_have_count(3)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    assert [row.get_attribute("data-chat") for row in rows.all()] == ["mom", "u1", "u2"]
    expect(page.locator("#receive-label")).to_have_text("Receive random message")
    page.get_by_role("button", name="More options").click()
    expect(page.get_by_role("menuitem", name="Test Message")).to_be_visible()
    assert not errors


def test_demo_chat_highlights_come_from_the_live_analyzer(page, live_url):
    from playwright.sync_api import expect
    responses = []
    page.on("response", lambda response: responses.append(response.json())
            if response.url.endswith("/api/scan") and response.status == 200 else None)
    load(page, live_url)
    page.locator('[data-chat="u2"]').click()
    expect(page.locator(".warning")).to_be_visible()
    flagged = next(result for result in responses if result["is_scam"])
    text = page.locator("#thread .bubble-text").inner_text()
    snippets = sorted([item["snippet"] for item in flagged["reasons"] if item["snippet"]], key=text.index)
    assert snippets and page.locator("#thread .hl").all_inner_texts() == snippets
    home(page)
    page.locator('[data-chat="u1"]').click()
    expect(page.locator('[data-scan="clean"]')).to_be_visible()
    expect(page.locator(".hl")).to_have_count(0)


def test_repeat_sender_adds_to_the_existing_chat(page, live_url):
    from playwright.sync_api import expect
    simulation = Simulation(page)
    load(page, live_url)
    rows = page.locator("#chat-list .row")
    for text in ["First hello", "Second hello"]:
        simulation.next_payload = {"sender": "Aunt Priya", "is_saved_contact": True, "message": text}
        page.locator("#receive-btn").click()
        expect(newest(page).locator(".row-preview-text")).to_have_text(text)
    expect(rows).to_have_count(4)
    expect(newest(page).locator(".badge")).to_have_text("2")
    newest(page).click()
    expect(page.locator("#thread .bubble-in")).to_have_count(2)
    assert page.locator("#thread .bubble-in .bubble-text").all_inner_texts() == ["First hello", "Second hello"]
    home(page)
    expect(newest(page).locator(".badge")).to_have_count(0)
    # A new message for one of the original demo chats lands in that chat too.
    simulation.next_payload = {"sender": "Mom", "is_saved_contact": True, "message": "Dinner at 7?"}
    page.locator("#receive-btn").click()
    expect(rows).to_have_count(4)
    expect(newest(page)).to_have_attribute("data-chat", "mom")
    expect(newest(page).locator(".badge")).to_have_text("2")


@pytest.mark.parametrize("width,height", [(390, 844), (320, 568)])
def test_backend_offset_spans_render_exact_phrases(page, live_url, width, height):
    """Explicit start/end spans, including offsets counted in code points after an emoji."""
    from playwright.sync_api import expect
    page.set_viewport_size({"width": width, "height": height})
    simulation = Simulation(page)
    texts = {"555-0900": SPAN_TEXT, "555-0901": "\U0001F389 " + SPAN_TEXT}
    spans = [("$300 per day", "unrealistic_earnings", "Unusually high earnings claim."),
             ("Deposit $60", "upfront_payment_request", "Upfront payment request."),
             ("within 24 hours", "urgency_pressure", "Urgency.")]

    def scan(route):
        body = route.request.post_data_json
        text = texts.get(body["sender"])
        if text is None:
            return route.fallback()
        route.fulfill(status=200, content_type="application/json", body=json.dumps(scan_result(
            reasons=[reason(category, explanation) for _, category, explanation in spans],
            spans=[dict(start=text.index(phrase), end=text.index(phrase) + len(phrase), text=phrase,
                        category=category, explanation=explanation)
                   for phrase, category, explanation in spans])))

    page.route("**/api/scan", scan)
    load(page, live_url)
    for sender, text in texts.items():
        simulation.next_payload = {"sender": sender, "is_saved_contact": False, "message": text}
        page.locator("#receive-btn").click()
        expect(newest(page).locator(".row-name")).to_have_text(sender)
        newest(page).click()
        expect(page.locator(".warning")).to_be_visible()
        marks = page.locator("#thread .hl")
        assert marks.all_inner_texts() == [phrase for phrase, _, _ in spans]
        assert page.locator("#thread .bubble-text").inner_text() == text
        expect(page.locator(".warning-source")).to_contain_text("Tap highlighted text")
        marks.nth(2).click()
        popup = page.locator("#evidence-pop")
        expect(popup).to_be_in_viewport(ratio=1)
        expect(popup.locator("#evidence-pop-phrase")).to_contain_text("within 24 hours")
        expect(popup.locator("#evidence-pop-category")).to_have_text("Urgency / pressure")
        expect(popup.locator("#evidence-pop-text")).to_have_text("Urgency.")
        marks.nth(0).click()  # switching phrases swaps the explanation
        expect(popup.locator("#evidence-pop-phrase")).to_contain_text("$300 per day")
        expect(popup.locator("#evidence-pop-text")).to_have_text("Unusually high earnings claim.")
        page.get_by_role("button", name="Close explanation").click()
        expect(popup).to_be_hidden()
        home(page)


def test_missing_or_invalid_spans_are_not_rendered(page, live_url):
    from playwright.sync_api import expect
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    simulation = Simulation(page)
    reasons = [reason("upfront_payment_request", "Upfront payment request."),
               reason("urgency_pressure", "Urgency.")]
    bad_spans = [
        dict(start=5, end=11, category="unrealistic_earnings"),                       # valid: "$300 p"... kept
        dict(start=8, end=14, category="urgency_pressure"),                           # overlaps the kept span
        dict(start=-3, end=4, category="urgency_pressure"),                           # negative
        dict(start=40, end=400, category="urgency_pressure"),                         # past the end
        dict(start=20, end=20, category="urgency_pressure"),                          # empty
        dict(start="19", end="30", category="urgency_pressure"),                      # not integers
        dict(start=19, end=30, text="Send $999", category="upfront_payment_request"),  # phrase not in message
        dict(category="urgency_pressure"),                                            # nothing to locate
        "within 24 hours", None, 7,                                                   # not objects
    ]
    results = {
        "555-0910": scan_result(reasons=reasons, spans=bad_spans),
        "555-0911": scan_result(reasons=reasons),                    # no spans, snippets null
        "555-0912": scan_result(reasons=reasons, spans="oops"),      # wrong type
        "555-0913": scan_result(is_scam=False, evidence_flagged=False, warning_source="none",
                                reasons=reasons[:1],
                                spans=[dict(start=19, end=30, category="upfront_payment_request")]),
    }

    def scan(route):
        result = results.get(route.request.post_data_json["sender"])
        if result is None:
            return route.fallback()
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))

    page.route("**/api/scan", scan)
    load(page, live_url)
    expected_marks = {"555-0910": [SPAN_TEXT[5:11]], "555-0911": [], "555-0912": [], "555-0913": []}
    for sender, marks in expected_marks.items():
        simulation.next_payload = {"sender": sender, "is_saved_contact": False, "message": SPAN_TEXT}
        page.locator("#receive-btn").click()
        expect(newest(page).locator(".row-name")).to_have_text(sender)
        newest(page).click()
        if sender == "555-0913":
            # No warning from the analyzer means no warning and no highlights in the UI.
            expect(page.locator('[data-scan="clean"]')).to_be_visible()
            expect(page.locator(".warning")).to_have_count(0)
        else:
            expect(page.locator(".warning")).to_be_visible()
            expect(page.locator(".warning-reasons li")).to_have_count(2)
        assert page.locator("#thread .hl").all_inner_texts() == marks
        assert page.locator("#thread .bubble-text").inner_text() == SPAN_TEXT
        if not marks:
            expect(page.locator("#dock")).not_to_contain_text("Tap highlighted text")
        home(page)
    assert not errors


def test_simulation_can_include_its_own_analysis(page, live_url):
    from playwright.sync_api import expect
    scan_requests = []
    page.on("request", lambda request: scan_requests.append(request.post_data_json)
            if request.url.endswith("/api/scan") else None)
    simulation = Simulation(page)
    load(page, live_url)
    simulation.next_payload = {
        "sender": {"name": "555-0920", "is_saved_contact": False}, "message": {"text": SPAN_TEXT},
        "analysis": scan_result(model_flagged=True, warning_source="both", reasons=[
            reason("upfront_payment_request", "Upfront payment request.", "Deposit $60")])}
    page.locator("#receive-btn").click()
    expect(newest(page).locator(".row-name")).to_have_text("555-0920")
    expect(newest(page).locator(".ico-warn")).to_have_count(1)
    newest(page).click()
    expect(page.locator(".warning-head")).to_contain_text("both flagged")
    expect(page.locator('.warning [data-model="flagged"]')).to_contain_text("Flagged")
    expect(page.locator(".warning [data-evidence-count='1']")).to_contain_text("1 finding")
    assert page.locator("#thread .hl").all_inner_texts() == ["Deposit $60"]
    assert all(request["sender"] != "555-0920" for request in scan_requests)


@pytest.mark.parametrize("failure", ["not_implemented", "http_error", "offline", "malformed", "timeout"])
def test_simulation_failure_is_shown_and_invents_nothing(page, live_url, failure):
    from playwright.sync_api import expect

    def fail(route):
        if failure == "offline":
            route.abort()
        elif failure == "timeout":
            pass  # Leave the request pending; the app's own timeout must fire.
        elif failure == "malformed":
            route.fulfill(status=200, content_type="application/json", body='{"sender":"555-0930"}')
        else:
            route.fulfill(status=503, content_type="application/json",
                          body='{"error":"Simulation data could not be loaded."}')

    # "not_implemented" is the real server on this branch, which has no simulation endpoint.
    if failure != "not_implemented":
        page.route("**/api/simulate", fail)
    load(page, live_url)
    rows = page.locator("#chat-list .row")
    page.locator("#receive-btn").click()
    banner = page.locator("#receive-error")
    expect(banner).to_be_visible(timeout=8000)
    expect(banner).to_contain_text("Couldn’t receive a message")
    expected = {"not_implemented": "doesn’t provide that feature yet (HTTP 405)",
                "http_error": "Simulation data could not be loaded. (HTTP 503)",
                "offline": "can’t be reached", "malformed": "can’t read", "timeout": "took too long"}
    expect(banner).to_contain_text(expected[failure])
    expect(rows).to_have_count(3)
    expect(page.locator(".warning, .hl")).to_have_count(0)
    expect(page.locator("#receive-btn")).to_be_enabled()
    expect(page.locator("#receive-label")).to_have_text("Receive random message")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if failure == "not_implemented":
        page.screenshot(path=str(SHOTS / "dynamic-receive-error-390.png"))
    banner.get_by_role("button", name="Dismiss").click()
    expect(banner).to_be_hidden()

    # Once the simulation answers, the same button works and the error clears.
    if failure != "not_implemented":
        page.unroute("**/api/simulate", fail)
    Simulation(page)
    page.locator("#receive-btn").click()
    expect(rows).to_have_count(4)
    expect(banner).to_be_hidden()


def test_scan_failure_for_a_received_chat_shows_an_error_not_a_verdict(page, live_url):
    from playwright.sync_api import expect
    simulation = Simulation(page)
    load(page, live_url)

    def fail(route):
        route.fulfill(status=503, content_type="application/json", body='{"error":"Unavailable"}')

    page.route("**/api/scan", fail)
    simulation.next_payload = {"sender": "555-0940", "is_saved_contact": False, "message": RECRUITER_TEXT}
    page.locator("#receive-btn").click()
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "error")
    newest(page).click()
    expect(page.locator('[data-scan="error"]')).to_be_visible()
    expect(page.locator(".warning, .hl, [data-scan='clean']")).to_have_count(0)
    page.unroute("**/api/scan", fail)
    page.get_by_role("button", name="Try again").click()
    expect(page.locator(".warning")).to_be_visible()
    expect(page.locator("#thread .hl").first).to_be_visible()
