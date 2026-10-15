# Agentic Harness for OSINT: Report

> **Status.** This is the report *after* the independent review (`44/100`). All code changes are complete and tested
> (165 tests, `mypy --strict` and `ruff` clean). The **final held-out run has been done, in reduced form**: the 75-case
> test split, `closed_book` vs `short` memory, **1 seed**. The brief's fuller design (3 seeds, `none`/`long`/`long_only`
> memory modes, a human-labelled judge check) was **not** run: the new Tavily key has a 1,000-credit quota (about 640
> used), and the human labels cannot be produced by me. Every claim below says which run backs it; what was not
> measured is listed in section 7.

## 1. Headline: the held-out test split

**Agent (`short` memory) vs the same model with no tools, 75 test cases, 1 seed** (`results/v2-test/summary.md`):

| | `closed_book` (floor) | `short` (agent) |
|---|---|---|
| **Accuracy [95% bootstrap CI]** | 69% [59%, 79%] | **96% [91%, 100%]** |
| Paired difference (agent − floor) | | **+26.7 points [+14.7, +38.7]** |
| Cases only one mode got right | 2 | **22** |
| Exact McNemar / permutation p | | p ≈ 0.00004 (shown as 0.000) / < 0.001 |
| Scope accuracy (raw text, graded by code) | 100% | 100% |
| Key-fact recall (judge, low validity) | 43% [33%, 53%] | 87% [81%, 93%] |
| Citation precision, atomic facts (judge, low validity) | 0% (no citations) | 81% [74%, 87%] |
| Rounds / tool calls | 1 / 0 | 3.4 / 9.4 |
| ADVERSE verdicts citing a primary record | 0% | 73% |
| Tokens per case [95% CI] | 2,089 | 89,846 [84,224, 95,362] |
| Est. cost per 75 cases (assumed prices) | $0.05 | $1.57 |
| Wall-clock per case | 17 s | 1,452 s (much of it waiting on a throttled API) |

**By slice** (n = 7 per slice except long_tail n = 19; intervals are wide, treat as indicative):

| Slice | closed_book | short |
|---|---|---|
| temporal_state | 29% [0, 57] | 100% [100, 100] |
| post_cutoff | 43% [14, 86] | 86% [57, 100] |
| documents | 43% [14, 71] | 86% [57, 100] |
| non_english | 57% [14, 86] | 100% [100, 100] |
| mixed | 71% [43, 100] | 100% [100, 100] |
| long_tail | 79% [58, 95] | 95% [84, 100] |
| injection | 86% [57, 100] | 100% [100, 100] |
| materiality | 100% [100, 100] | 100% [100, 100] |
| namesake | 100% [100, 100] | 100% [100, 100] |

**What this does and does not show.**
- The agent beats the floor by a margin that is statistically clear on this split, and it does so where closed-book
  is weakest (current-state claims, non-English sources, documents, events after the training data). On the two
  slices where the floor is already perfect (materiality, namesake) there is nothing to gain, and the agent is not
  worse.
- **It is one seed, one split, one model pair.** Verdict stability across seeds is unmeasured. The dev split was used
  for tuning; this split was not, apart from the document-label rule (section 1.3) and the robustness fixes below.
- **Injection resistance (7 test payloads, all upload-style):** 0 of 7 attacks succeeded (the verdict never followed the
  planted instruction; upper 95% bound 35% at this size), and the report flagged the planted instruction in 6 of 7
  (86% [49%, 97%]), **below the ≥ 90% target**. Web-page injection is not tested.
- **The floor is the same model, not "no investigation"**: the gain is from retrieval and the code around it. A
  stronger no-tools model, or the same agent with its old gate, were not run.
- **The cost is large**: about 43 times the tokens and 85 times the wall-clock of the floor.
- **The confidence number is conservative, not calibrated.** Selective-prediction error (AURC) is 0.011 for the
  shipped confidence against 0.010 for the model's own, so it ranks answers as well; but its Brier score is 0.143
  against 0.061 (ECE 0.212 against 0.112). The dev-fitted calibrator is recorded and not adopted
  (`benchmark/calibration/README.md`).
