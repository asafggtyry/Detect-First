# Training dataset source and notes

- **Dataset:** `fake_job_postings2`, OpenML data ID 46655, version 1.
- **Record:** https://www.openml.org/d/46655
- **Download:** `https://www.openml.org/data/v1/download/22121348/fake_job_postings2.arff`
- **Provenance:** OpenML describes this as an English, imbalanced dataset derived from the Employment Scam Aegean Dataset (EMSCAD), originally published on Kaggle as “Real / Fake Job Posting Prediction.” OpenML lists the source as Kaggle and identifies the related benchmark paper by Shi et al. (2021). The original Kaggle page credits the University of the Aegean Laboratory of Information & Communication Systems Security and marks its dataset CC0. The Kaggle download page indicates a subscription is required; this project uses the public OpenML download instead and does not require a Kaggle account.
- **Licence:** The OpenML record’s licence field is the non-specific value `Kaggle`. The original Kaggle dataset page marks the dataset CC0 (Public Domain). We preserve source attribution here because OpenML is a derivative distribution and its licence metadata is not itself a clear licence statement.
- **Measured contents:** The downloaded OpenML file has 12,725 records: 12,174 legitimate labels (0) and 551 fraudulent labels (1), or about 4.3% fraudulent. The training script rechecks this count and the file checksum each time it downloads the data.
- **Domain mismatch:** These are online job postings, not first-contact SMS or chat messages. The vocabulary, length, context, class balance, and fraud patterns may differ substantially from short recruitment texts. The model is a prototype demonstration, not validated for detecting first-contact messages.
- **Leakage precautions:** The training script normalizes and removes exact duplicate text before a stratified train/test split, rejects conflicting duplicate labels, then checks that no exact normalized text occurs in both partitions. It does not detect near-duplicates or templates with small edits.

The hand-authored examples in `data/synthetic/evaluation.jsonl` are a separate evaluation-only set inspired by scam patterns discussed by the U.S. Federal Trade Commission (upfront fees, fake checks, reshipping, and requests to move money). They are synthetic, are not part of EMSCAD, and are never used for training or threshold tuning. Their results must not be presented as real-world validation.

References:

- OpenML record 46655: https://www.openml.org/d/46655
- Original Kaggle dataset and its displayed CC0 metadata: https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
- Shi et al. (2021), *Benchmarking Multimodal AutoML for Tabular Data with Text Fields*: https://arxiv.org/abs/2111.02705
- Federal Trade Commission, *Job scams are getting more sophisticated*: https://consumer.ftc.gov/consumer-alerts/2022/09/job-scams-are-getting-more-sophisticated
