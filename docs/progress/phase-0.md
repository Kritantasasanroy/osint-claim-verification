# Phase 0: hygiene and reproducibility (H1–H4)

**H1. Everything committed.** The pre-review working tree was committed unchanged, before any behaviour change, in
nine commits (`2a3d305`..`401f69b`): plumbing, domain, agents, tools and memory, investigator, evaluation, CLI, docs,
v1 results. `git status` is clean apart from ignored files (`.env`, `review/`, `runs/`, caches, memory DBs).

**H2. Run manifest.** `evaluation/manifest.py`: every benchmark run directory gets `run_manifest.json` (git SHA,
dirty flag, settings without secrets, budget, benchmark file and SHA-256, split, seeds, modes, scoping mode, start
and end). Resuming from a different SHA or benchmark file raises `StaleRunDirectory` unless `--force-new`.
Test: `test_a_run_dir_refuses_to_mix_code_versions`.

**H3. Auditable trace.** Every metered event records the model id and, per model call, the system and user prompt
hashes and the raw completion. Full prompts go once into `prompts.jsonl`. Test:
`test_every_model_call_in_the_trace_can_be_traced_to_its_prompt_and_raw_output`.

**H4. Caches split.** `--llm-cache` and `--search-cache` (benchmark defaults: off and on). Every request carries
its seed. Test: `test_seeds_resample_the_model_while_the_search_cache_replays_evidence` (two seeds produce two
uncached model calls and one search call).

Checks after phase: pytest, mypy --strict, ruff all green.
