# Agentic Harness for OSINT

An autonomous investigation agent. Give it a **company, a person, or a factual claim**, as raw analyst text or as
**any document** (PDF, scan, screenshot, Word, Excel, PowerPoint, HTML, e-mail). It:

- scopes the input faithfully (entity, disambiguators, the full assertion, the as-of date), checked by code
- plans questions with roles (identity, core fact, verdict-deciding)
- searches the web and news, reads pages, and queries primary records (Wikidata, GLEIF, SEC EDGAR,
  CourtListener, Wayback, and OpenSanctions when a key is set)
- weighs every source by reliability, publication date and *independence* (syndicated copies count once)
- computes its confidence from the evidence, not from what the model says it believes
- refuses to stop until a code-enforced gate is met, and lets a red-team critic on another model buy one more check
- writes a report whose searches, coverage, Admiralty grades and manipulation flags come from the case file,
  and withdraws any sentence claiming a registry was checked when no tool checked it

It also **evaluates itself** against a closed-book baseline (the same model with no tools), with seeds, dev/test
splits, bootstrap confidence intervals and paired significance tests.

**Read next:** [REPORT.md](REPORT.md) (design, metrics, results, limitations),
[docs/INTERVIEW_QA.md](docs/INTERVIEW_QA.md) (the hard questions, each answered with a pointer to evidence),
[docs/architecture.md](docs/architecture.md) (diagram), [docs/designs/osint-harness.md](docs/designs/osint-harness.md)
(domain model), [docs/materiality.md](docs/materiality.md) (what ADVERSE means).

## Setup

Requires Python 3.12+.

```bash
pip install -e ".[dev]"
cp .env.example .env      # then put your keys in .env
```

| Variable | Needed | Used for |
|---|---|---|
| `NVIDIA_API_KEY` | yes | agents (`nvidia/nemotron-3-super-120b-a12b`), judge and red-team critic (`z-ai/glm-5.3-flash`, another model family), OCR (`nvidia/nemotron-parse`), embeddings |
| `TAVILY_API_KEY` | yes | web search, news search (with publication dates), page extraction |
| `SEC_USER_AGENT` | recommended | SEC asks EDGAR clients for a contact string |
| `COURTLISTENER_TOKEN` | optional | higher CourtListener rate limits |
| `OPENSANCTIONS_API_KEY` | optional | sanctions/PEP screening; **without it the report says sanctions lists were not checked** |
| `JUDGE_MODEL` | optional | override the judge model |

Wikipedia, Wikidata, GLEIF, EDGAR and Wayback need no key.

## Investigate something

```bash
python -m osint_harness investigate "Is Trevor Milton still serving a prison sentence?"
python -m osint_harness investigate "Patagonia (outdoor clothing company)"
python -m osint_harness investigate --file press_clipping.png          # subject derived from the document
python -m osint_harness investigate "Do Kwon is in custody in Montenegro" --as-of 2026-10-13
```

Options: `--memory none|short|long|long_only` (default `long`), `--as-of YYYY-MM-DD` (default today),
`--max-steps`, `--max-tool-calls`, `--out DIR`, `--no-cache`.

Each run writes `report.md`, `report.json` (schema v2), `trace.jsonl` (one event per step with model id, prompt
hashes and raw output) and `prompts.jsonl` (full prompt texts keyed by hash).

The report is ordered for an analyst: **bottom line** (verdict, ICD-203 estimative language, as-of date), key
findings with **Admiralty** source letters and **credibility 1–6**, minor adverse items, conflicts, **searches
performed** (from the trace), **coverage** (what was and was not checked), document assessment and manipulation
flags, gaps and next steps, sources.

## 3-minute demo

```bash
python -m osint_harness investigate "Michael I. Jordan, the UC Berkeley machine-learning professor, played professional basketball in the NBA." --memory short
```

Watch the scope line keep the claim and the disambiguator (the pre-review code scoped this to the bare name and ran
a sanctions screen on it), then open the report's *Searches performed* and *Coverage* sections.

## Run the benchmark

