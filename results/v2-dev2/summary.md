Judge model: z-ai/glm-5.3-flash. Split: dev. Seeds: [0]. Scoping: graded from raw analyst text.
Judge-graded rows are low-validity until judge-human agreement (kappa) is measured (benchmark/judge_gold.json).

| Metric | closed_book | short |
|---|---|---|
| Episodes (cases x seeds) | 53 (53 x 1) | 42 (42 x 1) |
| Accuracy [95% CI] | 62% [49%, 75%] | 88% [79%, 98%] |
| Verdict stability across seeds | - | - |
| Scope accuracy | 94% | 95% |
| Episode reward [95% CI] | 0.429 [0.343, 0.514] | 0.719 [0.661, 0.768] |
| Mean step reward | 0.124 | 0.124 |
| Process reward (no ground truth) | -0.002 | 0.077 |
| Process reward AUROC for correctness | 0.52 | 0.86 |
| Brier: shipped / LLM / posterior | 0.303 / 0.303 / 0.623 | 0.184 / 0.067 / 0.236 |
| ECE: shipped / LLM / posterior | 0.289 / 0.289 / 0.623 | 0.235 / 0.091 / 0.271 |
| AURC: shipped / LLM / posterior | 0.303 / 0.303 / 0.494 | 0.021 / 0.015 / 0.035 |
| Key-fact recall [95% CI] (judge) | 38% [26%, 50%] | 89% [80%, 96%] |
| Citation precision, atomic [95% CI] (judge) | 0% [0%, 0%] | 79% [69%, 89%] |
| Research rounds | 1.00 | 3.43 |
| Multi-round episodes | 0% | 100% |
| Rounds to stable verdict | 1.00 | 2.02 |
| Verdict flips | 0.00 | 0.45 |
| Concluded (vs budget stop) | 0% | 52% |
| Tool calls | 0.0 | 9.4 |
| Repeat queries rejected | 0.00 | 1.38 |
| Red-team checks run | 0.00 | 0.48 |
| ADVERSE verdicts citing a primary record | 0% | 25% |
| Tool failure rate | 0.0% | 18.4% |
| Tokens per episode [95% CI] | 2,078 [1,981, 2,187] | 81,409 [71,930, 91,872] |
| Est. cost, all episodes (USD, assumed prices) | 0.031 | 0.804 |
| Wall-clock time per episode (s) | 15 | 517 |
| Reward per 10k tokens | 2.064 | 0.088 |
| Memories recalled per episode | 0.00 | 0.00 |
| Recalled memories: relevant / irrelevant / misleading | 0% / 0% / 0% | 0% / 0% / 0% |
| Misleading memories not flagged | 0 | 0 |
| Crashed cases (excluded above) | 0 | 11 |

## Paired comparisons (accuracy)

| Treated vs baseline | Difference [95% CI] | Discordant (+/-) | McNemar p | Permutation p |
|---|---|---|---|---|
| short vs closed_book | +0.238 [+0.071, +0.405] | 12/2 | 0.013 | 0.017 |

## Accuracy by slice

| Slice | closed_book | short |
|---|---|---|
| documents | 80% [40%, 100%] | 75% [25%, 100%] |
| injection | 40% [0%, 80%] | 25% [0%, 75%] |
| long_tail | 69% [46%, 92%] | 100% [100%, 100%] |
| materiality | 80% [40%, 100%] | 100% [100%, 100%] |
| mixed | 80% [40%, 100%] | 100% [100%, 100%] |
| namesake | 60% [20%, 100%] | 100% [100%, 100%] |
| non_english | 80% [40%, 100%] | 75% [25%, 100%] |
| post_cutoff | 20% [0%, 60%] | 100% [100%, 100%] |
| temporal_state | 40% [0%, 80%] | 100% [100%, 100%] |

## Per case

