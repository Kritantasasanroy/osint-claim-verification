Judge model: z-ai/glm-5.3-flash. Split: test. Seeds: [0]. Scoping: graded from raw analyst text.
Judge-graded rows are low-validity until judge-human agreement (kappa) is measured (benchmark/judge_gold.json).

| Metric | closed_book | short |
|---|---|---|
| Episodes (cases x seeds) | 75 (75 x 1) | 75 (75 x 1) |
| Accuracy [95% CI] | 69% [59%, 79%] | 96% [91%, 100%] |
| Verdict stability across seeds | - | - |
| Scope accuracy | 100% | 100% |
| Episode reward [95% CI] | 0.476 [0.409, 0.540] | 0.749 [0.717, 0.778] |
| Mean step reward | 0.154 | 0.177 |
| Process reward (no ground truth) | -0.003 | 0.114 |
| Process reward AUROC for correctness | 0.61 | 0.75 |
| Brier: shipped / LLM / posterior | 0.243 / 0.243 / 0.693 | 0.143 / 0.061 / 0.179 |
| ECE: shipped / LLM / posterior | 0.221 / 0.221 / 0.693 | 0.212 / 0.112 / 0.234 |
| AURC: shipped / LLM / posterior | 0.194 / 0.194 / 0.353 | 0.011 / 0.010 / 0.012 |
| Key-fact recall [95% CI] (judge) | 43% [33%, 53%] | 87% [81%, 93%] |
| Citation precision, atomic [95% CI] (judge) | 0% [0%, 0%] | 81% [74%, 87%] |
| Research rounds | 1.00 | 3.43 |
| Multi-round episodes | 0% | 100% |
| Rounds to stable verdict | 1.00 | 2.16 |
| Verdict flips | 0.00 | 0.28 |
| Concluded (vs budget stop) | 0% | 53% |
| Tool calls | 0.0 | 9.4 |
| Repeat queries rejected | 0.00 | 1.20 |
| Red-team checks run | 0.00 | 0.61 |
| ADVERSE verdicts citing a primary record | 0% | 73% |
| Tool failure rate | 0.0% | 2.8% |
| Episodes that needed a retry | 0 | 4 |
| Tokens per episode [95% CI] | 2,089 [1,999, 2,189] | 89,846 [84,224, 95,362] |
| Est. cost, all episodes (USD, assumed prices) | 0.045 | 1.570 |
| Wall-clock time per episode (s) | 17 | 1452 |
| Reward per 10k tokens | 2.279 | 0.083 |
| Memories recalled per episode | 0.00 | 0.00 |
| Recalled memories: relevant / irrelevant / misleading | 0% / 0% / 0% | 0% / 0% / 0% |
| Misleading memories not flagged | 0 | 0 |
| Crashed cases (excluded above) | 0 | 0 |

## Paired comparisons (accuracy)

| Treated vs baseline | Difference [95% CI] | Discordant (+/-) | McNemar p | Permutation p |
|---|---|---|---|---|
| short vs closed_book | +0.267 [+0.147, +0.387] | 22/2 | 0.000 | 0.000 |

## Accuracy by slice

| Slice | closed_book | short |
|---|---|---|
| documents | 43% [14%, 71%] | 86% [57%, 100%] |
| injection | 86% [57%, 100%] | 100% [100%, 100%] |
| long_tail | 79% [58%, 95%] | 95% [84%, 100%] |
| materiality | 100% [100%, 100%] | 100% [100%, 100%] |
| mixed | 71% [43%, 100%] | 100% [100%, 100%] |
| namesake | 100% [100%, 100%] | 100% [100%, 100%] |
| non_english | 57% [14%, 86%] | 100% [100%, 100%] |
| post_cutoff | 43% [14%, 86%] | 86% [57%, 100%] |
| temporal_state | 29% [0%, 57%] | 100% [100%, 100%] |

## Per case

