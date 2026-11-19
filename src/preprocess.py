"""Convert a raw company record into a small "digest" so senang for the model to read.

Flow: data/companies.jsonl -> extract_company_digest() -> digest (small JSON)
-> generate.py sends it to the LLM. File ni tak call any API, it just count and arrange.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

# Data is "as of" 31 Dec 2025.
AS_OF_DATE = date(2025, 12, 31)


def sanitize_nones(obj: Any) -> Any:
    """None -> "N/A" for the prompt only. Digest asal kekal, sebab evaluate.py compare numbers."""
    if obj is None:
        return "N/A"
    if isinstance(obj, dict):
        return {k: sanitize_nones(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nones(v) for v in obj]
    return obj


def fmt_rm(val: float | int | None) -> str:
    if val is None:
        return "N/A"
    sign = "-" if val < 0 else ""
    abs_val = abs(val)
    if abs_val >= 1_000_000:
        return f"{sign}RM{abs_val / 1_000_000:.2f}M"
    if abs_val >= 1_000:
        return f"{sign}RM{abs_val:,.0f}"
    return f"{sign}RM{abs_val:.0f}"


def fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def extract_company_digest(record: dict[str, Any], include_flags: bool = True) -> dict[str, Any]:
    """Profile, governance, financial trend, litigation — all dikira dulu."""
    reg_no = record["registrationNumber"]
    profile = record["profile"]
    rels = record["relationships"]
    years = sorted(record["financials"]["years"], key=lambda y: y["financialYear"])
    cases = record["litigation"]["cases"]

    # Age, kira sampai 31 Dec 2025.
    inc_str = profile["incorporationDate"]
    age_years = round((AS_OF_DATE - date.fromisoformat(inc_str)).days / 365.25, 1)

    # Siapa pegang saham paling besar, dan berapa banyak saham ada pada directors.
    directors = rels["directors"]
    shareholders = sorted(rels["shareholders"], key=lambda s: s["percentage"], reverse=True)
    director_names = {d["name"] for d in directors}
    director_held_pct = sum(s["percentage"] for s in shareholders if s["name"] in director_names)
    top_shareholder = shareholders[0] if shareholders else None
    recent_board_changes = [d for d in directors if d["appointedOn"] >= "2025-01-01"]

    # Red flags and strengths. once, before the prompt.
    red_flags: list[str] = []
    strengths: list[str] = []
    fin_summary: list[dict[str, Any]] = []

    status = profile["status"]
    if status.lower() != "active":
        red_flags.append(f"Company status is '{status}' (not Active).")

    if not years:
        red_flags.append("No financial statements available in record.")
    else:
        for yr in years:
            fy = yr["financialYear"]
            audit = yr["audit"]
            stmt = yr["statements"]
            ratios = yr["ratiosAndMetrics"]
            prof = ratios["profitability"]
            liq = ratios["liquidityAndCashFlow"]
            cap = ratios["capitalStructure"]

            opinion = audit["opinion"]
            if opinion.lower() != "unqualified":
                red_flags.append(f"FY{fy} audit opinion is '{opinion}'.")

            fin_summary.append(
                {
                    "fy": fy,
                    "audit_opinion": opinion,
                    "revenue": fmt_rm(stmt["revenue"]),
                    "revenue_raw": stmt["revenue"],
                    "pat": fmt_rm(stmt["profitAfterTax"]),
                    "pat_raw": stmt["profitAfterTax"],
                    "net_margin": fmt_pct(prof["netProfitMargin"]),
                    "gross_margin": fmt_pct(prof["grossProfitMargin"]),
                    "quick_ratio": liq["quickRatio"],
                    "free_cash_flow": fmt_rm(liq["freeCashFlow"]),
                    "fcf_raw": liq["freeCashFlow"],
                    "leverage_ratio": cap["leverageRatio"],
                    "dscr": cap["debtServiceCoverageRatio"],
                    "total_equity": fmt_rm(stmt["totalEquity"]),
                    "equity_raw": stmt["totalEquity"],
                }
            )

        latest = fin_summary[-1]
        if len(fin_summary) >= 2:
            first = fin_summary[0]
            if first["revenue_raw"] and latest["revenue_raw"] is not None:
                rev_change = (
                    (latest["revenue_raw"] - first["revenue_raw"])
                    / abs(first["revenue_raw"])
                )
                if rev_change > 0.05:
                    strengths.append(
                        f"Revenue grew {fmt_pct(rev_change)} from FY{first['fy']} ({first['revenue']}) to FY{latest['fy']} ({latest['revenue']})."
                    )
                elif rev_change < -0.05:
                    red_flags.append(
                        f"Revenue declined {fmt_pct(abs(rev_change))} from FY{first['fy']} ({first['revenue']}) to FY{latest['fy']} ({latest['revenue']})."
                    )

        if latest["pat_raw"] is not None and latest["pat_raw"] < 0:
            red_flags.append(
                f"Net loss in FY{latest['fy']} ({latest['pat']}, margin {latest['net_margin']})."
            )
        if latest["equity_raw"] is not None and latest["equity_raw"] < 0:
            red_flags.append(
                f"Negative shareholder equity in FY{latest['fy']} ({latest['total_equity']})."
            )
        if latest["fcf_raw"] is not None and latest["fcf_raw"] < 0:
            red_flags.append(
                f"Negative Free Cash Flow in FY{latest['fy']} ({latest['free_cash_flow']})."
            )
        if latest["quick_ratio"] is not None and latest["quick_ratio"] < 1.0:
            red_flags.append(
                f"Tight short-term liquidity in FY{latest['fy']} (Quick Ratio: {latest['quick_ratio']:.2f})."
            )
        elif latest["quick_ratio"] is not None and latest["quick_ratio"] >= 1.2:
            strengths.append(
                f"Healthy short-term liquidity in FY{latest['fy']} (Quick Ratio: {latest['quick_ratio']:.2f})."
            )
        if latest["leverage_ratio"] is not None and latest["leverage_ratio"] > 2.0:
            red_flags.append(
                f"High leverage in FY{latest['fy']} (Leverage Ratio: {latest['leverage_ratio']:.2f})."
            )
        if latest["dscr"] is not None and latest["dscr"] < 1.0:
            red_flags.append(
                f"Debt Service Coverage Ratio below 1.0x in FY{latest['fy']} ({latest['dscr']:.2f}x)."
            )

    # Defendant cases = duit company yang mungkin kena bayar. Plaintiff = company tuntut orang.
    defendant_cases = [
        c for c in cases if str(c.get("role", "")).lower() == "defendant"
    ]
    plaintiff_cases = [
        c for c in cases if str(c.get("role", "")).lower() == "plaintiff"
    ]
    active_cases = [
        c
        for c in cases
        if str(c.get("status", "")).lower() not in {"closed", "settled", "dismissed", "resolved"}
    ]
    total_defendant_claim = sum(c.get("claimAmount") or 0 for c in defendant_cases)

    if defendant_cases:
        red_flags.append(
            f"Named as Defendant in {len(defendant_cases)} court case(s) totaling {fmt_rm(total_defendant_claim)} ({len(active_cases)} active/ongoing)."
        )
    elif not cases:
        strengths.append("Clean litigation record (0 court cases).")

    # Keep numbers as numbers. Cleanup : None -> "N/A" happens later, masa build the prompt.
    digest: dict[str, Any] = {
        "registrationNumber": reg_no,
        "companyName": profile["companyName"],
        "status": status,
        "companyType": profile["companyType"],
        "incorporationDate": inc_str,
        "ageYears": age_years,
        "industry": profile["industry"],
        "state": profile["state"],
        "natureOfBusiness": profile["natureOfBusiness"],
        "shareCapital": fmt_rm(profile["shareCapital"]),
        "formerNames": profile["formerNames"],
        "governance": {
            "directorCount": len(directors),
            "shareholderCount": len(shareholders),
            "directorOwnershipPct": round(director_held_pct, 2),
            "topShareholder": top_shareholder,
            "recentBoardAppointments2025": [
                f"{d['name']} ({d['designation']}, {d['appointedOn']})"
                for d in recent_board_changes
            ],
        },
        "financialTrajectory": fin_summary,
        "litigationSummary": {
            "totalCases": len(cases),
            "defendantCases": len(defendant_cases),
            "plaintiffCases": len(plaintiff_cases),
            "activeCases": len(active_cases),
            "totalDefendantClaimRM": fmt_rm(total_defendant_claim),
            "rawCases": cases,
        },
    }
    if include_flags:
        digest["precomputedStrengths"] = strengths
        digest["precomputedRedFlags"] = red_flags
    return digest


def load_companies(path: str | Path = "data/companies.jsonl") -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]