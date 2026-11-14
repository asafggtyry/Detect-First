"""Download/verify evaluation data without retraining the saved model."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detect_first.data import download_dataset, load_dataset

if __name__ == "__main__":
    path = ROOT / "data/raw/fake_job_postings2.arff"
    if not path.exists():
        download_dataset(path)
    _, stats = load_dataset(path)
    print(f"Verified {stats['rows_after_exact_deduplication']} deduplicated postings. Model unchanged.")
