# First-contact detection research

## Decision

Keep `models/job_posting_classifier.joblib` as the default. Do not promote the
experimental candidate. The best frozen candidate improved the auxiliary SMS
spam benchmark, but did not improve the already-seen synthetic first-contact
benchmark: it caught 4/16 scams versus 5/16 for the original, and 0/8 subtle
scams versus 2/8. No verified independent, labeled first-contact recruitment
test set was found. These results do not support replacing the production
artifact.

The experiments and thresholds below were frozen in
[`reports/selection.json`](../reports/selection.json) before the final
comparison in [`reports/improvement_evaluation.json`](../reports/improvement_evaluation.json).
They use no final evaluation examples for fitting or threshold selection.
This report reuses that recorded comparison; it does not retrain, tune, or
re-score the final set.

## Public data considered

| Dataset | Provenance, authenticity and labels | License and balance | Relevance, leakage and decision |
|---|---|---|---|
| [OpenML 46655, `fake_job_postings2`](https://www.openml.org/d/46655), EMSCAD-derived | Job-posting records labeled legitimate/fraudulent, not chat messages. The project source identifies the Kaggle-origin corpus and its university research attribution. Collection and label adjudication cannot be independently confirmed from the OpenML mirror alone. | OpenML's license field is the non-specific value `Kaggle`; the upstream Kaggle page displays CC0. Treat the mirror's redistribution terms as ambiguous and retain attribution pending legal review. 12,725 source rows (12,174 legitimate, 551 fraudulent); exact-text deduplication retains 12,525 (11,992 / 533). | The only recruitment-fraud-labelled corpus used. Long postings are a substantial domain mismatch for first-contact texts. The original 2,505-row posting holdout has known leakage: 548 near-template matches at cosine >=0.90, including three exact matches after stronger normalization. Candidate training purged 1,234 postings touching that historical holdout; the remaining candidate holdout still had four near matches. Historical scores are not clean estimates. |
| [UCI SMS Spam Collection, DOI 10.24432/C5CC84](https://archive.ics.uci.edu/dataset/228/sms+spam+collection) | UCI describes 5,574 SMS labeled `ham`/`spam`, assembled from several sources. Its notes say 425 spam examples were manually extracted from Grumbletext reports, where users often did not provide the original message; ham came from volunteer/research corpora. This is a mixed-provenance research collection, not verified recruitment fraud. | UCI lists CC BY 4.0; give attribution and confirm underlying-source conditions before redistribution. After normalized deduplication, 5,134 remain: 4,517 ham and 617 spam. The experiment grouped duplicates/templates into 3,077 train, 1,030 development and 1,027 final-test messages. | Useful only as auxiliary short-message spam data. Spam is not equivalent to employment fraud. No cross-source job overlap was found; group splits had no >=0.90 template overlap. The maximum measured similarity between the effective training text and the held-out synthetic set was 0.2444. Similarity checks cannot rule out semantic leakage. |

No accessible, provenance-auditable dataset of authentic, labeled first-contact
recruitment scam messages was identified in this work. Generic SMS phishing,
smishing, and spam corpora cannot fill that gap without labels for recruitment
context and message position. FTC consumer guidance is useful for developing
review questions, not a labeled training set.

The FTC describes warning patterns such as remote-work offers, vague duties,
unusually attractive earnings, upfront deposits or fees, urgent demands,
task-style scams, early requests for personal information, and messages that
ask someone to reply before providing basic job details. See [FTC job-scam
guidance](https://consumer.ftc.gov/consumer-alerts/2022/09/job-scams-are-getting-more-sophisticated).
These patterns were not converted into labels or used to train the model. The
current evidence rules cover only a subset; they do not detect task scams or
requests for personal data as such.

## Frozen model comparison

The experiment trained fixed lightweight TF-IDF/logistic-regression variants:
word unigrams/bigrams, character 3–5-grams, and word+character hybrids, with
and without auxiliary SMS data and training-only posting-prefix augmentation.
Thresholds 0.35, 0.50 and 0.65 were selected using the pre-reserved development
sets, maximizing mean posting/SMS F1 subject to a 5% false-positive-rate cap
per domain. `joint_hybrid_prefix` was selected at threshold 0.50. It combines
posting and UCI SMS training text; its SMS labels remain generic spam labels.

Positive-class metrics (`precision / recall / F1`); matrices use
`[[TN, FP], [FN, TP]]`.

| Method | Synthetic first-contact, N=32 (P/R/F1; FP/FN) | Subtle synthetic, N=16 (recall; FN) | Historical job holdout, N=2,505 (P/R/F1; FP/FN) | Grouped SMS holdout, N=1,027 (P/R/F1; FP/FN) |
|---|---|---|---|---|
| Original saved model | 1.000 / 0.313 / 0.476; 0/11 | 0.250; 6 | 0.612 / 0.692 / 0.649; 47/33 | 0.167 / 0.027 / 0.046; 15/110 |
| Selected `joint_hybrid_prefix` | 1.000 / 0.250 / 0.400; 0/12 | 0.000; 8 | 0.585 / 0.514 / 0.547; 39/52 | 0.906 / 0.938 / 0.922; 11/7 |
| Fixed keyword baseline | 1.000 / 0.375 / 0.545; 0/10 | 0.125; 7 | 0.133 / 0.019 / 0.033; 13/105 | 0.000 / 0.000 / 0.000; 0/113 |
| Always legitimate | 0.000 / 0.000 / 0.000; 0/16 | 0.000; 8 | 0.000 / 0.000 / 0.000; 0/107 | 0.000 / 0.000 / 0.000; 0/113 |

The synthetic matrix for the original is `[[16, 0], [11, 5]]`; for the selected
candidate it is `[[16, 0], [12, 4]]`. On subtle examples the matrices are,
respectively, `[[8, 0], [6, 2]]` and `[[8, 0], [8, 0]]`. The keyword baseline is
not the application's multi-category evidence policy.

The best candidate's SMS result is an improvement on an auxiliary ham/spam
test, not evidence that it detects recruitment scams. It loses on the synthetic
first-contact and historical job-posting results, including the subtle subset.
The original model therefore remains unchanged and is still not established as
reliable for first-contact detection.

All five frozen candidates are shown below so regressions are visible. Synthetic
values are precision/recall/F1 and false positives/false negatives; SMS and job
values use the same ordering and include false positives/false negatives.

| Candidate | Features and training sources | Threshold | Synthetic (P/R/F1; FP/FN) | Subtle recall (FN) | Job holdout (P/R/F1; FP/FN) | SMS holdout (P/R/F1; FP/FN) |
|---|---|---:|---|---|---|---|
| `job_word` | Word 1–2 grams; postings | 0.50 | 1.000 / 0.125 / 0.222; 0/14 | 0.125 (7) | 0.583 / 0.523 / 0.552; 40/51 | 0.500 / 0.044 / 0.081; 5/108 |
| `job_char` | Character 3–5 grams; postings | 0.65 | 1.000 / 0.125 / 0.222; 0/14 | 0.000 (8) | 0.613 / 0.430 / 0.506; 29/61 | 0.533 / 0.071 / 0.125; 7/105 |
| `joint_word` | Word 1–2 grams; postings + SMS | 0.50 | 1.000 / 0.188 / 0.316; 0/13 | 0.000 (8) | 0.653 / 0.439 / 0.525; 25/60 | 0.915 / 0.947 / 0.930; 10/6 |
| `joint_hybrid` | Word + character 3–5 grams; postings + SMS | 0.65 | 1.000 / 0.188 / 0.316; 0/13 | 0.000 (8) | 0.857 / 0.336 / 0.483; 6/71 | 0.963 / 0.920 / 0.941; 4/9 |
| `joint_hybrid_prefix` | Hybrid; postings + SMS + training-only posting prefixes | 0.50 | 1.000 / 0.250 / 0.400; 0/12 | 0.000 (8) | 0.585 / 0.514 / 0.547; 39/52 | 0.906 / 0.938 / 0.922; 11/7 |

The character-only and SMS-augmented models demonstrate that better performance
on one short-message domain does not transfer to the held-out recruitment-like
synthetic cases. All synthetic candidate models made zero false positives among
16 legitimate examples; that small, pre-evaluated sample is not a reliable
false-alarm estimate.

## Error examples and limits

- **Missed synthetic scam (original model):** “We are hiring remote assistants
  today. Deposit $60 in the next 24 hours to secure your position and earn up to
  $300 per day. Reply now for onboarding.” The model missed this hand-authored
  clear example; the separate rules may still flag it. Synthetic examples are
  not real-world proof.
- **False positive (original, historical posting holdout):** a legitimate,
  detailed specialist-physician vacancy was classified as fraudulent. The
  historical posting holdout produced 47 false positives; this example is a
  posting, not a first-contact message.
- **Synthetic false positives:** none among 16 hand-authored legitimate
  messages for these methods. That small, previously evaluated sample does not
  establish a low real-world false-positive rate.
- **Authentic recruitment messages:** no suitable independent labeled holdout
  was available. Recruitment-message precision, recall and false-alarm rates
  remain unknown.

The UI's `model_flagged` value is a binary prediction learned from text; it is
not a calibrated probability or explanation. Evidence categories are
deterministic rule/context observations. The combined warning is the model
flag OR at least two rule categories; neither output proves fraud or safety.

## Reproduction and data handling

The experiment protocol and split audit are in
[`reports/experiment_protocol.md`](../reports/experiment_protocol.md) and
[`reports/data_split_audit.json`](../reports/data_split_audit.json). Raw public
downloads are ignored; reports record hashes, counts and split membership
hashes rather than downloaded SMS text. The synthetic final set remains frozen
and excluded from fitting and threshold selection. Do not use the already
inspected final examples to tune future candidates.

## References

- Almeida & Hidalgo, [SMS Spam Collection, UCI](https://doi.org/10.24432/C5CC84),
  [UCI dataset page and license](https://archive.ics.uci.edu/dataset/228/sms+spam+collection).
- [OpenML dataset 46655](https://www.openml.org/d/46655), with project-level
  provenance and caveats in [`data/source.md`](../data/source.md).
- [FTC: Job scams are getting more sophisticated](https://consumer.ftc.gov/consumer-alerts/2022/09/job-scams-are-getting-more-sophisticated).