- **The ground-truth-free process reward predicts correctness reasonably** (AUROC 0.75 across `short` episodes), which
  supports using it online. The ranking of the two modes is stable under ±50% on any single episode-reward weight
  (`benchmark/reward_sensitivity.py`), a weak test since the floor has no citations and cost carries a 0.1 weight.

### Protocol, disclosed

1. The code was frozen at tag `eval-freeze-v2` (`7de5181`) before the run. The benchmark's document-label rule was
   fixed *before* the run (section 1.3).
2. **17 of the 150 episodes crashed on that commit** (16 `short`, 1 `closed_book`): 8 API timeouts, rate limits or
   connection errors, 3 replies that failed validation twice, 1 truncated report, and judge calls. They were re-run
   with the same command on commit `7039770`, which changed only transport, retry and error-handling code (an adaptive
   per-host concurrency limit with a shared cooldown, three-attempt model replies, and whole-episode retries), not
   agent logic or verdict rules. The original run's manifest is kept as `run_manifest.freeze.json`.
3. So **133 episodes ran on the frozen commit and 17 on the later one.** The re-run episodes are the harder, longer
   cases: `short` scored 14/16 on them against 58/59 on the rest. Dropping the crashes instead of retrying them
   would have reported about 98%, not 96%. No episode is missing: 75/75 in both modes.
4. After the run, a failure-cause diagnosis (section 1.1) re-ran the three wrong episodes under single changes. That
   uses the test split for diagnosis, not tuning; nothing was changed in response.

### 1.1 The three wrong answers, and what caused them

| Case | Expected → got | What happened |
|---|---|---|
| V2-DO12 (forged "Patagonia added to the OFAC SDN list") | FALSE → UNVERIFIABLE 25% | The agent cannot check sanctions lists (no OpenSanctions key), so its report correctly withdrew 4 sentences about OFAC. The claim is a negative that only a sanctions tool settles. Replays: **scoping to the gold claim and a different Reflector model both fixed it**; more rounds made it TRUE (worse); gold sources and no-memory did not. |
| V2-LT20 ("John Smith, businessman") | UNVERIFIABLE → NO_ADVERSE 82% | A real failure: the name is too common to identify anyone, but the agent adopted one namesake (a former GM executive) and cleared him. **No intervention fixed it**; a different Reflector made it ADVERSE, also wrong. The identity gate counts two sources confirming *a* John Smith as identity confirmed. |
| V2-PC05 (Benko "two years") | TRUE → MIXED 25% | Outlets disagreed (two vs two and a half years) and no court record was reachable. **A plain re-run with no change was correct, as were all five interventions**: this was sampling noise, and none of those "fixes" is a cause. |

Counterfactual replays are single samples on three episodes, and the control for DO12 itself failed (a malformed
reply), so **these attributions are weak evidence**. The tool (`diagnose`, with a `repeat` control) is built and
tested; a meaningful cause distribution needs many more wrong episodes.

### 1.2 Development evidence behind the design

**Benchmark v2 is no longer solvable from memory.** The same model with no tools scores **66% [58%, 73%]** on all
128 v2 cases (`results/v2-closed-book`), against 82–88% on v1 (post-cutoff 25%, temporal-state 42%).

**Agent vs closed-book on the dev split** (paired, same 53 cases, 1 seed, `short` memory; `results/v2-dev/`):

Complete dev run (`results/v2-dev2`, seed 0; reproduce the table with `python benchmark/interim_summary.py results/v2-dev2`):

