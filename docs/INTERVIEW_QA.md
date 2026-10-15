# Interview questions, answered with evidence

Each answer points at the metric, file, test or run that backs it. Where the evidence does not exist, the answer says
so: no number here is estimated.

**1. What does the bare model score with no tools, and what is your Δ with CI?**
On v1 the closed-book model scored 82–88%, so v1 measured memory, not investigation; v1 is now only a contamination
reference. On v2 it scores 66% [58%, 73%] over all 128 cases. **On the held-out test split (75 cases, 1 seed): floor
69% [59%, 79%], agent 96% [91%, 100%], Δ = +26.7 points [+14.7, +38.7]**, 22 cases only the agent got right against 2
only the floor got right, exact McNemar p ≈ 0.00004 (`results/v2-test/summary.md`, REPORT §1). One seed; the 3-seed
design was not affordable on the 1,000-credit search quota.

**2. Show cases the agent gets right that the bare model gets wrong, and show retrieval was the cause.**
22 test cases (per-case table in `results/v2-test/summary.md`); the gain is largest on current-state claims
(29% → 100%), non-English (57% → 100%), documents and post-cutoff events (43% → 86%). Examples with reports and traces
are in `results/sample/` (V2-TS02, V2-NE02) and `results/live-regressions/` (Do Kwon's 2025 extradition and sentencing
cited from dated news). Retrieval is the plausible cause, since the floor has no access to post-cutoff facts, but the
`gold_source`/`no_tools` replays that would prove it per case were run only on the 3 wrong answers (section 1.1), not
on the 22 wins.

**3. Is the memory effect significant? What's the run-to-run variance?**
**Not measured.** The `none`/`long`/`long_only` modes were not run on v2 (search quota), so I cannot say whether long-term
memory helps; the v1 claim (2 discordant cases, McNemar p = 0.5, reproduced by `test_exact_mcnemar_matches_the_reviews_two_case_effect`)
is withdrawn. Run-to-run variance is unmeasured too (1 seed). The one sampling-noise datapoint: V2-PC05 was wrong in the run
and right on a plain re-run with no change.

**4. What exactly does each memory mode remove?**
`docs/designs/osint-harness.md` §6 tabulates it. Since MEM4 the stopping gate, conflicts and posterior see the same window
as the agents (`test_the_none_mode_gate_sees_only_its_own_window`). The query ledger is a controller rule that applies in
every mode. Separate LLM and search caches stop round 1 replaying identically across modes (H4).

**5. Can two weak sources produce a confident ADVERSE?**
No. `test_two_weak_sources_cannot_produce_a_confident_verdict`: a model saying 99% over two 0.40 sources ships under 80%.
`test_c20_identity_confirmations_do_not_corroborate_an_adverse_verdict`: the C20 evidence does not satisfy the gate. Live:
Patagonia NO_ADVERSE in 3 of 3 runs; materiality slice 7/7 on the test split.

**6. Why can't YouTube become as trusted as Reuters?**
It is `USER_GENERATED` with a 0.5 ceiling, and track records learn only from ground truth (dev labels or an analyst),
never from the agent's majority (`test_twenty_agreements_cannot_lift...`, `test_track_records_are_learned_on_dev_cases_only`).

**7. Which tool checked the sanctions list?**
None, unless `OPENSANCTIONS_API_KEY` is set, and the report says so: "Sanctions lists (OFAC SDN, EU, UN, UK): not checked
(no connector)". A sentence claiming otherwise is withdrawn (C31 live re-run; `test_claims_about_unqueried_registries_are_withdrawn`).
The cost is visible: test case V2-DO12 (a forged "Patagonia on the SDN list") was answered UNVERIFIABLE, correctly cautious
but wrong, because no tool could settle it.

**8. Where does the confidence number come from?**
`investigation/confidence.py:ConfidenceCalibrator.ship`. The model picks the verdict; the confidence is the evidence
posterior's probability of it (`investigation/posterior.py`), capped at 0.99; each step stores all three numbers (LLM,
posterior, shipped). On the test split it ranks answers as well as the model's own number (AURC 0.011 vs 0.010) but is worse
calibrated (Brier 0.143 vs 0.061). A dev-fitted calibrator is recorded and not adopted (`benchmark/calibration/README.md`).

