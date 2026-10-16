# Findings report: Jensen Huang (Nvidia founder and CEO)

## Bottom line
**NO_ADVERSE** — almost certain (97%), as of 2026-10-01.  
**Subject type:** person  
**Identity:** Jensen Huang (Nvidia founder and CEO)

Verdict: NO_ADVERSE (97% confidence). As of 2026-10-01, Jensen Huang's full name is Jen-Hsun Huang and he is Founder, President, and Chief Executive Officer of Nvidia Corporation, with no known criminal convictions, charges, sanctions, or major civil judgments.

## Key findings
- Jensen Huang's full legal name is Jen-Hsun Huang and he serves as Founder, President, and Chief Executive Officer of Nvidia Corporation per the company's 2025 annual report filed with the SEC. [1A] _(credibility 3: possibly true)_
- As of October 1, 2026, there is no public record of Jensen Huang ever being convicted of a crime, charged with a criminal offense, sanctioned by a government regulator, or subject to a major civil judgment. [2D][3C][4B][5E] _(credibility 1: confirmed)_

## Minor adverse items (not material to the verdict)
- None found.

## Conflicting information
- No open conflict between independent sources.

## Searches performed

| Round | Tool | Query | Results | Decisive |
|---|---|---|---|---|
| 1 | news_search | Jensen Huang convicted charged sanctioned civil judgment 2024 2025 2026 | 6 |  |
| 1 | sanctions | Jensen Huang | UnusableArgument: sanctions needs a tool this toolbox offers, got: Jensen Huang |  |
| 1 | sec_edgar | Nvidia Corporation 2025 annual report Jensen Huang | 6 |  |
| 2 | web_search | Nvidia Corporation 2025 annual report PDF Jensen Huang CEO | 6 | yes |
| 2 | read_page | https://www.sec.gov/Archives/edgar/data/1045810/000104581025000012/nvda-20250128.htm | PageUnreadable: the page at https://www.sec.gov/Archives/edgar/data/1045810/000104581025000012/nvda-20250128.htm could not be read: 404 page not found |  |
| 2 | web_search | Jensen Huang criminal charge 2026 lawsuit | 6 |  |
| 3 | encyclopedia | Nvidia | 1 |  |
| 3 | web_search | Nvidia official history Jensen Huang founder 1993 | 6 | yes |
| 3 | read_page | https://www.nvidia.com/about-us/ | PageUnreadable: the page at https://www.nvidia.com/about-us/ could not be read: 404 page not found |  |
| 4 | court_records | Jen-Hsun Huang securities fraud | 6 |  |
| 4 | read_page | http://nvidianews.nvidia.com/bios/jensen-huang | 1 | yes |

## Coverage

Checked with a dedicated tool:
- Court dockets and judgments
- SEC EDGAR filings

Not checked:
- Sanctions lists (OFAC SDN, EU, UN, UK): not checked (no connector)
- Politically-exposed-person lists: not checked (no connector)
- Company registers: not checked (no connector)
- Insolvency registers: not checked (no connector)
- GLEIF legal-entity (LEI) records: not checked (a tool exists but was not used)
- Credit bureaus: not checked (no connector)
- Interpol notices: not checked (no connector)
- Archived (Wayback) copies of pages: not checked (a tool exists but was not used)
- The sanctions lookup tool failed due to missing tool support, so no automated check of sanctions lists was performed. [withdrawn: no tool checked sanctions]
- No search was conducted of foreign government sanctions lists (e.g., EU, UK) or civil judgment repositories beyond the sources examined. [withdrawn: no tool checked sanctions]

## Gaps and recommended next steps
- The direct SEC page for the 2025 annual report returned a 404 error, preventing verification via that specific URL; however, an alternate SEC URL provided the needed information.
- The Nvidia corporate about-us page was inaccessible (404), limiting direct confirmation from the company's main site.
- No direct search of federal criminal case docket (PACER) was performed to confirm absence of charges.
- Next: Query PACER for any federal criminal or civil cases involving Jensen Huang.
- Next: Check the U.S. Department of the Treasury’s OFAC sanctions list and the Consolidated Screening List for Jensen Huang.
- Next: Review the latest SEC EDGAR filings (e.g., 10‑K, 10‑Q) for any disclosed legal proceedings involving Jensen Huang after the 2025 annual report.
- Next: Search European Union sanctions lists and UK HM Treasury sanctions for any mention of Jensen Huang.

## Sources

Letters are Admiralty source-reliability grades (A best, F cannot be judged).
1. (A) [2025 NVIDIA Corporation Annual Review](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000098/finalforfiling-2025xannual.pdf) — official, reliability 0.95
2. (D) [Jensen Huang | NVIDIA Newsroom](http://nvidianews.nvidia.com/bios/jensen-huang) — unvetted, reliability 0.40
3. (C) [Who Is Jensen Huang, Nvidia's Founder and CEO - Business Insider](https://www.businessinsider.com/10-fascinating-facts-about-nvidia-ceo-jensen-huang-2024-2) — news, reliability 0.65
4. (B) [Jensen Huang - Wikipedia](https://en.wikipedia.org/wiki/Jensen_Huang) — reference, reliability 0.75
5. (E) [Oral History of Jensen Huang](https://www.youtube.com/watch?v=0c8i4T9BSqY) — user_generated, reliability 0.30
