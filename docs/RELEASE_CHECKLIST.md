# Final release checklist

- [x] Base the new `release/final-detect-first` branch on Fable's `91199a1`.
- [x] Preserve existing worktrees, uncommitted work and `release/veritas-2026`.
- [x] Integrate only the research document and backend leakage tests from `9d44f39`.
- [x] Keep both model artifacts and the production warning policy unchanged.
- [x] Start and serve real predictions without raw datasets; load benchmark data lazily.
- [x] Give actionable benchmark errors and preserve evaluation progress on prediction failure.
- [x] Reproduce the stored ML/rules/combined synthetic confusion matrices.
- [x] Update fresh-clone setup, runtime dependencies, navigation walkthrough and demo script.
- [x] Confirm final full-suite results and screenshot review in [verification](../reports/final_release_verification.md).
- [x] Restrict delivery to the new release branch; preserve the remote default and backup.

Before submission, the team must confirm organizer requirements/deadline, team
names and roles, AI disclosures, judge access and any required video or hosting.
See [submission checklist](SUBMISSION_CHECKLIST.md). No default-branch change,
repository publication, deployment, or hackathon submission is authorized by
this checklist; those remain separate user decisions.

Presentation-machine check: install dependencies with the README commands,
download the optional benchmark data before showing AI Evaluation, launch the
same-origin Python server, rehearse all three tabs, and verify Reset demo.
Use `--port 8001` if port 8000 is occupied; do not stop unrelated applications.
