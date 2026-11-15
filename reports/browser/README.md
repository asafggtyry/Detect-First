# Browser verification images

These PNGs are captured from real Chromium interactions with the local Python
server and saved production classifier. The final suite uses 1280×900 desktop
mode, 390×844 mobile mode and 320×568 mobile mode. Filenames end with the
viewport width. Screenshots disable animations only during capture so that
transitional opacity is not mistaken for the settled layout; application
animations remain enabled during the interactions.

Current release captures:

- `nav-chats-*`, `nav-test-*`, `nav-test-result-*`: destinations and live analysis.
- `nav-received-chat-*`, `dynamic-live-*`: actual server-generated conversations.
- `warning-*`, `highlight-explanation-*`, `all-findings-*`: compact warning and
  backend evidence explanations.
- `nav-evaluation-*`, `nav-evaluation-totals-*`: synthetic evaluation and all-32
  running totals from actual stored predictions. Sample order is randomized.
- `benchmark-unavailable-*`: real HTTP 503 with optional dataset setup instructions.
- `nav-receive-error-390`, `reset-error-*`, `warning-review-*`: deliberately
  injected transport/span failures; these are error-state tests, not successful
  inference results. The test source identifies each interception.

Other images inherited from earlier branches are historical. The final
[verification report](../final_release_verification.md) and
[JUnit report](../final_release_tests.xml) are the authority for this release's
test counts and coverage. Screenshots illustrate individual states; the tests
verify behavior, request payloads, predictions, history, and retry recovery.