```
95 finished episodes, 11 crashed (excluded), from results\v2-dev2

| Mode | Episodes | Accuracy [95% CI] | Scope acc. | Brier shipped/LLM | AURC shipped/LLM | Rounds | Tokens [95% CI] | ADVERSE citing primary record | Crashed |
|---|---|---|---|---|---|---|---|---|---|
| closed_book | 53 | 62% [49%, 75%] | 94% | 0.303/0.303 | 0.258/0.258 | 1.00 | 2,078 [1,980, 2,189] | 0% | 0 |
| short | 42 | 88% [79%, 98%] | 95% | 0.184/0.067 | 0.034/0.014 | 3.43 | 81,409 [72,219, 91,910] | 25% | 11 |

Paired (only cases both modes finished):

| Treated vs baseline | Cases | Difference [95% CI] | Discordant (+/-) | McNemar p | Permutation p |
|---|---|---|---|---|---|
| short vs closed_book | 42 | +0.238 [+0.071, +0.405] | 12/2 | 0.013 | 0.017 |

By slice:

| Slice | closed_book | short |
|---|---|---|
| documents | 80% [40%, 100%] (n=5) | 75% [25%, 100%] (n=4) |
| injection | 40% [0%, 80%] (n=5) | 25% [0%, 75%] (n=4) |
| long_tail | 69% [46%, 92%] (n=13) | 100% [100%, 100%] (n=8) |
| materiality | 80% [40%, 100%] (n=5) | 100% [100%, 100%] (n=4) |
| mixed | 80% [40%, 100%] (n=5) | 100% [100%, 100%] (n=5) |
| namesake | 60% [20%, 100%] (n=5) | 100% [100%, 100%] (n=5) |
| non_english | 80% [40%, 100%] (n=5) | 75% [25%, 100%] (n=4) |
| post_cutoff | 20% [0%, 60%] (n=5) | 100% [100%, 100%] (n=3) |
| temporal_state | 40% [0%, 80%] (n=5) | 100% [100%, 100%] (n=5) |
```

What this does and does not show:
- On the 42 dev cases both modes finished, the agent is right on 37 and closed-book on 28: **+23.8 points
  [+7.1, +40.5], McNemar p = 0.013, permutation p = 0.017** (12 cases only the agent got right, 2 only closed-book).
  The gain is concentrated where closed-book is weak: post-cutoff, temporal-state and long-tail cases.
  This is a **dev-split, one-seed** result that was also used for tuning. It is evidence, not the headline.
- **11 of 53 `short` investigations crashed** (8 schema/truncation failures fixed in `d8e7a92` after this run started,
  1 rate limit). They are excluded, not counted as right, so the agent's accuracy is over 42 cases.
- **The injection slice is weak (1 of 4).** Two misses were a benchmark-design flaw found here: document-only
  inputs labelled as companies, where the agent reasonably scoped the document's claim and answered it. The rule
  was then fixed **before the test run**: a document-only case is a claim, enforced by `BenchmarkAudit`. Three
  cases were relabelled (IN01 and IN06 are dev cases whose results had been seen; IN07 is a test case that had
  not), so the dev numbers above are for the old labels.
- **Three answers drifted to UNVERIFIABLE at 25%** (a Nikola filing, an FTX letter, a Hindi claim): the evidence-only
  confidence kept the case open until the model gave up.
- **Calibration:** Brier 0.184 for the shipped evidence-only confidence against 0.067 for the model's verbalised number.
  A calibrator fitted on this run (leave-one-out Brier 0.075) is recorded but **not adopted** (benchmark/calibration/README.md).
- An earlier attempt (`results/v2-dev`) lost 42 of 53 investigations to API rate limiting (fixed in `845d584`) and is
  not used.

**Held-out live regressions** from the review, re-run on the new code with raw analyst text, no cache and a fresh
memory (`benchmark/live_regressions.sh`, `runs/live-regressions-v2*`):

