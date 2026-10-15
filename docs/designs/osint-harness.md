# Domain model — Agentic Harness for OSINT

## 1. Durable nouns

These exist in any OSINT practice, whether or not this harness ships:

| Concept | Definition | Class |
|---|---|---|
| Subject | The thing under investigation: a company, a person, or a factual claim, stated in words. | general |
| Document | A file an analyst hands over (PDF, image, office file, text) and the text recovered from it. | general |
| Source | A retrieved publication (web page, filing, reference entry, uploaded document) with a known origin. | general |
| Evidence | One fact asserted by one source, and how it bears on one question about the subject. | general |
| Question | An open line of inquiry about the subject that evidence can answer. | general |
| Inquiry | One research action — a tool, an argument, the question it serves — together with what it returned: sources, or a failure. | general |
| Step | One research round: the inquiries made and the belief formed at its end. | general |
| Conflict | Two or more pieces of evidence on the same question that cannot all be true. | general |
| Verdict | The analyst's conclusion about the subject, from a fixed vocabulary per subject kind. | general |
| Belief | A probability distribution over the verdicts allowed for the subject, at one moment. | general |
| Report | The handed-back findings: verdict, confidence, cited findings, conflicts, gaps. | general |
| Case file | Everything gathered about one subject during one investigation (short-term memory). | general |
| Memory record | Something learned in a past investigation that may inform a later one (long-term memory). | ours |
| Source reliability | How trustworthy a publisher has proven to be: a tier prior plus observed corroboration. | ours |
| Benchmark case | A subject with a known ground-truth verdict and key facts, used to grade investigations. | ours |
| Trace | The append-only record of every step of one investigation. | plumbing |
| Question role | Whether a question settles identity, background, or the verdict. Only verdict-deciding evidence corroborates a verdict. | general |
| Publisher cluster | Sources that are one publication in substance (same domain or syndicated text); the unit of independence. | general |
| Severity | How grave an adverse fact is; only material severities can make a subject ADVERSE. | general |
| Admiralty grade | Source reliability A–F (from the reliability number) and information credibility 1–6 (from corroboration, directness, contest), judged separately. | general |
| Evidence posterior | A distribution over verdicts computed from evidence weights alone. | ours |
| Typed memory fact | (entity, relation, value, valid_from, valid_to, observed_at, sources); superseded, never contradicted. | ours |
| Run manifest | The code version, settings and benchmark hash that produced a set of results. | plumbing |

Plumbing (no business meaning): NVIDIA chat/embedding/OCR clients (`NvidiaChat`, `NvidiaEmbedder`, `NemotronParseOcr`; paid calls return `Metered[T]` = value + tokens + latency + cached), Tavily/Wikipedia tools, `Transport` (retries, concurrency, response cache), `Settings`.

## 2. Layering

```
Subject ── kind: SubjectKind (COMPANY | PERSON | CLAIM)
  └─ attached Documents (from uploads) ── each becomes a Source (tier USER_PROVIDED)

Investigation (one run over one Subject, the transaction unit)
  ├─ CaseFile (short-term memory)
  │    ├─ Questions        (the plan; Question.status: OPEN | ANSWERED | DROPPED)
  │    ├─ Sources          (keyed by URL, each with a SourceTier + reliability)
  │    ├─ Evidence         (the evidence of a Source on a Question; stance SUPPORTS | REFUTES | CONTEXT,
  │    │                    strength DIRECT | INDIRECT | WEAK)
  │    ├─ Conflicts        (derived: a Question with weighty SUPPORTS and REFUTES from independent domains)
  │    └─ Steps            (append-only; one per research round: its Inquiries + the Belief it ended on;
  │                         Inquiry = tool (ToolName) + argument + question + sources | failure,
  │                         Inquiry.outcome: FOUND | EMPTY | FAILED; evidence of a step = evidence with that
  │                         step number; CaseFile.beliefs / inquiries_from_step are derived from Steps)
  └─ Report                (terminal; written once)

LongTermMemory (spans investigations)
  ├─ MemoryRecord kind: ENTITY_FACT | LESSON   (recalled as Recollection = record + similarity)
  └─ PublisherOutcome rows (append-only) ──► TrackRecord per domain (corroborated / contradicted, derived)
  (MemoryStore protocol: LongTermMemory for `long`; NoLongTermMemory for `none` / `short`)

Benchmark ── BenchmarkCase (subject text, kind, expected verdict, acceptable verdicts, key facts, tags)
EpisodeResult = the grading of one completed Investigation against one BenchmarkCase (graded from its Steps)
CrashedEpisode = a case whose investigation failed after retries; counted separately, never averaged into quality
```

