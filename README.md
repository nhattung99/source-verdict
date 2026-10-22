# SourceVerdict

SourceVerdict dies without GenLayer: no EVM contract can read a news outlet About page and reason about editorial standards, ownership transparency, and political bias on-chain — only GenLayer's AI validators can fetch live source pages during consensus and produce a multi-node verified credibility assessment as a public-good on-chain registry.

## Problem

AI agents and researchers cite sources in reports, proposals, and governance votes, but there is no neutral on-chain mechanism to assess whether a source is credible. A professional newsroom, a personal blog, an official document, and a sensationalist site all look like URLs. Wikipedia and centralized fact-checkers are themselves single points of trust. DAO governance increasingly needs a verifiable source-quality check before a citation is allowed in a proposal.

## Solution

SourceVerdict accepts a public source URL and an optional second URL (an About page, a Wikipedia article, or a media-bias reference). During consensus, validators fetch those pages and score the source. The Credibility Score (0-100), tier, source type, and bias direction are stored permanently as a public-good credibility registry.

Remove `web.render` and the LLM and this contract is only a registry of whatever score the submitter typed in. The AI analysis is the product.

## How it works

1. **Submit.** Anyone calls `submit_source(source_url, about_url)`. Pass `""` to omit the about URL. The report is stored as `PENDING`. `url_cache[source_url]` points at this report id. A later submission of the same URL overwrites the cache entry. The earlier report stays readable by id.
2. **Assess.** Anyone calls `assess_source(report_id)`. Validators fetch the source page and, when provided, the about page, then judge credibility.
3. **Read the result.** `get_assessment(report_id)` returns the tier, source type, bias, score, confidence, reasoning, strengths, and weaknesses. `get_report(report_id)` returns the full record.
4. **Lookup cache.** `lookup_by_url(source_url)` returns the latest report stored for that URL, or `{"found": false}` when the URL has never been submitted.

The contract owner can call `invalidate_report(report_id)` on a `PENDING` record. That sets status to `UNASSESSABLE` and reasoning to `Invalidated by admin`.

## Tier guide

| Tier | Score | Meaning |
| --- | --- | --- |
| `HIGH_CREDIBILITY` | 75-100 | Multiple strengths, few weaknesses, transparent ownership, established professional standards. |
| `MODERATE` | 40-74 | Some strengths and some weaknesses. Generally reliable, with caveats. |
| `LOW_CREDIBILITY` | 0-39 | Significant weaknesses, opacity, or known credibility issues. At least one weakness is required. |
| `UNASSESSABLE` | 0 | The source could not be read, the model output could not be parsed, or the tier string was not one of the four labels. Admin invalidation of a pending report also sets this status. |

`get_assessment` reverts with `Not yet assessed` while status is `PENDING`. A tier other than `UNASSESSABLE` sets status to `ASSESSED`.

## Source types

`NEWS_OUTLET`, `ACADEMIC`, `OFFICIAL_DOCS`, `BLOG`, `SOCIAL_MEDIA`, `AGGREGATOR`, `UNKNOWN`.

- `NEWS_OUTLET`: professional journalism organization with editorial staff
- `ACADEMIC`: peer-reviewed journal, university publication, or research paper
- `OFFICIAL_DOCS`: government, standards body, or official project documentation
- `BLOG`: personal or organizational blog without a formal editorial process
- `SOCIAL_MEDIA`: Twitter/X, Reddit, Facebook, or similar platform content
- `AGGREGATOR`: news aggregator, content curator, or link-sharing site
- `UNKNOWN`: cannot be determined from the fetched content, or the model returned a label outside this set

## Bias directions

`LEFT`, `CENTER_LEFT`, `CENTER`, `CENTER_RIGHT`, `RIGHT`, `UNKNOWN`, `NA`.

`NA` means bias is not applicable, for example an academic paper, official documentation, or other technical content. `UNKNOWN` means the lean could not be determined. A label outside this set is stored as `UNKNOWN`.

## Consensus design

`assess_source` runs inside `gl.vm.run_nondet_unsafe`. Each validator fetches the pages and makes its own credibility judgment. Agreement is on the meaning of that judgment, not on whether the model returned well-formed JSON. A payload that parses is still rejected when the decision differs.