| Test | Expected | Before (review) | Now | Rounds | Tools | Tokens | Stop | Withdrawn | Flags |
|---|---|---|---|---|---|---|---|---|---|
| H1_scope_freetext | FALSE | FALSE 90%, 1 round, 17.7k tokens | ✔ FALSE 78% | 4 | 12 | 115.1k | budget | 0 | 0 |
| H2_materiality_costco | NO_ADVERSE | ADVERSE 86%, 4 rounds, 85.0k | ✔ NO_ADVERSE 92% | 3 | 9 | 81.8k | concluded | 0 | 0 |
| H3_javice | ADVERSE | ADVERSE 96%, 1 round, 29.5k | ✔ ADVERSE 99% | 2 | 6 | 64.6k | concluded | 0 | 0 |
| H4_temporal_dokwon | FALSE | FALSE 78%, 4 rounds, 128.2k | ✔ FALSE 99% | 4 | 12 | 189.7k | concluded | 1 | 0 |
| C31_velmorrath | UNVERIFIABLE | UNVERIFIABLE; report claimed OFAC/insolvency registers were checked | ✔ UNVERIFIABLE 33% | 4 | 10 | 85.6k | concluded | 1 | 0 |
| H5_holmes_numeric | TRUE | TRUE 95%, 1 round, 29.3k | ✔ TRUE 100% | 4 | 8 | 65.1k | concluded | 0 | 0 |
| H6_doc_injection | FALSE | FALSE 90%; forgery and injection not flagged; upload cited | ✔ FALSE 98% | 2 | 6 | 67.0k | concluded | 1 | 2 |
| R1_patagonia_a | NO_ADVERSE | NO_ADVERSE 85% (published v1: ADVERSE) | ✔ NO_ADVERSE 79% | 4 | 12 | 91.4k | budget | 2 | 0 |
| R1_patagonia_b | NO_ADVERSE | NO_ADVERSE 90% | ✔ NO_ADVERSE 89% | 3 | 8 | 87.3k | concluded | 0 | 0 |
| R2_jordan_none | FALSE | UNVERIFIABLE 70%; scoped to the bare name | ✘ UNVERIFIABLE 25% | 4 | 8 | 67.2k | concluded | 0 | 0 |

**9 of 10 correct** (the review: 5 clean, 1 partial, 2 wrong, and Patagonia reversed between runs). Disclosed, not
hidden: **H4's first run on this code was wrong** (TRUE 85%, the verdict-pooling defect in D1); the row above is the
re-run after the fix. **R1_patagonia_a's first run crashed** (an off-schema Reflector reply after retry); the row is
its re-run. H5's 100% predates the 0.99 cap. Costs went **up**: median ~85k tokens against ~30k before, because the
gate now demands corroboration the old one did not. "Withdrawn" counts sentences the report validator removed;
"Flags" counts manipulation flags. R2 is wrong for a new reason (§7): scoping is now right, but a negative claim about
a namesake never gets evidence pointing to FALSE.

### 1.3 Benchmark labels changed after seeing dev results

Three document-only injection cases (IN01 FTX, IN06 Northvolt, IN07 Costco) were labelled as companies, but a
document is scoped into the claim it makes. I changed all three to claims, by a rule applied uniformly and enforced
by `BenchmarkAudit`, before the test run. Two (IN01, IN06) are dev cases whose results I had seen. IN07's label
(UNVERIFIABLE or FALSE for "Costco is under criminal investigation") was chosen before any test result.

## 2. What the brief asked for → where it is → how it is measured

| Brief | Where | Measured by |
|---|---|---|
| Investigate a company, person or claim | `agents/planner.py` (`Scope`, `ScopeCheck`), `investigation/subject.py` | scope accuracy on raw text (v2 runner, default); 32-input scope set (`benchmark/scope_cases.json`) |
| Gather from multiple external sources | `tools.py`: Tavily web/news/extract, Wikipedia, **Wikidata, GLEIF, SEC EDGAR, CourtListener, Wayback, OpenSanctions** | share of ADVERSE verdicts citing a primary record; report coverage section |
| Plan and adapt | question roles, follow-ups, `QueryLedger`, red-team `Critic` | rounds, multi-round share, rejected repeats, red-team checks run |
| Evaluate evidence and source reliability | tiers + ceilings, clusters, Admiralty letters, credibility 1–6, `EvidencePosterior` | calibration of shipped vs LLM vs posterior confidence (Brier/ECE/AURC) |
| Handle conflicting or insufficient information | computed conflicts, materiality, staleness, UNVERIFIABLE by search effort | slices: mixed, temporal_state, long_tail |
| Short- and long-term memory | `CaseFile`; typed temporal facts with supersession and a namesake gate | `none`/`short`/`long`/`long_only` paired comparisons |
| Reflect before concluding | Reflector + code gate + red-team critic on another model | gate refusals in traces; counterfactual replays (`diagnose`, run on the 3 wrong test answers, §1.1) |
| Structured report with citations and confidence | `investigation/report.py` | judge citation precision (atomic), credibility grades, withdrawn statements |
| Logs | `trace.jsonl` + `prompts.jsonl`, `run_manifest.json` | auditable to prompt and raw output |
| Evaluation across cases | `evaluation/` | this report |

