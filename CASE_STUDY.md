# Company Summaries: Case Study

## Setup and tools

- **Provider and model:** DeepSeek API, `deepseek-flash` (the default in `generate.py`), `temperature=0.2`, thinking mode disabled, one run per company.
- **Companies:** I generated summaries for all 50. I labelled 15 and reviewed 12 side by side.
- **Time spent:** **5.5** Total hours. 2 Hours Understanding and 3.5 hours on the code
- **AI tools used:** Gemini, Claude and DeepSeek (DeepSeek is also the model the pipeline calls) wrote most of the pipeline code (digest, generation, evaluator, scripts, viewer) and drafted this document, the per-company notes, and a first pass at the 76 label items. I chose which criteria to keep and checked the label items against the raw records before using them. The 1–5 scores and failure categories in `results/review.csv` are mine.

## 1. What a good summary is for this team, and why

The team reads this summary first to decide whether a company deserves a closer look. So I treat it as a triage note, not a report. After reading 15 full records by hand, I settled on six things a good summary should do:

1. Say what the company does and give an overall risk view in the first sentence.
2. Surface anything that would make the team stop: defendant cases and their size, losses, negative equity, audit disclaimers, non-active status, and missing financials.
3. Use numbers exactly as they appear in the record. A wrong figure is worse than a missing one, because an analyst may trust it.
4. Say so when data is missing instead of guessing.
5. Keep the same short shape every time (about 110 to 160 words), so 50 of them can be skimmed quickly.
6. End with one concrete thing to verify.

I asked the model to propose a list of what a good summary should contain, then kept only the criteria that matched what I wanted to see. Two kinds of record shaped that choice. SYN-000302 and SYN-000333 have no financial statements at all, so a confident risk verdict would be a guess, and the summary has to say so. SYN-000286 and SYN-000397 are each defendants in six cases, including a pending winding-up petition (RM355.9k) and a settled RM7.43M debt claim, which an analyst would want to see before anything else. That is why criteria 2 and 4 are on the list.

To turn this into something measurable, I labelled 15 companies: `data/labels.yaml` holds 76 must-mention items. A model drafted a first pass, and I checked each item against the raw record and kept only facts that appear in it: an amount, a date, a shareholding, a case. No item comes from my digest or from a generated summary, so the evaluation does not just agree with my own assumptions.

## 2. What you built

The pipeline has three parts:

- `preprocess.py` turns a raw record into a small digest. It computes company age, formats RM amounts, and picks out the latest-year ratios. It can also add precomputed strengths and red flags.
- `generate.py` sends each company to the model and caches every response, so I can re-score without calling the API again. `--force` regenerates a cached file.
- `evaluate.py` scores each version against the raw records and my labels. It never touches the digest, so my rules cannot grade themselves.

I wanted to answer one question: **does precomputing red flags help the model, or does it just anchor it?** To test that, I compared three versions:

| Version | What the model sees | What it tests |
| :--- | :--- | :--- |
| `v1_raw` | The full record as JSON, short generic prompt | Baseline |
| `v2_numbers` | Digest with formatted numbers, no flags | Does clean formatting help? |
| `v3_flags` | Same digest plus precomputed flags and strengths | Do flags help or anchor? |

`v2` and `v3` use the same system prompt. The only difference is the flags, so the comparison is fair. I checked this by diffing the two payloads for a company: the only added keys are `precomputedStrengths` and `precomputedRedFlags`.

The flag rules read the years that are present. Audit opinions are checked in every year, so an older qualified or disclaimed opinion still surfaces (SYN-000217 carries an FY2023 disclaimer). Everything else uses the latest year: net loss, negative equity, negative free cash flow, quick ratio below 1.0, leverage above 2.0, and DSCR below 1.0. On top of that it flags a non-active status, a record with no financial statements at all, revenue moving more than 5% between the first and last year, and any defendant court cases. The same rules also emit strengths: a quick ratio of 1.2 or more is reported as healthy liquidity, and a clean litigation record is noted as a strength.

