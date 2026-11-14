# AI improvement protocol (2026-11-14)

Written before candidate training or reading final synthetic message contents.

- Preserve the original artifact and both original reports. Never train on or
  select parameters using `data/synthetic/evaluation.jsonl` (SHA256
  `e4e81f6b40849761443bcb1634a9b0fc16253061737bcfc49da5cd4383156256`).
- Keep the original 2,505 posting holdout for a paired comparison. Purge training
  postings in a near-duplicate component touching that holdout. The original
  artifact did not have this protection; explicitly disclose that asymmetry.
- Normalize contact addresses and numbers for similarity grouping. Group exact
  templates and pairs with cosine similarity >= 0.90 using word unigram/bigram
  TF-IDF, transitively. This is a split audit, never the classifier vocabulary.
  Similarity cannot rule out all semantic/template leakage.
- Group-split the remaining posting pool into training/development (75/25).
  Group-split UCI SMS into 60/20/20 train/development/final. Exclude cross-source
  duplicate components and quarantine conflicting exact SMS labels.
- Fit classifier vocabularies on training text only. Test five fixed candidates:
  job word, job character, joint word, joint word+character, and joint
  word+character with training-only 60-word posting prefixes. Prefix labels are
  weak inherited posting labels, not verified first-contact labels.
- Balanced logistic regression, C=1, seed=2026; word (1,2), character (3,5).
  Compare thresholds 0.35, 0.50, 0.65 only on development. Maximize mean of
  posting and SMS positive-class F1, subject to <=5% false-positive rate in each
  domain. If no candidate meets the guardrail, retain the original default.
- Freeze the chosen model and thresholds in `selection.json` before final
  evaluation. Do not retrain on development data, or change candidates after
  seeing final results. Report every candidate, including regressions.
- Evaluate the original, every frozen candidate, keyword and always-legitimate
  baselines on the same final subsets. Separate positive and negative counts,
  precision, recall, F1, FP/FN; split synthetic clear/subtle results. SMS labels
  mean ham/spam, NOT legitimate/fraudulent job offers.
- Final reports contain hashes/IDs, not raw downloaded messages or contact data.
  Raw public datasets and intermediate fitted models stay Git-ignored. No new
  private messages are collected. No frontend edits, pushes, merges or commits.

Interpretation: SMS is auxiliary domain adaptation, not proof of recruitment
scam detection. The existing synthetic benchmark was historically evaluated;
it is held out from this experiment, not a newly collected blind real-world set.