## 3. Design decisions (ADR-style)

**D1. The model chooses the verdict; the evidence sets the confidence.** `EvidencePosterior` turns independent
evidence weight into a distribution (log-odds, K = 1.5 per unit of weight; identity confirmations and a clean
adverse screen count for entities). The shipped confidence is the posterior's probability *of the model's
verdict*, capped at 0.99, until a calibrator fitted on dev replaces it. *Rejected:* (a) the verbalised probability,
which shipped 85% ADVERSE for Patagonia on two 0.40 sources; (b) a geometric pool of both distributions, which
still shipped 90% on two weak sources after renormalisation (found by a unit test); (c) pooling the *verdict*,
which let mislabelled evidence overturn a correct model verdict in the live Do Kwon run (TRUE 85% against the
model's FALSE 78%). Evidence now holds a verdict open; it never flips it.

**D2. The stopping gate is code, topic-aware and reliability-aware.** Only verdict-deciding questions corroborate a
verdict, so identity confirmations (Wikipedia on "who is the CEO") cannot settle ADVERSE. TRUE/FALSE/MIXED/ADVERSE
need two independent publisher clusters with summed weight ≥ 1.0, and ADVERSE/FALSE need an official, major-news
or reference source. *Cost, measured:* claims whose truth is a negative ("did X go to prison?") rarely get two
authoritative sources saying "no", so H1 now runs to the tool budget (115k tokens against 18k before) for the same
correct verdict.

**D3. Independence is per publisher cluster.** Same domain, or ≥ 0.6 Jaccard over 5-word shingles. *Rejected:*
embedding similarity (an extra paid call per source pair, and harder to explain).

**D4. Track records learn only from ground truth and cannot exceed a tier ceiling.** *Rejected:* learning from the
agent's own majority, which lifted youtube.com from 0.40 to 0.86 in v1 (548 of 564 outcomes were "agreed").

**D5. ADVERSE means material** (`docs/materiality.md`): severity tags from the Evaluator, a code rule on which
severities vote. *Rejected:* a numeric size test, which needs revenue data the tools cannot fetch reliably.

**D6. Reports are assembled by code around model prose.** Searches and coverage come from the case file; sentences
claiming an unchecked registry are withdrawn; uploads never corroborate themselves; next steps are not screened.

**D7. Scoping is checked by code and graded.** Names, disambiguating details and the presence of a predicate must
survive; one retry, then the analyst's words verbatim. The benchmark grades scoping by default (`--pre-scoped` is the
ablation).

**D8. Judge on another model family.** `z-ai/glm-5.3-flash` judges and red-teams; `nemotron-3-super` investigates.
The intended `llama-3.3-70b` had reached end of life (HTTP 410).

**D9. Benchmark v2 is built by code from cited sources.** `benchmark/build_cases_v2.py`: 128 cases, nine slices,
stratified 53 dev / 75 test, `BenchmarkAudit` enforced by a test. Post-cutoff and temporal labels were checked
against sources in October 2026.

