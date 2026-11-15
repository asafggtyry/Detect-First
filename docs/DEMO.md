# Two-minute demo script

Before recording: follow the README, including the optional `python scripts/download_test_data.py` step for AI Evaluation. Start the server, open `http://127.0.0.1:8000/`, and choose **Chats → More options → Reset demo**. Wait for **Live classifier connected**. Rehearse at 390×844 or desktop size. This is a suggested two-minute script; the organizer's actual limit is unconfirmed.

| Time | Action | Narration |
|---|---|---|
| 0:00–0:12 | Show the three bottom tabs with **Chats** selected. | “Detect First helps students pause before responding to unfamiliar job offers. These are fictional messages in a local prototype.” |
| 0:12–0:25 | Open **Mom**, then **Back to chats**; open **124-5135-2355**, then back. | “Saved contacts are skipped by our scope rule. This unknown sender was scanned without a warning. Neither outcome proves safety.” |
| 0:25–0:40 | Press **Receive Random Message**, show the automatically opened chat, then go back. | “The server selects a synthetic message and analyzes its text. The new conversation opens automatically and appears first in Chats. A scenario label does not dictate the prediction.” |
| 0:40–1:05 | Open **732-882-1944**, tap **Deposit $60**, close the explanation, and open **See all findings**. | “The compact warning points to suspicious phrases. These explanations come from evidence rules. The model itself missed this example; the rules triggered the warning.” |
| 1:05–1:15 | Close findings, tap **Accept Anyway**, reopen the flagged banner and tap **Block**. Go back. | “Accept allows simulated replies. Block removes the reply box. Neither action contacts a real sender.” |
| 1:15–1:30 | **Test a Message** → enter “Pay an activation fee for this job today.” → **Analyze**. | “Any text can be tested. Model classification and rule findings are separate. There is no reference label, so this input is not scored.” |
| 1:30–1:50 | **AI Evaluation → Start Blind Test → Next Message**, then scroll to Running totals. | “Predictions are stored before the synthetic reference label is revealed. Correct and Incorrect compare each system with that label. Across all 32 examples, ML caught five of sixteen scams. This is not real-world accuracy.” |
| 1:50–2:00 | **Chats → More options → Reset demo**. | “The value is a clear pause-and-review experience. Better independent recruitment-message validation is still needed.” |

The random example and evaluation order vary. Describe the actual output; never promise that every recruiter-style message is flagged. Do not present a screenshot or prerecorded result as a live server response.

## Rehearsal checks

- Confirm browser Back/Forward, all three tabs, and the conversation back button.
- Confirm **Tap highlighted text in the message to learn why.**, **Block**, and **Accept Anyway** fit on the presentation device.
- After accepting, type a fictional reply; block, reset, and verify the reply and decisions are cleared. Reset demo resets chats, not an independent blind run; use **Restart Blind Test** to restart evaluation.
- Test the optional benchmark download before recording. If missing, the app displays the setup command and does not invent a score. Install it and retry.
- If the API fails, use the displayed retry path after restoring the server.
- Do not describe historical posting scores or synthetic scores as real-world recruitment-scam accuracy. The unchanged combined policy has eight false alarms on the 16 synthetic legitimate examples.
