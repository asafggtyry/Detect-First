"""Browser checks for the three-destination navigation: Chats, Test a Message, AI Evaluation.

Everything runs against the real server and saved classifier; requests are only
intercepted in the tests that simulate a backend failure.
"""
from pathlib import Path

import pytest

from test_browser import home, live_url, page  # noqa: F401

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports" / "browser"
SIZES = [(1280, 900), (390, 844), (320, 568)]

CHATS_ONLY = ["#receive-btn", "#scenario-btn", "#chat-list", "#menu-btn"]
TEST_ONLY = ["#test-message", "#analyze-btn", "#reset-test-btn"]
EVALUATION_ONLY = ["#blind-start-btn", "#blind-status"]
CHAT_ONLY = ["#back-btn", "#thread", "#dock"]


def load(page, url, width, height):
    from playwright.sync_api import expect

    page.set_viewport_size({"width": width, "height": height})
    page.goto(url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect(page.locator("#receive-btn")).to_be_enabled()


def tab(page, name):
    return page.locator("#tabbar").get_by_role("link", name=name, exact=True)


def expect_screen(page, screen):
    """Exactly one screen is active and no control from another screen is showing."""
    from playwright.sync_api import expect

    expect(page.locator("#phone")).to_have_attribute("data-screen", screen)
    groups = {"chats": CHATS_ONLY, "test": TEST_ONLY, "evaluation": EVALUATION_ONLY, "chat": CHAT_ONLY}
    for name, selectors in groups.items():
        for selector in selectors:
            if name == screen:
                expect(page.locator(selector)).to_be_visible()
            else:
                expect(page.locator(selector)).to_be_hidden()
    expect(page.locator("#scenario-menu")).to_be_hidden()
    expect(page.locator("#evidence-pop")).to_be_hidden()
    active = {"chats": "screen-home", "chat": "screen-chat", "test": "screen-test", "evaluation": "screen-blind"}
    for name, element in active.items():
        assert page.locator(f"#{element}").evaluate("node => node.hasAttribute('inert')") == (name != screen)
    if screen == "chat":
        expect(page.locator("#tabbar")).to_be_hidden()
        expect(page.get_by_role("button", name="Back to chats")).to_be_visible()
    else:
        # Every destination keeps the same visible way back to Chats.
        expect(tab(page, "Chats")).to_be_in_viewport(ratio=1)
        expect(tab(page, "Test a Message")).to_be_in_viewport(ratio=1)
        expect(tab(page, "AI Evaluation")).to_be_in_viewport(ratio=1)
        current = "chats" if screen == "chats" else screen
        expect(page.locator('#tabbar a[aria-current="page"]')).to_have_count(1)
        expect(page.locator('#tabbar a[aria-current="page"]')).to_have_attribute("data-tab", current)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def receive(page):
    with page.expect_response(lambda response: response.url.endswith("/api/demo/receive")) as response:
        page.locator("#receive-btn").click()
    assert response.value.status == 200
    return response.value.json()["conversation"]


def choose_category(page, scenario):
    page.get_by_role("button", name="Choose demo scenario").click()
    page.locator(f'[data-scenario="{scenario}"]').click()


@pytest.mark.parametrize("width,height", SIZES)
def test_app_opens_to_chats_and_each_destination_shows_only_its_own_controls(page, live_url, width, height):
    from playwright.sync_api import expect

    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    load(page, live_url, width, height)
    expect_screen(page, "chats")
    expect(page.locator("#screen-home .appbar-title")).to_have_text("Detect First")
    expect(page.locator("#chat-list .row")).to_have_count(3)
    expect(page.get_by_role("button", name="Receive Random Message", exact=True)).to_be_in_viewport(ratio=1)
    expect(page.locator("#scenario-current")).to_have_text("Random")
    expect(page.locator("#scenario-btn")).to_be_in_viewport(ratio=1)
    # The full label fits, even at 320px.
    assert page.locator("#receive-label").evaluate("node => node.scrollWidth <= node.clientWidth")
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(animations="disabled", path=str(SHOTS / f"nav-chats-{width}.png"))

    tab(page, "Test a Message").click()
    expect_screen(page, "test")
    expect(page.locator("#screen-test .appbar-title")).to_have_text("Test a Message")
    expect(page.locator("#test-unscored")).to_contain_text("Not scored")
    page.screenshot(animations="disabled", path=str(SHOTS / f"nav-test-{width}.png"))

    tab(page, "AI Evaluation").click()
    expect_screen(page, "evaluation")
    expect(page.locator("#screen-blind .appbar-title")).to_have_text("AI Evaluation")
    expect(page.get_by_role("button", name="Start Blind Test", exact=True)).to_be_visible()
    expect(page.locator("#blind-synthetic")).to_contain_text("not proof of real-world accuracy")
    expect(page.locator("#blind-sample")).to_be_hidden()

    tab(page, "Chats").click()
    expect_screen(page, "chats")

    # An open conversation covers the tab bar and offers its own way back.
    page.locator('[data-chat="u2"]').click()
    expect_screen(page, "chat")
    # The root URL is always Chats, never a previously opened conversation.
    page.goto(live_url)
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect_screen(page, "chats")
    page.goto(live_url + "/#/chat/does-not-exist")
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect_screen(page, "chats")
    assert not errors


@pytest.mark.parametrize("width,height", SIZES)
def test_received_message_opens_its_conversation_with_the_real_result_and_persists(page, live_url, width, height):
    from playwright.sync_api import expect

    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.post_data_json)
            if request.url.endswith("/api/demo/receive") else None)
    load(page, live_url, width, height)

    def check_open_conversation(conversation):
        """The opened chat is the backend's conversation and shows its genuine analysis."""
        expect_screen(page, "chat")
        assert page.evaluate("location.hash") == "#/chat/" + conversation["id"]
        expect(page.locator("#thread .bubble-in .bubble-text").last).to_have_text(
            conversation["messages"][-1]["text"])
        analysis = conversation["analysis"]
        if conversation["saved_contact"]:
            expect(page.get_by_text("Saved contact · not scanned", exact=True)).to_be_visible()
            expect(page.locator(".warning, .hl, [data-scan]")).to_have_count(0)
        elif analysis["is_scam"]:
            expect(page.locator(".warning h2")).to_have_text("Potential job scam detected")
            assert page.locator("#thread .hl").all_inner_texts() == [
                span["excerpt"] for span in analysis["evidence_spans"]]
        else:
            # Includes recruiter-style messages the detector missed: no warning is forced.
            expect(page.locator('[data-scan="clean"]')).to_be_visible()
            expect(page.locator(".warning, .hl")).to_have_count(0)

    def back_to_chats_with_top_row(conversation):
        home(page)
        expect_screen(page, "chats")
        expect(page.locator("#chat-list .row").first).to_have_attribute("data-chat", conversation["id"])

    # Random is the default category and sends no scenario to the backend.
    random_chat = receive(page)
    assert requests[-1] == {}
    check_open_conversation(random_chat)
    expect(page.locator("#toast")).to_contain_text("New message from")
    page.screenshot(animations="disabled", path=str(SHOTS / f"nav-received-chat-{width}.png"))
    back_to_chats_with_top_row(random_chat)

    # The category picker beside the button chooses the sample type only.
    choose_category(page, "family_friend")
    expect(page.locator("#scenario-current")).to_have_text("Family")
    expect(page.get_by_role("button", name="Receive Message", exact=True)).to_be_visible()
    family = receive(page)
    assert requests[-1] == {"scenario_label": "family_friend"}
    assert family["saved_contact"] is True and family["analysis"]["scanned"] is False
    check_open_conversation(family)
    back_to_chats_with_top_row(family)

    choose_category(page, "potential_fraudulent_recruiter")
    expect(page.locator("#scenario-current")).to_have_text("Recruiter")
    recruiters = []
    for _ in range(10):
        recruiter = receive(page)
        assert requests[-1] == {"scenario_label": "potential_fraudulent_recruiter"}
        assert recruiter["saved_contact"] is False and recruiter["analysis"]["scanned"] is True
        check_open_conversation(recruiter)
        back_to_chats_with_top_row(recruiter)
        recruiters.append(recruiter)
    # The fixtures contain both caught and missed recruiter messages; each was shown as analyzed.
    assert any(item["analysis"]["is_scam"] for item in recruiters)
    assert any(not item["analysis"]["is_scam"] for item in recruiters)

    choose_category(page, "random")
    expect(page.locator("#scenario-current")).to_have_text("Random")
    expect(page.get_by_role("button", name="Receive Random Message", exact=True)).to_be_visible()

    # Received conversations survive other destinations and a reload.
    received = {random_chat["id"], family["id"]} | {item["id"] for item in recruiters}
    count = 3 + len(received - {"mom", "u1", "u2"})
    tab(page, "Test a Message").click()
    expect_screen(page, "test")
    tab(page, "Chats").click()
    expect_screen(page, "chats")
    expect(page.locator("#chat-list .row")).to_have_count(count)
    page.reload()
    expect(page.locator("#scan-status")).to_have_attribute("data-kind", "live")
    expect_screen(page, "chats")
    expect(page.locator("#chat-list .row")).to_have_count(count)
    expect(page.locator("#chat-list .row").first).to_have_attribute("data-chat", recruiters[-1]["id"])
    assert len(requests) == 12
    assert not errors


