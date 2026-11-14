# Two-minute demo script

Before recording: start the server using the README, open `http://127.0.0.1:8000/`, use **More options → Reset demo**, and wait for **Live classifier connected**. Use a 390×844 browser viewport or the desktop phone preview. Keep the local server running. Do not present a recording or screenshot as a live response. Do not spend demo time installing packages.

| Time | Action | Narration |
|---|---|---|
| 0:00–0:15 | Show chat list and prototype label. | “Detect First is a prototype for students receiving unfamiliar job offers. These are fictional chats, not WhatsApp messages. It helps someone pause and inspect an offer before replying.” |
| 0:15–0:30 | Open **Mom**. Point to the saved-contact note, then go back. | “Mom is a saved contact, so this conversation is not scanned. That is our scope rule, not a claim that every saved contact is safe.” |
| 0:30–0:45 | Open **124-5135-2355**, then go back. | “This harmless unknown sender's first message went to the live Python API and trained classifier. No warning was triggered. That does not guarantee safety, and later messages are not scanned.” |
| 0:45–1:15 | Open **732-882-1944**. Scroll the message to show the $60 deposit and $300/day claim. Scroll the evidence list. | “This recruitment message asks for a deposit and a quick reply while promising high daily earnings. The warning points to those patterns. It also tells us that this demo has not independently verified the employer.” |
| 1:15–1:35 | Point to **ML classifier did not flag this message**. | “Here is the critical distinction: the model did not flag this example. Separate evidence rules triggered the warning. The model learned from job postings, not real first-contact chats. It caught only five of sixteen scams in our small synthetic test.” |
| 1:35–1:48 | Tap **Block**. Show blocked state and absent reply box. | “Block stops replies in this simulation. Accept Anyway is available when someone chooses to continue; neither action contacts a real sender.” |
| 1:48–2:00 | Return home, use **Reset demo**. | “Reset lets us replay the demo. Our contribution is a clear pause-and-review experience with honest explanations. This is a prototype, and authentic recruitment-message validation is still unavailable.” |

Rehearse with a timer; narration is approximately 250 words plus interaction. Trim pauses to fit the organizer's actual limit, which is unconfirmed.

## Backup rehearsal checks (outside the two minutes)

- After Reset, open the recruitment chat → **Accept Anyway** → type a fictional reply → reopen **Flagged as a possible job scam** → **Block**. Confirm the reply box disappears.
- Reset again and verify choices and typed replies are cleared.
- If a connection error appears, restart the server, use **Try again**, and wait for the live status. Do not substitute fixture output or claim that a failed scan is safe.
- Never call the posting accuracy “recruitment-scam accuracy.” If asked about posting scores, disclose the near-template contamination and point to the evaluation table.
