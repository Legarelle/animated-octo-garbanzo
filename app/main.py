"""Viewer for the summaries. Reads files only, tak call any model."""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.jsonl"
SUMMARIES = ROOT / "summaries"

app = FastAPI(title="Company summaries viewer")


def load_companies() -> list[dict[str, Any]]:
    lines = COMPANIES.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@app.get("/api/companies")
def list_companies() -> list[dict[str, Any]]:
    return [
        {
            "registrationNumber": c["registrationNumber"],
            "companyName": c["profile"]["companyName"],
            "industry": c["profile"]["industry"],
            "state": c["profile"]["state"],
        }
        for c in load_companies()
    ]


@app.get("/api/companies/{registration_number}")
def get_company(registration_number: str) -> dict[str, Any]:
    for company in load_companies():
        if company["registrationNumber"] == registration_number:
            return company
    raise HTTPException(404, f"No company {registration_number}")


@app.get("/api/summaries")
def list_versions() -> list[str]:
    return sorted(p.stem for p in SUMMARIES.glob("*.jsonl"))


@app.get("/api/summaries/{version}")
def get_version(version: str) -> dict[str, Any]:
    """Parse one summaries file. Bad lines are skipped, not fatal."""
    path = SUMMARIES / f"{version}.jsonl"
    if Path(version).name != version or not path.is_file():
        raise HTTPException(404, f"No summaries/{version}.jsonl")

    summaries: dict[str, str] = {}
    invalid_lines: list[int] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines.append(number)
            continue
        summaries[row["registrationNumber"]] = row["summary"]
    return {"summaries": summaries, "invalidLines": invalid_lines}


app.mount("/", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
