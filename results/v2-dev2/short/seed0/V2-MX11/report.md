# Findings report: Wirecard was audited by EY, which signed off its 2019 accounts.

## Bottom line
**MIXED** — unlikely (25%), as of 2026-10-01.  
**Subject type:** claim

The claim is mixed: EY was Wirecard's appointed external auditor for 2019, but it refused to sign off the 2019 accounts on 18 June 2020 and therefore did not issue an audit opinion. Thus the subject was audited by EY, but EY did not sign off the accounts.

## Key findings
- EY was appointed external auditor of Wirecard for the fiscal year ending 2019. [1B][2C] _(credibility 2: probably true)_
- On 18 June 2020, EY formally refused to sign off Wirecard's 2019 accounts. [1B][3B] _(credibility 4: doubtful)_
- EY did not issue an unqualified audit opinion on Wirecard's 2019 financial statements. [1B][4C] _(credibility 4: doubtful)_
- EY did not issue any audit opinion (including qualified) for Wirecard's 2019 accounts after the refusal. [1B][3B] _(credibility 4: doubtful)_
- After the refusal, EY did not issue a revised opinion or withdrawal; it stated it was seeking clarification. [3B] _(credibility 4: doubtful)_

## Minor adverse items (not material to the verdict)
- None found.

## Conflicting information
- What is the full legal name and jurisdiction of the audit firm referred to as EY? - supported by finance.yahoo.com, wirecard.com (weight 1.05) vs refuted by europarl.europa.eu (weight 0.95)
- Did EY later issue any revised opinion or withdrawal after the refusal? - supported by cnbc.com (weight 0.85) vs refuted by europarl.europa.eu (weight 0.95)
  - Assessment: Q2: The full legal name and jurisdiction of EY. Supporting sources (finance.yahoo.com, wirecard.com) indicate EY is Ernst & Young GmbH Wirtschaftsprüfungsgesellschaft, Germany. Refuting source (europarl.europa.eu) focuses on EY's refusal to sign the audit report and does not directly dispute the name/jurisdiction. Weighted more heavily toward the supporting sources, so we accept the German GmbH description.
  - Assessment: Q7: Whether EY issued a revised opinion or withdrawal after refusing to sign Wirecard's 2019 accounts. Supporting source (cnbc.com) states EY did not issue a revised opinion and was seeking clarification. Refuting source (europarl.europa.eu) states EY declared fraud and false confirmations, which could be read as a statement but not an audit opinion. Weigh the cnbc.com source as more specific to audit opinion, thus lean toward no revised opinion, but acknowledge residual uncertainty.

## Searches performed

| Round | Tool | Query | Results | Decisive |
|---|---|---|---|---|
| 1 | gleif | Wirecard | 3 |  |
| 1 | gleif | Ernst & Young | 3 |  |
| 1 | web_search | Wirecard 2019 audit report Ernst & Young opinion | 6 | yes |
| 2 | web_search | EY disclaimer of opinion Wirecard 2019 financial statements | 6 |  |
| 2 | web_search | EY refused to sign off Wirecard 2019 accounts April 2020 date | 6 |  |
| 2 | web_search | EY withdrew audit opinion Wirecard 2019 revised opinion after refusal | 6 |  |
| 3 | web_search | Wirecard 2019 annual report auditor's report Ernst & Young | 6 | yes |
| 3 | sec_edgar | Wirecard 2019 | 6 |  |
| 3 | news_search | EY disclaimer of opinion Wirecard 2019 | 2 |  |
| 4 | news_search | Wirecard June 18 2020 EY refuses to sign 2019 accounts | 6 | yes |
| 4 | read_page | https://www.europarl.europa.eu/RegData/etudes/STUD/2020/651383/IPOL_STU(2020)651383_EN.pdf | 1 |  |
| 4 | read_page | https://www.cnbc.com/2020/06/18/wirecard-shares-plummet-as-payments-firm-postpones-annual-report.html | 1 | yes |

## Coverage

Checked with a dedicated tool:
- GLEIF legal-entity (LEI) records
- SEC EDGAR filings

Not checked:
- Sanctions lists (OFAC SDN, EU, UN, UK): not checked (no connector)
- Politically-exposed-person lists: not checked (no connector)
- Company registers: not checked (no connector)
- Insolvency registers: not checked (no connector)
- Court dockets and judgments: not checked (a tool exists but was not used)
- Credit bureaus: not checked (no connector)
- Interpol notices: not checked (no connector)
- Archived (Wayback) copies of pages: not checked (a tool exists but was not used)
- The exact legal name and jurisdiction of EY (Ernst & Young GmbH Wirtschaftsprüfungsgesellschaft) rests on mixed source weight; a definitive corporate registry check would remove uncertainty. [withdrawn: no tool checked company_register]

## Gaps and recommended next steps
- The precise date of EY's appointment as Wirecard's auditor for 2019 is not specified in the evidence; confirming the engagement letter would clarify the auditor-of-record period.
- Whether EY ever issued an internal draft opinion (e.g., the June 2 2020 draft mentioned in Bloomberg Tax) that was later withdrawn is not fully resolved.
- Next: Consult EY's official press release archive for a June 18 2020 statement on the Wirecard audit refusal.
- Next: Review BaFin enforcement documents and Wirecard insolvency filing for the auditor's role and any subsequent opinions.
- Next: Search for the alleged June 2 2020 draft unqualified audit opinion referenced in Bloomberg Tax to determine its status.
- Next: Check the German Federal Gazette (Bundesanzeiger) for any published auditor resignation or withdrawal notices related to Wirecard 2019.

## Sources

Letters are Admiralty source-reliability grades (A best, F cannot be judged).
1. (B) [The rise and fall of Wirecard | Reuters](https://www.reuters.com/business/finance/rise-fall-wirecard-2022-12-06) — major_news, reliability 0.85, published 2022-12-06
2. (C) [The rise and fall of Wirecard](https://sg.finance.yahoo.com/news/rise-fall-wirecard-085534538.html) — news, reliability 0.65, published 2020-07-30
3. (B) [Wirecard shares plummet as payments firm postpones annual report](https://www.cnbc.com/2020/06/18/wirecard-shares-plummet-as-payments-firm-postpones-annual-report.html) — major_news, reliability 0.85
4. (C) [Wirecard's auditors EY say they were victims of an 'elaborate' fraud by their client that ended in US$2 billion of missing funds](https://finance.yahoo.com/news/wirecards-auditors-ey-were-victims-093000015.html) — news, reliability 0.65