- Each URL is fetched inside its own try/except. A failed page becomes text in the prompt. The leader always returns a dict and never raises.
- **Three categorical fields, exact match.** `tier`, `source_type`, and `bias_direction` are the decision. All three must agree exactly. A validator that reads the source as `BLOG` with bias `LEFT` rejects a leader result of `NEWS_OUTLET` with bias `CENTER`, even when both payloads are valid JSON.
- **Score tolerance.** `credibility_score` may differ by at most 5 points, and only inside the same tier. A gap larger than 5 fails consensus. The score is the finer reading after the tier matches.
- **LOW_CREDIBILITY weakness check.** Both the leader and the validator must list at least one weakness. Agreeing on the tier string is not enough. A low-credibility call with no stated weakness does not pass.
- **Confidence bands.** Confidence is not compared as an exact integer. Validators use three bands: 0-34, 35-79, and 80-100. They must land in the same band. Reasoning text is not compared.

## Consistency rules

Before a result is stored, the contract forces the tier and the score to agree:

- `HIGH_CREDIBILITY` below 75 is placed at 80.
- `MODERATE` outside 40-74 is placed at 57.
- `LOW_CREDIBILITY` above 39 is placed at 20.
- `UNASSESSABLE` is always 0.
- `LOW_CREDIBILITY` with an empty weakness list is upgraded to `MODERATE` with score 57.
- An unknown tier becomes `UNASSESSABLE`. An unknown source type or bias direction becomes `UNKNOWN`.
- Strengths and weaknesses are stored as JSON array strings. A non-list value is stored as `[]`.

## Use cases

- DAO governance source requirements: check a citation before it is accepted in a proposal.
- AI agent citation filter: refuse a low-credibility URL before it is written into a report.
- Research due diligence: read the tier, bias, and weakness list before relying on a page.
- Journalism fact-checking tooling: keep a public on-chain registry of outlet assessments.

## Edge cases

- A failed fetch is caught per URL and written into the prompt. The call still finishes.
- An empty or very short page is treated as unreadable.
- Malformed model JSON falls back to `UNASSESSABLE` with score 0 and reasoning that starts with `Parse error`.
- Unknown tier, source type, and bias strings are normalized. The transaction does not revert.
- A non-list `strengths` or `weaknesses` value is stored as `[]`.
- `LOW_CREDIBILITY` without a weakness is stored as `MODERATE`.
- `url_cache` keeps the latest report id for a source URL. Older reports remain available through `get_report`.
- Only the contract owner can invalidate a `PENDING` report.

## Deploy on GenLayer Studio (studionet)

1. Open [GenLayer Studio](https://studio.genlayer.com) and create an Intelligent Contract.
2. Paste `contracts/source_verdict.py`. The file header must stay the first lines (v0.2.16 and the `py-genlayer` dependency). Do not add a frontend.
3. Select network **studionet**.
4. Deploy. The constructor takes no arguments and sets `owner` to the deployer.
5. Call `submit_source(source_url, about_url)`. Pass `""` when there is no about or reference URL.
6. Call `assess_source(report_id)`. Then read `get_assessment(report_id)` or `lookup_by_url(source_url)`.

## Run tests

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
gltest tests/
```

`pytest tests/test_source_verdict.py -v` runs the same 26 tests.

## Deployment

- **CONTRACT_ADDRESS:** `0x131ba118B8594AA4e38c9e54DB9267aE805Ab8c8`
- **NETWORK:** studionet
- **Explorer:** https://explorer-studio.genlayer.com/address/0x131ba118B8594AA4e38c9e54DB9267aE805Ab8c8

A read-only `get_count()` call against this address returned `0`. `lookup_by_url("https://reuters.com/technology/ai")` returned `{"found": false}`. The account has the deploy transaction only, so no assessment is stored on-chain yet. The worked example below is the expected result from the local test suite (`test_high_credibility_news_outlet`), not a receipt from studionet.

### Worked example (expected output, not a live assessment)

Input to `submit_source`:

```text
source_url:  https://reuters.com/technology/ai
about_url:   https://en.wikipedia.org/wiki/Reuters
```

Expected `get_assessment` after `assess_source`:

```json
{
  "report_id": "1",
  "source_url": "https://reuters.com/technology/ai",
  "tier": "HIGH_CREDIBILITY",
  "source_type": "NEWS_OUTLET",
  "bias_direction": "CENTER",
  "credibility_score": 88,
  "confidence": 92,
  "strengths": "[\"established since 1851\", \"corrections policy\", \"transparent ownership\", \"named authors\"]",
  "weaknesses": "[]"
}
```

`get_report` then has `"status": "ASSESSED"`. This is the outcome the local validator accepts when all three categoricals match, the score stays within 5 points of 88, the weakness lists agree, and confidence stays in the 80-100 band.
