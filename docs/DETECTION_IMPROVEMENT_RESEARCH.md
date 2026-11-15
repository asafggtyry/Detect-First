# Detection improvement research

Date: 2026-11-14
Branch: `research/detection-improvements`
Base: `feature/blind-ai-evaluation` at `d4b1ad2`

## Decision

Retain the production model, evidence policy, and model artifact unchanged.
No candidate has demonstrated an improvement on a defensible independent
first-contact recruitment benchmark. The available first-contact labels are
synthetic and already inspected, so they were not used for new tuning.

The repository's frozen candidate experiments were independently verified with
`python scripts/verify_model_integration.py --rebuild-groups` after downloading
the documented UCI source. Verification performs no fitting, threshold tuning,
model selection, or artifact overwrites.

## Current error taxonomy

The current blind report evaluates 32 repository-authored synthetic messages
(16 fraudulent, 16 legitimate). It is a demonstration set, not real-world
validation.

### ML false negatives: 11 of 16 scams

- **Payment and purchase mechanics:** gift cards, equipment fees, activation
  charges, refundable deposits, and supplier purchases are often short or
  operational rather than job-posting language.
- **Check and money movement scams:** fake checks, forwarding customer funds,
  returning excess money, and reshipping packages are not represented well by
  the job-posting training domain.
- **Personal-data and payroll requests:** bank account/routing information is
  requested before role details, but the model has no reliable first-contact
  context feature for this pattern.
- **Legitimate-looking recruitment framing:** several scams mention a role,
  interview, payroll, or hiring team and therefore resemble ordinary postings.
- **Weak lexical signal in subtle examples:** phrases such as “refundable
  equipment processing charge” and “standard hiring paperwork” bury the risky
  action in otherwise ordinary recruitment wording.

The misses are listed by ID in `reports/blind_ai_evaluation.json`; no examples
were removed or relabelled.

### Evidence-rule false positives: 8 of 16 legitimate messages

The rules are intentionally broad and treat job terms plus first-contact
context, urgency, employer verification, or limited role context as evidence.
The false alarms are legitimate applications, interview reminders, and ordinary
recruiter messages containing words such as “hiring,” “role,” “pay,”
“interview,” “application,” and “careers page.” The unverified-employer rule is
especially sensitive because a normal recruiter message cannot establish
verification from text alone.

### Combined-policy sensitivity

The combined policy is `model_flagged OR at least two evidence categories`.
On this synthetic set it improves recall from 31.25% for ML alone to 68.75%,
but keeps the evidence system's 8 false alarms. It is therefore more sensitive,
not demonstrably more accurate in the real world. The warning policy should not
be called calibrated or safe based on this set.

The production ML model itself produced zero false positives among these 16
synthetic legitimate examples, so this set does not show ML confusion with
legitimate recruiters. The rules and combined policy did produce 8 false alarms.
The historical 2,505-row job-posting holdout did contain 47 original-model false
positives, but that holdout has known near-template contamination and is not a
first-contact benchmark.

## Comparison results

Current blind synthetic comparison:

| System | N | TP | TN | FP | FN | Precision | Recall | F1 | Matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Original ML | 32 | 5 | 16 | 0 | 11 | 1.0000 | 0.3125 | 0.4762 | `[[16, 0], [11, 5]]` |
| Evidence rules | 32 | 9 | 8 | 8 | 7 | 0.5294 | 0.5625 | 0.5455 | `[[8, 8], [7, 9]]` |
| Combined warning | 32 | 11 | 8 | 8 | 5 | 0.5789 | 0.6875 | 0.6286 | `[[8, 8], [5, 11]]` |
| Always legitimate | 32 | 0 | 16 | 0 | 16 | 0.0000 | 0.0000 | 0.0000 | `[[16, 0], [16, 0]]` |

Frozen candidate experiments, selected using development data only:

