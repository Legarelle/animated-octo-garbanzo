from src.preprocess import extract_company_digest, fmt_pct, fmt_rm


def test_formatting():
    assert fmt_rm(5_352_856) == "RM5.35M"
    assert fmt_rm(-239_509) == "-RM239,509"
    assert fmt_rm(None) == "N/A"
    assert fmt_pct(0.1234) == "12.3%"
    assert fmt_pct(None) == "N/A"


def test_dormant_company_flags():
    sample = {
        "registrationNumber": "SYN-999999",
        "profile": {
            "companyName": "Contoh Holdings Sdn. Bhd.",
            "status": "Dormant",
            "companyType": "Private limited company",
            "incorporationDate": "2020-01-01",
            "industry": "Retail",
            "state": "Selangor",
            "natureOfBusiness": "Dormant shell",
            "shareCapital": None,
            "formerNames": [],
        },
        "relationships": {"directors": [], "shareholders": []},
        "financials": {"years": []},
        "litigation": {
            "cases": [
                {"role": "Defendant", "status": "Active", "claimAmount": 500_000}
            ]
        },
    }
    digest = extract_company_digest(sample)
    assert digest["shareCapital"] == "N/A"
    assert any("Dormant" in f for f in digest["precomputedRedFlags"])
    assert any("No financial statements" in f for f in digest["precomputedRedFlags"])
    assert any("Defendant" in f and "RM500,000" in f for f in digest["precomputedRedFlags"])


def test_include_flags_false_only_drops_the_flags():
    sample = {
        "registrationNumber": "SYN-999998",
        "profile": {
            "companyName": "Contoh Store Sdn. Bhd.",
            "status": "Active",
            "companyType": "Private limited company",
            "incorporationDate": "2021-03-01",
            "industry": "Retail",
            "state": "Selangor",
            "natureOfBusiness": "Retail of garments",
            "shareCapital": 100_000,
            "formerNames": [],
        },
        "relationships": {"directors": [], "shareholders": []},
        "financials": {"years": []},
        "litigation": {"cases": []},
    }
    with_flags = extract_company_digest(sample)
    without_flags = extract_company_digest(sample, include_flags=False)
    assert "precomputedRedFlags" in with_flags
    assert not {"precomputedStrengths", "precomputedRedFlags"} & without_flags.keys()
    stripped = {k: v for k, v in with_flags.items() if k not in ("precomputedStrengths", "precomputedRedFlags")}
    assert stripped == without_flags