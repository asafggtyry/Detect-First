# False-positive reduction protocol — fixed before development scoring

Base: `release/final-detect-first` at `16c657c853a90b7d63d6ca0272141d7ae9713d3a`.
Date: 2026-11-14, America/New_York. This is a rule-policy experiment only.

## Isolation and prior exposure

Do not change frontend, production model, evidence.py, state.py, server.py,
existing synthetic evaluation, demo fixtures, or production warning policy.
Experimental code has no production import/call path. Do not fit any model.
The current 32-example final set and its error taxonomy are already exposed:
the preceding release work exercised those messages, and existing research
describes errors. This cannot become a genuinely unseen test by renaming it.
Do not inspect its message rows to develop rules, tune thresholds, or select.

## Development data and labels

Author 80 new fictional messages, 40 legitimate and 40 fraudulent, with
preassigned labels and per-row origin/rationale. Labels describe the author's
scenario intent; a message's politeness, absence of indicators, or detector
output never supplies its label. Include genuine hiring/interview/payroll,
benefits, warehouse logistics, negation and scam education, as well as payment,
gift-card, check, money-transfer, home-reshipping and credential scenarios.
Include subtle scams with insufficient textual evidence and legitimate messages
that mention risky topics. All are first-contact evaluation scenarios; some
describe previously completed hiring with a new HR contact.

The same AI authors the examples and rules. Labels are fixed independently of
predictions, **not** independently human-adjudicated. Public agency guidance is
qualitative provenance for scenario construction, not a labeled message dataset.
The synthetic negative employers are stipulated genuine; this is not verified
from message text. No copied public/private messages or personal data.

Existing job/SMS development sets were reviewed for provenance and suitability.
Their posting-fraud and ham/spam labels cannot be reinterpreted as first-contact
scam labels, so they will not be the policy-selection endpoint.

Freeze and commit development data and this protocol before scoring. Run an
automated separation audit (without displaying final/demo messages): normalized
exact equality and TF-IDF word 1–2 gram cosine >=0.85 against final and all demo
texts. Abort on overlap; do not optimize examples against final scores. Also
report internal development duplicates. This does not prove semantic independence.

## Fixed candidate family

1. `strong_actions`: require affirmative combinations describing an applicant
   payment prerequisite, gift-card purchase/code transfer, check deposit plus
   money forwarding, personal-account money movement, home parcel receiving plus
   reshipping, or transmission of authentication secrets.
2. `strong_actions_sensitive`: the same plus an affirmative request for bank
   account/routing/identity information in an early-hiring or reply/chat context.

Ordinary job/hiring/interview/pay words, a missing employer verification, missing
role vocabulary, salary amount and urgency alone never constitute a candidate
warning. Use bounded sentence-local action/object matches with local negation
and education suppression; recruitment context may span sentences. Preserve
matched evidence offsets. Candidate signals are rule observations, not ML
explanations. Document limitations of lexical negation, spoofed context and
paraphrases. Freeze exact implementation before development scoring; no outcome-
driven revisions. Backend unit tests may correct implementation errors before
the first development score, never by consulting final examples.

## Comparison and selection (predetermined)

Report ML alone, original rules, original combined, both candidate rules, and
both candidate combined policies. Combined always means unchanged ML OR rules.
For each report TP/TN/FP/FN, precision, recall, F1, FPR and per-family errors.

Select using **development combined-policy results only**. Eligible candidates
must have FPR <=5% (at most 2/40 legitimate messages), strictly fewer FP than
original combined, no more FN than original combined, and F1 at least 0.05 above
original combined. Rank eligible policies by highest F1, then fewer FP, fewer FN,
then prefer `strong_actions`. If none qualify, retain original for production
recommendation but select the highest-ranked development candidate for a
**diagnostic** final comparison, explicitly marked ineligible. This fallback
keeps the requested final comparison informative without hiding a failed
development gate. Both candidates are always ranked by F1, fewer FP, fewer FN,
then `strong_actions`; eligibility takes precedence. This fallback was clarified
before any scoring, not in response to results. Do not use final results to
choose between candidates or reverse a failed development gate.

Save all development predictions and commit a selection artifact binding hashes
of code, data, protocol, production artifact, development report and separation
audit. A one-shot final command must verify hashes and a clean tree, create an
exclusive run marker **before** inference, and refuse a repeat or overwrite.
Evaluate only the development-selected policy, plus original and ML
comparators, on all 32 final messages once. Predict from text before adding the
label to the result. Report errors without revising policy afterwards.

Existing backend regressions may separately exercise the frozen original model
on the historical final set; they do not run candidate final inference or select
its policy. Run all backend tests before the one-shot candidate final evaluation.
Candidate tests must use new regression texts, not final or demo examples.

## Decision boundary

Synthetic development improvement and historical final improvement support
further testing, not real-world accuracy or automatic deployment. Recommend
keeping the stable production policy until independent human labeling and a new
prospective first-contact test support approval. Report the candidate's empirical
strengths even if the release recommendation remains conservative. No production
policy change without explicit user approval. Commit/push only this experiment.
