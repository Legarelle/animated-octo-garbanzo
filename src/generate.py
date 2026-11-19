"""Generate a summary for each company and save into summaries/<version>.jsonl.

Simple flow:
1. Ambil company digest (preprocess.py).
2. Send to DeepSeek with a system prompt ikut version.
3. Save the answer in cache/ supaya we don't pay for the same tokens twice.

Run: python -m src.generate --version v3_flags --limit 5
"""

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.preprocess import extract_company_digest, load_companies, sanitize_nones

load_dotenv()

DEFAULT_MODEL = "deepseek-flash"
RETRY_WAIT = 5

# v1: bagi model semua raw data, and then bagi summary as its output.
SYSTEM_PROMPT_V1 = (
    "You are a business analyst. Summarize the provided company JSON record in short Markdown "
    "so a procurement or partnership vetting team can decide if they should inspect it further."
)

# One prompt for both digest versions, so the only difference is the flags.
SYSTEM_PROMPT_V2 = """You are a commercial due-diligence analyst screening Malaysian companies as potential suppliers or project partners. Write a short brief (110-160 words) for the vetting analyst, using the company digest below.

The RM amounts, percentages and ratios in the digest are already computed - use them as they are, don't recalculate or round them again. Copy RM strings exactly as written, e.g. -RM239,509, not -RM239.5k.

Follow this format:

**Verdict:** one sentence on what the company does, how long it has been operating, and how risky it looks overall (Low / Moderate / Elevated Risk).
- **Financials:** two or three facts on latest revenue, profitability or margin trend, and cash flow or liquidity.
- **Governance:** board size, ownership concentration, and any 2025 board changes or former names.
- **Litigation & Risks:** litigation status and RM exposure, plus any financial or audit red flags, or say if it is clean.
- **Next Step:** one concrete thing the analyst should verify.

If something is missing from the digest (e.g. no financial years, null ratios), say so instead of guessing."""


def call_with_cache(
    client: OpenAI,
    model_name: str,
    version: str,
    reg_no: str,
    system_prompt: str,
    user_payload: str,
    force: bool = False,
) -> str:
    """Satu cache file per company. Reuse kalau dah ada, unless --force."""
    cache_dir = Path("cache") / version
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{reg_no}.json"

    if cache_file.exists() and not force:
        return json.loads(cache_file.read_text(encoding="utf-8"))["summary"]

    # Free tier selalu kena rate limit, so cuba 3 kali je.
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0.2,
                extra_body={"thinking": {"type": "disabled"}},
            )
            summary_text = (response.choices[0].message.content or "").strip()
            usage = response.usage.model_dump() if response.usage else {}
            cache_file.write_text(
                json.dumps(
                    {
                        "registrationNumber": reg_no,
                        "model": model_name,
                        "version": version,
                        "usage": usage,
                        "summary": summary_text,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return summary_text
        except Exception as e:
            print(f"[{reg_no}] Attempt {attempt + 1} failed ({e}). Retrying in {RETRY_WAIT}s...")
            time.sleep(RETRY_WAIT)

    raise RuntimeError(f"Failed to generate summary for {reg_no} after 3 attempts.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v3_flags", choices=["v1_raw", "v2_numbers", "v3_flags"])
    parser.add_argument("--model", default=DEFAULT_MODEL, help="DeepSeek model ID (default: deepseek-flash)")
    parser.add_argument("--limit", type=int, default=50, help="Berapa companies to process (1-50)")
    parser.add_argument("--force", action="store_true", help="Ignore the cache and regenerate every summary")
    args = parser.parse_args()

    if not 1 <= args.limit <= 50:
        parser.error("--limit must be between 1 and 50")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("Missing DEEPSEEK_API_KEY in environment or .env file.")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    companies = load_companies()[: args.limit]
    out_path = Path("summaries") / f"{args.version}.jsonl"

    with open(out_path, "w", encoding="utf-8") as out_f:
        for idx, comp in enumerate(companies, start=1):
            reg_no = comp["registrationNumber"]
            if args.version == "v1_raw":
                sys_prompt = SYSTEM_PROMPT_V1
                payload = json.dumps(comp)
            else:
                sys_prompt = SYSTEM_PROMPT_V2
                digest = extract_company_digest(comp, include_flags=args.version == "v3_flags")
                payload = json.dumps(sanitize_nones(digest), indent=2)

            summary = call_with_cache(
                client, args.model, args.version, reg_no, sys_prompt, payload, force=args.force
            )
            out_f.write(json.dumps({"registrationNumber": reg_no, "summary": summary}) + "\n")
            print(f"[{idx}/{len(companies)}] {reg_no} ({args.model}) -> {out_path}")


if __name__ == "__main__":
    main()