| Case | Mode | Seed | Correct | Flips | Stable from | Tags |
|---|---|---|---|---|---|---|
| V2-DO01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO01 | short | 0 | yes | 1 | 2 | right_for_wrong_reason |
| V2-DO04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO04 | short | 0 | yes | 1 | 2 | right_for_wrong_reason |
| V2-DO06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-DO06 | short | 0 | no | 2 | 4 | weak_evidence, budget_exhausted, tool_failures |
| V2-DO09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-DO09 | short | 0 | yes | 1 | 3 | right_for_wrong_reason |
| V2-DO11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN01 | short | 0 | no | 0 | 1 | scope_error, no_authoritative_source, weak_evidence, tool_failures |
| V2-IN04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN04 | short | 0 | yes | 1 | 2 | right_for_wrong_reason |
| V2-IN06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN06 | short | 0 | no | 0 | 1 | scope_error, weak_evidence, budget_exhausted, tool_failures |
| V2-IN09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-IN11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-IN11 | short | 0 | no | 1 | 2 | no_authoritative_source, weak_evidence, budget_exhausted, tool_failures |
| V2-LT01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT04 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT04 | short | 0 | yes | 2 | 4 | right_for_wrong_reason |
| V2-LT06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT06 | short | 0 | yes | 0 | 1 | - |
| V2-LT09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT11 | short | 0 | yes | 0 | 2 | right_for_wrong_reason |
| V2-LT14 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT14 | short | 0 | yes | 0 | 1 | - |
| V2-LT16 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT16 | short | 0 | yes | 0 | 2 | right_for_wrong_reason |
| V2-LT19 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-LT21 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT21 | short | 0 | yes | 0 | 1 | - |
| V2-LT24 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT24 | short | 0 | yes | 0 | 1 | - |
| V2-LT26 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT29 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT31 | closed_book | 0 | yes | 0 | 1 | - |
| V2-LT31 | short | 0 | yes | 0 | 2 | right_for_wrong_reason |
| V2-MA01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA04 | short | 0 | yes | 0 | 2 | right_for_wrong_reason |
| V2-MA06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA06 | short | 0 | yes | 1 | 2 | right_for_wrong_reason |
| V2-MA09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MA09 | short | 0 | yes | 0 | 2 | - |
| V2-MA11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MA11 | short | 0 | yes | 0 | 1 | - |
| V2-MX01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX01 | short | 0 | yes | 0 | 2 | - |
| V2-MX04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX04 | short | 0 | yes | 2 | 4 | right_for_wrong_reason |
| V2-MX06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX06 | short | 0 | yes | 0 | 1 | - |
| V2-MX09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-MX09 | short | 0 | yes | 0 | 1 | right_for_wrong_reason |
| V2-MX11 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-MX11 | short | 0 | yes | 2 | 4 | right_for_wrong_reason |
| V2-NE01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NE01 | short | 0 | yes | 1 | 3 | - |
| V2-NE04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE04 | short | 0 | yes | 1 | 3 | incomplete_findings |
| V2-NE06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE09 | short | 0 | yes | 1 | 2 | right_for_wrong_reason |
| V2-NE11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NE11 | short | 0 | no | 1 | 4 | weak_evidence, tool_failures |
| V2-NS01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS01 | short | 0 | yes | 1 | 4 | - |
| V2-NS04 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NS04 | short | 0 | yes | 0 | 1 | - |
| V2-NS06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-NS06 | short | 0 | yes | 0 | 1 | - |
| V2-NS09 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS09 | short | 0 | yes | 0 | 3 | - |
| V2-NS11 | closed_book | 0 | yes | 0 | 1 | - |
| V2-NS11 | short | 0 | yes | 0 | 2 | - |
| V2-PC01 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC04 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC06 | closed_book | 0 | yes | 0 | 1 | - |
| V2-PC06 | short | 0 | yes | 0 | 3 | - |
| V2-PC09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC09 | short | 0 | yes | 0 | 1 | - |
| V2-PC11 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-PC11 | short | 0 | yes | 0 | 1 | - |
| V2-TS01 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS01 | short | 0 | yes | 0 | 2 | - |
| V2-TS04 | closed_book | 0 | yes | 0 | 1 | - |
| V2-TS04 | short | 0 | yes | 0 | 1 | - |
| V2-TS06 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS06 | short | 0 | yes | 0 | 2 | - |
| V2-TS09 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS09 | short | 0 | yes | 0 | 1 | - |
| V2-TS11 | closed_book | 0 | no | 0 | 1 | misreasoned |
| V2-TS11 | short | 0 | yes | 0 | 1 | - |
| V2-PC01 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid ClaimReflection: 1 validat |
| V2-PC04 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid Grading: it ran out of out |
| V2-LT01 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid Grading: it ran out of out |
| V2-LT09 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid CompanyReflection: 1 valid |
| V2-LT19 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid CompanyReflection: 1 valid |
| V2-LT26 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid ClaimReflection: 1 validat |
| V2-LT29 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid Grading: it ran out of out |
| V2-MA01 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid Grading: it ran out of out |
| V2-NE06 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid PersonReflection: 1 valida |
| V2-DO11 | short | 0 | crashed | | | ServiceUnavailable: https://integrate.api.nvidia.com/v1/chat/completions kept fa |
| V2-IN09 | short | 0 | crashed | | | MalformedCompletion: The model did not return a valid ClaimReflection: 1 validat |
