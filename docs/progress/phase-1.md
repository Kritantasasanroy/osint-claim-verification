# Phase 1: agent correctness (A1–A10)

All code-level items are implemented with regression tests in `tests/test_remediation.py`. Live effects are
recorded in `phase-4.md`.

| ID | What changed | Where | Key test |
|---|---|---|---|
| A1 | `EvidencePosterior` (log-odds from independent evidence; identity and clean-screen terms for entities). The shipped belief's verdict comes from a log-linear pool of model and posterior; its confidence is the posterior (unfitted) or a dev-fitted logistic calibrator; capped at 0.99. All three are stored on every `Step`. | `investigation/posterior.py`, `confidence.py` | `test_two_weak_sources_cannot_produce_a_confident_verdict` |
| A2 | `QuestionRole`; the gate counts independent clusters on verdict-deciding questions only, weight ≥ 1.0, and an authoritative source for ADVERSE/FALSE | `case_file.py:unmet_conditions` | `test_c20_identity_confirmations_do_not_corroborate_an_adverse_verdict` |
| A3 | Tier ceilings; `USER_GENERATED` tier; layered prior (rating CSV → lists → TLD shape); outcomes only from ground truth (`ResolvedBy`), and only on the dev split | `source.py`, `case_file.py`, `runner.py` | `test_twenty_agreements_cannot_lift...`, `test_track_records_are_learned_on_dev_cases_only` |
| A4 | Publisher clusters (5-word shingles, Jaccard ≥ 0.6); Admiralty letters; credibility 1–6 | `independence.py`, `report.py` | `test_one_wire_story_on_three_domains_is_one_independent_publisher` |
| A5 | Full-quote containment, or rapidfuzz partial ratio ≥ 90, at least 20 characters; `quote_verified` | `agents/evaluator.py:QuoteCheck` | `test_a_quote_must_be_in_its_source_in_full` (4 cases) |
| A6 | `Subject.as_of`; "Today is …" in every prompt; Tavily `published_date`; relative staleness on state claims; newest-first briefings | `subject.py`, `case_file.py`, `briefing.py` | `test_old_evidence_on_a_state_claim_is_stale...`, `test_every_agent_prompt_carries_the_as_of_date` |
| A7 | `Severity`; only material severities vote ADVERSE; minor items reported; rubric in `docs/materiality.md` and the shared prompt rubric | `evidence.py`, `agents/rubric.py` | `test_only_material_adverse_facts_vote_for_adverse` |
| A8 | `Scope` with entity, disambiguators, assertion; `ScopeCheck` in code, one retry, then the analyst's own words; 32-input scope test set | `agents/planner.py`, `benchmark/scope_cases.json` | `test_the_jordan_scope_that_dropped_the_claim_is_caught` |
| A9 | Searches and coverage generated from the case file; registry claims that no tool checked are withdrawn; uploads never corroborate; document assessment | `report.py` | `test_the_report_withdraws_unchecked_registry_claims...` |
| A10 | `<untrusted_source>` wrappers and a standing rule in every prompt; `ManipulationScan` (regex) flags and halves reliability; injection slice in v2 | `source.py`, `briefing.py` | `test_an_upload_never_corroborates_itself_and_its_instructions_are_flagged` |

**Defects found by writing the tests** (all fixed before commit):

1. Pooling the confidence as well as the verdict still shipped 90% on two 0.40 sources, because renormalising a
   near-certain model distribution dominates. The confidence is now evidence-only until a calibrator is fitted.
2. An absolute one-year staleness horizon marked all of Do Kwon's evidence stale. Staleness is now relative to
   the newest dated evidence.
3. The name regex split "device" at the connector "de".
4. Keyword-argument evaluation order dropped withdrawn gap sentences silently.
5. With no identity question, adverse items were double-counted as identity confirmations.

**Not done in this phase:** an LLM-based injection detector (the detector is regex only). The A1 calibrator is
implemented and tested but **not yet fitted**: fitting needs a dev-split run (see phase 4).