## 3. Verdict vocabulary (per subject kind)

- CLAIM → `TRUE`, `FALSE`, `MIXED`, `UNVERIFIABLE`
- COMPANY / PERSON → `ADVERSE` (credible adverse findings: fraud, sanctions, insolvency, conviction, major litigation), `NO_ADVERSE`, `UNVERIFIABLE`

Rule: a Belief only puts mass on verdicts its subject kind allows (`SubjectKind.allowed_verdicts`); it carries the verdict the Reflector chose, which must be among the most probable (a tie is resolved by that choice, not by list order); confidence is that verdict's probability.

## 4. Invariants

1. Every finding in a Report cites at least one Source that is in the CaseFile **and is not the analyst's upload**;
   a finding only an upload supports is reported as the document's claim, never as corroboration.
2. Evidence is immutable once recorded. Staleness is not stored on it: it is derived by the CaseFile (a dated item
   on a state claim is stale when newer dated evidence on the same question is more than a year younger), and its
   weight is halved through `CaseFile.weigh`.
3. Beliefs and Steps are append-only. Each Step keeps the model's belief, the `EvidencePosterior` and the
   `ConfidenceInputs` beside the shipped belief, so every confidence number is traceable.
4. Source reliability = `min(tier ceiling, (prior·k + corroborated) / (k + corroborated + contradicted))`, k = 4.
   Ceilings: official 0.99, major news 0.95, reference 0.9, news 0.8, unvetted 0.6, user-generated and uploads 0.5.
   A source carrying text addressed to an AI reader has its reliability halved.
5. Evidence weight = reliability × strength (DIRECT 1.0, INDIRECT 0.6, WEAK 0.3; an unverifiable quote is WEAK).
   Independence is counted per **publisher cluster** (same domain, or ≥ 0.6 Jaccard over 5-word shingles), not per domain.
6. A Conflict exists on a Question when independent supporting and refuting weight are both ≥ 0.5 and neither
   side outweighs the other 2:1.
7. Publisher track records are learned only from `PublisherOutcome`s resolved by a benchmark label (dev split only)
   or an analyst, never from the agent's own conclusion.
8. An adverse item votes for ADVERSE only if its `Severity` is material (docs/materiality.md).
9. The shipped confidence comes from the evidence: the verdict is the argmax of a log-linear pool of the model's
   and the posterior's distributions; the confidence is the posterior's probability of it (or a dev-fitted
   logistic calibrator over [LLM probability, posterior, independent supporters, authoritative support]); ≤ 0.99.
10. The investigation stops only when `CaseFile.unmet_conditions` is empty for the shipped belief, computed over the
    memory mode's visible window: TRUE/FALSE/MIXED/ADVERSE need ≥ 2 independent clusters pointing at the verdict on
    non-identity questions with summed weight ≥ 1.0 (plus one official/major-news/reference source for ADVERSE and
    FALSE) and confidence ≥ 0.8; NO_ADVERSE needs 2 identity confirmations, an adverse screen and no material adverse
    item; UNVERIFIABLE needs 2 rounds with no verdict reaching weight 1.0. No open conflict in any case. A red-team
    critic may then buy one extra check. Otherwise the Budget (4 rounds, 12 tool calls) ends it.
11. A query that repeats an earlier one (token Jaccard ≥ 0.8 among searches, exact for page reads) is rejected by
    the `QueryLedger` in every memory mode.
12. Report prose naming a registry, list or database that no called tool covers is withdrawn; searches and coverage
    are generated from the CaseFile.

## 5. Behaviour homes

