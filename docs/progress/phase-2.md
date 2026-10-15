# Phase 2: gathering and adaptation (G1–G5)

| ID | Status | Notes |
|---|---|---|
| G1 | **Done** | Wikidata (QIDs, dates), GLEIF (LEI records), SEC EDGAR full text, CourtListener opinions, Wayback, and OpenSanctions (offered only with an API key; otherwise the report says sanctions lists were not checked). Each declares `covers`. Six mocked tests. Official records map to the `OFFICIAL` tier. |
| G2 | **Deferred** | Not implemented: no automatic `read_page` upgrade of decisive snippets, and no chunked retrieval beyond the 4,000-character window. Reason: the posterior/gate work (A1/A2) had priority; G2 changes evidence quality and would need its own measured comparison. |
| G3 | **Done** | `QueryLedger` (token Jaccard ≥ 0.8 among searches, exact match for page reads) in every memory mode; rejected repeats are shown to the Researcher for one more try. Logged as `query_rejected` events and counted per episode (`rejected_repeats`). |
| G4 | **Partial** | No value-of-information computation. What exists instead: the Reflector sees the evidence posterior and an ACH matrix, and an UNVERIFIABLE verdict closes on search effort (two rounds) rather than probability. A VOI stopping rule is future work. |
| G5 | **Partial** | Memory is re-queried whenever the Reflector raises follow-up questions. A namesake gate hides facts about another identity with the same name. Entity IDs are normalised name-plus-disambiguators, **not** Wikidata QIDs or LEIs (the tools return them, but they are not yet threaded into memory keys). |

Live smoke test: 10 investigations (`benchmark/live_regressions.sh`); results in `phase-4.md`.