## 3. How you know whether it's good

### Automatic checks

| Version | Label recall | RM number grounding | Structure |
| :--- | :--- | :--- | :--- |
| `v1_raw` | 63.2% (48/76) | 100.0% (see caveat) | 0% (prompt asks for no fixed headings) |
| `v2_numbers` | 56.6% (43/76) | 96.9% (9 unmatched of 290) | 100% |
| `v3_flags` | 56.6% (43/76) | 97.3% (8 unmatched of 292) | 100% |

How I read this:

- **Flags did not change label recall.** `v2` and `v3` each caught 43 of 76 items. The 5-item gap to `v1` is small, and `v1` is roughly twice as long (308 words on average, range 173 to 407, against 164 and 159), so it had more room to mention things. I would not claim any version is better on recall from this alone.
- **The `v1` grounding score is not comparable.** My check looks for `RM` amounts, and `v1` often writes `MYR` or `RM 4.21M` with a space, so only 15 numbers were checked, all of which matched. `v2` and `v3` had 290 and 292 checked.
- **None of the unmatched figures is invented.** They are the right numbers in a shape the check cannot see: correct totals of individual claim amounts (`RM892,500`, `RM9.54M`, `RM6.82M`, `RM10.71M`; the claims in each record sum to exactly these), a cash-burn amount written as a positive figure (`RM1.13M` for a free cash flow of -RM1,131,822), and three `RM0` statements for companies with no claims. That accounts for eight of them. `v2` has one more: the same RM10.71M total appears twice in the SYN-001212 summary, once in Litigation and once in the next step.
- **The `v1` structure score of 0% is by design**, because that prompt never asked for the five headings.

### Manual review

I read 12 companies side by side and scored each summary 1 to 5, with a failure category. `scripts/count_failures.py` reads `results/review.csv`:

| Version | Average score | Failure categories |
| :--- | :--- | :--- |
| `v1_raw` | 3.75 | `risk_label_off` x8, `contradiction` x2, `data_gap_handled_poorly` x1, `none` x1 |
| `v2_numbers` | 4.42 | `none` x9, `data_gap_handled_poorly` x2, `risk_label_off` x1 |
| `v3_flags` | 4.42 | `none` x8, `missed_key_risk` x2, `weak_next_step` x2 |

For SYN-000029:

| Version | Score | Failure | Comment |
| :--- | :--- | :--- | :--- |
| `v1_raw` | 4 | `risk_label_off` | "Catches DSO (88–97d), negative FCF, and Nov 2025 control shift, but uses a hedged recommendation instead of a clear risk tier." |
| `v2_numbers` | 5 | `none` | "Decision-ready Moderate Risk summary that pairs exact negative FCF (-RM239,509) and tight DSCR (1.07) with targeted governance and funding checks." |
| `v3_flags` | 4 | `missed_key_risk` | "Right verdict and clean structure, but omits the razor-thin DSCR (1.07x) and leaves the 58.25% majority holder unnamed." |

**`v1` is a baseline, not a fair rival.** It differs from `v2` in input, prompt and length, and its prompt never asked for a risk tier, so its eight `risk_label_off` marks partly reflect the prompt and not only the input. My question is about `v2` against `v3`, so that is the comparison I rely on.

The `v2` and `v3` averages are identical, but the winner flips company by company: `v2` took the two lowest marks (2 and 2) on companies where `v3` scored 5 and 5, and `v3` scored 3 on three companies where `v2` scored 5, 5 and 5.

**Bottom line.** On this data, precomputed flags neither clearly help nor hurt: both versions average 4.42. They helped where something was missing. For the two companies with no financials (SYN-000302 and SYN-000333), `v2` scored 2 and 2 and `v3` scored 5 and 5. They cost points on three other companies, where `v3` scored 3 against `v2`'s 5: SYN-000165, SYN-000267 and SYN-000381. SYN-000165 says "the only flag is the FY2024 quick ratio" while leverage climbed from 0.53 to 1.62; SYN-000267 leaves DSCR (1.37x) out and spends its next step on residual liability on a settled claim; SYN-000381 checks a registered-address mismatch and ignores the 51% parent. My reading is that flags help when something is missing or unusual and add little when nothing fires. With 12 companies I cannot prove that.