@pytest.mark.parametrize("width,height", SIZES)
def test_test_a_message_is_independent_and_unscored(page, live_url, width, height):
    from playwright.sync_api import expect

    other_requests, analyze_requests = [], []
    page.on("request", lambda request: analyze_requests.append(request.post_data_json)
            if request.url.endswith("/api/analyze") else None)
    page.on("request", lambda request: other_requests.append(request.url)
            if "/api/" in request.url and not request.url.endswith("/api/analyze") else None)
    load(page, live_url, width, height)
    tab(page, "Test a Message").click()
    expect_screen(page, "test")
    before = len(other_requests)

    message = "Hi, we're hiring for a remote assistant. Deposit $25 today to get started. Reply now for details."
    with page.expect_response(lambda response: response.url.endswith("/api/analyze")) as response:
        page.get_by_role("textbox", name="Message to analyze").fill(message)
        page.get_by_role("button", name="Analyze", exact=True).click()
    result = response.value.json()
    expect(page.locator("#test-status")).to_have_text("Analysis complete.")
    # The model's prediction and the evidence-rule signals are shown as separate sections.
    expect(page.locator("#test-model-title")).to_have_text("Model classification")
    expect(page.locator("[data-model-result]")).to_have_attribute(
        "data-model-result", "flagged" if result["model_flagged"] else "not-flagged")
    expect(page.locator("#test-evidence-title")).to_have_text("Evidence-based warning categories")
    assert result["reasons"]
    for reason in result["reasons"]:
        item = page.locator(f'[data-evidence="{reason["category"]}"]')
        expect(item).to_contain_text(reason["evidence"])
        if reason.get("snippet"):
            expect(item.locator(".test-snippet")).to_contain_text(reason["snippet"])
    expect(page.locator('[data-evidence="upfront_payment_request"] .test-snippet')).to_contain_text("Deposit $25")
    # Unscored: no reference label and no Correct/Incorrect verdict for arbitrary input.
    expect(page.locator("#test-unscored")).to_be_visible()
    text = page.locator("#screen-test").inner_text()
    assert "Reference label" not in text and "Correct" not in text and "Incorrect" not in text
    page.locator("#test-result").scroll_into_view_if_needed()
    page.screenshot(animations="disabled", path=str(SHOTS / f"nav-test-result-{width}.png"))

    # Nothing else was called, and the chats are untouched.
    assert analyze_requests == [{"message": message}]
    assert len(other_requests) == before
    tab(page, "Chats").click()
    expect_screen(page, "chats")
    expect(page.locator("#chat-list .row")).to_have_count(3)
    assert message not in (page.evaluate("localStorage.getItem('detect-first-demo-v1')") or "")
    # The draft and result are still there when coming back.
    tab(page, "Test a Message").click()
    expect(page.get_by_role("textbox", name="Message to analyze")).to_have_value(message)
    expect(page.locator("#test-verdict")).to_be_visible()