- On the concept: `SubjectKind.allowed_verdicts`, `DomainCatalogue.tier_of` (publisher → SourceTier), `SourceTier.prior_reliability`, `TrackRecord.reliability`, `Source.reliability`, `Evidence.weight`, `Inquiry.outcome`, `CaseFile.record_evidence / record_step / conflicts / conflicts_among / is_settled / publisher_outcomes`, `Belief.over / confidence / probability_of`, `Report.assemble / to_markdown / to_json`, `LongTermMemory.recall / remember / forget_investigation`.
- Role agents (LLM-backed, each owns one judgement): `Planner` (questions), `Researcher` (tool actions → Sources), `Evaluator` (Sources → Evidence), `Reflector` (CaseFile → Reflection: Belief + continue/conclude + follow-ups), `Reporter` (CaseFile → Report).
- Orchestration (not domain): `Investigator` runs the loop, budget and trace; `BenchmarkRunner` runs cases × memory modes.
- Grading (evaluation module): `Judge` (LLM grading against ground truth; `Grading.sized` fixes one answer per item), `StepReward`, `EpisodeReward`, `EpisodeResult` (graded from Steps; convergence = `steps_to_stable`, `verdict_flips`; failure diagnosis = `failure_modes`), `CrashedEpisode`, `Scoreboard` (aggregates, `MemoryImpact`).

## 6. Memory modes

| Mode | Tools | Short-term (what agents **and** the stopping gate see) | Long-term |
|---|---|---|---|
| `closed_book` | none | nothing: one answer from what the model knows | off |
| `none` | yes | only the current round's evidence, inquiries, conflicts and posterior, plus the analyst's uploads; the question list (the plan) stays visible | off |
| `short` | yes | the whole case file | off |
| `long` | yes | the whole case file | typed facts recalled at planning and again on follow-up questions; reliability lookups; written after the report |
| `long_only` | yes | as in `none` | as in `long` |

The query ledger is a controller rule and applies in every mode.

## 7. CRUD

- Subject, Document: created from input; immutable.
- Source: created on first retrieval, deduplicated by URL; immutable.
- Evidence, Inquiry, Step, Belief, TraceEvent: append-only.
- The trace is a log for humans; grading reads the domain objects (Steps, Evidence), never untyped trace payloads.
- Question: created by planner/reflector; transitions OPEN → ANSWERED | DROPPED only.
- Report: created once at the end; immutable.
- MemoryRecord, PublisherOutcome: append-only; TrackRecord: derived from outcome rows (no mutated counters). The one delete: `forget_investigation` erases what a crashed long-mode case wrote, so its retry starts from the memories of the cases before it.

## 8. API surface (CLI)

- `investigate [TEXT] [--file PATH ...] [--memory none|short|long]` → report.md, report.json, trace.jsonl
- `benchmark [--modes ...] [--cases ID ...] [--run-dir DIR]` → DIR/<mode>/<case>/{result|crash}.json, DIR/summary.json, DIR/summary.md, DIR/charts/

## 9. Type glossary (every class in `src/`, by layer)

The contract in full: each type the code defines, what it is, and its states. Private `_…` classes are
wire schemas for third-party responses (NVIDIA, Tavily, Wikipedia) or the `_Attempt`/`_VisibleText`
internals of a single plumbing class, and carry no domain meaning.

