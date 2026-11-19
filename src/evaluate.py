"""Score each summary version: RM grounding, label recall, structure. First filter, bukan proof."""

import csv
import json
import re
from pathlib import Path
from typing import Any

from src.labels import load_labels
from src.preprocess import load_companies

VERSIONS = ["v1_raw", "v2_numbers", "v3_flags"]
HEADINGS = ["Verdict", "Financials", "Governance", "Litigation", "Next Step"]
RM_TOKEN = re.compile(r"(-?)RM([\d,]+(?:\.\d+)?)([MmKk]?)")


def load_summaries(version: str) -> dict[str, str]:
    path = Path("summaries") / f"{version}.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["registrationNumber"]: row["summary"] for row in rows}


def all_numbers(node: Any) -> list[float]:
    """Every number in the raw record, minus metadata and percentages."""
    if isinstance(node, dict):
        return [n for key, value in node.items() if key not in ("financialYear", "percentage") for n in all_numbers(value)]
    if isinstance(node, list):
        return [n for value in node for n in all_numbers(value)]
    return [float(node)] if isinstance(node, (int, float)) else []


def is_grounded(match: re.Match[str], numbers: list[float]) -> bool:
    """Match against raw numbers, so a rounded display value (RM5.35M) still counts."""
    sign, digits, suffix = match.groups()
    scale = {"m": 1_000_000, "k": 1_000}.get(suffix.lower(), 1)
    value = float(digits.replace(",", "")) * scale * (-1 if sign else 1)
    tolerance = 0.5 * scale / 10 ** len(digits.partition(".")[2])
    return any(abs(value - number) <= tolerance for number in numbers)


def item_text(item: Any) -> str:
    return item if isinstance(item, str) else item.get("text") or ", ".join(item["keywords"])


def is_covered(summary: str, item: Any) -> bool:
    """60% of the item's words (or of its keywords) must appear in the summary."""
    keywords = item.get("keywords") if isinstance(item, dict) else None
    words = [word.lower() for word in keywords or item_text(item).split()]
    return bool(words) and sum(1 for word in words if word in summary.lower()) / len(words) >= 0.6


def pct(hits: int, total: int) -> str:
    return f"{100 * hits / total:.1f}" if total else "n/a"


def score(version: str, companies: list[dict]) -> tuple[list[Any], list[list[str]]]:
    summaries = load_summaries(version)
    labels = load_labels()
    n = grounded = rm_total = structure = label_hit = label_total = 0
    misses: list[list[str]] = []
    for company in companies:
        reg = company["registrationNumber"]
        if reg not in summaries:
            continue
        summary = summaries[reg]
        n += 1
        numbers = all_numbers(company)
        for match in RM_TOKEN.finditer(summary):
            rm_total += 1
            grounded += is_grounded(match, numbers)
        structure += all(heading.lower() in summary.lower() for heading in HEADINGS)
        for item in labels.get(reg, {}).get("must_mention", []):
            label_total += 1
            if is_covered(summary, item):
                label_hit += 1
            else:
                misses.append([version, reg, item_text(item)])
    return [version, n, pct(grounded, rm_total), pct(label_hit, label_total), pct(structure, n)], misses


def main():
    companies = load_companies()
    print(f"{'version':<10}{'n':>4}{'grounding %':>13}{'label recall %':>16}{'structure %':>13}")
    misses: list[list[str]] = []
    for version in VERSIONS:
        row, missed = score(version, companies)
        print(f"{row[0]:<10}{row[1]:>4}{row[2]:>13}{row[3]:>16}{row[4]:>13}")
        misses += missed
    Path("results").mkdir(exist_ok=True)
    with open("results/misses.csv", "w", newline="", encoding="utf-8") as out:
        csv.writer(out).writerows([["version", "registrationNumber", "missed_item"], *misses])
    print(f"\n{len(misses)} missed label items -> results/misses.csv")


if __name__ == "__main__":
    main()
