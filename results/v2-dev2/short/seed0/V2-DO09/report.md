# Findings report: Builder.ai was listed on Nasdaq in an IPO in February 2026, raising USD 1.2 billion, with trading beginning on 10 February 2026 under the ticker BLDR.

## Bottom line
**FALSE** — roughly even chance (51%), as of 2026-10-01.  
**Subject type:** claim  
**Identity:** Builder.ai (listed on Nasdaq; IPO; February 2026; raised USD 1.2 billion; 10 February 2026; ticker BLDR)

Verdict: FALSE (51% confidence). The only independent evidence indicates Builder.ai entered insolvency proceedings in 2025, which contradicts the claim of a February 2026 Nasdaq IPO raising USD 1.2 billion under ticker BLDR. The analyst‑provided image asserting the IPO is not verifiable and conflicts with the insolvency information, so the IPO claim is not supported.

## Key findings
- Builder.ai's inception date is 2016-00-00. [1B] _(credibility 3: possibly true)_
- Builder.ai entered insolvency proceedings in 2025. [2B] _(credibility 3: possibly true)_

## Minor adverse items (not material to the verdict)
- None found.

## Conflicting information
- No open conflict between independent sources.
  - Assessment: Conflict between analyst-provided image claiming a February 2026 Nasdaq IPO (builderai_ipo_2026.png) and Wikipedia entry stating Builder.ai entered insolvency proceedings in 2025. The analyst-provided image was disregarded as non‑verifiable per instruction, leaving the Wikipedia insolvency claim as the only independent evidence; thus the conflict is resolved in favor of the insolvency claim, supporting a FALSE verdict.

## Searches performed

| Round | Tool | Query | Results | Decisive |
|---|---|---|---|---|
| 1 | sec_edgar | Builder.ai IPO 2026 | 6 |  |
| 1 | web_search | Builder.ai legal name incorporated | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 1 | web_search | Builder.ai founded founders | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 2 | wikidata | Builder.ai | 1 | yes |
| 2 | gleif | Builder.ai | 0 |  |
| 2 | news_search | Builder.ai Nasdaq IPO February 2026 | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 3 | encyclopedia | Builder.ai | 1 | yes |
| 3 | sec_edgar | Builder.ai Form S-1 2026 | 6 |  |
| 4 | sec_edgar | Builder.ai F-1 2026 | 6 |  |
| 4 | news_search | Builder.ai BLDR Nasdaq listing 2026 | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 4 | read_page | https://www.wikidata.org/wiki/Q134984536 | ServiceRejected: https://api.tavily.com/extract rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |

## Coverage

Checked with a dedicated tool:
- GLEIF legal-entity (LEI) records
- SEC EDGAR filings
- structured_identity

Not checked:
- Sanctions lists (OFAC SDN, EU, UN, UK): not checked (no connector)
- Politically-exposed-person lists: not checked (no connector)
- Company registers: not checked (no connector)
- Insolvency registers: not checked (no connector)
- Court dockets and judgments: not checked (a tool exists but was not used)
- Credit bureaus: not checked (no connector)
- Interpol notices: not checked (no connector)
- Archived (Wayback) copies of pages: not checked (a tool exists but was not used)

## Document assessment and manipulation flags
- The analyst‑provided image builderai_ipo_2026.png is undated, shows a claim of a February 2026 Nasdaq IPO and USD 1.2 billion proceeds, but contradicts the independent Wikipedia entry indicating insolvency in 2025; it is not internally consistent with other evidence and does not constitute verifiable proof.

## Gaps and recommended next steps
- Legal name and country of incorporation have not been verified by independent sources.
- Exact founding date and principal founders are only known as a vague 2016 inception; no precise date or founder names are available.
- Whether an IPO actually occurred in February 2026, the ticker BLDR, and the claimed USD 1.2 billion proceeds remain unverified; no SEC filing, Nasdaq announcement, or major news coverage has been found.
- Details of any SEC Form S-1 or F-1 filing for the alleged IPO are missing.
- Official Nasdaq listing notice or press release for ticker BLDR around February 2026 has not been located.
- Coverage from major news outlets (Reuters, Bloomberg, Financial Times) regarding a Builder.ai Nasdaq IPO in February 2026 is absent.
- Next: Query SEC EDGAR for Builder.ai Form S-1 or F-1 filings dated 2026.
- Next: Search Nasdaq's website for a listing notice or press release for ticker BLDR around February 2026.
- Next: Search major news outlets (Reuters, Bloomberg, Financial Times) for articles about Builder.ai Nasdaq IPO in February 2026.
- Next: Check Gleif or other LEI registry for Builder.ai to obtain legal name and jurisdiction.

## Sources

Letters are Admiralty source-reliability grades (A best, F cannot be judged).
1. (B) [Wikidata: Builder.ai](https://www.wikidata.org/wiki/Q134984536) — reference, reliability 0.75
2. (B) [Wikipedia: Builder.ai](https://en.wikipedia.org/wiki/Builder.ai) — reference, reliability 0.75

## Documents provided
- builderai_ipo_2026.png