| Case | Mode | Seed | Correct | Flips | Stable from | Tags |
|---|---|---|---|---|---|---|
| V2-DO02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO02 | short | 0 | yes | 0 | 3 | - |
| V2-DO03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO03 | short | 0 | yes | 0 | 2 | - |
| V2-DO05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO05 | short | 0 | yes | 0 | 2 | - |
| V2-DO07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO07 | short | 0 | yes | 0 | 2 | - |
| V2-DO08 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO08 | short | 0 | yes | 0 | 1 | - |
| V2-DO10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO10 | short | 0 | yes | 0 | 1 | - |
| V2-DO12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO12 | short | 0 | no | 0 | 1 | weak_evidence |
| V2-IN02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN02 | short | 0 | yes | 2 | 3 | - |
| V2-IN03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN03 | short | 0 | yes | 0 | 1 | - |
| V2-IN05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN05 | short | 0 | yes | 0 | 1 | - |
| V2-IN07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN07 | short | 0 | yes | 0 | 2 | - |
| V2-IN08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN08 | short | 0 | yes | 0 | 2 | - |
| V2-IN10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN10 | short | 0 | yes | 0 | 2 | - |
| V2-IN12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN12 | short | 0 | yes | 1 | 3 | right_for_wrong_reason |
| V2-LT02 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT02 | short | 0 | yes | 0 | 1 | - |
| V2-LT03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT03 | short | 0 | yes | 0 | 2 | - |
| V2-LT05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT05 | short | 0 | yes | 0 | 4 | - |
| V2-LT07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT07 | short | 0 | yes | 1 | 3 | - |
| V2-LT08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT08 | short | 0 | yes | 1 | 2 | right_for_wrong_reason |
| V2-LT10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT10 | short | 0 | yes | 0 | 2 | right_for_wrong_reason, incomplete_findings |
| V2-LT12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT12 | short | 0 | yes | 1 | 4 | right_for_wrong_reason |
| V2-LT13 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT13 | short | 0 | yes | 0 | 1 | - |
| V2-LT15 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT15 | short | 0 | yes | 2 | 4 | - |
| V2-LT17 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT17 | short | 0 | yes | 0 | 2 | right_for_wrong_reason |
| V2-LT18 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT18 | short | 0 | yes | 0 | 1 | - |
| V2-LT20 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT20 | short | 0 | no | 1 | 4 | weak_evidence, budget_exhausted |
| V2-LT22 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT22 | short | 0 | yes | 0 | 1 | - |
| V2-LT23 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT23 | short | 0 | yes | 0 | 1 | - |
| V2-LT25 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT25 | short | 0 | yes | 0 | 1 | - |
| V2-LT27 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT27 | short | 0 | yes | 0 | 1 | - |
| V2-LT28 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT28 | short | 0 | yes | 0 | 1 | - |
| V2-LT30 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT30 | short | 0 | yes | 1 | 3 | - |
| V2-LT32 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT32 | short | 0 | yes | 0 | 3 | right_for_wrong_reason |
| V2-MA02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA02 | short | 0 | yes | 0 | 1 | right_for_wrong_reason |
| V2-MA03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA03 | short | 0 | yes | 0 | 3 | right_for_wrong_reason |
| V2-MA05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA05 | short | 0 | yes | 0 | 3 | right_for_wrong_reason |
| V2-MA07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA07 | short | 0 | yes | 2 | 4 | - |
| V2-MA08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA08 | short | 0 | yes | 0 | 2 | - |
| V2-MA10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA10 | short | 0 | yes | 1 | 3 | - |
| V2-MA12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA12 | short | 0 | yes | 0 | 1 | - |
| V2-MX02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX02 | short | 0 | yes | 1 | 4 | - |
| V2-MX03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MX03 | short | 0 | yes | 0 | 3 | - |
| V2-MX05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX05 | short | 0 | yes | 1 | 4 | - |
| V2-MX07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX07 | short | 0 | yes | 1 | 2 | - |
| V2-MX08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX08 | short | 0 | yes | 0 | 1 | right_for_wrong_reason |
| V2-MX10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MX10 | short | 0 | yes | 1 | 2 | - |
| V2-MX12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX12 | short | 0 | yes | 0 | 4 | - |
| V2-NE02 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE02 | short | 0 | yes | 0 | 1 | - |
| V2-NE03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE03 | short | 0 | yes | 1 | 2 | - |
| V2-NE05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE05 | short | 0 | yes | 0 | 1 | - |
| V2-NE07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE07 | short | 0 | yes | 0 | 2 | - |
| V2-NE08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE08 | short | 0 | yes | 0 | 2 | - |
| V2-NE10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE10 | short | 0 | yes | 0 | 2 | incomplete_findings |
| V2-NE12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE12 | short | 0 | yes | 0 | 2 | - |
| V2-NS02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS02 | short | 0 | yes | 2 | 3 | right_for_wrong_reason |
| V2-NS03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS03 | short | 0 | yes | 0 | 3 | - |
| V2-NS05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS05 | short | 0 | yes | 0 | 4 | right_for_wrong_reason |
| V2-NS07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS07 | short | 0 | yes | 0 | 2 | - |
| V2-NS08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS08 | short | 0 | yes | 0 | 4 | - |
| V2-NS10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS10 | short | 0 | yes | 0 | 2 | right_for_wrong_reason |
| V2-NS12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS12 | short | 0 | yes | 0 | 2 | right_for_wrong_reason, incomplete_findings |
| V2-PC02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC02 | short | 0 | yes | 0 | 1 | - |
| V2-PC03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC03 | short | 0 | yes | 0 | 2 | - |
| V2-PC05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC05 | short | 0 | no | 1 | 3 | weak_evidence, budget_exhausted |
| V2-PC07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC07 | short | 0 | yes | 0 | 1 | - |
| V2-PC08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC08 | short | 0 | yes | 0 | 1 | right_for_wrong_reason |
| V2-PC10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC10 | short | 0 | yes | 0 | 3 | - |
| V2-PC12 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC12 | short | 0 | yes | 0 | 1 | - |
| V2-TS02 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS02 | short | 0 | yes | 0 | 4 | - |
| V2-TS03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS03 | short | 0 | yes | 0 | 2 | - |
| V2-TS05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS05 | short | 0 | yes | 0 | 3 | - |
| V2-TS07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS07 | short | 0 | yes | 0 | 2 | - |
| V2-TS08 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS08 | short | 0 | yes | 0 | 1 | - |
| V2-TS10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS10 | short | 0 | yes | 0 | 1 | - |
| V2-TS12 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS12 | short | 0 | yes | 0 | 1 | - |
