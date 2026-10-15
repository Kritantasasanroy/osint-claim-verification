# Phase 4: evaluation validity (E1–E9), live checks and the final run

| ID | Status | Evidence |
|---|---|---|
| E1 | **Done** | `closed_book` mode, listed first in every summary. v2: 66% [58, 73] (all 128); test split 69% [59, 79]. |
| E2 | **Done** | `benchmark/cases_v2.json`: 128 cases, 9 slices of ≥ 12, 53 dev / 75 test stratified per slice, raw text, gold scope, source URLs, closed-book probe per case. `BenchmarkAudit` passes (test), including the rule that document-only cases are claims. |
| E3 | **Done** | Scoping on raw text is the default and graded; `--pre-scoped` is the ablation. Test split: 100%. |
| E4 | **Done (tooling), partly measured** | CIs, exact McNemar, permutation test in every summary. Verdict stability needs ≥ 2 seeds: **not measured**. |
| E5 | **Partial** | Judge on GLM-5.3-flash, atomic-fact citation precision, `gold-template`/`agreement` commands. κ unmeasured (needs a human). |
| E6 | **Partial** | Counterfactual `diagnose` with a `repeat` control, merged results; run on the 3 wrong test answers: one noise, one fixed by gold scope or another Reflector, one unresolved. Weak evidence at n = 3. |
| E7 | **Partial** | Δp from the shipped belief; process-reward AUROC 0.75 on `short` test episodes; ranking stable under ±50% on any one weight (`benchmark/reward_sensitivity.py`). Human ρ pending. |
| E8 | **Not done** | Budget sweep not run (search quota). |
| E9 | **Partial** | Brier by round over multi-round episodes only. Forced-3-round diagnostic not run. |

**The final run** (`results/v2-test`): test split, `closed_book` and `short`, 1 seed, concurrency 4.

- Code frozen at tag `eval-freeze-v2` (`7de5181`). 133 of 150 episodes ran on it.
- 17 episodes crashed (8 API errors, 3 replies failing validation twice, 1 truncated report, plus judge calls). They were
  re-run on `7039770`, which changed only transport, retry and error handling. All 75/75 episodes in both modes finished.
- Headline: 69% [59, 79] vs 96% [91, 100], Δ +26.7 [+14.7, +38.7], 22 vs 2 discordant. See REPORT §1.
- Quota: about 640 of 1,000 Tavily credits used overall (419 by the original run).

**Not run:** `none`, `long`, `long_only` modes; seeds 1 and 2; E8; E9. Reason: the search quota (the full design needs
~10,800 calls), and no human to label the judge sample.

**Other runs on this code:** `results/v2-closed-book` (128 cases), `results/v2-dev2` (dev, closed_book + short, 11
crashes on pre-fix code), `results/live-regressions` (10 held-out live tests plus 2 re-runs: 9/10 correct). `results/v2-dev`
is a voided attempt (42/53 lost to rate limiting), kept locally and not committed.
