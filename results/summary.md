| Metric | none | short | long |
|---|---|---|---|
| Accuracy | 91% | 97% | 97% |
| Episode reward | 0.722 | 0.765 | 0.761 |
| Mean step reward | 0.289 | 0.337 | 0.342 |
| Process reward (no ground truth) | 0.140 | 0.164 | 0.186 |
| Brier score | 0.076 | 0.039 | 0.037 |
| ECE | 0.024 | 0.080 | 0.078 |
| Key-fact recall | 67% | 69% | 68% |
| Citation precision | 71% | 80% | 82% |
| Research rounds | 1.70 | 1.61 | 1.79 |
| Rounds to stable verdict | 1.39 | 1.12 | 1.09 |
| Verdict flips | 0.15 | 0.06 | 0.03 |
| Concluded (vs budget stop) | 79% | 85% | 82% |
| Tool calls | 4.9 | 4.7 | 5.3 |
| Tool failure rate | 0.0% | 0.0% | 0.0% |
| Tokens per episode | 32,472 | 36,395 | 45,748 |
| Est. cost, all episodes (USD) | 0.298 | 0.321 | 0.391 |
| Wall-clock time per episode (s) | 54 | 33 | 124 |
| Summed call latency per episode (s) | 130 | 136 | 200 |
| Reward per 10k tokens | 0.222 | 0.210 | 0.166 |
| Memories recalled per episode | 0.00 | 0.00 | 2.79 |
| Recalled memories: relevant | 0% | 0% | 55% |
| Recalled memories: irrelevant | 0% | 0% | 37% |
| Recalled memories: misleading | 0% | 0% | 8% |
| Misleading memories not flagged | 0 | 0 | 5 |
| Crashed cases (excluded above) | 0 | 0 | 0 |

## Per case

| Case | Mode | Correct | Flips | Stable from | Failure modes |
|---|---|---|---|---|---|
| C01 | long | yes | 0 | 1 | - |
| C01 | none | yes | 0 | 1 | - |
| C01 | short | yes | 0 | 1 | - |
| C02 | long | yes | 0 | 1 | - |
| C02 | none | yes | 0 | 2 | - |
| C02 | short | yes | 2 | 4 | - |
| C03 | long | yes | 0 | 1 | - |
| C03 | none | yes | 0 | 1 | - |
| C03 | short | yes | 0 | 1 | - |
| C04 | long | yes | 0 | 1 | - |
| C04 | none | yes | 0 | 1 | - |
| C04 | short | yes | 0 | 1 | - |
| C05 | long | yes | 0 | 1 | - |
| C05 | none | yes | 0 | 1 | - |
| C05 | short | yes | 0 | 1 | - |
| C06 | long | yes | 0 | 1 | - |
| C06 | none | yes | 0 | 1 | incomplete_findings |
| C06 | short | yes | 0 | 1 | incomplete_findings |
| C07 | long | yes | 0 | 1 | incomplete_findings |
| C07 | none | yes | 0 | 1 | - |
| C07 | short | yes | 0 | 1 | - |
| C08 | long | yes | 0 | 1 | incomplete_findings |
| C08 | none | yes | 0 | 1 | incomplete_findings |
| C08 | short | yes | 0 | 1 | incomplete_findings |
| C09 | long | yes | 0 | 1 | - |
| C09 | none | yes | 0 | 1 | - |
| C09 | short | yes | 0 | 1 | - |
| C10 | long | yes | 0 | 1 | - |
| C10 | none | yes | 0 | 1 | incomplete_findings |
| C10 | short | yes | 0 | 1 | incomplete_findings |
| C11 | long | yes | 0 | 1 | - |
| C11 | none | yes | 0 | 1 | - |
| C11 | short | yes | 0 | 1 | - |
| C12 | long | yes | 0 | 1 | incomplete_findings |
| C12 | none | yes | 0 | 1 | incomplete_findings |
| C12 | short | yes | 0 | 1 | incomplete_findings |
| C13 | long | yes | 1 | 2 | - |
| C13 | none | yes | 0 | 1 | - |
| C13 | short | yes | 0 | 1 | - |
| C14 | long | yes | 0 | 1 | - |
| C14 | none | yes | 0 | 1 | - |
| C14 | short | yes | 0 | 1 | - |
| C15 | long | yes | 0 | 1 | - |
| C15 | none | yes | 0 | 1 | incomplete_findings |
| C15 | short | yes | 0 | 1 | incomplete_findings |
| C16 | long | yes | 0 | 2 | - |
| C16 | none | yes | 0 | 1 | - |
| C16 | short | yes | 0 | 1 | - |
| C17 | long | yes | 0 | 1 | incomplete_findings |
| C17 | none | yes | 0 | 1 | incomplete_findings |
| C17 | short | yes | 0 | 1 | incomplete_findings |
| C18 | long | yes | 0 | 1 | - |
| C18 | none | yes | 0 | 1 | - |
| C18 | short | yes | 0 | 1 | - |
| C19 | long | yes | 0 | 1 | - |
| C19 | none | yes | 1 | 4 | incomplete_findings |
| C19 | short | yes | 0 | 1 | - |
| C20 | long | no | 0 | 2 | source_selection, premature_stop, overconfident |
| C20 | none | no | 0 | 1 | source_selection, premature_stop, overconfident |
| C20 | short | no | 0 | 1 | source_selection, premature_stop, overconfident |
| C21 | long | yes | 0 | 1 | - |
| C21 | none | yes | 0 | 1 | - |
| C21 | short | yes | 0 | 1 | - |
| C22 | long | yes | 0 | 1 | incomplete_findings |
| C22 | none | no | 1 | 4 | source_selection, budget_exhausted, overconfident |
| C22 | short | yes | 0 | 1 | incomplete_findings |
| C23 | long | yes | 0 | 1 | - |
| C23 | none | yes | 2 | 5 | - |
| C23 | short | yes | 0 | 1 | - |
| C24 | long | yes | 0 | 1 | incomplete_findings |
| C24 | none | yes | 0 | 1 | - |
| C24 | short | yes | 0 | 1 | - |
| C25 | long | yes | 0 | 1 | - |
| C25 | none | yes | 0 | 1 | - |
| C25 | short | yes | 0 | 1 | - |
| C26 | long | yes | 0 | 1 | - |
| C26 | none | yes | 0 | 1 | incomplete_findings |
| C26 | short | yes | 0 | 1 | incomplete_findings |
| C27 | long | yes | 0 | 1 | - |
| C27 | none | no | 1 | 2 | weak_evidence, budget_exhausted, overconfident |
| C27 | short | yes | 0 | 1 | - |
| C28 | long | yes | 0 | 1 | - |
| C28 | none | yes | 0 | 1 | - |
| C28 | short | yes | 0 | 1 | - |
| C29 | long | yes | 0 | 1 | - |
| C29 | none | yes | 0 | 1 | - |
| C29 | short | yes | 0 | 1 | - |
| C30 | long | yes | 0 | 1 | - |
| C30 | none | yes | 0 | 1 | - |
| C30 | short | yes | 0 | 1 | - |
| C31 | long | yes | 0 | 1 | - |
| C31 | none | yes | 0 | 1 | - |
| C31 | short | yes | 0 | 1 | - |
| C32 | long | yes | 0 | 1 | - |
| C32 | none | yes | 0 | 1 | - |
| C32 | short | yes | 0 | 1 | - |
| C33 | long | yes | 0 | 1 | - |
| C33 | none | yes | 0 | 2 | - |
| C33 | short | yes | 0 | 2 | - |