### Investigation domain (general)
| Type | Definition | States / values |
|---|---|---|
| `Subject` | What is investigated, in words, plus the analyst's documents. | — |
| `SubjectKind` | The kind of subject; fixes the verdict vocabulary. | COMPANY, PERSON, CLAIM |
| `Verdict` | A conclusion from the kind's vocabulary (§3). | TRUE, FALSE, MIXED, ADVERSE, NO_ADVERSE, UNVERIFIABLE |
| `Belief` | Probabilities over the allowed verdicts and the verdict chosen from among the most probable. | — |
| `Question` | An open line of inquiry. | `QuestionStatus`: OPEN, ANSWERED, DROPPED |
| `Source` | A retrieved or uploaded publication with a publisher tier; its content is the `READ_WINDOW` (4000 chars) that every agent and the judge read. Uploads become one Source per readable piece (`Document.pieces`). | `SourceTier`: OFFICIAL, MAJOR_NEWS, REFERENCE, NEWS, USER_PROVIDED, UNVETTED |
| `DomainCatalogue` | Which publisher domains belong to which tier (unlisted → UNVETTED). | — |
| `Evidence` | One fact from one source on one question; immutable. | `Stance`: SUPPORTS, REFUTES, CONTEXT; `Strength`: DIRECT, INDIRECT, WEAK |
| `EvidenceBalance` | Independent weight for and against one question; each publisher domain counts once and on one side only (its heavier side; an exact tie counts on neither); `winners` is the heavier side's publishers (repeated items from the same domain count once; the same story syndicated on different domains is not detected). | — |
| `Conflict` | A question whose balance is weighty on both sides with neither side ahead 2:1 (invariant 6). | — |
| `PublisherOutcome` | Whether one publisher sided with the settled answer to a question in one investigation; a lone, unopposed publisher earns none. | agreed: true / false |
| `TrackRecord` | A publisher's derived corroborated / contradicted counts and the reliability they imply (invariant 4). | — |
| `Inquiry` | One research action and what it returned (§2): sources or a failure, never both. | `InquiryOutcome`: FOUND, EMPTY, FAILED; `ToolName`: WEB_SEARCH, NEWS_SEARCH, READ_PAGE, ENCYCLOPEDIA |
| `Step` | One research round: its inquiries and the belief it ended on. | — |
| `CaseFile` | Short-term memory of one investigation (§2); uploads are evidence at `UPLOAD_STEP` 0, visible in every memory mode but never an independent publisher (excluded from `independent_domains`, `balance` and `publisher_outcomes`). `independent_domains` counts the publishers on the heavier side of some question's balance, counted across questions. A dissenter on the losing side, or a publisher that weighs both sides equally, does not help the case settle. ("Corroborated" in a track record is stricter: see `PublisherOutcome`.) | — |
| `MemoryMode` | How much the agents may see (§6). | NONE, SHORT, LONG |
| `Finding` | One reported statement with confidence and citations. | — |
| `CitedSource` | A source a report cites, with the reliability it was weighed at. | — |
| `Report` | The handed-back findings (invariant 1); its conflicts are the CaseFile's computed conflicts, the reporter's prose only explains them (`conflict_notes`). | — |

### Intake (general)
| Type | Definition | States / values |
|---|---|---|
| `Document` | An uploaded file and the passages recovered from it. | — |
| `Passage` | Text recovered from one location of a document (a page, sheet, slide, image); content past a reader's cap, or an undecodable picture, is recorded as an UNREADABLE passage, never dropped silently. | `ExtractionMethod`: NATIVE_TEXT, TEXT_LAYER, OCR, UNREADABLE |
| `DocumentIntake` | Chooses the reader for a file by its extension. | — |
| `DocumentFormat` and `PlainTextFormat`, `HtmlFormat`, `EmailFormat`, `PdfFormat`, `ImageFormat`, `WordFormat`, `SpreadsheetFormat`, `SlideFormat` | One reader per file format. | — |
| `UnsupportedDocument`, `EmptyDocument` | A file of an unreadable format; a file with no recoverable text. | — |

### Memory (ours)
| Type | Definition | States / values |
|---|---|---|
| `MemoryRecord` | One fact or lesson learned from the agent's own concluded report. | `MemoryKind`: ENTITY_FACT, LESSON |
| `Recollection` | A recalled record and its similarity to the current subject; `label` (e.g. M3) is how agents, judge and scoreboard refer to it. | — |
| `MemoryStore` | What a memory tier can do: recall, remember, record publisher outcomes, track records, forget an investigation. | implemented by `LongTermMemory` (SQLite + embeddings) and `NoLongTermMemory` (none/short) |

