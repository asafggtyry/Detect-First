from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detect_first.data import DATASET_MD5, download_dataset
from detect_first.model import DATA_PATH, METRICS_PATH, MODEL_PATH, train_and_save


def main() -> None:
    if not DATA_PATH.exists():
        print("Downloading the public OpenML job-postings dataset...")
        download_dataset(DATA_PATH)
    elif DATA_PATH.stat().st_size == 0:
        raise ValueError(f"Dataset file is empty: {DATA_PATH}")
    result = train_and_save(DATA_PATH, MODEL_PATH, METRICS_PATH)
    print(f"Trained model saved to {MODEL_PATH}")
    print(f"Training metrics saved to {METRICS_PATH}")
    print(
        "Model holdout metrics: "
        + json.dumps(result["model"]["metrics"], sort_keys=True)
    )
    print(f"Expected dataset checksum: {DATASET_MD5}")


if __name__ == "__main__":
    main()
