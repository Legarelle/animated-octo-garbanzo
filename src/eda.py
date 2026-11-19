"""Quick EDA before writing any prompt.

Tengok dulu shape data: berapa company, industri apa, berapa takde financials,
berapa rugi, berapa kena saman. from there baru decide apa patut di summary.
"""

import json
from collections import Counter

from src.preprocess import extract_company_digest, load_companies


def main():
    companies = load_companies()
    industries = Counter()
    statuses = Counter()
    missing_fin = 0
    defendant_cos = 0
    loss_cos = 0
    neg_fcf_cos = 0
    null_ratio_cos = 0

    for comp in companies:
        d = extract_company_digest(comp)
        industries[d["industry"]] += 1
        statuses[d["status"]] += 1

        # Zero financial statements — that itself is a signal.
        if not d["financialTrajectory"]:
            missing_fin += 1
        else:
            latest = d["financialTrajectory"][-1]
            if latest["pat_raw"] is not None and latest["pat_raw"] < 0:
                loss_cos += 1
            if latest["fcf_raw"] is not None and latest["fcf_raw"] < 0:
                neg_fcf_cos += 1

        if d["litigationSummary"]["defendantCases"] > 0:
            defendant_cos += 1

        # Raw data memang ada "null" in ratios that can't be dikira.
        if "null" in json.dumps(comp.get("financials", {})):
            null_ratio_cos += 1

    print(
        json.dumps(
            {
                "total_companies": len(companies),
                "statuses": dict(statuses),
                "top_industries": industries.most_common(5),
                "companies_with_no_financials": missing_fin,
                "companies_with_null_ratios": null_ratio_cos,
                "companies_with_latest_net_loss": loss_cos,
                "companies_with_negative_fcf": neg_fcf_cos,
                "companies_as_litigation_defendant": defendant_cos,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()