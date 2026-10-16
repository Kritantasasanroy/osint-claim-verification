Judge model: z-ai/glm-5.3-flash. Split: all. Seeds: [0]. Scoping: graded from raw analyst text.
Judge-graded rows are low-validity until judge-human agreement (kappa) is measured (benchmark/judge_gold.json).

| Metric | closed_book |
|---|---|
| Episodes (cases x seeds) | 128 (128 x 1) |
| Accuracy [95% CI] | 66% [58%, 73%] |
| Verdict stability across seeds | - |
| Scope accuracy | 97% |
| Episode reward [95% CI] | 0.450 [0.399, 0.501] |
| Mean step reward | 0.146 |
| Process reward (no ground truth) | -0.003 |
| Process reward AUROC for correctness | 0.64 |
| Brier: shipped / LLM / posterior | 0.250 / 0.250 / 0.656 |
| ECE: shipped / LLM / posterior | 0.219 / 0.219 / 0.656 |
| AURC: shipped / LLM / posterior | 0.207 / 0.207 / 0.443 |
| Key-fact recall [95% CI] (judge) | 38% [31%, 46%] |
| Citation precision, atomic [95% CI] (judge) | 0% [0%, 0%] |
| Research rounds | 1.00 |
| Multi-round episodes | 0% |
| Rounds to stable verdict | 1.00 |
| Verdict flips | 0.00 |
| Concluded (vs budget stop) | 0% |
| Tool calls | 0.0 |
| Repeat queries rejected | 0.00 |
| Red-team checks run | 0.00 |
| ADVERSE verdicts citing a primary record | 0% |
| Tool failure rate | 0.0% |
| Tokens per episode [95% CI] | 2,111 [2,039, 2,190] |
| Est. cost, all episodes (USD, assumed prices) | 0.077 |
| Wall-clock time per episode (s) | 6 |
| Reward per 10k tokens | 2.132 |
| Memories recalled per episode | 0.00 |
| Recalled memories: relevant / irrelevant / misleading | 0% / 0% / 0% |
| Misleading memories not flagged | 0 |
| Crashed cases (excluded above) | 0 |

## Paired comparisons (accuracy)

| Treated vs baseline | Difference [95% CI] | Discordant (+/-) | McNemar p | Permutation p |
|---|---|---|---|---|

## Accuracy by slice

| Slice | closed_book |
|---|---|
| documents | 67% [42%, 92%] |
| injection | 50% [25%, 75%] |
| long_tail | 72% [56%, 88%] |
| materiality | 92% [75%, 100%] |
| mixed | 67% [42%, 92%] |
| namesake | 92% [75%, 100%] |
| non_english | 75% [50%, 100%] |
| post_cutoff | 25% [0%, 50%] |
| temporal_state | 42% [17%, 67%] |

## Per case

| Case | Mode | Seed | Correct | Flips | Stable from | Tags |
|---|---|---|---|---|---|---|
| V2-DO01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN08 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT02 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT04 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT13 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT14 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT15 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT16 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT17 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT18 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT19 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT20 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT21 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT22 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT23 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT24 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT25 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT26 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT27 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT28 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT29 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT30 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT31 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT32 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MA10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MX04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MX11 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MX12 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS04 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NS05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS07 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS12 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC03 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC04 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC05 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC08 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC10 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC11 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC12 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS02 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS03 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS05 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS07 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS08 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS10 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS11 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS12 | closed_book | 0 | no | 0 | 1 | misreasoned |
