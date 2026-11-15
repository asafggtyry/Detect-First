# First-contact policy development set

`false_positive_reduction.jsonl` contains 80 new authored fictional messages:
40 legitimate-intent and 40 fraudulent-intent scenarios. It is separate from
`data/synthetic/evaluation.jsonl` and all demo fixtures. Labels, origins and
rationales were written before detector implementation/scoring and committed
with the comparison protocol. No record is an authentic verified recruitment
message. The same AI authored data and policy; no independent human adjudication
has occurred. "Independent labels" here means independent of predictions, not
independent annotators. Do not market this set as real-world validation.

Each record has `id`, `text`, binary `label`, `family`, `origin`,
`label_rationale`, `label_method`, and `synthetic`. Labels describe stipulated
scenario intent. Negative examples assume genuine employers/educators, not
merely an absence of suspicious words. Four positive `latent_deception` examples
intentionally conceal intent in an ordinary first message. Text-only inference
cannot reliably distinguish such messages from genuine approaches.

Origin keys (reviewed 2026-11-14):

| Key | Source and role |
|---|---|
| `ftc_jobs` | [FTC Job Scams](https://consumer.ftc.gov/articles/job-scams): qualitative patterns for applicant fees, fake checks and home reshipping. |
| `ftc_hiring` | [FTC: Job scammers are looking to hire you](https://consumer.ftc.gov/consumer-alerts/2025/07/job-scammers-are-looking-hire-you): early requests for financial/identity information. |
| `ftc_scams` | [FTC: How To Avoid a Scam](https://consumer.ftc.gov/articles/how-avoid-scam): payment demands, gift-card codes and unsolicited sensitive-information requests. Authentication-secret cases are author-constructed extensions, not source-provided labeled examples. |
| `fbi_mules` | [FBI Money Mules](https://www.fbi.gov/how-we-can-help-you/common-frauds-and-scams/money-mules): moving another party's funds through a personal account in a job scheme. |
| `author_legitimate` | Newly authored benign controls, including recruiting, interviews, employer-paid benefits, post-hire HR, corporate logistics, warnings/negation and unrelated contacts. No claim of external verification. |
| `author_latent` | Newly authored fictional scam-intent controls with no overt indicator in the first message. |

Agency guidance informed scenario concepts only. Message wording is newly
authored, not quoted source messages; public advice does not verify these labels.
No real phone numbers, identity credentials or private communications were used.

Existing grouped development data reviewed: 2,214 posting examples and 1,030
SMS examples in the checksum-verified frozen `improvement_split.joblib` cache.
Posting labels describe ads; SMS labels mean ham/spam. Neither label ontology
establishes first-contact recruitment fraud. No relabeling or retraining is done.
The previously selected `joint_hybrid_prefix` model remains a rejected research
artifact; it is neither loaded nor selected for this policy experiment.

Selection and one-shot final-evaluation safeguards are defined in
[the preregistered protocol](../../docs/FALSE_POSITIVE_PROTOCOL.md). The
separation audit reports exact and lexical near-duplicate checks, not semantic
independence. The final set's prior exposure remains a material limitation.
