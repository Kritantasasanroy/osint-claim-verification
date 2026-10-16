# Sample outputs (no API keys needed)

Six cases from the held-out v2 **test** split, both modes, seed 0, copied unchanged from `results/v2-test/`:
V2-DO12, V2-LT20, V2-PC05, V2-TS02, V2-NE02, V2-IN02.

The first three are the agent's three wrong answers (a forged OFAC notice with no sanctions tool, an ambiguous "John Smith", and a sentence length reported two ways); the other three are correct cases from the temporal-state, non-English and injection slices. Each folder has `report.md`/`report.json` (what an analyst reads), `grading.json` (the judge), `result.json` (the measured episode), `trace.jsonl` and `prompts.jsonl` (every model call, auditable).

`run_manifest.freeze.json` is the manifest of the original run (code tag `eval-freeze-v2`); `run_manifest.json` is the one written by the last resume, which re-ran 17 crashed episodes on a later commit that only changed retry and rate-limit handling. See REPORT.md section 1.