@pytest.mark.parametrize("width,height", SIZES)
def test_ai_evaluation_reveals_reference_label_and_keeps_readable_running_totals(page, live_url, width, height):
    from playwright.sync_api import expect

    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    load(page, live_url, width, height)
    tab(page, "AI Evaluation").click()
    expect_screen(page, "evaluation")
    expect(page.locator("#blind-next-btn")).to_be_hidden()
    expect(page.locator("#blind-results")).to_be_hidden()

    def check(result):
        scam = bool(result["reference_label"])
        expect(page.locator("#blind-sample-meta")).to_contain_text(
            f'Message {result["sample_index"]} of {result["total_samples"]}')
        expect(page.locator("#blind-sample-text")).to_have_text(result["text"])
        expect(page.locator(".blind-reference")).to_contain_text("Reference label")
        expect(page.locator(".blind-reference strong")).to_have_text("Scam" if scam else "Not a scam")
        expect(page.locator(".blind-reference")).to_contain_text("after the predictions")
        systems = [("model", "model_prediction", "Trained model"),
                   ("evidence_rules", "evidence_prediction", "Evidence rules"),
                   ("combined_warning", "combined_prediction", "Combined system")]
        expect(page.locator("#blind-predictions .blind-row")).to_have_count(3)
        expect(page.locator("#blind-metrics tr")).to_have_count(3)
        for key, prediction, name in systems:
            flagged = bool(result[prediction])
            row = page.locator(f'#blind-predictions [data-system="{key}"]')
            expect(row.locator(".blind-row-name")).to_have_text(name)
            expect(row.locator(".blind-row-prediction")).to_have_text("Flagged as scam" if flagged else "Not flagged")
            expect(row.locator(".blind-verdict")).to_have_text("Correct" if flagged == scam else "Incorrect")
            if flagged != scam:
                expect(row.locator(".blind-row-why")).to_have_text("Missed scam" if scam else "False alarm")
            metric = result["metrics"][key]
            total = page.locator(f'#blind-metrics [data-system="{key}"]')
            expect(total.locator("th strong")).to_have_text(name)
            expect(total.locator('[data-total="correct"]')).to_have_text(
                f'{metric["true_positives"] + metric["true_negatives"]} of {metric["examples"]}')
            expect(total.locator('[data-total="missed"]')).to_have_text(str(metric["false_negatives"]))
            expect(total.locator('[data-total="false-alarms"]')).to_have_text(str(metric["false_positives"]))
        expect(page.locator("#blind-tested")).to_have_text(
            f'Messages Tested: {result["sample_index"]} of {result["total_samples"]}')

    with page.expect_response(lambda response: response.url.endswith("/api/evaluation/next")) as response:
        page.get_by_role("button", name="Start Blind Test", exact=True).click()
    first = response.value.json()
    assert first["sample_index"] == 1
    check(first)
    expect(page.get_by_role("button", name="Restart Blind Test", exact=True)).to_be_visible()
    for button in ["#blind-start-btn", "#blind-next-btn"]:
        assert page.locator(button).evaluate("node => node.scrollWidth <= node.clientWidth")

    results = [first]
    for _ in range(31):
        with page.expect_response(lambda response: response.url.endswith("/api/evaluation/next")) as response:
            page.get_by_role("button", name="Next Message", exact=True).click()
        results.append(response.value.json())
        check(results[-1])
    assert [item["sample_index"] for item in results] == list(range(1, 33))
    assert len({item["sample_id"] for item in results}) == 32
    expect(page.locator("#blind-next-btn")).to_be_hidden()
    expect(page.locator("#blind-status")).to_contain_text("All 32 messages were tested")
    assert any(row["model_prediction"] != row["reference_label"] for row in results)
    assert any(row["model_prediction"] == row["reference_label"] for row in results)

    # Readable column names, no unexplained abbreviations, and an explicit synthetic-data notice.
    headers = page.locator("#screen-blind thead th").all_inner_texts()
    assert [header.strip() for header in headers] == ["System", "Correct", "Missed Scams", "False Alarms"]
    assert all(page.locator("#screen-blind thead th").nth(index).get_attribute("title") for index in (1, 2, 3))
    words = page.locator("#screen-blind").inner_text().replace("\n", " ").split()
    assert not {"TP", "TN", "FP", "FN", "F1", "N", "Precision", "Recall"} & set(words)
    expect(page.locator("#blind-synthetic")).to_be_visible()
    expect(page.locator("#blind-provenance")).to_contain_text("Synthetic demonstration only")
    expect(page.locator("#blind-results-title")).to_have_text("Running totals")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.locator(".blind-table-wrap").evaluate("node => node.scrollWidth <= node.clientWidth")
    page.locator("#blind-sample").scroll_into_view_if_needed()
    page.screenshot(animations="disabled", path=str(SHOTS / f"nav-evaluation-{width}.png"))
    page.locator("#blind-results").scroll_into_view_if_needed()
    page.screenshot(animations="disabled", path=str(SHOTS / f"nav-evaluation-totals-{width}.png"))

    # Progress is kept while visiting another destination, and Restart begins a fresh run.
    tab(page, "Chats").click()
    expect_screen(page, "chats")
    expect(page.locator("#chat-list .row")).to_have_count(3)
    tab(page, "AI Evaluation").click()
    check(results[-1])
    with page.expect_response(lambda response: response.url.endswith("/api/evaluation/next")) as response:
        page.get_by_role("button", name="Restart Blind Test", exact=True).click()
    restarted = response.value.json()
    assert restarted["sample_index"] == 1
    check(restarted)
    assert not errors