| Candidate | Features | Synthetic P/R/F1 | FP/FN | Subtle recall | Job holdout P/R/F1 | SMS holdout P/R/F1 |
|---|---|---|---:|---:|---|---|
| Original | Word 1-2 grams, postings | 1.000 / 0.313 / 0.476 | 0/11 | 0.250 | 0.612 / 0.692 / 0.649 | 0.167 / 0.027 / 0.046 |
| `job_word` | Word 1-2 grams, postings | 1.000 / 0.125 / 0.222 | 0/14 | 0.125 | 0.583 / 0.523 / 0.552 | 0.500 / 0.044 / 0.081 |
| `job_char` | Character 3-5 grams, postings | 1.000 / 0.125 / 0.222 | 0/14 | 0.000 | 0.613 / 0.430 / 0.506 | 0.533 / 0.071 / 0.125 |
| `joint_word` | Postings + generic SMS | 1.000 / 0.188 / 0.316 | 0/13 | 0.000 | 0.653 / 0.439 / 0.525 | 0.915 / 0.947 / 0.930 |
| `joint_hybrid` | Word + character, postings + generic SMS | 1.000 / 0.188 / 0.316 | 0/13 | 0.000 | 0.857 / 0.336 / 0.483 | 0.963 / 0.920 / 0.941 |
| `joint_hybrid_prefix` | Hybrid plus training-only posting prefixes | 1.000 / 0.250 / 0.400 | 0/12 | 0.000 | 0.585 / 0.514 / 0.547 | 0.906 / 0.938 / 0.922 |

The candidate models improve generic SMS spam performance but do not improve
synthetic recruitment-like first-contact performance. Generic spam labels are
not employment-fraud labels.

## Dataset investigation

| Dataset | Authenticity and labels | Licence/provenance | Relevance and leakage result |
|---|---|---|---|
| OpenML 46655 / `fake_job_postings2` | 12,725 job-posting records; 12,174 legitimate and 551 fraudulent before exact deduplication. Labels describe postings, not first-contact messages. | OpenML reports a non-specific Kaggle value; upstream Kaggle displays CC0, but redistribution terms remain ambiguous. Attribution retained. | Relevant recruitment-fraud domain but a major message-format mismatch. Historical posting holdout has 548 near-template matches at cosine >=0.90, including 3 stronger-normalization exact matches. |
| UCI SMS Spam Collection, DOI 10.24432/C5CC84 | 5,574 ham/spam SMS; retained audit set 5,134 after duplicate/conflict removal: 4,517 ham and 617 spam. Spam is not verified employment fraud. | UCI lists CC BY 4.0; source messages have mixed provenance and underlying-source conditions should be respected. | Useful auxiliary short-message data only. Grouped train/dev/test partitions have no >=0.90 template overlap; it cannot establish recruitment-fraud accuracy. |
| Repository synthetic evaluation | 32 hand-authored fictional first-contact examples, balanced 16/16, clear/subtle difficulty labels. | Repository-authored; no external public-data licence. | Exact normalized overlap with training is zero. It has already been inspected and must not be used for future tuning. |
| Demo fixtures | 30 synthetic scenario fixtures used by the interactive simulator. | Repository-authored demonstration content. | Never use for fitting, threshold selection, or independent accuracy claims. |

No defensible authentic public dataset with verified first-contact recruitment
labels was found. FTC guidance was used only as qualitative review context, not
as labels or training data.

## Safe-experiment boundary

The frozen experiments considered word and character n-grams, class weighting,
word/character hybrids, auxiliary SMS data, posting-prefix augmentation, and
thresholds selected on reserved development data. They did not use the 32 final
synthetic examples, the 30 demo fixtures, or the reserved SMS test partition
for fitting or threshold selection.

Future work needs a new, pre-registered authentic first-contact dataset with
verified label meaning and group-aware duplicate/near-duplicate splitting.
Until then, changing the production model or warning policy would be tuning to
an exposed synthetic demonstration set, not evidence-based improvement.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/verify_release_metrics.py
.\.venv\Scripts\python.exe scripts/verify_model_integration.py --rebuild-groups
.\.venv\Scripts\python.exe -m pytest -q
```

The production artifact remains unchanged at SHA-256
`6e6359e96e201c8814fdc183f070acef1c35daa963b699b6206bf83eceff2c42`.
