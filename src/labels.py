"""Hand labels: what a good summary must mention for a company."""

from pathlib import Path
from typing import Any

import yaml


def load_labels(path: str | Path = "data/labels.yaml") -> dict[str, dict[str, Any]]:
    """Company -> labels. Entries with an empty must_mention are skipped."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {reg: label for reg, label in raw.items() if label.get("must_mention")}