@pytest.mark.parametrize("width,height", SIZES)
def test_browser_back_and_forward_move_between_destinations(page, live_url, width, height):
    from playwright.sync_api import expect

    load(page, live_url, width, height)
    expect_screen(page, "chats")
    tab(page, "Test a Message").click()
    expect_screen(page, "test")
    tab(page, "AI Evaluation").click()
    expect_screen(page, "evaluation")
    page.go_back()
    expect_screen(page, "test")
    page.go_back()
    expect_screen(page, "chats")
    page.go_forward()
    expect_screen(page, "test")
    page.go_forward()
    expect_screen(page, "evaluation")
    tab(page, "Chats").click()
    expect_screen(page, "chats")

    page.locator('[data-chat="u2"]').click()
    expect_screen(page, "chat")
    expect(page.locator("#chat-name")).to_have_text("732-882-1944")
    page.go_back()
    expect_screen(page, "chats")
    page.go_forward()
    expect_screen(page, "chat")
    expect(page.locator("#chat-name")).to_have_text("732-882-1944")
    home(page)
    expect_screen(page, "chats")

    # A received message's conversation is a normal history entry too.
    conversation = receive(page)
    expect_screen(page, "chat")
    page.go_back()
    expect_screen(page, "chats")
    expect(page.locator("#chat-list .row").first).to_have_attribute("data-chat", conversation["id"])
    page.go_forward()
    expect_screen(page, "chat")
    assert page.evaluate("location.hash") == "#/chat/" + conversation["id"]