### What reading the summaries showed

These come from my reading, and every one below was checked against the record:

- **Flags changed the risk label for 3 of 12 companies** (SYN-000217, 302, 333), always upward: Moderate to Elevated for 217, Low to Elevated for 302 and 333. For the two with no financials, `v2` says Low Risk while also saying financial health cannot be assessed; `v3` says Elevated Risk. Here the flags helped.
- **Neither version flags a missing financial year.** SYN-000286 and SYN-000397 both report FY2022 and FY2024 with no FY2023, and my digest only iterates the years that exist. `v2` for SYN-000397 mentioned it by chance ("No FY2023 figures are in the digest"); `v3` did not.
- **Flags only look at the latest year, so trends are invisible.** For SYN-000381, leverage went from 0.78 to 1.65 and the quick ratio fell from 2.16 to 1.36. `v1` flagged both. `v2` and `v3` report the same movement in one sentence and then say there are no red flags, and `v3`'s digest even lists "Healthy short-term liquidity in FY2024 (Quick Ratio: 1.36)" as a strength, which points the model the other way.
- **A status bug.** For SYN-000267 the record has five plaintiff cases: one pending, two settled, one dismissed, one withdrawn. `v1` said six cases (all plaintiff) but correctly noted one pending; `v2` and `v3` said five plaintiff cases, two active. My code treats any status other than closed, settled, dismissed or resolved as active, so the withdrawn case is counted as ongoing. I have not fixed it, because that would mean regenerating `v2` and `v3`; it is the first item under next steps.
- **Model misreads around counts.** `v3` for SYN-000397 wrote "4 still active—including a settled RM7,427,000 debt-recovery claim". Four active matches my count, but the settled case is the largest of the six, so the sentence contradicts itself.

### Limits of this evaluation

- Only 15 companies are labelled and 12 reviewed, so small differences mean little.
- Label recall uses keyword matching, so it can miss correct paraphrases and give credit for loosely related words. Of the 94 missed items, 33 contain only figures that do appear in the summary (for example an item saying "from RM5.13M (2022) to RM5.35M (2024)" when the summary gives both figures but not in that shape), 36 had some figures present and some missing, and 25 had none of the item's figures or no figures at all. The recall numbers understate coverage.
- I reviewed every label and scored every summary myself, once, and not blind.
- Each company was generated once, so I cannot say how much results vary between runs.
- Grounding only checks RM amounts, not percentages or ratios.

## 4. What you'd do next, and how you'd keep improving it

**Which version I would ship:** `v3_flags`, after the digest fixes below. The two versions tie on average score, but the worst `v2` failure, calling a company with no financials Low Risk, is the one that matters most to a vetting team, and the flags fix it. I would not ship it before fixing the missing-year and trend gaps, because those are where the flags are blind or point the wrong way.

1. **Fix the digest where my labels exposed gaps:** count "withdrawn" cases as closed, detect missing financial years, add multi-year trends (leverage, quick ratio, margin) to the flags, and check how "judgment entered" cases are counted. Then regenerate `v2` and `v3` and rerun the evaluation.
2. **Score more carefully:** blind the `v2`/`v3` comparison, label more companies, and rerun each version a few times to see the variance.
3. **Improve the measurement:** extend grounding to percentages and ratios, and try an LLM judge, but only after checking how well it agrees with my own labels.
4. **Test on messier data:** the synthetic records are clean, so I would try it on real filings with real names, where "verify Director 1's identity" would no longer be noise.
5. **Keep improving it with feedback:** have the vetting team rate summaries and log which ones they overrode, then use that to update the labels and the flag rules.