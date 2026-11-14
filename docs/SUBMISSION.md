# Detect First — hackathon write-up

**Prototype for the Veritas AI 2026 hackathon. Intended track: AI + Finance; official track and submission requirements still need confirmation.**

## Problem and audience

Students looking for their first job may encounter unfamiliar recruiters promising easy earnings or asking for payment before work begins. Detect First helps high school students pause and inspect a first-contact job message before replying. It is an educational messaging simulation, not a deployed fraud-prevention service.

## What we built and what is original

A WhatsApp-inspired interface combines three fictional conversations, a first-message-only scan policy, a real locally trained text classifier, transparent rule observations, and a choice to Block or Accept Anyway. Saved contacts bypass scanning; Reset makes the scenarios repeatable. The project's contribution is this interaction and its explicit separation of learned predictions from deterministic evidence. We do not claim to have invented text classification or to be the first scam-warning application.

## Technical approach

Plain HTML, CSS and JavaScript call a same-origin Flask API. A saved scikit-learn pipeline uses word unigram/bigram TF-IDF and balanced logistic regression trained on an EMSCAD-derived OpenML job-posting dataset. The API returns the model's Boolean prediction separately from evidence categories and the combined warning decision. The app warns if the model flags the text or at least two rule categories appear. Rules inspect wording and client-supplied sender context; they do not verify employers. Failure shows a connection error, never a sample result. There is no paid model API or messaging integration.

## Measured results

The historical 2,505-posting holdout reproduces 96.81% accuracy, 61.16% precision, 69.16% recall and 64.91% F1, with 47 false positives and 33 false negatives. The always-legitimate baseline achieves 95.73% accuracy and zero fraud recall. **The posting holdout has known near-template contamination: the prior audit found 548 near matches, including three exact matches after stronger normalization. These are historical comparisons, not clean generalization estimates.**

On 32 hand-authored synthetic messages, the classifier catches only 5 of 16 synthetic scams, misses 11, and flags none of 16 legitimate examples. It catches 2 of 8 subtle scams. A fixed keyword baseline catches 6 of 16. The rejected candidate catches 4 of 16 overall and none of 8 subtle scams, so the original model remains in use. These small, previously exposed synthetic examples are not real-world validation. See [evaluation tables](EVALUATION.md) and the [release test report](../reports/release_verification.md).

## Limitations and responsible scope

Authentic first-contact recruitment validation is unavailable. Job postings differ from short chats, the dataset is imbalanced, rules can misread negation or context, and sender metadata is supplied by the client. In fact, an unknown first-contact job message can already accumulate two context categories and trigger a warning without a fee or deadline. Rules are not independent proof. Later messages are intentionally unscanned. A warning does not prove fraud; no warning does not prove safety. Block affects this simulation only. No employer is independently verified.

The demo runs locally with fictional messages. Incoming scan text is processed in memory; sender IDs, message hashes and results remain in server memory, while simulated replies and choices persist in this browser. No real phone, WhatsApp or employer account is accessed.

## Credits and disclosure

Dataset: OpenML 46655 (`fake_job_postings2`), derived from EMSCAD; original dataset credited to the University of the Aegean Laboratory of Information & Communication Systems Security. Synthetic patterns: FTC job-scam guidance. UI: the repository's Fable frontend, inspired by WhatsApp, with no affiliation. Libraries include scikit-learn, Flask, Streamlit, joblib, pytest and Playwright. Earlier README credits GitHub Copilot SDK; OpenAI Codex assisted release engineering, testing and documentation. Team members must confirm their names, roles and complete AI-tool disclosures before submission. See [provenance](../data/source.md).
