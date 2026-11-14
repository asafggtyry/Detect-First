"""Capture real responses from the separately started local CLI server."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    assert urlparse(base).hostname in {"127.0.0.1", "localhost"}, "Use a local demo server"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844},
                                      is_mobile=True, has_touch=True)
        page = context.new_page()
        urls, scans, errors = [], [], []
        page.on("request", lambda request: urls.append(request.url))
        page.on("response", lambda response: scans.append({
            "request": response.request.post_data_json,
            "status": response.status, "response": response.json(),
        }) if response.url.endswith("/api/scan") else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        expect(page.locator("#scan-status")).to_have_text("Live classifier connected.")
        for width, height in [(390, 844), (320, 568)]:
            page.set_viewport_size({"width": width, "height": height})
            page.screenshot(path=str(ROOT / f"reports/browser/home-{width}.png"))
        assert len(scans) == 2 and not errors
        assert all(urlparse(url).netloc == urlparse(base).netloc for url in urls)
        assert all("demo-fixtures" not in url for url in urls)
        by_sender = {scan["request"]["sender"]: scan["response"] for scan in scans}
        assert by_sender["124-5135-2355"]["warning_source"] == "none"
        recruitment = by_sender["732-882-1944"]
        assert recruitment["warning_source"] == "evidence" and recruitment["model_flagged"] is False
        mom = context.request.post(base + "/api/scan", data={
            "message": "How are you?", "sender": "Mom",
            "is_saved_contact": True, "is_first_message": True,
        })
        assert mom.ok and mom.json()["skipped_reason"] == "saved_contact"
        private_paths = {path: context.request.get(base + path).status for path in [
            "/models/job_posting_classifier.joblib", "/.git/config",
            "/data/raw/fake_job_postings2.arff",
        ]}
        assert all(status == 404 for status in private_paths.values())
        report = dict(url=base, frontend_scan_requests=scans,
                      saved_contact_direct_api=mom.json(),
                      all_page_requests_same_origin=True, fixture_script_loaded=False,
                      javascript_errors=errors, private_paths_http_status=private_paths)
        (ROOT / "reports/release_demo_responses.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
        browser.close()
        print("Live CLI demo verified: 2 real frontend scans, saved-contact exclusion, no external requests or fixture scripts.")


if __name__ == "__main__":
    main()
