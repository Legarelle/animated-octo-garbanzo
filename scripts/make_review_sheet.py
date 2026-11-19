"""Write results/review.csv: one row per (company, version), three columns left blank for hand scoring."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `src` imports work when run as a script

from src.evaluate import VERSIONS, load_summaries
from src.labels import load_labels

COMPANIES = 12
COLUMNS = ["registrationNumber", "version", "summary", "my_score_1_to_5", "failure_category", "comment"]


def main():
    labelled = list(load_labels())[:COMPANIES]
    if not labelled:
        raise SystemExit("No labelled companies in data/labels.yaml - fill in must_mention first.")
    summaries = {version: load_summaries(version) for version in VERSIONS}
    rows = [
        {
            "registrationNumber": reg,
            "version": version,
            "summary": summaries[version].get(reg, ""),
            "my_score_1_to_5": "",
            "failure_category": "",
            "comment": "",
        }
        for reg in labelled
        for version in VERSIONS
    ]
    Path("results").mkdir(exist_ok=True)
    with open("results/review.csv", "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows ({len(labelled)} companies x {len(VERSIONS)} versions) -> results/review.csv")


if __name__ == "__main__":
    main()