### Agents and orchestration
| Type | Definition | States / values |
|---|---|---|
| `Planner`, `Researcher`, `Evaluator`, `Reflector`, `Reporter` | The five role agents (§5). | — |
| `Scope`, `Plan`, `ResearchAction`, `ResearchAgenda`, `EvidenceDraft`, `Assessment`, `VerdictScore`, `Reflection`, `FindingDraft`, `FactDraft`, `ReportDraft` | Each agent's JSON-schema answer, and how it applies to the case file. `Reflection.for_kind` limits verdicts to the subject kind. | `Decision`: CONTINUE, CONCLUDE |
| `CaseBriefing` | The case file as an agent may see it under the memory mode. | — |
| `Investigator` | Runs the loop (orchestration only). | — |
| `Budget` | Limits on rounds, tool calls, and actions per round. | — |
| `Investigation` | One finished run: case file, report, recollections, trace, wall-clock time. | `StopReason`: CONCLUDED, STEP_BUDGET, TOOL_BUDGET |
| `Toolbox`, `ResearchTool`, `TavilySearch`, `WebSearch`, `NewsSearch`, `PageReader`, `Encyclopedia` | The research tools; a failing tool yields a FAILED inquiry. | `UnusableArgument` when an argument can't be used; `PageUnreadable` when the extractor reports the page as failed |
| `TraceLog`, `TraceEvent` | The append-only JSONL log for humans. | `TraceEventKind`: SCOPED, MEMORY_RECALLED, PLANNED, RESEARCH_CHOSEN, TOOL_CALLED, EVIDENCE_ASSESSED, REFLECTED, REPORTED, MEMORY_WRITTEN |

### Evaluation (ours)
| Type | Definition | States / values |
|---|---|---|
| `Benchmark`, `BenchmarkCase` | The ground-truth cases. | — |
| `Judge`, `Grading` | LLM grading of outputs against ground truth; one answer per item (`Grading.sized`). | `MemoryLabel`: RELEVANT, IRRELEVANT, MISLEADING |
| `StepReward`, `EpisodeReward` | The rewards (REPORT §3.1). | — |
| `StepRecord` | One graded round: verdict, confidence, p(acceptable), reward. | — |
| `EpisodeResult` | One completed investigation graded; convergence (`steps_to_stable`, `verdict_flips`) and failure diagnosis (`failure_modes`). | `FailureMode`: MEMORY_INTERFERENCE, SOURCE_SELECTION, WEAK_EVIDENCE, UNRESOLVED_CONFLICT, PREMATURE_STOP, BUDGET_EXHAUSTED, TOOL_FAILURES, OVERCONFIDENT, MISREASONED, INCOMPLETE_FINDINGS, UNDERCONFIDENT |
| `CrashedEpisode` | A case that failed after retries; counted, never averaged. | — |
| `Episode` | The outcome of running one case: an `EpisodeResult` or a `CrashedEpisode`. | — |
| `EpisodeDiagnosis` | An episode's convergence and failure tags, written per case as `diagnosis.json` and tabulated in `summary.md`. | — |
| `Scoreboard`, `ModeSummary`, `MemoryImpact` | Aggregates per memory mode and paired memory deltas (None = pair not run). Per-round curves: levels (p(acceptable)) carry an early-concluded episode's last value forward; increments (step reward) count unrun rounds as 0. `StepValue` / `EpisodeValue` are the per-round / per-episode metric extractors it aggregates. | — |
| `BenchmarkRunner`, `BenchmarkSummary`, `BenchmarkCharts` | Runs, summarises and charts a benchmark. | — |

### Plumbing
| Type | Definition |
|---|---|
| `Settings`, `TokenPrice`, `MissingSetting` | Configuration from the environment; reference prices for cost estimates; a missing required key. |
| `Transport`, `ResponseCache`, `HttpReply`, `ServiceUnavailable`, `ServiceRejected` | All outbound HTTP: retries, concurrency, cache; `post_model` / `get_model` validate a reply and evict it from the cache if unusable. |
| `NvidiaChat`, `NvidiaEmbedder`, `NemotronParseOcr`, `EmbeddingPurpose`, `Metered`, `TokenUsage`, `MalformedCompletion`, `ConstrainedEnums` | NVIDIA clients; a paid call's value with tokens, latency and cache flag; a reply that is not a valid answer; answer schemas that narrow a shared enum (e.g. a per-kind `Reflection` offers only that kind's verdicts, derived from its `ALLOWED`) in the schema the model sees and is decoded into; naming an enum the schema lacks is an error. |
| `Harness`, `CommandLine`, `InvestigationRequest`, `BenchmarkRequest` | Composition root and command line. |