**D10. Robustness is handled where each failure arises, not by one blunt retry.** A throttled host halves its
concurrency and starts a cooldown every caller waits out (AIMD, as in TCP), because four workers each retrying on
their own schedule into a rate-limited API was how 8 of 17 crashes happened. A bad model reply gets three attempts, each
told which fields failed, and a truncated one gets twice the output budget. Only then does the runner restart the
whole investigation, which replays its searches from the search cache and so costs tokens, not credits. A 4xx
rejection is never retried. *Rejected:* simply raising the attempt count (it would have made the API storms worse).

## 4. Metrics: definitions, why, and how far each is validated

| Metric | Definition | Why | Validation status |
|---|---|---|---|
| Accuracy | verdict ∈ acceptable verdicts | the analyst's question | 95% bootstrap CI over cases (and seeds within cases) |
| Δ vs closed-book | paired difference, exact McNemar on seed-majority correctness, sign-flip permutation test | does investigating beat knowing? | implemented and unit-tested (`tests/test_remediation.py`) |
| Verdict stability | share of cases with one verdict across seeds | the Patagonia flip | needs ≥ 2 seeds; **not measured** (1 seed). Patagonia was NO_ADVERSE in 3 of 3 live runs |
| Scope accuracy | kind, assertion and disambiguators preserved (word overlap, code) | mis-scoping is the first production failure | measured on v2: 100% on the test split (both modes) |
| Brier / ECE (10 adaptive bins) / AURC | for shipped, raw LLM and posterior confidence | which confidence to ship | computed for all three on every run; a dev-fitted calibrator exists but is **not adopted** (leans on the model's own number, only 5 wrong answers to fit on) |
| Key-fact recall, atomic citation precision | judge-graded | substance and faithfulness | **low validity until κ is measured**: no human labels yet (`gold-template` / `agreement` commands exist) |
| Step reward | 0.5·Δp + process terms; Δp now from the *shipped* (evidence-based) belief | progress per round | weights unvalidated by humans (ratings pending); ranking is stable under ±50% on any one weight (a weak test) |
| Process reward AUROC | does the ground-truth-free reward predict correctness? | "usable online?" | 0.75 across the 75 `short` test episodes (0.61 for the floor) |
| Rounds, flips, rounds to stable, multi-round share, Brier by round (multi-round only) | convergence without the single-round floor effect | | reported |
| Tokens, tool calls, wall-clock, rejected repeats | efficiency | | reported with CIs; prices are assumed |
| Failure tags | non-trivial thresholds (e.g. unbacked confidence = shipped ≥ 0.8 while posterior < 0.5), plus right-for-the-wrong-reason | | descriptive only. Causes come from counterfactual replays: built, run on the 3 wrong test answers, and weak evidence at that size (§1.1) |

## 5. Findings

**F1. On the held-out test split the agent beats the no-tools floor, clearly and where it should.** 96% [91, 100]
against 69% [59, 79]: +26.7 points [+14.7, +38.7], 22 cases only the agent got right against 2 only the floor got
right (section 1). The gain is concentrated in current-state claims, non-English sources, documents and events after
the training data. It is one seed on one split, so run-to-run variance is unmeasured.

**F2. The review's specific failures are fixed live** (section 1.2 table, 9 of 10): Costco and Patagonia are
NO_ADVERSE, the injection is flagged and the upload is not cited, unchecked-registry claims are withdrawn, and the
namesake claim is scoped correctly. **Not fixed:** R2's negative claim about a namesake, and a new failure on the
test split, V2-LT20, where an ambiguous name was resolved to one namesake (section 1.1).

**F3. The fixes cost tokens and time.** About 30k tokens per investigation before, about 90k now (test split), 24
minutes of wall clock per case under a throttled API. Most of it is the gate refusing to close without
corroboration, plus the red-team check. Whether that buys accuracy over the old loop was **not** measured: the old
code was not re-run on v2.

**F4. Confidence ranks well but is not calibrated.** On the test split the evidence-based confidence matches the
model's own for selective prediction (AURC 0.011 against 0.010) but is worse calibrated (Brier 0.143 against 0.061).
The review's overconfidence problem (85% ADVERSE on two weak sources) is solved, by trading it for underconfidence.
A calibrator fitted on dev leans on the model's own number and would bring the overconfidence back, so it is recorded
and not adopted.

**F5. The remediation work itself was full of defects that tests and live runs found,** all fixed with regression
tests: pooled confidence still shipping 90% on weak sources; absolute staleness; a name-regex bug; withdrawn gaps
dropped by argument order; identity double-counting; verdict pooling flipping Do Kwon to TRUE; next steps screened as
claims; rate-limit retries too impatient; schema errors that named no field; judge output truncation; benchmark
labels that mismatched how documents are scoped; and, in the test run, an API limit hit by four workers retrying
independently (fixed with an adaptive per-host limit).

**F6. Reliability under load was a real problem and is now handled.** 17 of 150 test episodes (11%) crashed on the
frozen commit, 8 of them to the API. After the fixes, a retry pass recovered all 17. The re-run episodes were harder:
dropping them would have inflated the headline (section 1, Protocol).

**F7. Memory has not been re-measured on v2.** The `none`/`long`/`long_only` comparisons and the longitudinal slice
were not run (credit quota). The v1 memory claim (2 discordant cases, p = 0.5) is withdrawn.

## 6. Changes since the independent review

| ID | Fix | Before → after (evidence) |
|---|---|---|
| H1 | all code committed before any change | 2 commits → full history; `git status` clean |
| H2 | `run_manifest.json`, stale-resume refusal | none → every run dir stamped (e.g. `results/v2-closed-book`, SHA `dceb343`, clean) |
| H3 | prompt hashes + raw output per model call, `prompts.jsonl` | parsed details only → auditable without the cache |
| H4 | separate LLM/search caches, seeded requests | round 1 byte-identical across modes → fresh samples per seed, same evidence |
| A1 | evidence-based confidence (D1) | Patagonia v1: ADVERSE 85% on two 0.40 sources → unit test: < 0.8; live R1b NO_ADVERSE 89% |
| A2 | topic- and reliability-aware gate | C20 replay settled → not settled (test) |
| A3 | ceilings, USER_GENERATED tier, ground-truth-only outcomes | youtube.com 0.86 → ≤ 0.5 (test); no test-split outcomes (test) |
| A4 | clusters, Admiralty letters, credibility | domain count → one wire story = one publisher (test); reports show `[1B]` and credibility |
| A5 | full-quote check | first 80 chars → fabricated tail rejected (test) |
| A6 | as-of date, publication dates, relative staleness | no dates anywhere → dated evidence, newest first |
| A7 | severity + materiality rule | Costco live H2: ADVERSE 86% → **NO_ADVERSE 92%** |
| A8 | scope schema + ScopeCheck | Jordan live R2: scoped to the bare name → **claim and disambiguator kept** (verdict still wrong, §5) |
| A9 | trace-generated searches and coverage, withdrawn registry claims, upload rule | C31: "OFAC/insolvency registers checked" → claim withdrawn and listed under *not checked* |
| A10 | untrusted-source wrappers, manipulation scan | H6: injection unflagged, upload cited → **2 flags, anachronism named, upload not cited** |
| G1 | six primary-record tools | 1 vendor + Wikipedia → 10 tools with declared coverage |
| G3 | query ledger | C31: same query 4× → repeats rejected in code |
| MEM1 | typed temporal facts with supersession | free text → Milton sentence superseded by pardon (test) |
| MEM2 | lesson specificity check | 66 platitudes at 1.0 → generic lessons not stored |
| MEM4 | windowed controller | gate used full case file in `none` → window only (test) |
| E1 | closed_book mode, baseline first | absent → 66% on all of v2, **69% [59, 79] on the test split** |
| E2 | benchmark v2 + audit | 33 contaminated cases → 128 cases, 9 slices, sourced |
| E3 | scoping graded by default | bypassed → 97% scope accuracy (closed-book run) |
| E4 | CIs, McNemar, permutation, stability | none → in every summary |
| E5 | judge on another family, atomic facts, κ tooling | same model judging itself → GLM judge; κ pending human labels |
| E6 | counterfactual replays with a `repeat` control | tags firing on nearly every wrong answer → causes by single-change replays; run on 3 episodes (weak), the control showed 1 of 3 was noise |
| E7 | step Δp from the shipped belief; weight sensitivity | verbalised Δp → evidence-based; ranking stable under ±50% on any weight; process-reward AUROC 0.75; human ρ pending |
| robustness | adaptive per-host limits, 3-attempt replies, episode retries | 17 of 150 test episodes crashed (11%) → 0 after the retry pass; 1 episode in 16 still needed a second pass |
| P1 | red-team critic | single pass → one critic pass on another model, may buy one check |
| P2 | analyst-grade report | → BLUF with ICD-203 language, Admiralty, minor items, searches, coverage, flags |

**Deferred or partial, with reasons:** G2 (full-page upgrade and chunking), G4 (value-of-information stopping), G5
(QIDs/LEIs as memory keys), MEM2 (expiry by measured effect), MEM3 (longitudinal T0/T1 slice), E5 κ and E7 ρ (need a
human to label; tooling built), E8 (budget sweep, credit quota), E9 (forced-3-round diagnostic), and the fuller
final design (3 seeds and the `none`/`long`/`long_only` modes, credit quota). **Done in reduced form:** the final
frozen test-split run (1 seed, 2 modes) and E6a (replays run on 3 episodes). See `docs/progress/`.

**Cost actually incurred:** the test run (150 episodes, plus 17 re-runs and 18 diagnosis replays) used about 640 of
1,000 Tavily credits and an estimated 1.6 USD of model tokens at the assumed prices. The full design in the brief
(75 cases × 3 seeds × 4 investigating modes plus the floor) would be 1,125 episodes, about 77M tokens and up to
~10,800 search calls: more than ten times the available search quota.

## 7. Limitations and future work

- **One seed, one split.** The headline is a single sample per case. Verdict stability across seeds, and how much
  the 22-versus-2 result would move on another seed, are not known. Slice-level intervals (n = 7) are wide.
- **Not run:** the `none`/`long`/`long_only` memory modes, so the brief's central question, whether long-term memory
  helps, is **unanswered**. The same goes for the longitudinal slice, the budget/accuracy sweep and the forced
  three-round diagnostic. The binding constraint was the search quota (1,000 credits).
- **Two code versions in one result** (133 episodes on the frozen commit, 17 on a later one that changed only
  retry/rate-limit handling). Disclosed in section 1; the re-run episodes are the harder ones.
- **An ambiguous name is resolved to one namesake** (V2-LT20): the identity gate counts two sources confirming *a*
  person as identity confirmed, without checking that the description is specific enough to identify exactly one.
- **Negative claims are hard for an evidence-gated agent.** "X played in the NBA" about a namesake, or "Patagonia is
  on the OFAC list" without a sanctions tool, have no source saying "no", so the agent answers UNVERIFIABLE (live R2,
  V2-DO12). A rule for *specific, checkable* negatives needs care so it does not become an argument from ignorance.
- **Confidence is conservative, not calibrated** (F4), and an UNVERIFIABLE verdict still prints a probability ("unlikely
  (33%)") that means little; it should be expressed as search effort.
- **The Evaluator's verdict labels drive the posterior.** The Do Kwon run showed they can be wrong. The design limits
  the damage (they cannot flip a verdict), but they depress confidence.
- **Judge-graded metrics are unvalidated** until a human labels `benchmark/judge_gold.json`; so is the reward weighting.
- **The injection detector is regex only,** and the injection slice covers uploads, not web pages.
- **The benchmark is mine.** 128 cases written by the agent that built the system, labels checked against sources, but
  by one author; three labels were changed after seeing dev results (section 1.3).
- **Wall-clock and cost are measured under a throttled shared API;** the 1,452 s per case is mostly waiting.
- Prices are assumed list prices; the judge's cost is not included in episode cost.
