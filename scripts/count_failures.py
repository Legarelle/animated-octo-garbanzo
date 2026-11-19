"""Count failure_category and average my_score_1_to_5 per version from results/review.csv."""

import csv
from collections import Counter
from pathlib import Path

CSV_PATH = Path("results/review.csv")


def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"{CSV_PATH} not found - run scripts/make_review_sheet.py first.")
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for version in dict.fromkeys(row["version"] for row in rows):
        mine = [row for row in rows if row["version"] == version]
        scores = []
        for row in mine:
            try:
                scores.append(float(row["my_score_1_to_5"]))
            except ValueError:
                pass  # blank or not a number, so not scored yet
        average = f"{sum(scores) / len(scores):.2f}" if scores else "n/a"
        print(f"{version}: avg score {average} ({len(scores)}/{len(mine)} scored)")
        failures = Counter(row["failure_category"].strip() for row in mine if row["failure_category"].strip())
        for category, count in failures.most_common():
            print(f"  {count:>3}  {category}")


if __name__ == "__main__":
    main()