**9. Who grades the grader?**
A different model family (`z-ai/glm-5.3-flash`) with atomic-fact citation checks. **Judge–human κ is not measured**:
`python -m osint_harness gold-template RUN_DIR` exports a blind labelling file and `agreement` computes κ, but it needs a
human to label it. Until then every judge-graded row is marked low-validity in the summary.

**10. What happens with a real but thinly documented entity?**
The v2 long-tail slice has 30 such cases (SEC litigation-release defendants, OFAC-designated front companies, small
GLEIF-registered firms). On the test split (n = 19): floor 79% [58, 95], agent 95% [84, 100]. The one miss is instructive:
"John Smith, businessman" (V2-LT20) should be UNVERIFIABLE, but the agent adopted one specific namesake and cleared him at 82%.

**11. What happens with an injected instruction in a page or upload?**
Upload-style payloads (7 on the test split): 0 of 7 attacks succeeded (the verdict never followed the planted instruction;
upper 95% bound 35% at this size), and the planted instruction was flagged in 6 of 7 (86% [49%, 97%]), **below the ≥ 90% target**.
Web-page injection is not tested; the detector is regex only.

**12. How do failure tags discriminate causes?**
They do not; they describe. Causes come from counterfactual replays (`diagnose`, with a `repeat` control): run on the 3 wrong
test answers, they show one was sampling noise (V2-PC05), one was fixed by the gold scope or a different Reflector (V2-DO12),
and one by nothing (V2-LT20). Three episodes is weak evidence (REPORT §1.1).

**13. Is everything committed and reproducible from a SHA?**
Yes for code: `git log` from `2a3d305`; the frozen tag is `eval-freeze-v2`. Every run directory carries `run_manifest.json`
with SHA and dirty flag, and a resume from other code is refused unless forced
(`test_a_run_dir_refuses_to_mix_code_versions`). **The test run mixes two commits** (133 episodes on the freeze, 17 re-run
on a later one that changed only retry and rate-limit handling); the freeze manifest is kept beside the final one.
Traces carry prompt hashes and raw output (`prompts.jsonl`).

**14. How does ground truth that changes over time stay valid?**
Each case has an `as_of`; every prompt says "Today is …"; evidence carries publication dates; state claims discount evidence a
year older than the newest. Memory supersedes facts instead of contradicting them (`test_a_pardon_supersedes_a_sentence...`).
v2's temporal-state slice uses 2025–2026 changes (Apple's and Disney's CEOs, Berkshire, X, SBF's appeal): test split 29% → 100%.
A longitudinal same-entity-twice slice was not built.

**15. Why did Patagonia flip between runs, and how stable is it now?**
Verbalised confidence over weak sources and no materiality rule. It is now NO_ADVERSE in 3 of 3 live runs (79–89%) and the
materiality slice is 7/7. Multi-seed stability on the benchmark is not measured.

**16. How do you stop a mis-scoped namesake reaching an analyst?**
`ScopeCheck` (`agents/planner.py`): names, details and predicates must survive scoping, with one retry, then the analyst's words.
Live R2 keeps the claim and "UC Berkeley machine-learning professor". Scope accuracy is graded by default: 100% on the test
split. It does not stop an *ambiguous* name (V2-LT20) being resolved to one namesake; that is an open failure.

**17. Is the reward measuring anything a human cares about?**
Unknown: no human ratings were collected (`gold-template` exports 40 blind reports; `agreement` reports Spearman ρ). What is
measured: the ground-truth-free process reward predicts correctness (AUROC 0.75 over the 75 `short` test episodes), and the
mode ranking is stable under ±50% on any one episode-reward weight (a weak test; `benchmark/reward_sensitivity.py`).

**18. Where is the cost/quality sweet spot?**
Not mapped: the budget sweep (E8) was not run. What is known (test split): the floor costs ~2k tokens and 17 s per case for
69%; the agent ~90k tokens and ~24 min (mostly waiting under rate limits) for 96%. The `accuracy_vs_tokens.png` chart plots
both with intervals.
