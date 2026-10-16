# Findings report: Costco Wholesale Corporation was convicted of wire fraud on 3 February 2026 and fined USD 2.4 billion.

## Bottom line
**FALSE** — unlikely (25%), as of 2026-10-01.  
**Subject type:** claim  
**Identity:** Costco Wholesale Corporation (3 February 2026)

VERDICT: FALSE (25% confidence). The decisive facts are that Costco Wholesale Corporation's legal name and ticker are confirmed, its headquarters and business are as described, and its 2026 SEC filings show no disclosure of a wire‑fraud conviction or a $2.4 billion fine, while the only support for the claim is an unverified, undated image.

## Key findings
- Costco Wholesale Corporation's exact legal name is Costco Wholesale Corporation and its stock ticker is COST. [1A][2B] _(credibility 3: possibly true)_
- Costco Wholesale Corporation's worldwide headquarters are in Issaquah, Washington and it operates a chain of membership-only big-box warehouse club retail stores. [2B] _(credibility 6: cannot be judged)_
- Costco Wholesale Corporation's 2026 SEC filings (dated 2026-03-11, 2026-06-03, and 2026-10-07) disclose no items related to a wire fraud conviction or any fine. [3A][4A][5A] _(credibility 4: doubtful)_

## Minor adverse items (not material to the verdict)
- None found.

## Conflicting information
- No open conflict between independent sources.
  - Assessment: The claim of a 3 February 2026 wire‑fraud conviction and a $2.4 billion fine is supported only by an undated image (costco_conviction_notice.png), whereas multiple 2026 SEC filings show no disclosure of such a conviction or fine. The SEC filings were given greater weight because they are official, regularly submitted regulatory documents, while the image lacks verifiable metadata and corroboration.

## Searches performed

| Round | Tool | Query | Results | Decisive |
|---|---|---|---|---|
| 1 | court_records | Costco Wholesale Corporation wire fraud | 6 |  |
| 1 | wikidata | Costco Wholesale Corporation | 1 |  |
| 1 | encyclopedia | Costco Wholesale Corporation | 1 | yes |
| 2 | court_records | United States v. Costco Wholesale Corporation | 6 |  |
| 2 | news_search | Costco Wholesale Corporation wire fraud conviction February 2026 Department of Justice | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 2 | sec_edgar | Costco Wholesale Corporation 2026 10-K legal proceedings | 6 | yes |
| 3 | news_search | Costco Wholesale Corporation wire fraud conviction February 2026 | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 3 | sec_edgar | Costco Wholesale Corporation wire fraud | 6 | yes |
| 3 | news_search | Department of Justice press release Costco wire fraud February 2026 | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 4 | web_search | United States v. Costco Wholesale Corporation 2026 wire fraud | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 4 | web_search | costco_conviction_notice.png metadata authenticity | ServiceRejected: https://api.tavily.com/search rejected the request with HTTP 432: {"detail":{"error":"This request exceeds your plan's set usage limit. Please upgrade your plan or contact support@tavily.com"}} |  |
| 4 | court_records | United States v. Costco Wholesale Corporation criminal | 6 |  |

## Coverage

Checked with a dedicated tool:
- Court dockets and judgments
- SEC EDGAR filings
- structured_identity

Not checked:
- Sanctions lists (OFAC SDN, EU, UN, UK): not checked (no connector)
- Politically-exposed-person lists: not checked (no connector)
- Company registers: not checked (no connector)
- Insolvency registers: not checked (no connector)
- GLEIF legal-entity (LEI) records: not checked (a tool exists but was not used)
- Credit bureaus: not checked (no connector)
- Interpol notices: not checked (no connector)
- Archived (Wayback) copies of pages: not checked (a tool exists but was not used)

## Document assessment and manipulation flags
- The analyst‑provided document costco_conviction_notice.png is undated and makes a specific factual claim about a past conviction (as of 2026‑10‑01). It contains no verifiable metadata, digital signatures, or source information that would allow authentication, and it is not corroborated by any official government or regulatory source. Consequently its authenticity cannot be established and it may be manipulated or fabricated.
- Asserted only by the provided document (not independently corroborated): The sole support for the alleged conviction is an undated image (costco_conviction_notice.png) claiming a 3 February 2026 wire‑fraud conviction and a $2.4 billion fine.

## Gaps and recommended next steps
- No verifiable news articles, Department of Justice press releases, or major‑wire service reports from February 2026 concerning a Costco wire‑fraud conviction were accessible due to search‑service limits.
- The authenticity and provenance of costco_conviction_notice.png could not be established because metadata verification and external corroboration searches were blocked by service limits.
- No PACER docket or federal criminal case record for 'United States v. Costco Wholesale Corporation' in 2026 could be retrieved.
- No DOJ press release or official court document confirming the alleged conviction or fine was located.
- Next: Request an official copy of the alleged conviction notice from the Department of Justice to verify authenticity.
- Next: Examine the metadata and provenance of costco_conviction_notice.png using forensic tools to assess possible manipulation.
- Next: Search PACER for any criminal case titled 'United States v. Costco Wholesale Corporation' filed in 2026 and retrieve the docket and judgment documents.
- Next: Search major news wires (Bloomberg, Reuters, AP) and DOJ press‑release archives for February 2026 announcements of a Costco wire‑fraud conviction or $2.4 billion fine.

## Sources

Letters are Admiralty source-reliability grades (A best, F cannot be judged).
1. (A) [SEC 10-Q: COSTCO WHOLESALE CORP /NEW  (COST)  (CIK 0000909832)](https://www.sec.gov/Archives/edgar/data/909832/000090983225000015/costex10210q21625.htm) — official, reliability 0.95, published 2025-03-13
2. (B) [Wikipedia: Costco](https://en.wikipedia.org/wiki/Costco) — reference, reliability 0.75
3. (A) [SEC 10-K: COSTCO WHOLESALE CORP /NEW  (COST)  (CIK 0000909832)](https://www.sec.gov/Archives/edgar/data/909832/000090983226000093/cost-20260830.htm) — official, reliability 0.95, published 2026-10-07
4. (A) [SEC 10-Q: COSTCO WHOLESALE CORP /NEW  (COST)  (CIK 0000909832)](https://www.sec.gov/Archives/edgar/data/909832/000090983226000051/cost-20260510.htm) — official, reliability 0.95, published 2026-06-03
5. (A) [SEC 10-Q: COSTCO WHOLESALE CORP /NEW  (COST)  (CIK 0000909832)](https://www.sec.gov/Archives/edgar/data/909832/000090983226000029/cost-20260215.htm) — official, reliability 0.95, published 2026-03-11

## Documents provided
- costco_conviction_notice.png