@pytest.mark.parametrize("width,height", SIZES)
def test_highlights_block_accept_and_reset_still_work(page, live_url, width, height):
    from playwright.sync_api import expect

    load(page, live_url, width, height)
    page.locator('[data-chat="u2"]').click()
    expect_screen(page, "chat")
    expect(page.locator(".warning h2")).to_have_text("Potential job scam detected")
    for name in ["Block", "Accept Anyway"]:
        expect(page.get_by_role("button", name=name, exact=True)).to_be_in_viewport(ratio=1)

    mark = page.locator('#thread .hl[data-category="upfront_payment_request"]')
    mark.click()
    popup = page.locator("#evidence-pop")
    expect(popup).to_be_in_viewport(ratio=1)
    expect(page.locator("#evidence-pop-category")).to_have_text("Upfront payment request")
    expect(page.locator("#evidence-pop-phrase")).to_have_text(f"“{mark.inner_text()}”")
    expect(page.locator("#evidence-pop-note")).to_contain_text("Rule-based observation")
    page.keyboard.press("Escape")
    expect(popup).to_be_hidden()
    mark.focus()
    page.keyboard.press("Enter")
    expect(popup).to_be_visible()
    page.get_by_role("button", name="Close explanation").click()
    expect(popup).to_be_hidden()

    page.get_by_role("button", name="Accept Anyway", exact=True).click()
    expect(page.locator('[data-state="accepted"]')).to_be_visible()
    expect(page.get_by_role("textbox", name="Type a message")).to_be_visible()
    page.get_by_role("button", name="Flagged as a possible job scam").click()
    page.get_by_role("button", name="Block", exact=True).click()
    expect(page.locator('[data-state="blocked"]')).to_be_visible()
    expect(page.get_by_role("textbox", name="Type a message")).to_have_count(0)
    home(page)
    expect_screen(page, "chats")
    expect(page.locator('[data-chat="u2"]')).to_contain_text("You blocked this contact")

    received = receive(page)
    expect_screen(page, "chat")
    home(page)
    expect(page.locator("#chat-list .row")).to_have_count(3 if received["id"] in {"mom", "u1", "u2"} else 4)

    page.get_by_role("button", name="More options").click()
    page.get_by_role("menuitem", name="Reset demo").click()
    expect(page.locator("#toast")).to_contain_text("Demo reset")
    expect_screen(page, "chats")
    rows = page.locator("#chat-list .row")
    expect(rows).to_have_count(3)
    assert [row.get_attribute("data-chat") for row in rows.all()] == ["mom", "u1", "u2"]
    expect(page.locator('[data-chat="u2"]')).not_to_contain_text("You blocked this contact")
    page.locator('[data-chat="u2"]').click()
    expect(page.get_by_role("button", name="Accept Anyway", exact=True)).to_be_visible()


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("failure", ["http_error", "offline", "malformed"])
def test_backend_errors_never_create_fake_messages_or_results(page, live_url, width, height, failure):
    from playwright.sync_api import expect

    def fail(route):
        if failure == "offline":
            route.abort()
        elif failure == "malformed":
            route.fulfill(status=200, content_type="application/json", body='{"conversation":{"id":"x"}}')
        else:
            route.fulfill(status=503, content_type="application/json", body='{"error":"Unavailable"}')

    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    load(page, live_url, width, height)
    page.route("**/api/demo/receive", fail)
    page.route("**/api/evaluation/start", fail)
    page.locator("#receive-btn").click()
    banner = page.locator("#receive-error")
    expect(banner).to_be_visible()
    expect(banner).to_be_in_viewport(ratio=1)
    assert banner.inner_text().strip()
    # No conversation was invented or opened, and the button is usable again.
    expect_screen(page, "chats")
    expect(page.locator("#chat-list .row")).to_have_count(3)
    assert page.evaluate("location.hash") in ("", "#/")
    expect(page.locator("#receive-btn")).to_be_enabled()
    expect(page.get_by_role("button", name="Receive Random Message", exact=True)).to_be_visible()
    if (width, failure) == (390, "http_error"):
        page.screenshot(animations="disabled", path=str(SHOTS / "nav-receive-error-390.png"))

    tab(page, "AI Evaluation").click()
    expect_screen(page, "evaluation")
    page.get_by_role("button", name="Start Blind Test", exact=True).click()
    expect(page.locator("#blind-status")).to_contain_text("No result was made up")
    expect(page.locator("#blind-sample")).to_be_hidden()
    expect(page.locator("#blind-results")).to_be_hidden()
    expect(page.locator("#blind-predictions .blind-row")).to_have_count(0)
    expect(page.get_by_role("button", name="Start Blind Test", exact=True)).to_be_enabled()

    # Once the backend answers again, the same buttons work.
    page.unroute("**/api/demo/receive", fail)
    page.unroute("**/api/evaluation/start", fail)
    page.get_by_role("button", name="Start Blind Test", exact=True).click()
    expect(page.locator("#blind-sample")).to_be_visible()
    tab(page, "Chats").click()
    conversation = receive(page)
    expect_screen(page, "chat")
    assert page.evaluate("location.hash") == "#/chat/" + conversation["id"]
    expect(page.locator("#receive-error")).to_be_hidden()
    assert not errors
