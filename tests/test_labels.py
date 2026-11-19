from pathlib import Path

from src.labels import load_labels


def test_skips_companies_without_must_mention(tmp_path: Path):
    path = tmp_path / "labels.yaml"
    path.write_text(
        'SYN-1:\n  must_mention: ["posts a net loss"]\n  notes: "checked"\n'
        'SYN-2:\n  must_mention: []\n  notes: ""\n',
        encoding="utf-8",
    )
    assert load_labels(path) == {"SYN-1": {"must_mention": ["posts a net loss"], "notes": "checked"}}