```bash
# cost estimate only, no calls
python -m osint_harness benchmark --cases-file benchmark/cases_v2.json --seeds 3 --estimate-only

# development: dev split, one seed
python -m osint_harness benchmark --cases-file benchmark/cases_v2.json --split dev --run-dir results/v2-dev

# reproduce the headline numbers (what was actually run: test split, 1 seed, two modes)
git checkout eval-freeze-v2
python -m osint_harness benchmark --cases-file benchmark/cases_v2.json --split test --seeds 1     --modes closed_book short --run-dir results/v2-test --concurrency 4

# the fuller design in the brief (not run: it needs ~77M tokens and ~10,800 search calls)
python -m osint_harness benchmark --cases-file benchmark/cases_v2.json --split test --seeds 3     --modes closed_book none short long long_only --run-dir results/v2-test-full
```

Modes: `closed_book` (no tools, no memory: the floor), `none`, `short`, `long`, `long_only`. Defaults: LLM cache
**off** (fresh samples per seed), search cache **on** (same evidence across modes and seeds). `--pre-scoped` skips
scoping (ablation); by default scoping runs on the raw `input_text` and is graded.

**Cost.** What was run (75 test cases x 2 modes, plus 17 retried episodes and 18 diagnosis replays) used about 640
Tavily credits and roughly 1.6 USD of model tokens at the assumed prices; an investigation is about 90k tokens. The full
design in the brief (75 cases x 3 seeds x 4 investigating modes plus the floor) is 1,125 episodes, ~77M tokens and up to
~10,800 search calls: use `--estimate-only` first. **A free Tavily key (1,000 credits) is not enough for it.**

Rate limits are handled in the transport (an adaptive per-host concurrency limit with a shared cooldown), model replies
get three attempts, and a failed investigation is restarted up to three times (searches replay from the cache).

Every run directory carries `run_manifest.json` (git SHA, dirty flag, settings without secrets, benchmark hash,
seeds, split); the runner refuses to resume a directory written by other code unless `--force-new`.

Output: `summary.md` / `summary.json` (per-mode metrics with 95% CIs, paired comparisons against the closed-book
floor, accuracy by slice), `charts/` (including accuracy vs tokens with CIs), and per episode
`<mode>/seed<N>/<case>/` with `report.md`, `trace.jsonl`, `grading.json`, `result.json`, `diagnosis.json`.

**Benchmarks.** [benchmark/cases_v2.json](benchmark/cases_v2.json) is the headline: 128 cases in nine slices
(post-cutoff, long-tail, materiality, namesake, temporal-state, documents, injection, non-English, mixed), each with
raw analyst wording, a gold scope and ground-truth source URLs, split 53 dev / 75 test, built by
[benchmark/build_cases_v2.py](benchmark/build_cases_v2.py). v1 ([benchmark/cases.json](benchmark/cases.json), 33
cases) is kept as a contamination reference. [benchmark/scope_cases.json](benchmark/scope_cases.json) is a 32-input
scope test set. [benchmark/live_regressions.sh](benchmark/live_regressions.sh) re-runs the independent review's
held-out live tests.

## Development

```bash
pytest            # 150 tests; all third-party HTTP is mocked
mypy              # --strict over src/
ruff check src tests
```

## Layout

```
src/osint_harness/
  intake/            documents.py (one reader per format), ocr.py (nemotron-parse)
  investigation/     domain: subject, verdict, source (tiers, ceilings, Admiralty), evidence (severity),
                     question (roles), independence (clusters, query ledger), posterior, confidence,
                     case_file (stopping gate), report (validators, coverage)
  agents/            rubric, planner (+ScopeCheck), researcher, evaluator (+QuoteCheck), reflector,
                     critic, reporter, closed_book, briefing
  investigator.py    the loop
  tools.py           Tavily, Wikipedia, Wikidata, GLEIF, SEC EDGAR, CourtListener, Wayback, OpenSanctions
  memory.py          typed temporal facts, supersession, namesake gate, lessons, track records
  trace.py           JSONL log + prompt sidecar
  evaluation/        benchmark (+audit), manifest, runner, judge, rewards, episode, scoreboard, stats, charts
benchmark/           cases_v2.json, cases.json, scope_cases.json, documents/, build_cases_v2.py
docs/                architecture, design, materiality, INTERVIEW_QA, progress/
results/             benchmark output (v1 results are from the pre-review code; see REPORT)
```
