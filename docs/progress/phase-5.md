# Phase 5: reflection and reporting (P1–P2)

| ID | Status | Notes |
|---|---|---|
| P1 | **Done** | A red-team `Critic` on the judge's model family argues for the runner-up verdict and may name one cheap check, which the loop runs once (`test_a_red_team_check_buys_exactly_one_more_round`). The Reflector sees an analysis-of-competing-hypotheses matrix (evidence × verdicts). Not done: the ACH matrix in `report.json`. |
| P2 | **Done** | Report order: bottom line (verdict, ICD-203 estimative phrase, as-of), key findings with Admiralty letters and credibility 1–6, minor adverse items, conflicts, searches performed, coverage and "not checked", document assessment and manipulation flags, gaps and next steps, sources. `report.json` carries `schema_version: "2"`. Live example: `results/live-regressions/live-regressions-v2/H6_doc_injection`. |

Known presentation flaw: an UNVERIFIABLE verdict prints a probability ("unlikely (33%)") that means little for
insufficiency. It should be expressed as search effort.
